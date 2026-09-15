import re
import uuid

from backend.core.database import session_scope
from .models import WebApp, Feedback, Bridge


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or uuid.uuid4().hex[:12]


class AppPortalManagerCLI:
    def __init__(self, core_config):
        self.config = core_config

    def register_commands(self, subparsers):
        parser = subparsers.add_parser(
            "app-portal",
            help="Manage the App Portal (web app registry and feedback)",
        )
        sp = parser.add_subparsers(dest="subcommand", required=True, help="App portal commands")

        sp.add_parser("list-apps", help="List registered web apps")

        register = sp.add_parser("register-app", help="Register a web app manually")
        register.add_argument("--name", required=True)
        register.add_argument("--directory", required=True, dest="directory",
                              help="OpenCode project directory (session directory)")
        register.add_argument("--session-id", required=True, dest="session_id",
                              help="Pinned OpenCode session id")
        register.add_argument("--slug", default=None)
        register.add_argument("--url", default=None)
        register.add_argument("--description", default=None)
        register.add_argument("--bridge-device-id", default=None, dest="bridge_device_id")
        register.add_argument("--tag", action="append", dest="tags", default=[])

        delete = sp.add_parser("delete-app", help="Delete a registered web app")
        delete.add_argument("--slug", required=True)

        update = sp.add_parser("update-app", help="Update a registered web app (only given fields change)")
        update.add_argument("--slug", required=True)
        update.add_argument("--name", default=None)
        update.add_argument("--description", default=None)
        update.add_argument("--url", default=None)
        update.add_argument("--directory", default=None, dest="directory")
        update.add_argument("--session-id", default=None, dest="session_id")
        update.add_argument("--bridge-device-id", default=None, dest="bridge_device_id")
        update.add_argument("--status", default=None,
                            help="e.g. active / archived")
        update.add_argument("--tag", action="append", dest="tags", default=None,
                            help="Replace tags (repeatable)")

        fb = sp.add_parser("list-feedback", help="List feedback")
        fb.add_argument("--app-slug", default=None, dest="app_slug")

        sp.add_parser("list-bridges", help="List registered app-portal bridges")

        parser.set_defaults(func=self.handle_cli)

    def handle_cli(self, args):
        if args.subcommand == "list-apps":
            self.list_apps()
        elif args.subcommand == "register-app":
            self.register_app(args)
        elif args.subcommand == "update-app":
            self.update_app(args)
        elif args.subcommand == "delete-app":
            self.delete_app(args.slug)
        elif args.subcommand == "list-feedback":
            self.list_feedback(args.app_slug)
        elif args.subcommand == "list-bridges":
            self.list_bridges()

    def list_apps(self):
        with session_scope() as session:
            rows = session.query(WebApp).order_by(WebApp.created_at).all()
            if not rows:
                print("(no web apps registered)")
                return
            print(f"{'SLUG':<32} {'NAME':<32} {'SESSION':<32} BRIDGE")
            for a in rows:
                print(f"{a.slug:<32} {a.name:<32} {a.opencode_session_id:<32} {a.bridge_device_id}")

    def register_app(self, args):
        slug = args.slug or _slugify(args.name)
        with session_scope() as session:
            if session.query(WebApp).filter_by(slug=slug).first():
                print(f"Error: app slug {slug!r} already exists")
                return False
            bridge_device_id = args.bridge_device_id
            if not bridge_device_id:
                from .api import _settings
                bridge_device_id = _settings["bridge_device_id"]
            app = WebApp(
                slug=slug,
                name=args.name,
                description=args.description,
                url=args.url,
                project_directory=args.directory,
                opencode_session_id=args.session_id,
                bridge_device_id=bridge_device_id,
                source="manual",
                tags=args.tags or [],
            )
            session.add(app)
            session.flush()
            print(f"Registered app: slug={app.slug} id={app.id}")
            return True

    def update_app(self, args):
        with session_scope() as session:
            app = session.query(WebApp).filter_by(slug=args.slug).first()
            if not app:
                print(f"Error: app {args.slug!r} not found")
                return False
            if args.name is not None:
                app.name = args.name
            if args.description is not None:
                app.description = args.description
            if args.url is not None:
                app.url = args.url
            if args.directory is not None:
                app.project_directory = args.directory
            if args.session_id is not None:
                app.opencode_session_id = args.session_id
            if args.bridge_device_id is not None:
                app.bridge_device_id = args.bridge_device_id
            if args.status is not None:
                app.status = args.status
            if args.tags is not None:
                app.tags = args.tags
            session.flush()
            print(f"Updated app: {app.slug}")
            return True

    def delete_app(self, slug: str):
        with session_scope() as session:
            app = session.query(WebApp).filter_by(slug=slug).first()
            if not app:
                print(f"Error: app {slug!r} not found")
                return False
            session.delete(app)
            print(f"Deleted app: {slug}")
            return True

    def list_feedback(self, app_slug):
        with session_scope() as session:
            query = session.query(Feedback).order_by(Feedback.created_at.desc())
            if app_slug:
                app = session.query(WebApp).filter_by(slug=app_slug).first()
                if not app:
                    print(f"Error: app {app_slug!r} not found")
                    return False
                query = query.filter(Feedback.app_id == app.id)
            rows = query.limit(50).all()
            if not rows:
                print("(no feedback)")
                return
            print(f"{'ID':<38} {'STATUS':<12} {'CREATED':<22} BODY")
            for f in rows:
                body = (f.body or "").replace("\n", " ")[:60]
                created = f.created_at.isoformat() if f.created_at else "-"
                print(f"{f.id:<38} {f.status:<12} {created:<22} {body}")

    def list_bridges(self):
        with session_scope() as session:
            rows = session.query(Bridge).order_by(Bridge.registered_at).all()
            if not rows:
                print("(no bridges registered)")
                return
            print(f"{'DEVICE_ID':<24} {'WEBUI_BASE_URL':<40} LAST_SEEN")
            for b in rows:
                last_seen = b.last_seen.isoformat() if b.last_seen else "-"
                print(f"{b.device_id:<24} {str(b.webui_base_url):<40} {last_seen}")
