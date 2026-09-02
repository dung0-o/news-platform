-- ============================================================
-- Test: article_id must not be null (Silver)
-- ============================================================
SELECT article_id
FROM {{ ref('silver_cleaned_articles') }}
WHERE article_id IS NULL
