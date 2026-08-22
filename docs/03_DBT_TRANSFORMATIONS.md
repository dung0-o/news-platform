# Document 4: dbt Transformation Logic (Business Rules)

## Overview
dbt (Data Build Tool) executes SQL `SELECT` statements inside BigQuery to transform raw Bronze data into Silver and Gold tables. dbt handles dependencies automatically using `{{ ref() }}`. 

## Folder Structure in Your dbt Project
```
my_dbt_project/
├── models/
│   ├── staging/
│   │   └── stg_raw_articles.sql      # Reads Bronze (external table)
│   ├── silver/
│   │   └── silver_cleaned_articles.sql  # Dedup logic
│   └── gold/
│       └── gold_article_features.sql    # Entity extraction + features
├── tests/
│   └── generic/
│       ├── not_null_article_id.sql
│       └── unique_url.sql
└── dbt_project.yml
```

## Transformation Rules (Coding Logic for the AI)

### 1. Staging Model: `stg_raw_articles.sql`
- **Purpose**: Lightly cast data types from the external table. 
- **Logic**: 
  - Cast `published_at` and `scraped_at` to `TIMESTAMP`.
  - Cast `category` to `STRING` if null, default to `'general'`.
  - Keep all fields exactly as they are from Bronze (no dedup yet).

### 2. Silver Model: `silver_cleaned_articles.sql`
- **Purpose**: Clean, deduplicate, and validate.
- **Dependency**: `{{ ref('stg_raw_articles') }}`
- **Key Rules**:
  1. **Deduplication**: Use a CTE with `ROW_NUMBER() OVER (PARTITION BY url ORDER BY scraped_at DESC) AS rn`. Filter `WHERE rn = 1`.
  2. **HTML Stripping**: Apply `REGEXP_REPLACE(description, r'<[^>]+>', '')` to remove any HTML tags accidentally scraped.
  3. **Whitespace**: `TRIM()` all string fields.
  4. **Null Handling**: Use `COALESCE(author, 'Unknown')`. If `title` is null, drop the row entirely.
  5. **Generation**: Create `article_id` using `TO_HEX(MD5(url))`.
  6. **Partition/Cluster**: dbt will defer partitioning to the BigQuery DDL (set in `dbt_project.yml`). We just output the `SELECT`.

### 3. Gold Model: `gold_article_features.sql`
- **Purpose**: Extract business features and entities for ML and dashboards.
- **Dependency**: `{{ ref('silver_cleaned_articles') }}`
- **Key Rules**:
  1. **Entity Extraction**: 
     - Write a `CASE` statement checking `UPPER(title)` against a list: `'TESLA'`, `'APPLE'`, `'MICROSOFT'`, `'GOOGLE'`, `'AMAZON'`, `'NVIDIA'`, `'META'`, `'FACEBOOK'`.
     - If none match, output `'Other'`.
     - *Note: Keep this regex-based for now. We will expand the list later if we want.*
  2. **Word Count**: 
     - `ARRAY_LENGTH(SPLIT(title, ' '))` for word count.
  3. **Model Input**: 
     - Concatenate title and description: `CONCAT(title, ' ', description) AS model_input_text`.
  4. **Source Priority**:
     - `CASE` to assign `1` for Tier 1 sources (Reuters, AP, Bloomberg), `2` for Tier 2 (Yahoo Finance, MarketWatch), `3` for everything else.
  5. **Placeholders**:
     - Add `sentiment_score`, `sentiment_label`, `model_confidence` as `NULL` columns (to be filled later by FastAPI).

## dbt Materialization Strategy
- **Staging**: `materialized='view'` (Cheap, doesn't store data).
- **Silver**: `materialized='table'` and `incremental_strategy='merge'` (Merge on `article_id` or `url`). Use `unique_key='url'`.
- **Gold**: `materialized='table'` and `incremental_strategy='insert_overwrite'` (Partitioned by `publish_date`).

## Generic Tests (Defined in `schema.yml`)
Include these tests to ensure data quality:
```yaml
models:
  - name: silver_cleaned_articles
    tests:
      - not_null:
          column_name: article_id
      - unique:
          column_name: url
      - not_null:
          column_name: title
      - not_null:
          column_name: published_at
  - name: gold_article_features
    tests:
      - accepted_values:
          column_name: company_entity
          values: ['Tesla', 'Apple', 'Microsoft', 'Google', 'Amazon', 'NVIDIA', 'Meta', 'Other']
      - not_null:
          column_name: model_input_text
```

## Incremental Logic (BigQuery Specific)
In the Silver and Gold models, use:
```sql
-- dbt will automatically add this to the WHERE clause for incremental runs
WHERE scraped_at > (SELECT MAX(scraped_at) FROM {{ this }})
```
This ensures you only process new articles each hour, saving your BigQuery free tier quota.