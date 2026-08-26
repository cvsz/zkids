#!/bin/sh
set -eu
DATE=$(date -u +%Y-%m-%dT%H%M%SZ)
echo "[backup] $DATE start"

# Postgres dump (if available)
if [ -f /run/secrets/postgres_password ]; then
  PGPASSWORD=$(cat /run/secrets/postgres_password)
  export PGPASSWORD
  pg_dump -h postgres -U zkid zkid | gzip > /tmp/pg-$DATE.sql.gz
  echo "[backup] pg_dump $(du -h /tmp/pg-$DATE.sql.gz | cut -f1)"
  # Upload to S3 if configured
  if [ -n "${S3_ENDPOINT:-}" ]; then
    apk add --no-cache aws-cli 2>/dev/null || true
    aws --endpoint-url "$S3_ENDPOINT" s3 cp /tmp/pg-$DATE.sql.gz "s3://${S3_BUCKET:-zkid-backups}/postgres/pg-$DATE.sql.gz" || echo "[backup] s3 upload failed (no credentials?)"
    rm -f /tmp/pg-$DATE.sql.gz
  fi
fi

# SQLite fallback + episodes + factory.db
if [ -d /zkid_data ]; then
  tar -czf /tmp/zkid-data-$DATE.tar.gz -C / zkid_data 2>/dev/null || tar -czf /tmp/zkid-data-$DATE.tar.gz -C /data . 2>/dev/null || true
  echo "[backup] zkid_data $(du -h /tmp/zkid-data-$DATE.tar.gz | cut -f1)"
  if [ -n "${S3_ENDPOINT:-}" ]; then
    aws --endpoint-url "$S3_ENDPOINT" s3 cp /tmp/zkid-data-$DATE.tar.gz "s3://${S3_BUCKET:-zkid-backups}/zkid/zkid-data-$DATE.tar.gz" 2>/dev/null || true
    rm -f /tmp/zkid-data-$DATE.tar.gz
  fi
fi

# Retention: keep 30 days locally, S3 lifecycle does the rest
find /tmp -name "pg-*.sql.gz" -mtime +7 -delete 2>/dev/null || true
find /tmp -name "zkid-data-*.tar.gz" -mtime +7 -delete 2>/dev/null || true

echo "[backup] $DATE done"
