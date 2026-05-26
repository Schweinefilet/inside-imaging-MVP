"""HTTP API blueprint for hospital integration endpoints."""

from __future__ import annotations

import datetime as _dt
import ipaddress
import logging
import os
from functools import wraps
from typing import Optional, Tuple

from flask import Blueprint, Response, jsonify, render_template, request

from src import db
from src.integration import auth as int_auth
from src.integration import phi as int_phi
from src.integration import return_paths as int_return
from src.integration import translator as int_translator
from src.integration import extensions as int_ext
from src.storage import get_storage


integration_bp = Blueprint("integration", __name__, url_prefix="/integration")

_INTEGRATION_RATE_LIMIT = os.getenv("INTEGRATION_RATE_LIMIT", "120 per minute")


def _rate_limit(view):
    """Apply the shared Flask-Limiter from app.py if it's available.
    Imported lazily to avoid the circular import api.py <- app.py <- api.py."""
    _lim = int_ext.limiter
    if _lim is None:
        return view
    return _lim.limit(_INTEGRATION_RATE_LIMIT, key_func=lambda: request.headers.get("X-API-Key") or _client_ip())(view)


def _client_ip() -> str:
    """Honor X-Forwarded-For when behind a trusted proxy (set TRUST_FORWARDED_FOR=1)."""
    if os.getenv("TRUST_FORWARDED_FOR", "0") == "1":
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or ""


def _ip_allowed(allowlist_csv: str, client_ip: str) -> bool:
    """allowlist_csv = "10.0.0.0/8,203.0.113.5". Empty string = no restriction."""
    if not allowlist_csv:
        return True
    if not client_ip:
        return False
    try:
        ip_obj = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for raw in allowlist_csv.split(","):
        entry = raw.strip()
        if not entry:
            continue
        try:
            net = ipaddress.ip_network(entry, strict=False)
            if ip_obj in net:
                return True
        except ValueError:
            continue
    return False


def _require_api_key(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        raw = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if raw.lower().startswith("bearer "):
            raw = raw[7:]
        key_record = int_auth.resolve_api_key(raw)
        if not key_record:
            logging.warning("Integration API: invalid/missing key from ip=%s", _client_ip())
            return jsonify({"error": "invalid or missing API key"}), 401

        tenant_id = key_record["tenant_id"]
        # Per-tenant IP allowlist (column added to tenants; empty = no restriction)
        tenant_cfg = db.get_tenant_integration(tenant_id) or {}
        allowlist = tenant_cfg.get("ip_allowlist", "") or ""
        if allowlist and not _ip_allowed(allowlist, _client_ip()):
            logging.warning("Integration API: IP not in tenant allowlist tenant=%s ip=%s",
                            tenant_id, _client_ip())
            return jsonify({"error": "source IP not permitted for this tenant"}), 403

        request.tenant_id = tenant_id
        request.api_key_label = key_record.get("label", "")
        return fn(*args, **kwargs)
    return wrapped


def _extract_report_payload() -> Tuple[str, Optional[str], dict]:
    """Return (report_text, inbound_blob, metadata_dict).
    Supports JSON {report_text, ...} or multipart with 'report' file (PDF or text)."""
    metadata = {}
    report_text = ""
    inbound_blob: Optional[bytes] = None

    if request.is_json:
        body = request.get_json(silent=True) or {}
        report_text = (body.get("report_text") or body.get("text") or "").strip()
        metadata = {
            "accession_number": str(body.get("accession_number", "")),
            "patient_id": str(body.get("patient_id", "")),
            "patient_name": str(body.get("patient_name", "")),
            "study_uid": str(body.get("study_uid", "")),
            "language": str(body.get("language", "English")),
            "source_ref": str(body.get("source_ref", "")),
        }
        inbound_blob = report_text.encode("utf-8") if report_text else None
        return report_text, inbound_blob, metadata

    metadata = {
        "accession_number": request.form.get("accession_number", ""),
        "patient_id": request.form.get("patient_id", ""),
        "patient_name": request.form.get("patient_name", ""),
        "study_uid": request.form.get("study_uid", ""),
        "language": request.form.get("language", "English"),
        "source_ref": request.form.get("source_ref", ""),
    }

    uploaded = request.files.get("report") or request.files.get("file")
    if uploaded and uploaded.filename:
        inbound_blob = uploaded.read()
        name = (uploaded.filename or "").lower()
        if name.endswith(".pdf"):
            try:
                report_text = int_translator.extract_text_from_pdf(inbound_blob)
            except Exception:
                logging.exception("PDF text extraction failed")
                report_text = ""
        else:
            try:
                report_text = inbound_blob.decode("utf-8", errors="ignore")
            except Exception:
                report_text = ""
    else:
        report_text = (request.form.get("report_text") or "").strip()
        inbound_blob = report_text.encode("utf-8") if report_text else None

    return report_text, inbound_blob, metadata


def _render_patient_copy(tenant_integration: dict, translation: dict, metadata: dict) -> bytes:
    from app import HTML as _HTML  # WeasyPrint binding, late import

    if not _HTML:
        raise RuntimeError("WeasyPrint is not available")

    html_str = render_template(
        "patient_copy.html",
        structured=translation["structured"],
        patient=translation["patient"],
        hospital_name=tenant_integration.get("display_name") or translation["patient"].get("hospital"),
        accession_number=metadata.get("accession_number", ""),
        generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    return _HTML(string=html_str, base_url=request.host_url).write_pdf()


@integration_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "inside-imaging-integration"})


@integration_bp.route("/reports", methods=["POST"])
@_rate_limit
@_require_api_key
def receive_report():
    tenant_id = request.tenant_id

    try:
        report_text, inbound_blob, metadata = _extract_report_payload()
    except Exception as exc:
        return jsonify({"error": f"could not parse payload: {exc}"}), 400

    if not report_text:
        return jsonify({"error": "no report text provided (use JSON 'report_text' or upload a PDF/text file as 'report')"}), 400

    tenant_integration = db.get_tenant_integration(tenant_id) or {}
    phi_mode = int_phi.normalize_mode(tenant_integration.get("phi_mode", "passthrough"))

    # Scrub identifiers + report text per tenant's PHI mode (before any persistence or LLM call).
    if phi_mode != "passthrough":
        metadata = int_phi.scrub_metadata(metadata, phi_mode, tenant_salt=tenant_id)
        report_text = int_phi.scrub_text(report_text, phi_mode)

    storage = get_storage()

    report_id = db.insert_integration_report({
        "tenant_id": tenant_id,
        "source": "http",
        "source_ref": metadata.get("source_ref", ""),
        "accession_number": metadata.get("accession_number", ""),
        "patient_id_truncated": db.truncate_name(metadata.get("patient_name", "")),
        "study_uid": metadata.get("study_uid", ""),
        "status": "received",
        "language": metadata.get("language", "English"),
    })

    inbound_key = f"tenants/{tenant_id}/integration/inbound/{report_id}.bin"
    if inbound_blob:
        try:
            storage.put(inbound_key, inbound_blob, content_type="application/octet-stream")
            db.update_integration_report(report_id, inbound_storage_key=inbound_key)
        except Exception:
            logging.exception("Failed to persist inbound blob for report %s", report_id)

    db.log_audit_event(
        tenant_id=tenant_id,
        username=f"apikey:{request.api_key_label or 'unlabeled'}",
        action="integration.report.received",
        resource_type="integration_report",
        resource_uid=str(report_id),
        ip_address=request.remote_addr or "",
        user_agent=request.headers.get("User-Agent", ""),
        details=f"accession={metadata.get('accession_number', '')} bytes={len(inbound_blob or b'')}",
    )

    try:
        translation = int_translator.run_translation(report_text, language=metadata.get("language", "English"))
    except Exception as exc:
        db.update_integration_report(report_id, status="error", error=str(exc), mark_processed=True)
        return jsonify({"error": f"translation failed: {exc}", "report_id": report_id}), 500

    try:
        pdf_bytes = _render_patient_copy(tenant_integration, translation, metadata)
    except Exception as exc:
        logging.exception("PDF render failed")
        db.update_integration_report(report_id, status="error", error=f"pdf_render: {exc}", mark_processed=True)
        return jsonify({"error": f"pdf render failed: {exc}", "report_id": report_id}), 500

    outbound_key = f"tenants/{tenant_id}/integration/outbound/{report_id}.pdf"
    try:
        storage.put(outbound_key, pdf_bytes, content_type="application/pdf")
        db.update_integration_report(report_id, outbound_pdf_key=outbound_key)
    except Exception:
        logging.exception("Failed to persist outbound PDF for report %s", report_id)

    delivery = []
    if tenant_integration:
        delivery = int_return.dispatch(
            tenant_integration,
            pdf_bytes,
            metadata={
                "report_id": str(report_id),
                "accession_number": metadata.get("accession_number", ""),
                "patient_id": metadata.get("patient_id", ""),
                "patient_name": metadata.get("patient_name", ""),
                "study_uid": metadata.get("study_uid", ""),
            },
        )
        for r in delivery:
            db.log_audit_event(
                tenant_id=tenant_id,
                username=f"apikey:{request.api_key_label or 'unlabeled'}",
                action=f"integration.return.{r.get('path', '?')}",
                resource_type="integration_report",
                resource_uid=str(report_id),
                ip_address=request.remote_addr or "",
                user_agent=request.headers.get("User-Agent", ""),
                outcome="success" if r.get("ok") else "error",
                details=str(r)[:500],
            )

    db.update_integration_report(report_id, status="processed", mark_processed=True)

    if request.args.get("return") == "json":
        return jsonify({
            "report_id": report_id,
            "status": "processed",
            "delivery": delivery,
            "outbound_pdf_key": outbound_key,
        })

    resp = Response(pdf_bytes, mimetype="application/pdf")
    resp.headers["Content-Disposition"] = 'inline; filename="patient_copy.pdf"'
    resp.headers["X-Report-Id"] = str(report_id)
    resp.headers["X-Delivery-Results"] = ";".join(
        f"{r.get('path')}={('ok' if r.get('ok') else 'fail')}" for r in delivery
    ) or "none"
    return resp


@integration_bp.route("/reports/<int:report_id>", methods=["GET"])
@_require_api_key
def get_report(report_id):
    record = db.get_integration_report(report_id)
    if not record or record["tenant_id"] != request.tenant_id:
        return jsonify({"error": "not found"}), 404
    return jsonify(record)
