"""Reference example of an out-of-tree portal extension.

It is discovered through the ``portal.extensions`` entry-point group (see
``pyproject.toml``) and selected in the portal config by its ID::

    {
      "extensions": [
        {"id": "hello", "config": {"greeting": "hi"}},
        {"id": "obtainium"}
      ]
    }
"""
from fastapi import APIRouter

from backend.extensions.base import BaseExtension


class HelloExtension(BaseExtension):
    """Adds a ``GET /api/hello`` route and a ``hello <name>`` CLI command."""

    ID = "hello"

    def __init__(self, core_config, ext_config=None):
        super().__init__(core_config)
        self.ext_config = ext_config or {}
        self.tags = ["greeting"]
        self.router = self._build_router()

    def _build_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/hello", tags=["hello"])

        @router.get("")
        def hello():
            return {"id": self.ID, "message": self.ext_config.get("greeting", "hello")}

        return router

    def register_cli_commands(self, subparsers):
        parser = subparsers.add_parser("hello", help="Example external extension command")
        parser.add_argument("name")
        parser.set_defaults(func=lambda args: print(f"hello, {args.name}"))

    def get_startup_info(self, local_ip: str) -> list:
        return [
            f"Hello extension: http://{local_ip}:{self.config.DEFAULT_PORT}/api/hello",
        ]
