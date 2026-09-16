# Is Rust worth it for backend / device_agent? (evaluated)

Measured (2026-09): backend 5,591 LOC (control_plane 2,241 / obtainium 1,062 /
app_portal 1,064 / core 669 / storage 208); device_agent 730 LOC. Nix closures:
`packages.portal-device-agent` 176.6 MiB, `packages.portal` 240.5 MiB (mostly CPython).

## Verdict
- **backend: keep Python.** Portability is irrelevant (runs on the NAS via NixOS).
  The dynamic extension model (ID registry, duck-typed hooks) is cheap in Python and
  expensive in Rust: no stable ABI, so plugins mean `abi_stable`/`libloading`
  (same-compiler constraint) or WASM components. A 5.6k LOC rewrite buys little.
- **device_agent: portability is real** (Android/nix-on-droid, NAS, other edge hosts).
  A Rust/Go static binary (~single-digit MB, no interpreter) is the only way to drop
  the ~150 MiB CPython runtime. Go cross-compiles more easily; Rust if control is needed.
  Performance is not a requirement here.
- **Chosen path (done)**: split `device_agent` into its own distribution
  (`device_agent/pyproject.toml` + `default.nix`, deps websockets+jsonschema only,
  no backend import). Flake output `packages.portal-device-agent`. Devices now install
  176 MiB instead of 240 MiB. Revisit Rust/Go only if "no Python runtime on device"
  becomes a hard requirement.

## External extension mechanism (done)
`backend/core/extensions.py` resolves an extension ID from `EXTENSION_REGISTRY`
(first-party) plus the `portal.extensions` entry-point group. Config selects IDs
(`{"id": ..., "config": {...}}`). Example: `examples/hello_extension`; docs:
`docs/external-extensions.md`. Test: `backend/core/tests/test_external_extension.py`.
External extensions depend on the `portal` distribution for `BaseExtension`.
Caveat: no hot reload; backups key extension data by CLASS NAME (on-disk format).
