---
name: sops-nix-age-secret-verification
description: Use when setting up or troubleshooting sops-nix encrypted secrets on NixOS: sops decrypt fails, age key mismatch, .sops.yaml recipients, age identity keys.txt, sops not found, tools unavailable in PATH, portal-service secrets, htpasswd htaccess user, secrets.yaml creation. Covers deriving the age public key from the private identity, verifying it matches .sops.yaml recipients, and installing sops/htpasswd via nix shell when not on PATH.
---

# sops-nix / age Secret Setup & Verification

Use when deploying a NixOS service that reads sops-nix secrets (e.g. portal-service on sv01) and decryption fails, the age identity doesn't match `.sops.yaml`, or `sops`/`htpasswd` are not installed.

## When to use
- `sops` decrypt errors (age no applicable keys / decryption failed)
- `age-encrypted` files in the repo can't be read
- `sops` or `htpasswd` binaries are missing from PATH
- Adding a new secret for a NixOS service module (e.g. `nixos/portal-service.nix`, `web-infrastructure.nix`)

## Procedure

1. **Confirm the tools and how they're declared.**
   - `which sops age htpasswd nixos-rebuild` — on this NixOS host `sops` is often not on PATH.
   - Grep the NixOS modules and the dotfiles repo for how secrets are wired: `grep -rn "sops.secrets" components/host/sv01/services/*.nix`. Secrets are declared in `dotfiles/components/host/sv01/` (`portal.nix`, `secrets.yaml`, `secrets.nix`).

2. **Install missing tools without modifying the system.**
   - `nix shell nixpkgs#sops nixpkgs#apacheHttpd --command sh -c 'sops --version; which htpasswd'`
   - apacheHttpd provides `htpasswd` for the htaccess user file.

3. **Verify the age identity matches `.sops.yaml` recipients.**
   - Read the identity: `cat ~/.config/sops/age/keys.txt` (contains the private key + the age public key in the comment).
   - Read recipients: `cat /home/syoch/dotfiles/.sops.yaml` — under `creation_rules`, the `age` list must contain exactly that public key (e.g. `age17jjjatas...`).
   - If `.sops.yaml` is absent/empty, `sops` auto-creates it from the current identity — so run `sops` once to regenerate.
   - Mismatch causes the classic *"no age key available"* decrypt error.

4. **Re-encrypt existing secrets after any key change.**
   - `sops updatekeys` (or re-`sops edit`) the `secrets.yaml` files after adding/rotating recipients; otherwise stale `sops` encryption metadata points at the old key.

## Pitfalls
- `~/.config/sops/age/id_syoch` may not exist; the identity lives in `keys.txt`.
- `sops` not found on NixOS is normal — always use the `nix shell` one-liner; never edit the system config just to get a CLI tool.
- Secret files live in the **dotfiles repo** (`/home/syoch/dotfiles`), while the NixOS modules live in this repo — the split causes confusion; check both.
- `htpasswd` is in `apacheHttpd`, not a dedicated package — do not `nixpkgs#apache`.
