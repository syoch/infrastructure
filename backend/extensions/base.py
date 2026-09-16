from typing import Any


class BaseExtension:
    """
    Abstract base class for all portal extensions.
    Any extension should inherit from this class and implement the necessary methods.
    """

    #: Stable identifier used by deployment configuration (see config.EXTENSIONS).
    ID: str = ""

    def __init__(self, core_config: Any):
        """
        Initializes the extension with the global backend core configuration.
        """
        self.config = core_config
        self.tags: list[str] = []
        self.host: Any = None

    def setup(self) -> None:
        """
        Initial hook to set up the extension.
        This is called during server startup and CLI execution.
        """
        pass

    def get_routes(self) -> dict[str, Any]:
        """
        Returns a dictionary mapping HTTP URL paths to handler callables.
        Example:
            return {
                "/api/my-extension-route": self.handle_my_route
            }
            
        The handler callable should accept:
            (handler_instance, path, query_params)
        """
        return {}

    def get_post_routes(self) -> dict[str, Any]:
        """
        Returns a dictionary mapping HTTP POST URL paths to handler callables.
        Example:
            return {
                "/api/my-extension-post": self.handle_my_post
            }
        """
        return {}

    def register_cli_commands(self, subparsers: Any) -> None:
        """
        Interface for adding commands to the main CLI (manage.py).
        Should register subparsers and associate them with handling functions.
        Example:
            parser = subparsers.add_parser("my-ext-command", help="Help text")
            parser.set_defaults(func=self.handle_cli_command)
        """
        pass

    def backup_data(self, session: Any) -> dict[str, Any]:
        """
        Optional hook to return JSON-serializable database records or metadata for backup.
        """
        return {}

    def restore_data(self, session: Any, data: dict[str, Any], strategy: str) -> None:
        """
        Optional hook to restore data serialized by backup_data.
        """
        pass

    def get_backup_directories(self) -> dict[str, str]:
        """
        Optional hook to return a dict of {archive_subfolder_name: local_absolute_directory_path}
        specifying physical directories to package in the backup tarball.
        """
        return {}

    def restore_directories(self, temp_dir: str) -> None:
        """
        Optional hook to restore physical directories for this extension from the extracted backup temp directory.
        """
        pass

    def get_referenced_file_hashes(self, session: Any) -> set[str]:
        """
        Optional hook to return a set of file hashes (e.g., SHA-256) currently referenced by this extension's models.
        Used by storage provider extensions for generic orphan detection / GC.
        """
        return set()

    def get_startup_info(self, local_ip: str) -> list[str]:
        """
        Optional hook to return a list of diagnostic/info strings to be printed on startup.
        """
        return []




