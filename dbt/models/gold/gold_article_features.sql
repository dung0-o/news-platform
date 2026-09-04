-- ============================================================
-- Gold Model: Article Features for ML & Dashboard
-- ============================================================
-- Purpose: Extract business features, entities, and word counts
--          from Silver data, ready for sentiment model input
--          and FastAPI dashboard queries.
-- Dependency: {{ ref('silver_cleaned_articles') }}
-- Materialization: table, incremental_strategy=insert_overwrite
-- Partition: publish_date (date)
-- Cluster: company_entity
-- ============================================================

WITH prepared AS (
  SELECT
    -- Primary key for joining with model predictions
    article_id,

    -- Title and description (used for entity extraction & word counts)
    title,
    description,

    -- URL for joining with model predictions
    url,

    -- Source name for source priority tiering
    source_name,

    -- Published date for partitioning
    published_at,

    -- Enrichment success flag (pass-through)
    enrichment_success,

    -- Model input text: prefer full_text from enrichment, fallback to description
    -- --------------------------------------------------------
    -- 1. Remove control characters (ASCII 0-31, except tab/newline)
    -- 2. Collapse multiple spaces/newlines into a single space
    -- 3. Trim leading/trailing whitespace
    -- 4. Truncate to 1500 characters (safe for BERT)
    -- --------------------------------------------------------
    LEFT(
      REGEXP_REPLACE(
        REGEXP_REPLACE(
          COALESCE(full_text, description),
          -- Remove control chars (except newline \n and tab \t)
          r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ''
        ),
        -- Collapse multiple whitespace chars into a single space
        r'\s+', ' '
      ),
      1500
    ) AS model_input_text

  FROM {{ ref('silver_cleaned_articles') }}
  WHERE description IS NOT NULL
    AND TRIM(description) != ''
)

SELECT
  article_id,

  -- ============================================================
  -- Entity Extraction: Known companies in article titles
  -- ============================================================
  CASE
    WHEN REGEXP_CONTAINS(UPPER(title), 'TESLA') THEN 'Tesla'
    WHEN REGEXP_CONTAINS(UPPER(title), 'APPLE') THEN 'Apple'
    WHEN REGEXP_CONTAINS(UPPER(title), 'MICROSOFT') THEN 'Microsoft'
    WHEN REGEXP_CONTAINS(UPPER(title), 'GOOGLE|ALPHABET') THEN 'Google'
    WHEN REGEXP_CONTAINS(UPPER(title), 'AMAZON') THEN 'Amazon'
    WHEN REGEXP_CONTAINS(UPPER(title), 'NVIDIA') THEN 'NVIDIA'
    WHEN REGEXP_CONTAINS(UPPER(title), 'META|FACEBOOK') THEN 'Meta'
    ELSE 'Other'
  END AS company_entity,

  -- ============================================================
  -- Date for partitioning
  -- ============================================================
  DATE(published_at) AS publish_date,

  -- ============================================================
  -- Feature Engineering: Word counts
  -- ============================================================
  ARRAY_LENGTH(SPLIT(title, ' ')) AS title_word_count,
  ARRAY_LENGTH(SPLIT(description, ' ')) AS description_word_count,
  ARRAY_LENGTH(SPLIT(model_input_text, ' ')) AS model_input_word_count,

  -- ============================================================
  -- Model input text (truncated, ready for BERT)
  -- ============================================================
  model_input_text,

  -- ============================================================
  -- Enrichment metadata (indicates text quality)
  -- ============================================================
  enrichment_success AS text_is_full_content,

  -- ============================================================
  -- Source tiering: quality weighting
  -- ============================================================
  CASE
    WHEN source_name IN ('Reuters', 'AP', 'Bloomberg', 'CNBC', 'FT') THEN 1   -- Tier 1: premium
    WHEN source_name IN ('Yahoo Finance', 'MarketWatch', 'Seeking Alpha') THEN 2 -- Tier 2: mid-tier
    ELSE 3                                                                    -- Tier 3: other
  END AS source_priority,

  -- ============================================================
  -- Placeholder columns: filled by FastAPI after prediction
  -- ============================================================
  CAST(NULL AS FLOAT64) AS sentiment_score,
  CAST(NULL AS STRING) AS sentiment_label,
  CAST(NULL AS FLOAT64) AS model_confidence,

  -- ============================================================
  -- Metadata: source, URL, title, description
  -- ============================================================
  source_name,
  url,
  title,
  description

FROM prepared
