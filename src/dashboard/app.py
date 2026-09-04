"""Streamlit Dashboard — News Intelligence Platform.

Interactive sentiment analytics for global financial news.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from typing import Any

import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from config import settings

# ============================================================
# Color Palette
# ============================================================
PRIMARY = "#1A237E"
BACKGROUND = "#F5F7FA"
POSITIVE = "#00C853"
NEGATIVE = "#D32F2F"
NEUTRAL = "#9E9E9E"

# ============================================================
# Data Fetching Helpers
# ============================================================
API_URL = settings.api_url.rstrip("/")


@st.cache_data(ttl=3600)
def fetch_predictions(company: str, days: int) -> dict[str, Any] | None:
    """Fetch sentiment predictions for a company via the FastAPI /predict endpoint.

    Args:
        company: Company name to look up.
        days: Number of past days to analyze.

    Returns:
        Dict with keys: company, days_analyzed, average_sentiment,
        sentiment_label, trend, latest_articles, cache_hit.
        Returns None on error.
    """
    try:
        params: dict[str, Any] = {"company": company, "days": days}
        resp = requests.get(f"{API_URL}/predict", params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Failed to fetch predictions: {exc}")
        return None


@st.cache_data(ttl=21600)
def fetch_anomalies(days: int, threshold: float) -> dict[str, Any] | None:
    """Fetch anomaly alerts via the FastAPI /anomalies endpoint.

    Args:
        days: Lookback window in days.
        threshold: Sentiment change threshold.

    Returns:
        Dict with keys: lookback_days, threshold, anomalies.
        Returns None on error.
    """
    try:
        params: dict[str, Any] = {"days": days, "threshold": threshold}
        resp = requests.get(f"{API_URL}/anomalies", params=params, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        st.error(f"Failed to fetch anomalies: {exc}")
        return None


@st.cache_data(ttl=3600)
def fetch_last_updated() -> str | None:
    """Fetch the latest scrape timestamp from BigQuery.

    Returns:
        ISO-formatted timestamp string, or None on error.
    """
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=settings.gcp_project_id)
        table_id = f"{settings.gcp_project_id}.{settings.bq_dataset_name}.gold_article_features"

        query = f"""
        SELECT MAX(CAST(publish_date AS STRING)) AS latest
        FROM `{table_id}`
        WHERE sentiment_score IS NOT NULL
        """
        results = list(client.query(query).result())
        if results and results[0].latest:
            return results[0].latest
        return None
    except Exception as exc:
        st.error(f"Failed to fetch last updated: {exc}")
        return None


# ============================================================
# UI Sections
# ============================================================


def render_header() -> None:
    """Render the header section with title, tagline, and last updated."""
    st.markdown(
        f"""
        <style>
        .header-title {{ font-size: 28px; font-weight: 700; color: {PRIMARY}; }}
        .header-tagline {{ font-size: 14px; color: #666; margin-top: 4px; }}
        .header-meta {{ font-size: 12px; color: #999; margin-top: 8px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="header-title">📈 News Intelligence Dashboard</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="header-tagline">Real-time sentiment analytics for global financial news</div>',
        unsafe_allow_html=True,
    )

    last_updated = fetch_last_updated()
    if last_updated:
        st.markdown(
            f'<div class="header-meta">Last updated: {last_updated}</div>',
            unsafe_allow_html=True,
        )


def render_sidebar() -> tuple[str, int, int]:
    """Render the sidebar with input controls.

    Returns:
        Tuple of (company, days, lookback_days).
    """
    with st.sidebar:
        st.header("🔍 Search")

        company = st.text_input(
            "Company Name",
            value="Tesla",
            key="company_input",
        )

        days = st.slider("Days", 7, 90, settings.default_days, key="days_slider")

        st.divider()

        lookback_days = st.slider(
            "Lookback (days)",
            1,
            7,
            settings.default_lookback_days,
            key="lookback_days_slider",
        )
        threshold = st.slider(
            "Anomaly Threshold",
            0.1,
            5.0,
            settings.default_threshold,
            step=0.1,
            key="threshold_slider",
        )

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Refresh", use_container_width=True, key="refresh_btn"):
                st.rerun()
        with col2:
            if st.button("Export CSV", use_container_width=True, key="export_btn"):
                st.download_button(
                    label="Download Data",
                    data=_generate_csv_data(company, days),
                    file_name=f"{company}_sentiment_{dt.date.today().isoformat()}.csv",
                    mime="text/csv",
                )

        return company, days, lookback_days


def _generate_csv_data(company: str, days: int) -> str:
    """Generate CSV content for export.

    Args:
        company: Company name.
        days: Number of days.

    Returns:
        CSV-formatted string.
    """
    data = fetch_predictions(company, days)
    if not data:
        return "No data available.\n"

    lines: list[str] = []
    lines.append(
        f"company,average_sentiment,sentiment_label,days_analyzed,cache_hit"
    )

    if data.get("trend"):
        for entry in data["trend"]:
            lines.append(
                f"{company},"
                f"{entry.get('avg_sentiment', 'N/A')}"
                f',{entry.get("article_count", 0)}'
            )

    if data.get("latest_articles"):
        lines.append(
            f"{company},title,source,publish_date,sentiment,url"
        )
        for article in data["latest_articles"]:
            lines.append(
                f"{company},"
                f'{article.get("title", "")},'
                f'{article.get("source", "")},'
                f'{article.get("publish_date", "")},'
                f'{article.get("sentiment", "N/A")},'
                f'{article.get("url", "")}'
            )

    return "\n".join(lines) + "\n"


def render_kpi_tiles(
    data: dict[str, Any] | None,
    anomalies: dict[str, Any] | None,
) -> None:
    """Render the KPI tiles row."""
    col1, col2, col3 = st.columns(3)

    # Tile 1: Average Sentiment
    with col1:
        st.markdown(
            '<div style="font-size: 13px; color: #666; margin-bottom: 4px;">'
            "Average Sentiment",
            unsafe_allow_html=True,
        )
        if data and data.get("average_sentiment") is not None:
            score = data["average_sentiment"]
            color = POSITIVE if score >= 0 else NEGATIVE
            direction = "↑" if score >= 0 else "↓"
            st.markdown(
                f'<div style="font-size: 36px; font-weight: 700; color: {color};">'
                f"{direction} {score:.2f}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size: 32px; font-weight: 700; color: #999;">'
                "N/A</div>",
                unsafe_allow_html=True,
            )

    # Tile 2: Total Articles
    with col2:
        st.markdown(
            '<div style="font-size: 13px; color: #666; margin-bottom: 4px;">'
            "Total Articles Analyzed",
            unsafe_allow_html=True,
        )
        if data and data.get("trend"):
            total = sum(entry.get("article_count", 0) for entry in data["trend"])
            st.markdown(
                f'<div style="font-size: 36px; font-weight: 700; color: {PRIMARY};">'
                f"{total:,}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size: 32px; font-weight: 700; color: #999;">'
                "N/A</div>",
                unsafe_allow_html=True,
            )

    # Tile 3: Breaking Alerts
    with col3:
        st.markdown(
            '<div style="font-size: 13px; color: #666; margin-bottom: 4px;">'
            "Breaking Alerts (Anomalies)",
            unsafe_allow_html=True,
        )
        if anomalies and anomalies.get("anomalies"):
            count = len(anomalies["anomalies"])
            st.markdown(
                f'<div style="font-size: 36px; font-weight: 700; color: {NEGATIVE};">'
                f"{count}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-size: 32px; font-weight: 700; color: #999;">'
                "0</div>",
                unsafe_allow_html=True,
            )


def render_time_series_chart(data: dict[str, Any] | None) -> None:
    """Render the time-series sentiment chart with dual-axis."""
    st.subheader("📉 Sentiment Trend")

    if not data or not data.get("trend"):
        st.info("No trend data available for this company.")
        return

    trend = data["trend"]
    if not trend:
        st.info("No trend data available.")
        return

    # Plotly figure with line + shaded CI + bar chart
    fig = go.Figure()

    # Line chart — average sentiment
    dates = [entry["date"] for entry in trend]
    sentiments = [entry.get("avg_sentiment", 0) for entry in trend]
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=sentiments,
            mode="lines",
            name="Avg Sentiment",
            line=dict(color=PRIMARY, width=2),
            hovertemplate=(
                r"Date: %{x}<br>"
                r"Articles: %{extra.data[0].marker.size}<extra></extra>"
            ),
        )
    )

    # Horizontal reference line at 0 (neutral)
    fig.add_hline(y=0, line_dash="dash", line_color="#CCCCCC", opacity=0.5)

    # Shaded area around the line (±0.1)
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[s - 0.1 for s in sentiments]
            + [s + 0.1 for s in reversed(sentiments)],
            fill="toself",
            fillcolor="rgba(26, 35, 126, 0.1)",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Bar chart — article volume (secondary axis)
    fig.add_trace(
        go.Bar(
            x=dates,
            y=[entry.get("article_count", 0) for entry in trend],
            name="Articles",
            marker_color="#1A237E",
            marker_line_color="rgba(26, 35, 126, 0.5)",
            hovertemplate=(
                r"Date: %{x}<br>"
                r"Articles: %{y}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Sentiment Trend & Article Volume",
        xaxis_title="Date",
        yaxis_title="Avg Sentiment Score",
        yaxis_range=[-1, 1],
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        height=450,
        hovermode="x unified",
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_entity_bar_chart(data: dict[str, Any] | None) -> None:
    """Render the entity word cloud as a horizontal bar chart."""
    st.subheader("🏷️ Co-occurring Entities")

    if not data or not data.get("latest_articles"):
        st.info("No article data available.")
        return

    # Build entity frequency from latest articles
    entities: dict[str, int] = {}
    for article in data["latest_articles"]:
        title = article.get("title", "")
        source = article.get("source", "")
        combined = f"{title} {source}"
        for word in combined.split():
            word = word.strip(".,!?;:")
            if len(word) >= 3:  # Filter out short words
                entities[word.lower()] = entities.get(word.lower(), 0) + 1

    # Sort by frequency and take top 10
    top_entities = sorted(entities.items(), key=lambda x: x[1], reverse=True)[:10]

    if not top_entities:
        st.info("No entities found.")
        return

    fig = px.bar(
        top_entities,
        x=[e[0] for e in top_entities],
        y=[e[1] for e in top_entities],
        orientation="h",
        title=f"Top Entities for {data['company']}",
        labels={"x": "Entity", "y": "Frequency"},
        color=[POSITIVE if v > 0 else NEGATIVE for k, v in top_entities[::1]],
        color_discrete_sequence=[PRIMARY] * len(top_entities),
        height=300,
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        template="plotly_white",
    )

    st.plotly_chart(fig, use_container_width=True)


def render_latest_news(data: dict[str, Any] | None) -> None:
    """Render the latest news feed."""
    st.subheader("📰 Latest News")

    if not data or not data.get("latest_articles"):
        st.info("No latest articles available.")
        return

    articles = data["latest_articles"]
    for article in articles:
        sentiment = article.get("sentiment")
        color = POSITIVE if sentiment and sentiment >= 0.5 else NEGATIVE if sentiment and sentiment < 0 else NEUTRAL

        sentiment_label = "Positive" if sentiment and sentiment >= 0.5 else (
            "Negative" if sentiment and sentiment < 0 else "Neutral"
        )

        st.markdown(
            f"""
            - **{article.get('title', 'N/A')}**
              _{article.get('source', 'Unknown')} · {article.get('publish_date', 'N/A')}_
              🟢 {sentiment_label} ({sentiment:.2f} if sentiment else "")
            """,
            unsafe_allow_html=True,
        )

        url = article.get("url", "")
        if url:
            st.markdown(
                f'    [Read Article]({url})',
                unsafe_allow_html=True,
            )


def render_raw_data_table(data: dict[str, Any] | None) -> None:
    """Render the raw data table (toggleable)."""
    show_data = st.toggle("Show Raw Data", key="raw_data_toggle")

    if not show_data or not data:
        return

    if not data.get("trend") and not data.get("latest_articles"):
        st.info("No data to display.")
        return

    # Trend table
    if data.get("trend"):
        st.markdown("### Sentiment Trend")
        trend = data["trend"]
        table_data = []
        for entry in trend:
            table_data.append({
                "Date": entry.get("date", ""),
                "Avg Sentiment": entry.get("avg_sentiment", "N/A"),
                "Article Count": entry.get("article_count", 0),
            })
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )

    # Latest articles table
    if data.get("latest_articles"):
        st.markdown("### Latest Articles")
        articles = data["latest_articles"]
        table_data = []
        for article in articles:
            table_data.append({
                "Title": article.get("title", ""),
                "Source": article.get("source", ""),
                "Date": article.get("publish_date", ""),
                "Sentiment": article.get("sentiment", "N/A"),
                "URL": article.get("url", ""),
            })
        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# Main Application
# ============================================================


def main() -> None:
    """Run the News Intelligence Dashboard."""
    st.set_page_config(
        page_title="News Intelligence Dashboard",
        page_icon="📈",
        layout="wide",
    )

    # Apply background color
    st.markdown(
        f'<style>body {{ background-color: {BACKGROUND}; }} '
        f'footer {{ visibility: hidden; }} </style>',
        unsafe_allow_html=True,
    )

    # 1. Header
    render_header()

    # 2. Sidebar
    company, days, lookback_days = render_sidebar()

    # 3. KPI Tiles
    data = fetch_predictions(company, days)
    anomalies = fetch_anomalies(lookback_days, settings.default_threshold)
    render_kpi_tiles(data, anomalies)

    # 4. Time-Series Chart
    render_time_series_chart(data)

    # 5. Entity Bar Chart
    render_entity_bar_chart(data)

    # 6. Latest News Feed
    render_latest_news(data)

    # 7. Raw Data Table
    render_raw_data_table(data)


if __name__ == "__main__":
    main()
