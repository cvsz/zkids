# zkids.zeaz.dev — Cloudflare + Terraform deployment

Public URL: https://zkids.zeaz.dev

## Topology

```
browser ──Cloudflare edge──▶ zkids-tunnel (cloudflared connector, systemd)
                                 └─ ingress: zkids.zeaz.dev → http://127.0.0.1:8010
                                            (zkid web dashboard, systemd)
```

Everything cloud-side is code in this directory:

| Resource | Purpose |
|---|---|
| `cloudflare_tunnel.zkids` | dedicated `zkids-tunnel` (isolated from zeaz-platform) |
| `cloudflare_zero_trust_tunnel_cloudflared_config.zkids` | full ingress ownership: hostname → loopback origin + 404 fallback |
| `cloudflare_dns_record.zkids` | proxied CNAME `<tunnel-id>.cfargotunnel.com` |

The stack deliberately does **not** touch the shared `zeaz-platform` tunnel or any
other `*.zeaz.dev` hostname.

## Host services (systemd)

- `zkids-web.service` — runs `.venv/bin/python -m zkid.cli --root /home/cvsz/zkid web --port 8010`
  with `EnvironmentFile=/etc/zkids-web/env` (`ZKID_WEB_TOKEN=<operator secret>`).
  Mutating endpoints (`POST /api/produce`) require the `X-Auth-Token` header; if the
  token is unset the API is strictly read-only.
- `zkids-tunnel.service` — cloudflared connector using the tunnel token fetched from
  the Cloudflare API after `terraform apply`.

## Apply

```bash
cd deploy/terraform
export TF_VAR_cloudflare_api_token=$(sudo grep -oP '(?<=^CLOUDFLARE_API_TOKEN=).*' /etc/cloudflared-zaffiliate/token.env)
terraform init
terraform plan
terraform apply
```

Then install the connector token:

```bash
CF_API_TOKEN=$TF_VAR_cloudflare_api_token ./install.sh
```

`install.sh` is idempotent: it generates the operator token if missing, installs
both systemd units (`zkids-web`, `zkids-tunnel`), and fetches the connector token
from the Cloudflare API (the API returns it as a plain string in `result`).
