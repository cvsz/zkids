# Self-Hosting Enterprise Guide

This is the production self-hosting manual for `zkids.zeaz.dev` — same stack that runs on `core.zeaz.dev`.

## Architecture (self-hosted)

```
Internet → Cloudflare (WAF, Zero Trust) → cloudflared Tunnel (zkids-tunnel) → Caddy :443 → api:8010 (zkid Python) → Postgres 16 + Redis 7 + MinIO (S3)
                                                      ↘ worker → Postgres/Redis/MinIO
                                                      ↘ Prometheus → Grafana
```

All services run as non-root, read-only FS, `no-new-privileges`, `cap_drop: ALL`, resource limits, healthchecks.

## One-command deploy

```bash
# 1. Prepare secrets (0600, never commit)
mkdir -p secrets
openssl rand -hex 32 > secrets/web_token.txt
openssl rand -hex 32 > secrets/postgres_password.txt
openssl rand -hex 16 > secrets/s3_access.txt
openssl rand -hex 32 > secrets/s3_secret.txt
openssl rand -hex 12 > secrets/grafana_admin.txt
openssl rand -hex 32 > secrets/redis_password.txt
chmod 600 secrets/*

# 2. All free model keys — already copied from zworkforce/.env.ai → zkid/.env (143 keys, 0600)
# free_env.py auto-loads both; no manual step needed. Verify:
curl http://127.0.0.1:8010/api/free/catalog | jq '.llm | map(.provider)'

# 3. Launch
docker compose -f compose.production.yml up -d --build
# or systemd on bare metal:
sudo cp deploy/systemd/zkids-web.service /etc/systemd/system/ && sudo systemctl enable --now zkids-web
sudo cp deploy/systemd/zkids-tunnel.service /etc/systemd/system/ && sudo systemctl enable --now zkids-tunnel
```

## Configuration (realtime, no restart)

`PUT /api/config` with `X-Auth-Token` updates `config/factory.yaml` and reloads `FactoryConfig` in-process. UI `Settings` tab does this live. `providers` values are allow-listed in `src/zkid/web/server.py:config_put` (`offline/ollama/openrouter_free/nvidia_free/opencode_free/kilocode_free/meta_free/pollinations/hf_image/procedural_cartoon/edge_tts/kenburns/veo`).

Env overrides win: `ZKID_LLM_PROVIDER` etc. from systemd `EnvironmentFile` or `zworkforce/.env.ai`.

## Backups

- Postgres `pg_dump` gzipped hourly via `backup` service → `s3://zkid-backups/postgres/` (MinIO or R2)
- `zkid_data` (episodes, factory.db, logs) tar.gz daily → same bucket
- Retention: 30d S3 lifecycle, 7d local `/tmp`
- Restore: `gunzip < pg-*.sql.gz | psql $DATABASE_URL` + `tar -xzf zkid-data-*.tar.gz -C /`

## Updates & Patching

- `watchtower` label optional, or manual `docker compose pull && up -d`
- `dependabot.yml` + `npm audit` / `pip-audit` in CI — `SECURITY.md` policy
- `Caddy` auto-TLS via Cloudflare, `cloudflared` auto-updates disabled (`--no-autoupdate` pinned)

## Monitoring

- `GET /health` / `GET /ready` / `GET /metrics` (Prometheus) — Caddy, api, postgres, redis all have `healthcheck`
- Prometheus scrapes `api:8010/metrics` every 10s → Grafana datasource `prometheus:9090`
- Logs JSON to `json-file` `max-size 10m` `max-file 3` → Loki if desired
- Alert on `disk_free_gb < 5`, `ffmpeg != ok`, `5xx > 1%`

## Hardening checklist

- [ ] `secrets/*` `0600`, never in git (`.gitignore` has `.env`)
- [ ] `read_only: true` + `tmpfs: [/tmp]` + `no-new-privileges` on all services
- [ ] `SECURITY_HEADERS` `CSP` `HSTS` `X-Frame-Options DENY` from `src/zkid/security.py`
- [ ] `RateLimiter` 10 rps burst 30 per IP+path, `429` with `X-RateLimit-*`
- [ ] `audit_log` table on every `POST /api/produce` `POST /api/gates/*` `PUT /api/config`
- [ ] `validate_episode_id` `validate_topic` `sanitize_note` on all inputs
- [ ] `tenant` column on `episodes/assets/generation_jobs` (add `?tenant=` filter, default `default`)
- [ ] `X-Request-Id` on every response, logged via `zkid.web`
