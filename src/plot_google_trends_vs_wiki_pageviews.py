"""
Automated Google Trends vs Wikipedia Pageviews comparison.

Fetches the top N most-viewed articles from any language edition,
downloads their Google Trends data (2025, Worldwide, Web Search),
and generates comparison plots (PNG).

Usage:
    # Top 10 enwiki articles (default)
    python plot_trends_vs_wiki.py

    # Top 50 articles
    python plot_trends_vs_wiki.py --top 50

    # Top 20 from German Wikipedia
    python plot_trends_vs_wiki.py --wiki dewiki --top 20

    # Top 30 from French Wikipedia, skip main page
    python plot_trends_vs_wiki.py --wiki frwiki --top 30 --skip-main

    # Specific articles only (from enwiki by default)
    python plot_trends_vs_wiki.py --titles "ChatGPT" "Donald Trump" "Ed Gein"

    # Specific articles from German Wikipedia
    python plot_trends_vs_wiki.py --wiki dewiki --titles "ChatGPT" "Deutschland"

Supported wikis: enwiki, dewiki, frwiki, svwiki, nlwiki, ruwiki, eswiki, itwiki, arwiki, plwiki
"""

import argparse
import os
import sys
import time
import csv
import polars as pl
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("/Users/manju/Downloads/DataFest2026")
OUTPUT_DIR = DATA_DIR / "trend_plots"
GT_CACHE_DIR = DATA_DIR / "google_trends_cache"


# ───────────────────────────────────────────
# 1. Google Trends download (via SerpAPI)
# ───────────────────────────────────────────
def download_google_trends(keyword: str, api_key: str, delay: int = 2) -> pl.DataFrame | None:
    """Download Google Trends weekly RSI via SerpAPI. Returns polars DataFrame or None."""
    from serpapi import GoogleSearch

    # Check cache first
    safe = keyword.replace(" ", "_")
    cache_path = GT_CACHE_DIR / f"{safe}.csv"
    if cache_path.exists():
        print(f"  [cached] {cache_path.name}")
        gt = pl.read_csv(cache_path)
        rsi_col = gt.columns[1]
        gt = gt.with_columns(pl.col("Time").str.strptime(pl.Date, "%Y-%m-%d").alias("gt_week"))
        gt = gt.rename({rsi_col: "google_trends_rsi"}).select("gt_week", "google_trends_rsi")
        return gt

    try:
        params = {
            "engine": "google_trends",
            "q": keyword,
            "date": "2025-01-01 2025-12-31",
            "geo": "",
            "data_type": "TIMESERIES",
            "api_key": api_key,
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        if "interest_over_time" not in results or not results["interest_over_time"].get("timeline_data"):
            print(f"  [no data] SerpAPI returned empty for '{keyword}'")
            return None

        # Parse timeline data into CSV
        rows = []
        for point in results["interest_over_time"]["timeline_data"]:
            # Use the start timestamp of each period
            ts = int(point["timestamp"])
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
            value = point["values"][0]["extracted_value"]
            rows.append({"Time": date_str, "RSI": value})

        # Save to cache CSV
        with open(cache_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Time", "RSI"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"  [downloaded] {cache_path.name} ({len(rows)} weeks)")

        # Read back as polars
        gt = pl.read_csv(cache_path)
        gt = gt.with_columns(pl.col("Time").str.strptime(pl.Date, "%Y-%m-%d").alias("gt_week"))
        gt = gt.rename({"RSI": "google_trends_rsi"}).select("gt_week", "google_trends_rsi")
        time.sleep(delay)
        return gt

    except Exception as e:
        print(f"  [error] SerpAPI failed for '{keyword}': {e}")
        return None


# ───────────────────────────────────────────
# 2. Wikipedia weekly pageviews
# ───────────────────────────────────────────
def get_wiki_weekly(page_title: str, page_id: int, gt_weeks: list,
                    page_views: pl.DataFrame, wiki_db: str = "enwiki") -> pl.DataFrame | None:
    """Aggregate daily pageviews into GT week buckets, compute RSI."""
    daily = (
        page_views
        .filter((pl.col("wiki_db") == wiki_db) & (pl.col("page_id") == page_id))
        .with_columns(pl.col("day").str.strptime(pl.Date, "%Y-%m-%d"))
        .sort("day")
    )
    if len(daily) == 0:
        return None

    sorted_weeks = sorted(gt_weeks)

    def assign_week(day):
        for i in range(len(sorted_weeks) - 1, -1, -1):
            if day >= sorted_weeks[i]:
                return sorted_weeks[i]
        return None

    weekly = (
        daily
        .with_columns(
            pl.col("day").map_elements(assign_week, return_dtype=pl.Date).alias("gt_week")
        )
        .filter(pl.col("gt_week").is_not_null())
        .group_by("gt_week")
        .agg(pl.col("pageviews").sum().alias("weekly_views"))
        .sort("gt_week")
        .with_columns(
            (pl.col("weekly_views") / pl.col("weekly_views").max() * 100)
            .round(1).alias("wiki_rsi")
        )
    )
    return weekly


# ───────────────────────────────────────────
# 3. Plot
# ───────────────────────────────────────────
def make_plot(combined: pl.DataFrame, display_name: str, output_png: Path):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=combined["gt_week"].to_list(), y=combined["wiki_rsi"].to_list(),
        mode="lines+markers", name="Wikipedia Pageviews (RSI 0–100)",
        line=dict(color="#1f77b4", width=2.5), marker=dict(size=6),
    ))
    fig.add_trace(go.Scatter(
        x=combined["gt_week"].to_list(), y=combined["google_trends_rsi"].to_list(),
        mode="lines+markers", name="Google Trends (RSI 0–100)",
        line=dict(color="#ff7f0e", width=2.5), marker=dict(size=6),
    ))
    fig.update_layout(
        title=dict(
            text=f"{display_name}: Google Trends vs Wikipedia Pageviews (2025)<br>"
                 f"<sub>Both normalized to 0–100 RSI | Weekly</sub>",
            font=dict(size=18),
        ),
        xaxis_title="Week Starting",
        yaxis_title="Relative Interest (0–100)",
        yaxis=dict(range=[0, 110]),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.50, xanchor="center", x=0.5),
        hovermode="x unified",
        width=1050, height=520,
    )
    fig.write_image(str(output_png), scale=2)


# ───────────────────────────────────────────
# 4. Main pipeline
# ───────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Google Trends vs Wikipedia comparison")
    parser.add_argument("--wiki", type=str, default="enwiki",
                        help="Language edition (default: enwiki). Options: enwiki, dewiki, frwiki, svwiki, nlwiki, ruwiki, eswiki, itwiki, arwiki, plwiki")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top articles by pageviews (default: 10)")
    parser.add_argument("--titles", nargs="+",
                        help="Specific page titles (overrides --top)")
    parser.add_argument("--api-key", type=str, default=None,
                        help="SerpAPI key. Can also set SERPAPI_KEY env variable.")
    parser.add_argument("--delay", type=int, default=2,
                        help="Seconds between SerpAPI requests (default: 2).")
    parser.add_argument("--skip-main", action="store_true",
                        help="Skip main page from top list")
    args = parser.parse_args()
    wiki_db = args.wiki

    # Resolve API key
    api_key = args.api_key or os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("ERROR: SerpAPI key required. Provide via --api-key or SERPAPI_KEY env variable.")
        print("  Sign up free at: https://serpapi.com/users/sign_up")
        sys.exit(1)

    # Create output dirs
    OUTPUT_DIR.mkdir(exist_ok=True)
    GT_CACHE_DIR.mkdir(exist_ok=True)

    # Load Wikipedia data
    print(f"Loading Wikipedia data for {wiki_db}...")
    page_info = pl.read_ndjson(str(DATA_DIR / "data" / "page_info.json.gz"))
    page_views = pl.read_ndjson(str(DATA_DIR / "data" / "page_views.json.gz"))
    print("Done.\n")

    # Main page titles vary by language
    main_pages = {
        "enwiki": "Main_Page", "dewiki": "Wikipedia:Hauptseite",
        "frwiki": "Wikipédia:Accueil_principal", "eswiki": "Wikipedia:Portada",
        "itwiki": "Pagina_principale", "nlwiki": "Hoofdpagina",
        "plwiki": "Wikipedia:Strona_główna", "svwiki": "Portal:Huvudsida",
        "ruwiki": "Заглавная_страница", "arwiki": "الصفحة_الرئيسية",
    }

    # Determine articles to process
    if args.titles:
        articles = []
        for title in args.titles:
            wiki_title = title.replace(" ", "_")
            match = page_info.filter(
                (pl.col("wiki_db") == wiki_db) & (pl.col("page_title") == wiki_title)
            )
            if len(match) == 0:
                # Try partial match
                match = page_info.filter(
                    (pl.col("wiki_db") == wiki_db)
                    & (pl.col("page_title").str.contains(f"(?i){wiki_title}"))
                )
            if len(match) == 0:
                print(f"WARNING: '{wiki_title}' not found in {wiki_db}, skipping.")
                continue
            articles.append({
                "page_title": match["page_title"][0],
                "page_id": match["page_id"][0],
                "pageviews": match["pageviews"][0],
            })
    else:
        # Top N by pageviews
        wiki_pages = page_info.filter(pl.col("wiki_db") == wiki_db)
        if args.skip_main and wiki_db in main_pages:
            wiki_pages = wiki_pages.filter(pl.col("page_title") != main_pages[wiki_db])
        top = wiki_pages.sort("pageviews", descending=True).head(args.top)
        articles = top.select("page_title", "page_id", "pageviews").to_dicts()

    print(f"Processing {len(articles)} articles:\n")
    for i, a in enumerate(articles):
        print(f"  {i+1:3d}. {a['page_title']}  ({a['pageviews']:,} views)")
    print()

    # Process each article
    success = 0
    failed = 0
    for i, article in enumerate(articles):
        title = article["page_title"]
        pid = article["page_id"]
        display = title.replace("_", " ")
        gt_keyword = display.replace(",", "")  # Remove commas for Google Trends

        print(f"[{i+1}/{len(articles)}] {display}")

        # Download Google Trends
        gt = download_google_trends(gt_keyword, api_key=api_key, delay=args.delay)
        if gt is None:
            failed += 1
            continue

        # Get Wikipedia weekly
        gt_weeks = gt["gt_week"].to_list()
        wiki_weekly = get_wiki_weekly(title, pid, gt_weeks, page_views, wiki_db)
        if wiki_weekly is None or len(wiki_weekly) == 0:
            print(f"  [skip] No Wikipedia daily data for {title}")
            failed += 1
            continue

        # Join and plot
        combined = gt.join(wiki_weekly, on="gt_week", how="inner").sort("gt_week")
        if len(combined) < 5:
            print(f"  [skip] Only {len(combined)} overlapping weeks")
            failed += 1
            continue

        safe = title.lower().replace(" ", "_")
        out_png = OUTPUT_DIR / f"{safe}_trends_vs_wiki.png"
        make_plot(combined, display, out_png)
        print(f"  [done] {out_png.name}  ({len(combined)} weeks)")
        success += 1

        # Rate limit delay
        if i < len(articles) - 1:
            time.sleep(args.delay)

    print(f"\n{'='*50}")
    print(f"Finished: {success} plots saved to {OUTPUT_DIR}/")
    if failed:
        print(f"  ({failed} skipped due to errors or missing data)")


if __name__ == "__main__":
    main()
