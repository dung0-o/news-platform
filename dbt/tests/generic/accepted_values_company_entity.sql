-- ============================================================
-- Test: company_entity must be one of the accepted values (Gold)
-- ============================================================
SELECT company_entity
FROM {{ ref('gold_article_features') }}
WHERE company_entity NOT IN (
  'Tesla', 'Apple', 'Microsoft', 'Google', 'Amazon',
  'NVIDIA', 'Meta', 'Other'
)
