"""
Built-in operations advertised by the portal device agent.

These operations let the WebUI configure the agent itself: list/add/update/
delete/test user operations, view the full config, and trigger a reload.
"""
import copy


def _string_field(name: str, title: str, **extra) -> dict:
    base = {"type": "string", "title": title}
    base.update(extra)
    return {name: base}


def _json_field(name: str, title: str) -> dict:
    return {
        name: {
            "type": "string",
            "title": title,
            "ui_hint": {"widget": "json"},
        }
    }


def _add_or_update_schema() -> dict:
    return {
        "type": "object",
        "required": ["id", "name", "command"],
        "properties": {
            **_string_field("id", "Operation ID (e.g. system.reboot)"),
            **_string_field("name", "Display name"),
            **_string_field("group", "Group", default="default"),
            **_string_field("description", "Description"),
            **_string_field(
                "command",
                "Command (JSON array of argv, or shell string)",
            ),
            "shell": {"type": "boolean", "title": "Run via shell? (sh -c)"},
            "timeout_seconds": {
                "type": "integer",
                "title": "Timeout (seconds)",
                "default": 30,
                "minimum": 1,
            },
            "params_schema": {
                "type": "string",
                "title": "params_schema (JSON Schema as JSON text)",
                "ui_hint": {"widget": "json"},
            },
            "ui_hint": {
                "type": "string",
                "title": "ui_hint (JSON object as JSON text)",
                "ui_hint": {"widget": "json"},
            },
        },
    }


def _test_schema() -> dict:
    return {
        "type": "object",
        "required": ["id"],
        "properties": {
            **_string_field("id", "Operation ID"),
            "params": {
                "type": "string",
                "title": "params (JSON object as text)",
                "ui_hint": {"widget": "json"},
            },
        },
    }


BUILTIN_OPS = [
    {
        "id": "device.config.list_operations",
        "name": "List Operations",
        "group": "device.config",
        "description": "List the operations currently registered on this device (built-in + user-defined).",
        "ui_hint": {"kind": "button", "label": "List Ops"},
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "id": "device.config.add_operation",
        "name": "Add Operation",
        "group": "device.config",
        "description": "Append a new user-defined operation to the agent's config and reload.",
        "ui_hint": {"kind": "form", "label": "Add Operation"},
        "params_schema": _add_or_update_schema(),
    },
    {
        "id": "device.config.update_operation",
        "name": "Update Operation",
        "group": "device.config",
        "description": "Replace an existing user-defined operation by id and reload.",
        "ui_hint": {"kind": "form", "label": "Update Operation"},
        "params_schema": _add_or_update_schema(),
    },
    {
        "id": "device.config.delete_operation",
        "name": "Delete Operation",
        "group": "device.config",
        "description": "Remove a user-defined operation by id and reload.",
        "ui_hint": {"kind": "form", "label": "Delete Operation"},
        "params_schema": {
            "type": "object",
            "required": ["id"],
            "properties": {
                **_string_field("id", "Operation ID"),
            },
        },
    },
    {
        "id": "device.config.test_operation",
        "name": "Test Operation",
        "group": "device.config",
        "description": "Run an operation locally and return stdout/stderr/exit_code (does not affect server state).",
        "ui_hint": {"kind": "form", "label": "Test Operation"},
        "params_schema": _test_schema(),
    },
    {
        "id": "device.config.get_config",
        "name": "Get Config",
        "group": "device.config",
        "description": "Return the current config.json content as text.",
        "ui_hint": {"kind": "button", "label": "Get Config"},
        "params_schema": {"type": "object", "properties": {}},
    },
    {
        "id": "device.config.reload",
        "name": "Reload Config",
        "group": "device.config",
        "description": "Re-read config.json and re-register all operations on the server.",
        "ui_hint": {"kind": "button", "label": "Reload", "confirm": True},
        "params_schema": {"type": "object", "properties": {}},
    },
]


def get_builtin_ops() -> list:
    return copy.deepcopy(BUILTIN_OPS)


_BUILTIN_IDS = frozenset(op["id"] for op in BUILTIN_OPS)


def is_builtin(op_id: str) -> bool:
    return op_id in _BUILTIN_IDS
