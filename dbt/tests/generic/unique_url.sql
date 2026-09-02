-- ============================================================
-- Test: url must be unique (Silver)
-- ============================================================
SELECT url
FROM {{ ref('silver_cleaned_articles') }}
GROUP BY url
HAVING COUNT(*) > 1
