-- ============================================================
-- Staging Model: Raw Articles (Light Cast)
-- ============================================================
-- Purpose: Lightly cast data types from the Bronze external table.
-- Materialization: view
-- ============================================================

SELECT
  -- Generate a deterministic article_id using MD5 of the URL
  TO_HEX(MD5(url)) AS article_id,

  source_name,

  -- Cast category to STRING, default 'general' if null
  CAST(COALESCE(category, 'general') AS STRING) AS category,

  -- Cast timestamps to TIMESTAMP
  CAST(published_at AS TIMESTAMP) AS published_at,
  CAST(scraped_at AS TIMESTAMP) AS scraped_at,
  CAST(enriched_at AS TIMESTAMP) AS enriched_at,

  -- String fields: keep as-is (no trimming yet — that happens in Silver)
  author,
  title,
  description,
  full_text,
  enrichment_attempted,
  enrichment_success,
  parsing_method,
  url,
  language

FROM {{ source('bronze', 'raw_articles') }}
