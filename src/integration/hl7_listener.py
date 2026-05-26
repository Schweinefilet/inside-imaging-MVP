"""HL7 v2 MLLP listener for ORU^R01 finalized reports.

Run as a separate worker process (see Procfile entry `hl7worker`).
Hospital PACS/RIS systems forward reports here; the listener extracts the
narrative text and submits it to the standard /integration/reports
processing path so all return paths and audit logging stay consistent.
"""

from __future__ import annotations

import logging
import os
import socket
import socketserver
import ssl
import threading
from typing import Optional, Tuple

import requests

from src import config, db
from src.integration import auth as int_auth


SB = b"\x0b"   # MLLP Start Block
EB = b"\x1c"   # MLLP End Block
CR = b"\x0d"   # Carriage Return


def _parse_oru(message: str) -> dict:
    """Extract just what we need from an ORU^R01 message without depending on hl7apy at runtime.
    Falls back to a minimal hand-rolled parser if hl7apy is unavailable."""
    out = {
        "control_id": "",
        "accession_number": "",
        "patient_id": "",
        "patient_name": "",
        "study_uid": "",
        "report_text": "",
        "sending_facility": "",
    }

    obx_chunks: list = []
    for raw_line in message.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        if not raw_line:
            continue
        fields = raw_line.split("|")
        seg = fields[0]
        if seg == "MSH" and len(fields) > 9:
            out["sending_facility"] = fields[3] if len(fields) > 3 else ""
            out["control_id"] = fields[9] if len(fields) > 9 else ""
        elif seg == "PID" and len(fields) > 5:
            out["patient_id"] = fields[3].split("^")[0] if len(fields) > 3 and fields[3] else ""
            out["patient_name"] = fields[5].replace("^", " ").strip() if len(fields) > 5 and fields[5] else ""
        elif seg == "OBR" and len(fields) > 3:
            out["accession_number"] = fields[3].split("^")[0] if fields[3] else ""
            if not out["study_uid"] and len(fields) > 18:
                out["study_uid"] = fields[18] or ""
        elif seg == "OBX" and len(fields) > 5:
            value = fields[5]
            if value:
                obx_chunks.append(value.replace("\\.br\\", "\n"))

    out["report_text"] = "\n".join(obx_chunks).strip()
    return out


def _build_ack(message: str, ack_code: str = "AA", text: str = "") -> bytes:
    control_id = ""
    sending_app = "INSIDEIMG"
    receiving_app = "HOSPITAL"
    for raw_line in message.replace("\r\n", "\r").replace("\n", "\r").split("\r"):
        if raw_line.startswith("MSH"):
            f = raw_line.split("|")
            if len(f) > 5:
                receiving_app = f[2]
                sending_app = f[4] or sending_app
            if len(f) > 9:
                control_id = f[9]
            break

    msh = (
        f"MSH|^~\\&|{sending_app}|INSIDEIMG|{receiving_app}|HOSPITAL|"
        f"|||{control_id}|P|2.5"
    )
    msa = f"MSA|{ack_code}|{control_id}|{text or 'Received'}"
    ack_payload = (msh + "\r" + msa + "\r").encode("utf-8")
    return SB + ack_payload + EB + CR


def _forward_to_api(parsed: dict, target_url: str, api_key: str) -> Tuple[int, str]:
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    payload = {
        "report_text": parsed.get("report_text", ""),
        "accession_number": parsed.get("accession_number", ""),
        "patient_id": parsed.get("patient_id", ""),
        "patient_name": parsed.get("patient_name", ""),
        "study_uid": parsed.get("study_uid", ""),
        "source_ref": f"hl7:{parsed.get('control_id', '')}",
    }
    try:
        resp = requests.post(target_url + "?return=json", headers=headers, json=payload, timeout=30)
        return resp.status_code, resp.text[:300]
    except Exception as exc:
        return 0, str(exc)


def _build_handler_class(target_url: str, api_key: str):
    class MLLPHandler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            buffer = b""
            while True:
                chunk = self.request.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while SB in buffer and EB + CR in buffer:
                    start = buffer.index(SB)
                    end = buffer.index(EB + CR, start)
                    raw_msg = buffer[start + 1:end].decode("utf-8", errors="ignore")
                    buffer = buffer[end + 2:]

                    parsed = _parse_oru(raw_msg)
                    if not parsed["report_text"]:
                        ack = _build_ack(raw_msg, "AE", "No report text found in OBX")
                        self.request.sendall(ack)
                        continue

                    status_code, body_preview = _forward_to_api(parsed, target_url, api_key)
                    if status_code in (200, 201, 202):
                        ack = _build_ack(raw_msg, "AA", "Processed")
                    else:
                        # Body preview may contain user error detail; do NOT log it (it can include PHI).
                        ack = _build_ack(raw_msg, "AE", f"Upstream {status_code}")
                        logging.warning("HL7 -> API forward failed (status=%s)", status_code)
                    self.request.sendall(ack)
    return MLLPHandler


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class TLSThreadingTCPServer(ThreadingTCPServer):
    """MLLP-over-TLS server. Wraps the accept socket in an SSLContext."""

    def __init__(self, server_address, RequestHandlerClass, *, ssl_context: ssl.SSLContext):
        self._ssl_context = ssl_context
        super().__init__(server_address, RequestHandlerClass)

    def get_request(self):
        sock, addr = self.socket.accept()
        try:
            tls_sock = self._ssl_context.wrap_socket(sock, server_side=True)
        except ssl.SSLError as exc:
            logging.warning("MLLP TLS handshake failed from %s: %s", addr, exc)
            sock.close()
            raise
        return tls_sock, addr


def _build_ssl_context() -> Optional[ssl.SSLContext]:
    """Return an SSLContext if HL7_TLS_CERT and HL7_TLS_KEY env vars are set,
    else None (caller falls back to plain MLLP)."""
    cert = os.getenv("HL7_TLS_CERT", "")
    key = os.getenv("HL7_TLS_KEY", "")
    if not (cert and key):
        return None
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    # Require mutual TLS if a CA is provided — protects against rogue clients.
    ca = os.getenv("HL7_TLS_CLIENT_CA", "")
    if ca:
        ctx.load_verify_locations(cafile=ca)
        ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def serve_forever(host: Optional[str] = None, port: Optional[int] = None,
                  target_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
    host = host or config.HL7_LISTENER_HOST
    port = port or config.HL7_LISTENER_PORT
    target_url = (target_url or config.INTEGRATION_BASE_URL or "http://127.0.0.1:5000") + "/integration/reports"
    api_key = api_key or os.getenv("HL7_FORWARD_API_KEY", "")

    if not api_key:
        raise RuntimeError("HL7_FORWARD_API_KEY env var is required (issue via management CLI)")

    handler = _build_handler_class(target_url, api_key)
    ssl_ctx = _build_ssl_context()

    if ssl_ctx is not None:
        server = TLSThreadingTCPServer((host, port), handler, ssl_context=ssl_ctx)
        mode = "MLLP/TLS (mTLS)" if os.getenv("HL7_TLS_CLIENT_CA") else "MLLP/TLS"
    else:
        if os.getenv("INSIDEIMAGING_ENV", "").lower() in ("production", "prod"):
            raise RuntimeError(
                "HL7 listener refusing to start: production environment but no TLS configured. "
                "Set HL7_TLS_CERT and HL7_TLS_KEY env vars, or run with INSIDEIMAGING_ENV=development."
            )
        server = ThreadingTCPServer((host, port), handler)
        mode = "MLLP (plaintext — DEVELOPMENT ONLY)"

    logging.info("HL7 listener bound to %s:%s [%s], forwarding to %s",
                 host, port, mode, target_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    db.init_db()
    serve_forever()
