#!/usr/bin/env bash
set -ex

echo "[*] Testing direct access to backend service"
curl --max-time 5 localhost:9101 > /dev/null && echo "[+] Direct access to backend service succeeded" || echo "[-] Direct access to backend service failed"

echo "[*] Testing access to backend service via jump server with port forwarding"
ssh -N -R 0.0.0.0:8001:localhost:9101 syoch-vpn &
SSH_PID=$!
sleep 2
ssh syoch-vpn "curl --max-time 5 -vs 172.18.0.1:8001" && echo "[+] Access to backend service via jump server succeeded" || echo "[-] Access to backend service via jump server failed"
kill $SSH_PID 2>/dev/null || true
wait $SSH_PID 2>/dev/null || true
