#!/usr/bin/env bash
# One-shot installer for zkids.zeaz.dev origin services.
# Terraform (deploy/terraform/) owns all Cloudflare resources; this script
# only provisions the local systemd units and fetches the connector token.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACCOUNT_ID="9afd03fff02846b4ca89caeff350ce56"
TUNNEL_ID="$(cd "$ROOT/deploy/terraform" && terraform output -raw tunnel_id)"

if [[ -f /etc/zkids-web/env ]]; then
  echo "[i] operator token already present"
else
  WEBTOKEN="$(openssl rand -hex 24)"
  printf 'ZKID_WEB_TOKEN=%s\n' "$WEBTOKEN" | sudo tee /etc/zkids-web/env >/dev/null
  sudo chmod 600 /etc/zkids-web/env
  echo "[+] operator token generated at /etc/zkids-web/env"
fi

sudo cp "$ROOT/deploy/systemd/zkids-web.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zkids-web

if [[ ! -f /etc/cloudflared-zkids/token.env ]]; then
  CF_API_TOKEN="${CF_API_TOKEN:?export CF_API_TOKEN first}"
  curl -s -H "Authorization: Bearer $CF_API_TOKEN" \
    "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/cfd_tunnel/$TUNNEL_ID/token" \
    | sudo python3 -c "
import json,sys,pathlib
tok=json.load(sys.stdin)['result']
p=pathlib.Path('/etc/cloudflared-zkids'); p.mkdir(parents=True,exist_ok=True)
f=p/'token.env'; f.write_text(f'TUNNEL_TOKEN={tok}\n'); f.chmod(0o600)
"
fi

sudo cp "$ROOT/deploy/systemd/zkids-tunnel.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zkids-tunnel

echo "[✓] zkids-web and zkids-tunnel active — https://zkids.zeaz.dev"
