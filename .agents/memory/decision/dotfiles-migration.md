# dotfiles follow-up required (breaking changes)

This repo's refactor changed interfaces that dotfiles (`inputs.syoch-infra`, `github:syoch/infrastructure`)
must adopt in a SEPARATE task. Until then dotfiles is broken.

Changes to apply in dotfiles:
- `flake.nix`: `syoch-infra.nixosModules.syoch-portal` → `syoch-infra.nixosModules.portal`.
- `components/host/sv01/services/portal.nix`: `services.syoch-portal` → `services.portal`;
  `systemd.services.syoch-portal` → `portal` (unit renamed).
- Portal config JSON (sops secret `portal-config`): `extensions` must now be a list of IDs, e.g.
  `[{"id":"storage","config":{"uploads_dir":"..."}},{"id":"obtainium"},{"id":"control-plane"},{"id":"app-portal"}]`.
  The old `{module, class}` schema no longer loads.
- Host data migration if adopting the new default names: StateDirectory/user/DB
  `syoch-portal` → `portal` (`/var/lib/syoch-portal` → `/var/lib/portal`, Postgres db/user).
- `packages.portal` and `packages.aarch64-linux.portal` are unchanged (device-agent package path is unchanged).
- Optional: dotfiles has its own `services.portal-device-agent` module in `components/host/syoch-nix/portal-device-agent.nix`
  (same option name as this repo's `nixosModules.portal-device-agent`); reconcile (adopt one) to avoid collisions.
- `nixosModules.web-infrastructure` no longer exists; sv01 composes nginx/acme itself already.
