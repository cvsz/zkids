# Runbook — Factory OS

## Incident: API 5xx spike

1. Check `GET /health` / `GET /ready` — `ffmpeg`/`db`/`disk_free_gb`
2. `curl http://127.0.0.1:8010/metrics` — `zkid_requests_5xx`, `zkid_latency_p95`
3. `journalctl -u zkids-web -n 100` / `docker logs api --tail 100`
4. If DB: `pg_isready` / `sqlite3 factory.db "PRAGMA integrity_check;"`
5. Rollback: `git revert` + `docker compose up -d` or `systemctl restart zkids-web`

## Incident: Queue stuck (MANUAL_REVIEW growing)

- `GET /api/detail?ep=EP001` → `jobs[].state` + `error` + `attempts/max_retries`
- Check `budget` `max_cost_usd_per_episode` — `PUT /api/config` to raise
- `POST /api/gates/approve` with `X-Auth-Token` to unblock, or `DELETE /api/characters/bad-id`
- Logs: `logs/produce-*.log` tail via `GET /api/tasks/<id>`

## Incident: Disk full

- `GET /api/system/info` `episodes_disk` / `disk_free_gb`
- Prune: `docker system prune` + `find episodes -name "*.mp4" -mtime +30 -delete` (keep provenance)
- S3 lifecycle already moves backups to R2 after 30d

## Deploy

- `terraform -chdir=deploy/terraform apply` (tunnel + DNS)
- `docker compose -f compose.production.yml up -d --build` (api/worker/postgres/redis/minio/caddy/prometheus/grafana)
- `systemctl daemon-reload && systemctl restart zkids-web zkids-tunnel` (bare metal)

## Backup restore

```bash
gunzip -c /tmp/pg-2026-08-26T00:00:00Z.sql.gz | psql $DATABASE_URL
tar -xzf /tmp/zkid-data-2026-08-26T00:00:00Z.tar.gz -C /
systemctl restart zkids-web
```

## Secrets rotation

- `openssl rand -hex 32 > secrets/web_token.txt && chmod 600` + `systemctl restart zkids-web` (also update `CLOUDFLARE_TUNNEL_TOKEN` via `deploy/terraform` `random_password` rotation)
- Never commit `secrets/*` or `.env` — `.gitignore` enforced, `0600`
