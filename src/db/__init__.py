"""Database package for Inside Imaging.

Splits the previous monolithic src/db.py into focused submodules. Every
public symbol from the old module is re-exported here so existing imports
(`from src import db; db.get_stats()`) continue to work unchanged.
"""

from src.db.connection import (
    DB_PATH,
    get_connection,
    init_db,
    _format_timestamp,
)
from src.db.patients import (
    truncate_name,
    _parse_age,
    _DISEASE_KEYWORDS,
    _format_tags_display,
    normalize_study_name,
    detect_disease_tags,
    add_patient_record,
    store_report_event,
    get_report_brief,
    get_report_detail,
    get_user_reports,
    get_recent_reports,
    get_all_reports_admin,
    delete_patient_record,
)
from src.db.stats import (
    get_stats,
)
from src.db.users import (
    get_user_by_username,
    create_user,
    get_user_by_google_id,
    create_oauth_user,
    is_account_locked,
    record_failed_login,
    record_successful_login,
    assign_role,
    remove_role,
    get_user_roles,
    has_any_role,
    get_totp_secret,
    is_totp_enabled,
    set_totp_secret,
    enable_totp,
    disable_totp,
    get_user_specialty,
    set_user_specialty,
    VALID_SPECIALTIES,
    SPECIALTY_DEFAULT_MODALITY,
)
from src.db.tenants import (
    get_user_tenant,
    get_tenant,
    create_tenant,
    update_tenant_integration,
    get_tenant_integration,
)
from src.db.audit import (
    log_audit_event,
    get_audit_log,
)
from src.db.dicom import (
    upsert_dicom_study,
    upsert_dicom_series,
    insert_dicom_instance,
    get_dicom_studies,
    get_dicom_series,
    get_dicom_instances,
    get_dicom_instance_by_uid,
)
from src.db.integration import (
    create_api_key,
    lookup_api_key,
    revoke_api_key,
    insert_integration_report,
    update_integration_report,
    get_integration_report,
)
from src.db.feedback import (
    submit_feedback,
    delete_feedback,
    get_feedback_by_id,
    update_feedback,
    get_all_feedback,
    update_feedback_status,
    get_user_feedback,
    get_few_shot_examples,
    get_reviewed_report_ids,
    get_feedback_metrics,
)
from src.db.embeddings import (
    embed_approved_feedback,
)
from src.db.backup import backup_db

__all__ = [
    # connection
    "DB_PATH", "get_connection", "init_db",
    # patients / analytics
    "truncate_name", "normalize_study_name", "detect_disease_tags",
    "add_patient_record", "store_report_event",
    "get_report_brief", "get_report_detail", "get_user_reports", "get_recent_reports",
    "get_all_reports_admin", "delete_patient_record",
    # stats
    "get_stats",
    # users
    "get_user_by_username", "create_user",
    "get_user_by_google_id", "create_oauth_user",
    "is_account_locked", "record_failed_login", "record_successful_login",
    # roles
    "assign_role", "remove_role", "get_user_roles", "has_any_role",
    # mfa
    "get_totp_secret", "is_totp_enabled", "set_totp_secret", "enable_totp", "disable_totp",
    # specialty
    "get_user_specialty", "set_user_specialty", "VALID_SPECIALTIES", "SPECIALTY_DEFAULT_MODALITY",
    # tenants
    "get_user_tenant", "get_tenant", "create_tenant",
    "update_tenant_integration", "get_tenant_integration",
    # audit
    "log_audit_event", "get_audit_log",
    # dicom
    "upsert_dicom_study", "upsert_dicom_series", "insert_dicom_instance",
    "get_dicom_studies", "get_dicom_series",
    "get_dicom_instances", "get_dicom_instance_by_uid",
    # integration
    "create_api_key", "lookup_api_key", "revoke_api_key",
    "insert_integration_report", "update_integration_report", "get_integration_report",
    # feedback
    "submit_feedback", "delete_feedback", "get_feedback_by_id", "update_feedback",
    "get_all_feedback", "update_feedback_status", "get_user_feedback",
    "get_few_shot_examples", "embed_approved_feedback",
    "get_reviewed_report_ids", "get_feedback_metrics",
    # backup
    "backup_db",
]
