# dotfiles follow-up — DONE (2026-09)

dotfiles (`github.com/syoch/dotfiles`) has been updated for the infrastructure refactors.
Changes applied (uncommitted in dotfiles at the time of writing; dotfiles has other unrelated
pending changes — commit selectively):
- `flake.nix`: `syoch-infra.nixosModules.syoch-portal` → `.portal`; nix-on-droid
  `packages.aarch64-linux.portal` → `portal-device-agent`.
- `components/host/sv01/services/portal.nix`: `services.syoch-portal` → `services.portal`;
  `systemd.services.syoch-portal` → `portal`; added explicit `users.users.syoch-portal` /
  `users.groups.syoch-portal` (the module no longer creates them now that its default changed).
  OS user/group and Postgres db/role intentionally KEEP the `syoch-portal` names (no data migration).
- `components/host/sv01/services/pgsql.nix`: `before = [ "portal.service" ]`.
- `components/host/syoch-nix/portal-device-agent.nix`: agent binary now from
  `packages.portal-device-agent` (`agentPkg`), while `portal-opencode-tool` still comes from
  `packages.portal`.
- sops secret `components/host/sv01/secrets.yaml` `portal-config`: `extensions` migrated from
  `{module, class}` to `{id, ...}` (`storage`/`obtainium`/`control-plane`/`app-portal`) using
  `sops set --value-file` (only that key decrypted).

Verified (with `--override-input syoch-infra path:<infra>`): `nixosConfigurations.sv01`,
`nixosConfigurations.syoch-nix` and `nixOnDroidConfigurations.default` all evaluate; the
aarch64 `portal-device-agent` package exists.

Remaining operational steps (user):
- Push the infrastructure changes, then in dotfiles run `nix flake update syoch-infra`
  (flake.lock still pins the old rev `757cd14`).
- Rebuild/deploy the hosts (`nixos-rebuild switch`); the systemd unit renamed
  `syoch-portal.service` → `portal.service`.
- The infra `nixosModules.portal-device-agent` (`services.portal-device-agent`) is NOT imported by
  dotfiles (dotfiles keeps its own richer local module of the same option name) — no conflict.
