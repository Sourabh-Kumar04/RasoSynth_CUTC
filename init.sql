-- Initialize database schema
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config JSONB,
    progress FLOAT DEFAULT 0.0,
    current_stage VARCHAR(100),
    samples_processed INTEGER DEFAULT 0,
    samples_generated INTEGER DEFAULT 0,
    cost_usd FLOAT DEFAULT 0.0,
    error TEXT
);

-- Datasets table
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50),
    size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    output_path VARCHAR(500)
);

-- Samples table
CREATE TABLE IF NOT EXISTS samples (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    instruction TEXT,
    response TEXT,
    input TEXT,
    metadata JSONB,
    quality_score FLOAT,
    difficulty_tier INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT,
    source_type VARCHAR(50),
    title VARCHAR(500),
    metadata JSONB,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Quality scores table
CREATE TABLE IF NOT EXISTS quality_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sample_id UUID REFERENCES samples(id) ON DELETE CASCADE,
    relevance FLOAT,
    toxicity FLOAT,
    hallucination FLOAT,
    overall FLOAT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_samples_dataset_id ON samples(dataset_id);
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
CREATE INDEX IF NOT EXISTS idx_sources_discovered_at ON sources(discovered_at);

-- =============================================================================
-- CHECKPOINT & ORCHESTRATION TABLES
-- =============================================================================

-- Orchestration checkpoints for resumable workflows
CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    progress FLOAT NOT NULL,
    sources_discovered INTEGER DEFAULT 0,
    sources_extracted INTEGER DEFAULT 0,
    samples_filtered INTEGER DEFAULT 0,
    samples_generated INTEGER DEFAULT 0,
    provider_context JSONB,
    fallback_provider VARCHAR(100),
    extracted_content JSONB DEFAULT '[]',
    filtered_samples JSONB DEFAULT '[]',
    constructed_samples JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_job_id ON orchestration_checkpoints(job_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at ON orchestration_checkpoints(created_at DESC);

-- Provider migration history
CREATE TABLE IF NOT EXISTS provider_migrations (
    migration_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) NOT NULL,
    from_provider VARCHAR(100),
    to_provider VARCHAR(100),
    failure_type VARCHAR(50),
    checkpoint_id UUID,
    success BOOLEAN DEFAULT TRUE,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_provider_migrations_job_id ON provider_migrations(job_id);
CREATE INDEX IF NOT EXISTS idx_provider_migrations_created_at ON provider_migrations(created_at DESC);

-- Partial datasets preservation
CREATE TABLE IF NOT EXISTS partial_datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) NOT NULL,
    checkpoint_id UUID,
    samples JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_partial_datasets_job_id ON partial_datasets(job_id);

-- Provider failover events tracking
CREATE TABLE IF NOT EXISTS failover_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    failure_type VARCHAR(50) NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    latency_ms FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_failover_events_job_id ON failover_events(job_id);
CREATE INDEX IF NOT EXISTS idx_failover_events_provider ON failover_events(provider);
CREATE INDEX IF NOT EXISTS idx_failover_events_created_at ON failover_events(created_at DESC);