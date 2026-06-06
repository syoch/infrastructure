import re
import secrets
import uuid
from datetime import datetime, timedelta
from backend.core.database import session_scope
from .models import (
    Device, DeviceACL, DeviceBootstrapToken, OperationSpec, CommandRequest,
)


DEVICE_ID_REGEX = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$")
KNOWN_TYPES = {"device"}


def _strip_type_prefix(value: str) -> str:
    if ":" in value:
        type_, pattern = value.split(":", 1)
        return pattern
    return value


def validate_acl_field(field: str, value: str, require_prefix: bool) -> None:
    if require_prefix:
        if ":" not in value:
            raise ValueError(f"{field}: must be in format '<type>:<pattern>'")
        type_, pattern = value.split(":", 1)
        if type_ not in KNOWN_TYPES:
            raise ValueError(f"{field}: unknown type {type_!r}")
    else:
        pattern = value
    try:
        re.compile(pattern)
    except re.error as e:
        raise ValueError(f"{field}: invalid regex: {e}")


def validate_device_id(value: str) -> None:
    if not DEVICE_ID_REGEX.match(value):
        raise ValueError(
            f"device id must match {DEVICE_ID_REGEX.pattern} (got {value!r})"
        )


def generate_bearer_token() -> str:
    return "tk_" + secrets.token_urlsafe(32)


class ControlPlaneManagerCLI:
    def __init__(self, core_config):
        self.config = core_config

    def register_commands(self, subparsers):
        parser = subparsers.add_parser(
            "control",
            help="Manage the Control Plane (devices, ACLs, bootstrap tokens)",
        )
        sp = parser.add_subparsers(dest="subcommand", required=True, help="Control plane commands")

        sp.add_parser("list-acl", help="List all ACL rules")

        grant = sp.add_parser("grant", help="Create a new ACL rule")
        grant.add_argument("--source", required=True, help="Source device pattern (e.g. 'device:.*')")
        grant.add_argument("--target", required=True, help="Target device pattern (e.g. 'device:nixos-server')")
        grant.add_argument("--operation", required=True, help="Operation regex (e.g. '.*', '^reboot$')")

        revoke = sp.add_parser("revoke", help="Delete an ACL rule by id")
        revoke.add_argument("--acl-id", required=True, dest="acl_id", help="ACL UUID")

        sp.add_parser("list-devices", help="List registered devices")

        rename = sp.add_parser("rename-device", help="Rename a device")
        rename.add_argument("--device-id", required=True, dest="device_id")
        rename.add_argument("--display-name", required=True, dest="display_name")

        delete_dev = sp.add_parser("delete-device", help="Delete a device")
        delete_dev.add_argument("--device-id", required=True, dest="device_id")

        set_admin = sp.add_parser("set-admin", help="Set the ACL admin device (first WebUI device)")
        set_admin.add_argument("--device-id", required=True, dest="device_id")

        sp.add_parser("show-admin", help="Show the current ACL admin device")

        sp.add_parser("clear-admin", help="Clear the ACL admin flag (locks ACL management)")

        issue = sp.add_parser(
            "issue-bootstrap-token",
            help="Issue a one-time bootstrap token for a new device to register",
        )
        issue.add_argument("--device-id", required=True, dest="device_id")
        issue.add_argument("--display-name", required=True, dest="display_name")
        issue.add_argument("--ttl-minutes", type=int, default=15, dest="ttl_minutes")

        sp.add_parser("list-operations", help="List registered operation specs")

        sp.add_parser("list-commands", help="List command requests (most recent first)")

        show_cmd = sp.add_parser("show-command", help="Show a command request by id")
        show_cmd.add_argument("--command-id", required=True, dest="command_id")

        parser.set_defaults(func=self.handle_cli)

    def handle_cli(self, args):
        if args.subcommand == "list-acl":
            self.list_acl()
        elif args.subcommand == "grant":
            self.grant(args.source, args.target, args.operation)
        elif args.subcommand == "revoke":
            self.revoke(args.acl_id)
        elif args.subcommand == "list-devices":
            self.list_devices()
        elif args.subcommand == "rename-device":
            self.rename_device(args.device_id, args.display_name)
        elif args.subcommand == "delete-device":
            self.delete_device(args.device_id)
        elif args.subcommand == "set-admin":
            self.set_admin(args.device_id)
        elif args.subcommand == "show-admin":
            self.show_admin()
        elif args.subcommand == "clear-admin":
            self.clear_admin()
        elif args.subcommand == "issue-bootstrap-token":
            self.issue_bootstrap_token(args.device_id, args.display_name, args.ttl_minutes)
        elif args.subcommand == "list-operations":
            self.list_operations()
        elif args.subcommand == "list-commands":
            self.list_commands()
        elif args.subcommand == "show-command":
            self.show_command(args.command_id)

    def list_acl(self):
        with session_scope() as session:
            rows = session.query(DeviceACL).order_by(DeviceACL.created_at).all()
            if not rows:
                print("(no ACL rules)")
                return
            print(f"{'ID':<38} {'SOURCE':<24} {'TARGET':<24} {'OPERATION':<24} CREATED_AT")
            for r in rows:
                print(
                    f"{r.id:<38} {r.source_device:<24} {r.target_device:<24} "
                    f"{r.operation:<24} {r.created_at.isoformat()}"
                )

    def grant(self, source: str, target: str, operation: str):
        try:
            validate_acl_field("source", source, require_prefix=True)
            validate_acl_field("target", target, require_prefix=True)
            validate_acl_field("operation", operation, require_prefix=False)
        except ValueError as e:
            print(f"Error: {e}")
            return False
        with session_scope() as session:
            existing = session.query(DeviceACL).filter_by(
                source_device=source, target_device=target, operation=operation
            ).first()
            if existing:
                print(f"ACL already exists: id={existing.id}")
                return False
            acl = DeviceACL(source_device=source, target_device=target, operation=operation)
            session.add(acl)
            session.flush()
            print(f"Created ACL: id={acl.id}")
            return True

    def revoke(self, acl_id: str):
        with session_scope() as session:
            row = session.query(DeviceACL).filter_by(id=acl_id).first()
            if not row:
                print(f"Error: ACL id {acl_id!r} not found")
                return False
            session.delete(row)
            print(f"Deleted ACL: id={acl_id}")
            return True

    def list_devices(self):
        with session_scope() as session:
            rows = session.query(Device).order_by(Device.registered_at).all()
            if not rows:
                print("(no devices)")
                return
            print(
                f"{'ID':<24} {'DISPLAY_NAME':<28} {'WS_STATE':<16} "
                f"{'IS_ADMIN':<8} {'LAST_SEEN':<20} TOKEN"
            )
            for d in rows:
                last_seen = d.last_seen.isoformat() if d.last_seen else "-"
                print(
                    f"{d.id:<24} {d.display_name:<28} {d.ws_state:<16} "
                    f"{str(d.is_first_webui_device):<8} {last_seen:<20} {d.bearer_token}"
                )

    def rename_device(self, device_id: str, display_name: str):
        try:
            validate_device_id(device_id)
        except ValueError as e:
            print(f"Error: {e}")
            return False
        with session_scope() as session:
            d = session.query(Device).filter_by(id=device_id).first()
            if not d:
                print(f"Error: device {device_id!r} not found")
                return False
            d.display_name = display_name
            print(f"Renamed device {device_id} -> {display_name!r}")
            return True

    def delete_device(self, device_id: str):
        try:
            validate_device_id(device_id)
        except ValueError as e:
            print(f"Error: {e}")
            return False
        with session_scope() as session:
            d = session.query(Device).filter_by(id=device_id).first()
            if not d:
                print(f"Error: device {device_id!r} not found")
                return False
            session.delete(d)
            print(f"Deleted device {device_id}")
            return True

    def set_admin(self, device_id: str):
        try:
            validate_device_id(device_id)
        except ValueError as e:
            print(f"Error: {e}")
            return False
        with session_scope() as session:
            d = session.query(Device).filter_by(id=device_id).first()
            if not d:
                print(f"Error: device {device_id!r} not found")
                return False
            session.query(Device).filter(
                Device.is_first_webui_device == True
            ).update({"is_first_webui_device": False})
            d.is_first_webui_device = True
            print(f"Set admin: {device_id}")
            return True

    def show_admin(self):
        with session_scope() as session:
            d = session.query(Device).filter_by(is_first_webui_device=True).first()
            if not d:
                print("(no admin device set)")
                return
            print(f"{d.id}\t{d.display_name}\t{token_first8(d.bearer_token)}")

    def clear_admin(self):
        with session_scope() as session:
            count = session.query(Device).filter(
                Device.is_first_webui_device == True
            ).update({"is_first_webui_device": False})
            print(f"Cleared admin flag from {count} device(s)")
            return True

    def issue_bootstrap_token(self, device_id: str, display_name: str, ttl_minutes: int):
        try:
            validate_device_id(device_id)
        except ValueError as e:
            print(f"Error: {e}")
            return False
        if ttl_minutes <= 0 or ttl_minutes > 24 * 60:
            print(f"Error: ttl-minutes must be 1..1440 (got {ttl_minutes})")
            return False
        token_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)
        with session_scope() as session:
            existing = session.query(Device).filter_by(id=device_id).first()
            if existing:
                print(f"Error: device {device_id!r} is already registered")
                return False
            tok = DeviceBootstrapToken(
                id=token_id,
                device_id=device_id,
                display_name=display_name,
                expires_at=expires_at,
            )
            session.add(tok)
            print(f"Bootstrap token: {token_id}")
            print(f"Device: {device_id} ({display_name})")
            print(f"Expires: {expires_at.isoformat()} (in {ttl_minutes} minutes)")
            print("Use this token with the device agent or WebUI to register.")
            return True

    def list_operations(self):
        with session_scope() as session:
            rows = session.query(OperationSpec).order_by(
                OperationSpec.provider, OperationSpec.id
            ).all()
            if not rows:
                print("(no operations registered)")
                return
            print(
                f"{'ID':<32} {'PROVIDER':<24} {'GROUP':<16} {'NAME':<28} LAST_SEEN"
            )
            for r in rows:
                last_seen = r.last_seen.isoformat() if r.last_seen else "-"
                print(
                    f"{r.id:<32} {r.provider:<24} {r.group:<16} "
                    f"{r.name:<28} {last_seen}"
                )

    def list_commands(self):
        with session_scope() as session:
            rows = (
                session.query(CommandRequest)
                .order_by(CommandRequest.created_at.desc())
                .limit(50)
                .all()
            )
            if not rows:
                print("(no commands)")
                return
            print(
                f"{'ID':<38} {'TARGET':<24} {'SOURCE':<24} {'OPERATION':<24} "
                f"{'STATUS':<12} CREATED_AT"
            )
            for r in rows:
                print(
                    f"{r.id:<38} {r.target_device_id:<24} {r.source_device_id:<24} "
                    f"{r.operation:<24} {r.status:<12} {r.created_at.isoformat()}"
                )

    def show_command(self, command_id: str):
        with session_scope() as session:
            r = session.query(CommandRequest).filter_by(id=command_id).first()
            if not r:
                print(f"Error: command {command_id!r} not found")
                return False
            print(f"ID:             {r.id}")
            print(f"Target:         {r.target_device_id}")
            print(f"Source:         {r.source_device_id}")
            print(f"Operation:      {r.operation}")
            print(f"Status:         {r.status}")
            print(f"Created:        {r.created_at.isoformat()}")
            print(f"Claimed:        {r.claimed_at.isoformat() if r.claimed_at else '-'}")
            print(f"Completed:      {r.completed_at.isoformat() if r.completed_at else '-'}")
            print(f"Timeout sec:    {r.timeout_seconds}")
            print(f"Params:         {r.params}")
            print(f"Result:         {r.result}")
            print(f"Error:          {r.error}")
            return True


def token_first8(token: str) -> str:
    return token[:8] + "..." if token else "-"
