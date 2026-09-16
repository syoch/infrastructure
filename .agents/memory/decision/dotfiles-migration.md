# dotfiles follow-up required (breaking changes)

This repo's refactors changed interfaces that dotfiles (`inputs.syoch-infra`,
`github:syoch/infrastructure`) must adopt in a SEPARATE task. Until then dotfiles is broken.

Changes to apply in dotfiles:
- `flake.nix`: `syoch-infra.nixosModules.syoch-portal` → `syoch-infra.nixosModules.portal`.
- `components/host/sv01/services/portal.nix`: `services.syoch-portal` → `services.portal`;
  `systemd.services.syoch-portal` → `portal` (unit renamed).
- Portal config JSON (sops secret `portal-config`): `extensions` must now be a list of IDs, e.g.
  `[{"id":"storage","config":{"uploads_dir":"..."}},{"id":"obtainium"},{"id":"control-plane"},{"id":"app-portal"}]`.
  The old `{module, class}` schema no longer loads.
- **device agent is now a separate package**: use `syoch-infra.packages.<system>.portal-device-agent`
  (deps: websockets+jsonschema only) instead of `packages.portal`. In
  `components/host/syoch-nix/portal-device-agent.nix`, `portalPkg` currently points at
  `packages.portal` and runs `${portalPkg}/bin/portal-device-agent` (no longer provided there);
  set the agent path to `packages.portal-device-agent` while keeping `portal-opencode-tool`
  from `packages.portal`.
- nix-on-droid: `syoch-infra.packages.aarch64-linux.portal-device-agent` (or `portal` if the
  full app is needed).
- Host data migration if adopting the new default names: StateDirectory/user/DB
  `syoch-portal` → `portal` (`/var/lib/syoch-portal` → `/var/lib/portal`, Postgres db/user).
- `packages.portal` / `packages.aarch64-linux.portal` still exist and are unchanged in name.
- Optional: dotfiles has its own `services.portal-device-agent` module (same option name as this
  repo's `nixosModules.portal-device-agent`); reconcile (adopt one) to avoid collisions.
- `nixosModules.web-infrastructure` no longer exists; sv01 composes nginx/acme itself already.
