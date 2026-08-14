-- Migration: Add export destination columns to datasets table
-- Run this if you encounter: column datasets.s3_url does not exist

ALTER TABLE datasets
    ADD COLUMN IF NOT EXISTS s3_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS hf_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS kaggle_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS export_format VARCHAR(50);
