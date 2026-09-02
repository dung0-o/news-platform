-- ============================================================
-- Silver Model: Cleaned & Deduplicated Articles
-- ============================================================
-- Purpose: Clean, deduplicate, and validate Bronze data into a
--          reliable Silver table ready for feature engineering.
-- Dependency: {{ ref('stg_raw_articles') }}
-- Materialization: table, incremental_strategy=merge, unique_key=url
-- ============================================================

WITH base AS (
  SELECT
    -- Generate a deterministic article_id using MD5 of the URL
    TO_HEX(MD5(url)) AS article_id,

    -- Source metadata
    source_name,

    -- Author: COALESCE to 'Unknown' if missing
    COALESCE(author, 'Unknown') AS author,

    -- Title: must not be null or blank (drop rows that fail)
    TRIM(title) AS title,

    -- Description: strip HTML tags and trim whitespace
    TRIM(REGEXP_REPLACE(description, '<[^>]+>', '')) AS description,

    -- Full text content (from enrichment)
    TRIM(full_text) AS full_text,

    -- Enrichment metadata
    enrichment_attempted,
    enrichment_success,
    parsing_method,

    -- URL (must not be null)
    url,

    -- Timestamps: handle timezone parsing safely
    PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', published_at) AS published_at,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', scraped_at) AS scraped_at,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%dT%H:%M:%E*SZ', enriched_at) AS enriched_at,

    -- Category: COALESCE to 'general' if missing
    COALESCE(category, 'general') AS category,

    -- Language: COALESCE to 'en' if missing
    COALESCE(language, 'en') AS language

  FROM {{ ref('stg_raw_articles') }}
  WHERE title IS NOT NULL
    AND TRIM(title) != ''
    AND url IS NOT NULL
),

deduped AS (
  SELECT *,
    -- Row number per URL, ordered by most recent scrape first
    ROW_NUMBER() OVER (
      PARTITION BY url
      ORDER BY scraped_at DESC
    ) AS rn
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
