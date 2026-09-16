---
name: nixos-portal-nginx-basic-auth-test
description: Use when adding nginx virtual host or HTTP Basic Auth options to the portal NixOS module and verifying them with the NixOS VM integration test. Trigger keywords: portal-service.nix, nginx vhost, auth_basic, htpasswd, {SHA} hash, openssl dgst sha1 base64, nix build check portal-test, NixOS VM test, 401 status, curl http_code, mkIf locations merge.
---

## When to use

Use when extending `nixos/portal-service.nix` (the `services.portal` module) with nginx virtual-host or HTTP Basic Auth options, and verifying via the NixOS VM test. Typical work: adding `nginx`/`basicAuth` option blocks, wiring `services.nginx.virtualHosts`, and asserting 401/200 status codes in the flake.nix NixOS test.

## Procedure

1. Add options as `mkOption` blocks inside the module's `options` (e.g. `nginx.hostName`, `basicAuth.htpasswdFile`, `basicAuth.protectedPaths`). Use `mkEnableOption` for booleans.

2. Wire config under `config`:
   - Build the vhost locations as ONE attribute set in a single expression: `locations = { "/" = { proxyPass = ...; }; } // lib.optionalAttrs (cfg.basicAuth.enable && cfg.basicAuth.htpasswdFile != null) (lib.genAttrs cfg.basicAuth.protectedPaths (path: { proxyPass = ...; extraConfig = ''auth_basic "${cfg.basicAuth.realm}"; auth_basic_user_file ${cfg.basicAuth.htpasswdFile};''; }));`
   - Pitfall: do NOT assign `services.nginx.virtualHosts."...".locations` twice under two separate `mkIf` statements — the merged attribute causes a hard-to-read eval conflict. Use `//`/`lib.optionalAttrs` in one expression.
   - Add `assertions = [ { assertion = !cfg.basicAuth.enable || cfg.basicAuth.htpasswdFile != null; message = "..."; } ];` for required-fields.
   - protectedPaths keys use nginx location syntax: exact `= /path` or prefix `/path/`.

3. Generate the `{SHA}` htpasswd entry (nginx auth_basic SHA variant):
   `printf 'password' | openssl dgst -sha1 -binary | base64` -> `{SHA}<hash>`
   Use it in the test as `htpasswdFile = pkgs.writeText "x.htpasswd" "user:{SHA}<hash>"`.

4. In the flake.nix NixOS test node: enable `services.portal.nginx`/`basicAuth`, set `hostName = "portal.test.local"`, and add testScript curl assertions:
   `machine.succeed("curl -s -o /dev/null -w '%{http_code}\\n' -H 'Host: portal.test.local' http://127.0.0.1/scrape-index.html | grep -q '^401$'")` and with `-u user:pass` expecting `^200$`.

5. Run the test:
   `nix build .#checks.x86_64-linux.portal-test --no-link` (takes minutes; tail output). Success shows only the dirty-tree warning; failure prints `machine #` boot logs revealing actual HTTP status.

6. Re-verify the plain package still builds: `nix build .#portal --no-link`.

## Pitfalls

- Missing APK download paths return **404 even when auth passes** — assert `^404$` for authenticated downloads of nonexistent APKs, `^200$` for real pages. Unauthenticated hits on protected paths return 401.
- The `Host:` header must be the vhost hostName (`portal.test.local`), not the default `test.local`, or curl hits the wrong vhost and never sees auth.
- Status-only curl idiom: `-s -o /dev/null -w '%{http_code}'` piped to `grep -q '^NNN$'` inside `machine.succeed`; escaping `\n` matters inside the NixOS testScript string.
- After every module change, the NixOS test must be fully rebuilt (no incremental VM cache reuse).
