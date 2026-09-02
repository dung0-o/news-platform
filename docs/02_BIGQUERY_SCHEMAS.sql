-- ============================================================
-- Document 3: BigQuery Schema Definitions (DDL)
-- ============================================================
-- Purpose: Defines the exact table structures for the Silver and Gold layers.
-- Execution Order: 
--   1. Bronze (External Table pointing to GCS)
--   2. Silver (Cleaned, Deduplicated)
--   3. Gold (Feature Engineered, Aggregated)

-- ------------------------------------------------------------
-- 1. BRONZE LAYER (External Table)
-- ------------------------------------------------------------
-- This points directly to the JSONL files in GCS. No data is stored in BigQuery.
-- Partitioning is handled by the GCS folder structure (ingest_date).

CREATE OR REPLACE EXTERNAL TABLE `my_project.bronze.raw_articles`
WITH PARTITION COLUMNS (
  ingest_date DATE
)
OPTIONS (
  format = 'NEWLINE_DELIMITED_JSON',
  uris = ['gs://my-news-lake/*'],
  hive_partition_uri_prefix = 'gs://my-news-lake/'
);


-- ------------------------------------------------------------
-- 2. SILVER LAYER (Cleaned & Deduplicated)
-- ------------------------------------------------------------
-- Partitioned by ingest_date (derived from scraped_at).
-- Clustered by source_name and category for faster filters.

CREATE OR REPLACE TABLE `my_project.silver.cleaned_articles`
PARTITION BY DATE(scraped_at)
CLUSTER BY source_name, category
OPTIONS (
  description = 'Cleaned, deduplicated news articles ready for feature engineering',
  partition_expiration_days = 90  -- Auto-delete older data to stay within free tier
) AS
WITH base AS (
  SELECT 
    -- Generate a deterministic UUID using MD5 of the URL
    MD5(url) AS article_id,
    source_name,
    COALESCE(author, 'Unknown') AS author,
    TRIM(title) AS title,
    TRIM(REGEXP_REPLACE(description, r'<[^>]+>', '')) AS description,
    TRIM(full_text) AS full_text,
    enrichment_attempted,
    enrichment_success,
    parsing_method,
    url,
    -- Handle timezone parsing
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', published_at) AS published_at,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', scraped_at) AS scraped_at,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', enriched_at) AS enriched_at,
    COALESCE(category, 'general') AS category,
    COALESCE(language, 'en') AS language
  FROM `my_project.bronze.raw_articles`
  -- Only include records with essential fields
  WHERE title IS NOT NULL 
    AND TRIM(title) != ''
    AND url IS NOT NULL
    AND published_at IS NOT NULL
),
deduped AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY url ORDER BY scraped_at DESC) AS rn
  FROM base
)
SELECT 
  article_id,
  source_name,
  author,
  title,
  description,
  full_text,
  enrichment_attempted,
  enrichment_success,
  parsing_method,
  enriched_at,
  url,
  published_at,
  scraped_at,
  DATE(scraped_at) AS ingest_date,
  category,
  language
FROM deduped
WHERE rn = 1;  -- Keep only the latest version of each URL


-- ------------------------------------------------------------
-- 3. GOLD LAYER (Feature Engineered for ML & Dashboards)
-- ------------------------------------------------------------
-- Partitioned by publish_date (derived from published_at).
-- Clustered by company_entity (the target of user searches).

-- CTE to prepare the truncated input text once
WITH prepared AS (
  SELECT 
    article_id,
    title,
    description,
    url,
    source_name,
    published_at,
    enrichment_success,
    -- TRUNCATE HERE: 2000 characters = ~500 tokens (safe for BERT)
    LEFT(COALESCE(full_text, description), 2000) AS model_input_text,
  FROM `my_project.silver.cleaned_articles`
  WHERE description IS NOT NULL 
    AND TRIM(description) != ''
)
SELECT 
  article_id,
  -- Entity Extraction: Look for known companies in the title
  CASE 
    WHEN REGEXP_CONTAINS(UPPER(title), r'TESLA') THEN 'Tesla'
    WHEN REGEXP_CONTAINS(UPPER(title), r'APPLE') THEN 'Apple'
    WHEN REGEXP_CONTAINS(UPPER(title), r'MICROSOFT') THEN 'Microsoft'
    WHEN REGEXP_CONTAINS(UPPER(title), r'GOOGLE|ALPHABET') THEN 'Google'
    WHEN REGEXP_CONTAINS(UPPER(title), r'AMAZON') THEN 'Amazon'
    WHEN REGEXP_CONTAINS(UPPER(title), r'NVIDIA') THEN 'NVIDIA'
    WHEN REGEXP_CONTAINS(UPPER(title), r'META|FACEBOOK') THEN 'Meta'
    ELSE 'Other'
  END AS company_entity,
  
  DATE(published_at) AS publish_date,
  
  -- Feature Engineering
  ARRAY_LENGTH(SPLIT(title, ' ')) AS title_word_count,
  ARRAY_LENGTH(SPLIT(description, ' ')) AS description_word_count,
  ARRAY_LENGTH(SPLIT(model_input_text, ' ')) AS model_input_word_count,
  model_input_text,

  -- Enrichment metadata (useful for debugging and resume signaling)
  enrichment_success AS text_is_full_content,
  
  -- Source tiering (for quality weighting)
  CASE 
    WHEN source_name IN ('Reuters', 'AP', 'Bloomberg', 'CNBC', 'FT') THEN 1  -- Tier 1
    WHEN source_name IN ('Yahoo Finance', 'MarketWatch', 'Seeking Alpha') THEN 2 -- Tier 2
    ELSE 3  -- Tier 3
  END AS source_priority,

  -- Placeholder columns for model results (updated by FastAPI)
  CAST(NULL AS FLOAT64) AS sentiment_score,
  CAST(NULL AS STRING) AS sentiment_label,
  CAST(NULL AS FLOAT64) AS model_confidence,
  
  -- Metadata
  source_name,
  url,
  title,
  description

FROM prepared;