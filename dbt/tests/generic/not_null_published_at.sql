-- ============================================================
-- Test: published_at must not be null (Silver)
-- ============================================================
SELECT published_at
FROM {{ ref('silver_cleaned_articles') }}
WHERE published_at IS NULL
