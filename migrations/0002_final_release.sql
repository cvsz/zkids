CREATE TABLE IF NOT EXISTS character_versions (
  tenant_id TEXT NOT NULL,
  character_id TEXT NOT NULL,
  version TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, character_id, version)
);

CREATE TABLE IF NOT EXISTS storyboards (
  tenant_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, episode_id, revision)
);

CREATE TABLE IF NOT EXISTS qc_reviews (
  tenant_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('PASS','RETRY','MANUAL_REVIEW','FAIL')),
  notes TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analytics_events (
  tenant_id TEXT NOT NULL,
  event_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  scene_id TEXT,
  event_type TEXT NOT NULL,
  position_seconds DOUBLE PRECISION,
  value DOUBLE PRECISION,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, event_id)
);

CREATE INDEX IF NOT EXISTS analytics_episode_scene_idx
ON analytics_events (tenant_id, episode_id, scene_id, event_type);

CREATE TABLE IF NOT EXISTS episode_variants (
  tenant_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  language TEXT NOT NULL,
  experiment_id TEXT,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, episode_id, variant_id)
);

CREATE TABLE IF NOT EXISTS publications (
  tenant_id TEXT NOT NULL,
  publication_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  destination TEXT NOT NULL,
  external_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, publication_id),
  UNIQUE (tenant_id, idempotency_key)
);
