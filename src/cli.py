"""Flask CLI commands for tenant and API key management.

Register in app.py:
    from src.cli import tenant_group, apikey_group
    app.cli.add_command(tenant_group, "tenant")
    app.cli.add_command(apikey_group, "apikey")

Usage:
    flask tenant create --tenant-id athma --display-name "Athma Hospital" \
        --phi-mode pseudonymize --hl7-sending-facility ATHMA_MAIN \
        --webhook-url https://athma.example/webhook --return-path webhook

    flask tenant list

    flask apikey issue --tenant-id athma --label stratus-hl7-listener

    flask apikey revoke --tenant-id athma --label stratus-hl7-listener
"""

from __future__ import annotations

import click

from src import db
from src.integration import auth as int_auth
from src.integration.return_paths import _validate_webhook_url


# ---------------------------------------------------------------------------
# tenant commands
# ---------------------------------------------------------------------------

@click.group("tenant")
def tenant_group():
    """Manage Inside Imaging tenants (hospitals / facilities)."""


@tenant_group.command("create")
@click.option("--tenant-id", required=True, help="Unique tenant identifier (slug, no spaces).")
@click.option("--display-name", default="", help="Human-readable hospital name.")
@click.option("--region", default="", help="Geographic region (informational).")
@click.option(
    "--phi-mode",
    type=click.Choice(["pseudonymize", "full_deidentify", "passthrough"]),
    default="pseudonymize",
    show_default=True,
    help="PHI handling mode for this tenant.",
)
@click.option("--hl7-sending-facility", default="",
              help="HL7 MSH-4 Sending Facility value for automatic HL7 routing.")
@click.option("--webhook-url", default="", help="URL to POST translated PDFs to (webhook return path).")
@click.option(
    "--return-path",
    type=click.Choice(["webhook", "dicom_sc", "none"]),
    default="webhook",
    show_default=True,
    help="How to deliver translated reports back to the hospital.",
)
@click.option("--pacs-host", default="", help="PACS hostname for DICOM C-STORE return path.")
@click.option("--pacs-port", type=int, default=0, help="PACS DICOM port (default 104).")
@click.option("--pacs-ae-title", default="", help="Called AE title on the PACS.")
def tenant_create(tenant_id, display_name, region, phi_mode, hl7_sending_facility,
                  webhook_url, return_path, pacs_host, pacs_port, pacs_ae_title):
    """Create a new tenant record. Prints the tenant_id on success."""
    db.init_db()

    if webhook_url:
        try:
            _validate_webhook_url(webhook_url)
        except ValueError as exc:
            click.echo(f"ERROR: invalid webhook URL — {exc}", err=True)
            raise SystemExit(1)

    existing = db.get_tenant(tenant_id)
    if existing:
        click.echo(f"ERROR: tenant '{tenant_id}' already exists.", err=True)
        raise SystemExit(1)

    db.create_tenant(
        tenant_id=tenant_id,
        display_name=display_name,
        region=region,
        phi_mode=phi_mode,
        hl7_sending_facility=hl7_sending_facility,
    )

    # Apply integration settings that live in separate columns.
    integration_kwargs = {}
    if webhook_url:
        integration_kwargs["webhook_url"] = webhook_url
    if return_path:
        integration_kwargs["return_path"] = return_path
    if pacs_host:
        integration_kwargs["pacs_host"] = pacs_host
    if pacs_port:
        integration_kwargs["pacs_port"] = pacs_port
    if pacs_ae_title:
        integration_kwargs["pacs_ae_title"] = pacs_ae_title
    if hl7_sending_facility:
        integration_kwargs["hl7_sending_facility"] = hl7_sending_facility
    if integration_kwargs:
        db.update_tenant_integration(tenant_id, **integration_kwargs)

    click.echo(tenant_id)


@tenant_group.command("list")
def tenant_list():
    """Print all tenants with key configuration fields."""
    db.init_db()
    tenants = db.list_tenants()
    if not tenants:
        click.echo("No tenants found.")
        return
    header = f"{'TENANT ID':<24} {'DISPLAY NAME':<30} {'REGION':<12} {'PHI MODE':<18} {'RETURN PATH'}"
    click.echo(header)
    click.echo("-" * len(header))
    for t in tenants:
        click.echo(
            f"{t['tenant_id']:<24} {t['display_name']:<30} {t['region']:<12}"
            f" {t['phi_mode']:<18} {t['return_path']}"
        )


# ---------------------------------------------------------------------------
# apikey commands
# ---------------------------------------------------------------------------

@click.group("apikey")
def apikey_group():
    """Manage integration API keys for hospital tenants."""


@apikey_group.command("issue")
@click.option("--tenant-id", required=True, help="Tenant to issue the key for.")
@click.option("--label", default="", help="Human-readable label (e.g. 'stratus-hl7-listener').")
def apikey_issue(tenant_id, label):
    """Issue a new API key for a tenant. Prints the raw key ONCE — copy it now."""
    db.init_db()

    tenant = db.get_tenant(tenant_id)
    if not tenant:
        click.echo(f"ERROR: tenant '{tenant_id}' not found. Create it first with 'flask tenant create'.", err=True)
        raise SystemExit(1)

    raw_key, key_id = int_auth.issue_api_key(tenant_id, label=label)

    click.echo("")
    click.echo("=" * 60)
    click.echo("  API KEY ISSUED — copy this value NOW.")
    click.echo("  It will NOT be shown again.")
    click.echo("=" * 60)
    click.echo(f"  Tenant  : {tenant_id}")
    click.echo(f"  Label   : {label or '(none)'}")
    click.echo(f"  Key ID  : {key_id}")
    click.echo(f"  Raw Key : {raw_key}")
    click.echo("=" * 60)
    click.echo("")
    click.echo("If this key is used for HL7 forwarding, also store it on the tenant:")
    click.echo(f"  (run SQL or use the DB to set tenants.hl7_api_key = '{raw_key}'")
    click.echo(f"   WHERE tenant_id = '{tenant_id}')")
    click.echo("")


@apikey_group.command("revoke")
@click.option("--tenant-id", required=True, help="Tenant the key belongs to.")
@click.option("--label", default="", help="Label of the key(s) to revoke.")
@click.option("--key-hash", "key_hash", default="",
              help="SHA-256 hash of the raw key (alternative to --label).")
def apikey_revoke(tenant_id, label, key_hash):
    """Revoke an API key by label or SHA-256 hash."""
    db.init_db()

    if not label and not key_hash:
        click.echo("ERROR: provide --label or --key-hash.", err=True)
        raise SystemExit(1)

    if key_hash:
        ok = db.revoke_api_key_by_hash(key_hash)
        if ok:
            click.echo(f"Revoked key with hash {key_hash[:16]}… for tenant '{tenant_id}'.")
        else:
            click.echo(f"ERROR: no active key found with that hash.", err=True)
            raise SystemExit(1)
    else:
        count = db.revoke_api_key_by_label(tenant_id, label)
        if count:
            click.echo(f"Revoked {count} key(s) with label '{label}' for tenant '{tenant_id}'.")
        else:
            click.echo(f"ERROR: no active key found with label '{label}' for tenant '{tenant_id}'.", err=True)
            raise SystemExit(1)
