-- ============================================================
-- Test: model_input_text must not be null (Gold)
-- ============================================================
SELECT model_input_text
FROM {{ ref('gold_article_features') }}
WHERE model_input_text IS NULL
