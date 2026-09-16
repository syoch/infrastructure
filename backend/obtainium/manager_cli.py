import os
import json
import hashlib
import shutil
from backend.utils.network import get_local_ip
from backend.core.database import session_scope
from .models import App, Category, Setting, LocalAppAPK

class ObtainiumRepoManagerCLI:
    """
    Handles CLI operations (bootstrap, import, compile) for the obtainium_repo extension.
    Uses the database instead of flat files.
    """
    def __init__(self, core_config, compiler):
        self.config = core_config
        self.compiler = compiler

    def register_commands(self, subparsers):
        """Registers CLI arguments under obtainium-repo command."""
        # Main parser for obtainium-repo
        repo_parser = subparsers.add_parser(
            "obtainium-repo", 
            help="Manage Obtainium App Repository configurations"
        )
        
        # Subcommands for obtainium-repo
        repo_subparsers = repo_parser.add_subparsers(dest="subcommand", required=True, help="Repo commands")
        
        # import
        import_parser = repo_subparsers.add_parser(
            "import", 
            help="Import raw Obtainium export JSON file into database"
        )
        import_parser.add_argument("file", help="Path to raw JSON file")
        


        repo_parser.set_defaults(func=self.handle_cli)
 
    def handle_cli(self, args):
        """Dispatches commands to corresponding methods."""
        if args.subcommand == "import":
            self.import_from_file(args.file)


    def import_app_config(self, app_data, session):
        """Imports an individual app configuration dictionary into database session."""
        app_id = app_data.get("id")
        if not app_id:
            return None

        # Upsert application
        app = session.query(App).filter_by(id=app_id).first()
        if not app:
            app = App(id=app_id)
            session.add(app)

        app.name = app_data.get("name", "")
        app.url = app_data.get("url", "")
        app.override_source = app_data.get("overrideSource")
        app.preferred_apk_index = app_data.get("preferredApkIndex")
        app.pinned = app_data.get("pinned", False)
        app.allow_id_change = app_data.get("allowIdChange", False)

        # Parse additionalSettings
        additional_settings = app_data.get("additionalSettings")
        if additional_settings:
            if isinstance(additional_settings, str):
                try:
                    app.additional_settings = json.loads(additional_settings)
                except Exception:
                    app.additional_settings = {"raw": additional_settings}
            else:
                app.additional_settings = additional_settings
        else:
            app.additional_settings = {}

        # Sync categories
        category_names = app_data.get("categories", [])
        categories = []
        for cat_name in category_names:
            cat = session.query(Category).filter_by(name=cat_name).first()
            if not cat:
                # Add default category color
                cat = Category(name=cat_name, color=4284857472)
                session.add(cat)
            categories.append(cat)
        app.categories = categories

        return app_id



    def import_from_file(self, filepath):
        """Parses a raw Obtainium export JSON and splits it into database configs."""
        if not os.path.exists(filepath):
            print(f"Error: File not found at {filepath}")
            return False

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON from {filepath}: {e}")
            return False

        try:
            with session_scope() as session:
                imported_count = 0
                for app in data.get("apps", []):
                    app_id = self.import_app_config(app, session)
                    if app_id:
                        imported_count += 1

                # Merge global settings & categories
                settings_data = data.get("settings")
                if settings_data:
                    for k, v in settings_data.items():
                        if k == "categories":
                            parsed_cats = v
                            if isinstance(v, str):
                                try:
                                    parsed_cats = json.loads(v)
                                except Exception:
                                    parsed_cats = {}
                            
                            for cat_name, cat_color in parsed_cats.items():
                                cat = session.query(Category).filter_by(name=cat_name).first()
                                if cat:
                                    cat.color = cat_color
                                else:
                                    new_cat = Category(name=cat_name, color=cat_color)
                                    session.add(new_cat)
                        else:
                            setting = session.query(Setting).filter_by(key=k).first()
                            if setting:
                                setting.value = v
                            else:
                                new_setting = Setting(key=k, value=v)
                                session.add(new_setting)

            print(f"Successfully imported {imported_count} apps from {filepath}.")
            return True
        except Exception as e:
            print(f"Error during import: {e}")
            return False


