"""Return-path dispatchers: deliver Patient's Copy PDFs back to the hospital."""

from __future__ import annotations

import datetime as _dt
import io
import ipaddress
import logging
import socket
import urllib.parse
from typing import Dict, List

import requests


def _is_public_addr(addr_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(addr_str)
    except ValueError:
        return False
    return not (addr.is_loopback or addr.is_private or addr.is_link_local
                or addr.is_reserved or addr.is_unspecified)


def _resolve_public_addrs(host: str) -> set:
    """Resolve `host` and return only its public addresses. Raises ValueError
    if resolution fails or every address is private/reserved."""
    try:
        resolved = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise ValueError(f"Webhook hostname could not be resolved: {host!r}") from exc

    public = {a for a in resolved if _is_public_addr(a)}
    if not public:
        raise ValueError(
            f"Webhook URL resolves only to private/reserved addresses ({resolved}). "
            "Only public endpoints are permitted."
        )
    return public


def _validate_webhook_url(url: str) -> str:
    """Raise ValueError if the URL targets a private/reserved address (SSRF
    prevention). Returns one validated public IP for the hostname."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise ValueError(f"Invalid webhook URL: {exc}") from exc

    if parsed.scheme not in ("https", "http"):
        raise ValueError(
            f"Webhook URL must use http or https scheme, got: {parsed.scheme!r}"
        )

    host = parsed.hostname
    if not host:
        raise ValueError("Webhook URL has no hostname")

    return next(iter(_resolve_public_addrs(host)))


class _PinnedHostAdapter(requests.adapters.HTTPAdapter):
    """Route every request through this adapter to a pre-resolved IP, while
    still validating the TLS certificate (and setting SNI/Host) against the
    original hostname.

    Without this, `_validate_webhook_url` resolves the hostname once to check
    it isn't private/internal, and then the plain `requests.post()` call
    resolves it AGAIN independently to actually connect — a classic DNS
    rebinding TOCTOU: an attacker controlling DNS for the configured webhook
    domain can answer the first lookup with a public IP and the second with
    an internal one. Pinning the connection to the address we already
    validated means there is only ever one resolution in effect.
    """

    def __init__(self, pinned_ip: str, hostname: str):
        self._pinned_ip = pinned_ip
        self._hostname = hostname
        super().__init__()

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        # requests >= 2.32 routes every connection through this hook (not the
        # older get_connection(url, proxies) override point) — swap in the
        # pre-validated IP for the actual TCP connection, but keep TLS
        # verification (assert_hostname/server_hostname) pinned to the real
        # hostname so certificate checking and SNI are unaffected.
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(request, verify, cert)
        host_params["host"] = self._pinned_ip
        if host_params.get("scheme") == "https":
            pool_kwargs["assert_hostname"] = self._hostname
            pool_kwargs["server_hostname"] = self._hostname
        return host_params, pool_kwargs

    def get_connection(self, url, proxies=None):
        # Fallback for requests < 2.32, which never calls
        # build_connection_pool_key_attributes and routes through here instead.
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme
        port = parsed.port or (443 if scheme == "https" else 80)
        pool_kwargs = {"assert_hostname": self._hostname, "server_hostname": self._hostname} if scheme == "https" else {}
        return self.poolmanager.connection_from_host(
            self._pinned_ip, port=port, scheme=scheme, pool_kwargs=pool_kwargs
        )


def deliver_webhook(webhook_url: str, pdf_bytes: bytes, metadata: Dict[str, str]) -> Dict:
    if not webhook_url:
        raise ValueError("webhook_url is empty")
    pinned_ip = _validate_webhook_url(webhook_url)
    hostname = urllib.parse.urlparse(webhook_url).hostname

    files = {"pdf": ("patient_copy.pdf", pdf_bytes, "application/pdf")}
    data = {k: str(v or "") for k, v in metadata.items()}

    session = requests.Session()
    session.mount("http://", _PinnedHostAdapter(pinned_ip, hostname))
    session.mount("https://", _PinnedHostAdapter(pinned_ip, hostname))
    try:
        # allow_redirects=False: a redirect target is unvalidated — following
        # it would let a webhook we already checked hand the PHI PDF off to
        # an arbitrary, unvalidated internal address.
        #
        # Host header: http.client derives it from the *actual* connection
        # (our pinned IP) unless told otherwise, since we never changed the
        # request URL itself — set it explicitly back to the real hostname.
        resp = session.post(
            webhook_url, files=files, data=data, timeout=20, allow_redirects=False,
            headers={"Host": urllib.parse.urlparse(webhook_url).netloc},
        )
    finally:
        session.close()
    return {
        "status_code": resp.status_code,
        "ok": resp.ok,
        "body_preview": resp.text[:500] if resp.text else "",
    }


def deliver_dicom_sc(
    pdf_bytes: bytes,
    *,
    pacs_host: str,
    pacs_port: int,
    pacs_ae_title: str,
    our_ae_title: str,
    study_instance_uid: str,
    patient_name: str = "",
    patient_id: str = "",
    accession_number: str = "",
    series_description: str = "Patient's Copy",
) -> Dict:
    """Wrap the PDF as a DICOM Encapsulated PDF and C-STORE it to the hospital's PACS.
    The hospital can then print/route it via their existing PACS workflow."""
    import pydicom
    from pydicom.dataset import Dataset, FileDataset
    from pydicom.uid import generate_uid, ExplicitVRLittleEndian
    from pynetdicom import AE
    from pynetdicom.sop_class import EncapsulatedPDFStorage

    sop_instance_uid = generate_uid()
    series_instance_uid = generate_uid()

    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = EncapsulatedPDFStorage
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    ds = FileDataset("patient_copy.dcm", {}, file_meta=file_meta, preamble=b"\0" * 128)
    now = _dt.datetime.now()

    ds.SOPClassUID = EncapsulatedPDFStorage
    ds.SOPInstanceUID = sop_instance_uid
    ds.StudyInstanceUID = study_instance_uid or generate_uid()
    ds.SeriesInstanceUID = series_instance_uid
    ds.Modality = "DOC"
    ds.ConversionType = "WSD"
    ds.PatientName = patient_name or "UNKNOWN^PATIENT"
    ds.PatientID = patient_id or "UNKNOWN"
    ds.AccessionNumber = accession_number or ""
    ds.StudyID = "1"
    ds.SeriesNumber = 999
    ds.InstanceNumber = 1
    ds.SeriesDescription = series_description
    ds.DocumentTitle = series_description
    ds.MIMETypeOfEncapsulatedDocument = "application/pdf"
    ds.ContentDate = now.strftime("%Y%m%d")
    ds.ContentTime = now.strftime("%H%M%S")
    ds.AcquisitionDateTime = now.strftime("%Y%m%d%H%M%S")
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.is_little_endian = True
    ds.is_implicit_VR = False

    pdf_padded = pdf_bytes + (b"\x00" if len(pdf_bytes) % 2 else b"")
    ds.EncapsulatedDocument = pdf_padded

    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds, write_like_original=False)
    buf.seek(0)
    sc_dataset = pydicom.dcmread(buf, force=True)

    ae = AE(ae_title=our_ae_title or "INSIDEIMG")
    ae.add_requested_context(EncapsulatedPDFStorage)

    assoc = ae.associate(pacs_host, int(pacs_port), ae_title=pacs_ae_title)
    if not assoc.is_established:
        raise RuntimeError(f"Could not associate with PACS {pacs_ae_title}@{pacs_host}:{pacs_port}")

    try:
        status = assoc.send_c_store(sc_dataset)
    finally:
        assoc.release()

    if status is None or getattr(status, "Status", None) != 0x0000:
        raise RuntimeError(f"C-STORE failed: status={getattr(status, 'Status', '?')!r}")

    return {
        "sop_instance_uid": sop_instance_uid,
        "series_instance_uid": series_instance_uid,
        "study_instance_uid": ds.StudyInstanceUID,
    }


def dispatch(
    tenant_integration: Dict,
    pdf_bytes: bytes,
    metadata: Dict[str, str],
) -> List[Dict]:
    """Run every configured return path for a tenant. Returns one result dict per path."""
    results: List[Dict] = []
    return_path = (tenant_integration.get("return_path") or "webhook").lower()

    targets: List[str] = []
    if return_path == "both":
        targets = ["webhook", "pacs"]
    elif return_path in ("webhook", "pacs"):
        targets = [return_path]
    elif return_path in ("none", "skip"):
        return [{"path": "none", "ok": True, "info": "delivery disabled"}]

    for target in targets:
        try:
            if target == "webhook":
                if not tenant_integration.get("webhook_url"):
                    results.append({"path": "webhook", "ok": False, "error": "webhook_url not configured"})
                    continue
                r = deliver_webhook(tenant_integration["webhook_url"], pdf_bytes, metadata)
                results.append({"path": "webhook", **r})
            elif target == "pacs":
                if not tenant_integration.get("pacs_host") or not tenant_integration.get("pacs_port"):
                    results.append({"path": "pacs", "ok": False, "error": "pacs_host/port not configured"})
                    continue
                r = deliver_dicom_sc(
                    pdf_bytes,
                    pacs_host=tenant_integration["pacs_host"],
                    pacs_port=tenant_integration["pacs_port"],
                    pacs_ae_title=tenant_integration["pacs_ae_title"],
                    our_ae_title=tenant_integration.get("our_ae_title") or "INSIDEIMG",
                    study_instance_uid=metadata.get("study_uid", ""),
                    patient_name=metadata.get("patient_name", ""),
                    patient_id=metadata.get("patient_id", ""),
                    accession_number=metadata.get("accession_number", ""),
                )
                results.append({"path": "pacs", "ok": True, **r})
        except Exception as exc:
            logging.exception("Return path %s failed", target)
            results.append({"path": target, "ok": False, "error": str(exc)})

    return results
