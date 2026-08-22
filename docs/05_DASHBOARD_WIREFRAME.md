# Document 6: Streamlit Dashboard Wireframe (UI/UX)

## Overview
A single-page, interactive web app built with **Streamlit**. It serves as the public-facing interface for the News Intelligence platform. The dashboard is deployed on **Streamlit Cloud** (free tier) and connects to the FastAPI backend + BigQuery directly for fast queries.

## Design Principles
- **Clean & Professional**: Minimalist, blue/white color scheme (professional finance look).
- **Mobile-Responsive**: Works on both desktop and tablet.
- **Intuitive**: Users can type a company name and instantly see results.

---

## Page Layout (Top to Bottom)

### 1. Header Section
- **Project Logo/Title**: "📈 News Intelligence Dashboard".
- **Tagline**: "Real-time sentiment analytics for global financial news".
- **Last Updated**: Shows the timestamp of the latest scraped data (fetched from BigQuery).

---

### 2. Input Controls (Sidebar)
- **Company Search**: Text input box with autocomplete (dropdown) showing the top 50 companies from the Gold table.
- **Date Range Selector**: Two date pickers (Start Date, End Date). Default: Last 30 days.
- **Refresh Button**: Manually triggers a fresh query (bypasses cache).
- **Export Button**: Downloads the current chart data as a CSV file.

---

### 3. KPI Tiles (Top Row)
Three large metric cards displayed horizontally:

| Tile | Metric | Source |
| :--- | :--- | :--- |
| **Tile 1** | Average Sentiment (Last N days) | BigQuery `AVG(sentiment_score)` |
| **Tile 2** | Total Articles Analyzed | BigQuery `COUNT(*)` |
| **Tile 3** | Breaking Alerts (Anomalies) | FastAPI `/anomalies` endpoint |

Each tile displays a big number, a small trend arrow (up/down vs. previous period), and a sparkline (mini chart).

---

### 4. Time-Series Sentiment Chart (Main Visual)
- **Chart Type**: Line chart with shaded confidence interval.
- **X-Axis**: Date (publish_date).
- **Y-Axis**: Average Sentiment Score (-1 to +1).
- **Interactivity**: Hover over any point to see exact date, score, and article count.
- **Overlay**: A horizontal line at `0` (neutral) for reference.
- **Below the chart**: A small bar chart showing article volume per day (dual-axis).

---

### 5. Entity Word Cloud / Bar Chart
- **Purpose**: Show which entities are mentioned most frequently alongside the searched company.
- **Visual**: If the search is "Tesla", show top 10 co-occurring entities (e.g., "Elon Musk", "BYD", "EV", "China").
- **Chart Type**: Horizontal bar chart (easier to read) with counts.

---

### 6. Latest News Feed (Bottom Section)
- **Purpose**: Show the actual headlines that drove the sentiment trends.
- **Display**: A scrollable list of the 5 most recent articles (title, source, published time, sentiment score).
- **Sentiment Color**: Green (positive), Red (negative), Gray (neutral) bullet indicator.
- **Clickable**: Each headline links to the original article URL (opens in new tab).

---

### 7. Data Table (Optional Toggle)
- **Toggle Button**: "Show Raw Data" expands a table with all columns (article_id, title, description, source, date, sentiment).
- **Purpose**: For users who want to verify the underlying data.

---

## Technical Implementation (For the AI)

**Streamlit Layout Code Structure**:

```python
# 1. Sidebar Controls
company = st.sidebar.text_input("Company Name", "Tesla")
days = st.sidebar.slider("Days", 7, 90, 30)
refresh = st.sidebar.button("Refresh Data")

# 2. Call FastAPI
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_predictions(company, days):
    response = requests.get(f"{API_URL}/predict", params={"company": company, "days": days})
    return response.json()

# 3. Display KPIs
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Avg Sentiment", f"{data['average_sentiment']:.2f}")
# ... similar for col2, col3

# 4. Time-Series Chart
fig = px.line(data['trend'], x='date', y='avg_sentiment', ...)
st.plotly_chart(fig, use_container_width=True)

# 5. Entity Bar Chart
# Use data from FastAPI or compute from BigQuery directly
fig2 = px.bar(top_entities, x='entity', y='count')
st.plotly_chart(fig2)

# 6. News Feed
for article in data['latest_articles']:
    st.markdown(f"**{article['title']}** - {article['source']}")
```

---

## Data Fetching Strategy (Performance Optimization)

| Component | Data Source | Caching Strategy |
| :--- | :--- | :--- |
| **KPI Tiles** | FastAPI `/predict` | Part of the main response, cached in Upstash. |
| **Time-Series Chart** | FastAPI `/predict` (trend array) | Upstash cache (6 hours). |
| **Entity Bar Chart** | Direct BigQuery query (FastAPI not needed) | Query BigQuery directly with `@st.cache_data` in Streamlit. |
| **News Feed** | FastAPI `/predict` (latest_articles) | Upstash cache (6 hours). |
| **Anomaly Alerts** | FastAPI `/anomalies` | Upstash cache (1 hour). |

---

## Color Palette & Typography

| Element | Color | Hex |
| :--- | :--- | :--- |
| Positive Sentiment | Green | `#00C853` |
| Neutral Sentiment | Gray | `#9E9E9E` |
| Negative Sentiment | Red | `#D32F2F` |
| Primary Accent | Dark Blue | `#1A237E` |
| Background | Light Gray | `#F5F7FA` |
| Font | Inter (or system sans-serif) | N/A |