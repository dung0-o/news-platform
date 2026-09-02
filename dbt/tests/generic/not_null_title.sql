-- ============================================================
-- Test: title must not be null (Silver)
-- ============================================================
SELECT title
FROM {{ ref('silver_cleaned_articles') }}
WHERE title IS NULL
