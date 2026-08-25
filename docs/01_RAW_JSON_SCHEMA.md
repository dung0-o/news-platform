# Raw JSON Schema (Bronze Layer)

## Scraped Data Source
NewsAPI and Google News RSS feeds. Article enrichment using `requests` and `BeautifulSoup` fetches the full HTML body text from the article URLs.

## Output Format
All scraped data must be saved in **JSONL (JSON Lines)** format: one valid JSON object per line, **not** a single JSON array.

## Folder Structure (Partitioning)
The scraper must save files to a folder structure partitioned by `ingest_date`:
```
raw_data/ingest_date=2026-08-21/batch_14-00.jsonl
raw_data/ingest_date=2026-08-21/batch_15-00.jsonl
```
This matches the standard Hive-style partitioning expected by BigQuery external tables.

## Exact JSON Object Attributes
Every scraped record must contain the following fields:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `source_id` | String | Yes | e.g., "reuters", "bbc-news" (from API) |
| `source_name` | String | Yes | Full source name, e.g., "Reuters" |
| `author` | String | No | Author name (if available), default "" |
| `title` | String | **Yes** | Article headline. Main input for sentiment model. |
| `description` | String | **Yes** | Article summary/metadata. Concatenated with `title` for model. |
| `url` | String | **Yes** | Unique identifier for deduplication. |
| `url_to_image` | String | No | Thumbnail URL (optional), default "" |
| `published_at` | String (ISO 8601) | **Yes** | Publication timestamp, e.g., "2026-08-21T14:30:00Z" |
| `full_text` | String | No | Full article body extracted by BeautifulSoup. Default `""`. |
| `enrichment_attempted` | Boolean | No | Was enrichment attempted for this URL? Default `false`. |
| `enrichment_success` | Boolean | No | Did extraction yield > 100 characters? Default `false`. |
| `parsing_method` | String | No | Parser strategy used (`'reuters'`, `'bbc'`, `'generic'`). Default `""`. |
| `enriched_at` | String (ISO 8601) | No | When enrichment occurred. Default `""`. |
| `category` | String | No | e.g., "business", "technology". Default "general" |
| `language` | String | No | ISO code, e.g., "en". Default "en" |
| `scraped_at` | String (ISO 8601) | **Yes** | Timestamp when scraper ran. MUST be added by scraper. |

## Sample JSON Record
```json
{
  "source_id": "reuters",
  "source_name": "Reuters",
  "author": "Jane Smith",
  "title": "Tesla shares surge on record EV deliveries in Q3",
  "description": "Tesla Inc reported a record number of electric vehicle deliveries, beating analyst expectations...",
  "url": "https://reuters.com/business/tesla-surge-2026-08-21",
  "url_to_image": "",
  "published_at": "2026-08-21T14:30:00Z",
  "full_text": "Tesla Inc reported a record 500,000 electric vehicle deliveries in the third quarter, surpassing analyst expectations...",
  "enrichment_attempted": true,
  "enrichment_success": true,
  "parsing_method": "reuters",
  "enriched_at": "2026-08-21T15:05:00Z",
  "category": "business",
  "language": "en",
  "scraped_at": "2026-08-21T15:00:00Z"
}
```

## Validation Rules (Scraper Must Enforce)
- The scraper must **not** output empty `title` or `description` fields.
- The scraper must use the local system timezone to generate `scraped_at` and `enriched_at` as UTC.
- The scraper must write the file using UTF-8 encoding.
- If `enrichment_attempted = true`, `enriched_at` must be populated.
- If `enrichment_success = true`, `full_text` must contain > 100 characters.