# Portal Device Agent on Android (Termux + nix-on-droid)

This guide shows how to run `portal-device-agent` on an Android device that has
Tailscale + Termux + nix-on-droid installed.

## 1. Install required apps (one-time)

- **Termux** (from F-Droid, not Play Store)
- **Termux:Boot** (from F-Droid) — runs scripts at boot
- **nix-on-droid** — provides a Nix environment on Android

In Termux:

```sh
pkg install git curl jq

# Install nix-on-droid (follow its README; one-line installer is fine)
curl -L https://raw.githubusercontent.com/t184256/nix-on-droid/master/install-nix-on-droid.sh | bash

# Restart Termux so nix-on-droid takes effect.
```

## 2. Bring up Tailscale (one-time)

```sh
pkg install tailscale
sudo tailscale up
```

Verify connectivity from Termux:

```sh
tailscale ping <your-portal-host>
```

## 3. Install `portal-device-agent`

In the nix-on-droid environment (any `nix-on-droid shell`), add the portal
package. The simplest path is to install it from this repository:

```sh
git clone https://github.com/syoch/infrastructure ~/infrastructure
cd ~/infrastructure
nix profile install .
```

After that, `portal-device-agent` should be in `PATH`.

## 4. Create config.json

```sh
mkdir -p ~/.config/portal-device-agent
cat > ~/.config/portal-device-agent/config.json <<'EOF'
{
  "device_id": "my-android",
  "display_name": "My Android",
  "server_url": "https://portal.syoch.org",
  "bootstrap_token_file": "/data/data/com.termux/files/home/.config/portal-device-agent/bootstrap-token",
  "operations": [
    {
      "id": "device.info",
      "name": "Device Info",
      "group": "device",
      "description": "Show basic device info",
      "command": ["sh", "-c", "getprop ro.product.model; getprop ro.build.version.release; uname -a"],
      "shell": false,
      "timeout_seconds": 10,
      "ui_hint": {"kind": "button", "label": "Device Info"},
      "params_schema": {"type": "object", "properties": {}}
    }
  ]
}
EOF
chmod 600 ~/.config/portal-device-agent/config.json
```

## 5. Issue a bootstrap token

From your portal server, run:

```sh
portal-manage control issue-bootstrap-token --device-id my-android --display-name "My Android"
```

Copy the token into `~/.config/portal-device-agent/bootstrap-token` on the
Android device:

```sh
chmod 600 ~/.config/portal-device-agent/bootstrap-token
# paste the token
```

## 6. Test the agent manually first

```sh
portal-device-agent --config ~/.config/portal-device-agent/config.json
```

You should see `[device-agent] connected to ws://...` on stderr.

Verify in the portal's `#/control` Devices tab that `my-android` is online and
its operations are listed.

## 7. Autostart with Termux:Boot

```sh
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/portal-device-agent.sh <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
# Wait for nix-on-droid to be ready
for i in $(seq 1 30); do
  if [ -x "$PREFIX/bin/nix-on-droid" ]; then
    break
  fi
  sleep 2
done
# Wait for Tailscale to come up
for i in $(seq 1 30); do
  if command -v tailscale >/dev/null 2>&1; then
    if tailscale status >/dev/null 2>&1; then
      break
    fi
  fi
  sleep 5
done
exec nix-on-droid run portal-device-agent \
  --config /data/data/com.termux/files/home/.config/portal-device-agent/config.json
EOF
chmod +x ~/.termux/boot/portal-device-agent.sh
```

Open Termux:Boot once so it can register itself with the system, then reboot.

## 8. Send commands from portal WebUI

In `#/control` → Devices → select `my-android` → run any of the agent's
advertised operations. The result (stdout/stderr/exit_code) will appear inline.

## 9. Edit config from the portal

The agent advertises built-in operations under the `device.config` group:
- `List Operations` (button) — see the current user-defined operations
- `Add Operation` (form) — add a new operation; the `params_schema` and
  `ui_hint` fields are textareas where you paste JSON
- `Update Operation` / `Delete Operation` / `Test Operation` (forms)
- `Get Config` (button) — see the full config.json
- `Reload` (button) — re-reads config and re-registers on the server

After `Add Operation` / `Update Operation` / `Delete Operation`, the agent
automatically reloads (in-place, no restart needed).

## Troubleshooting

| Symptom | Check |
|---|---|
| `[device-agent] register failed: HTTP 409` | A device with the same `device_id` is already registered. Issue a new bootstrap token AND change `device_id`, OR delete the old device with `portal-manage control delete-device --device-id <id>`. |
| `[device-agent] connection error: ...` | Tailscale isn't up yet. Increase the wait loop in the Termux:Boot script. |
| Operations not visible in portal | Click `Reload` in the device's `device.config` group, or send SIGHUP: `pkill -HUP -f portal-device-agent`. |
| `command timed out after Ns` | Increase `timeout_seconds` in the operation's config, or fix the underlying command. |
