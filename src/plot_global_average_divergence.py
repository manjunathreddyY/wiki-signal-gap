import polars as pl
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime
import os
import glob

# Find all language files that have trends data
files = glob.glob('Combined_view/*wiki_comb_normalized_with_trends.csv')

# Create a list to hold all dataframes
dfs = []
for file_path in files:
    df = pl.read_csv(file_path)
    
    # Cast RSI and normalized_views to numeric
    df = df.with_columns([
        pl.col("RSI").cast(pl.Float64, strict=False),
        pl.col("normalized_views").cast(pl.Float64, strict=False),
    ])
    df = df.filter(pl.col("RSI").is_not_null() & pl.col("normalized_views").is_not_null())
    dfs.append(df)

# Combine all languages into one massive DataFrame
combined_df = pl.concat(dfs)

# Convert Time to Date
combined_df = combined_df.with_columns(
    pl.col("Time").str.strptime(pl.Date)
)

print(f"Aggregating {len(combined_df)} total article-weeks across all languages...")

# Average normalized_views and RSI across ALL articles and ALL languages per week
weekly = combined_df.group_by("Time").agg([
    pl.col("normalized_views").mean().alias("avg_normalized_views"),
    pl.col("RSI").mean().alias("avg_rsi"),
    # Calculate Residual / Divergence (RSI - Wiki)
    (pl.col("RSI") - pl.col("normalized_views")).mean().alias("mean_divergence"),
    pl.len().alias("article_count")
]).sort("Time")

pdf = weekly.to_pandas()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                gridspec_kw={'height_ratios': [3, 1]})

# Identify the cutoff point (e.g. November 1, 2025)
cutoff_date = datetime.date(2025, 11, 1)

# Split the data into two parts
pdf_main = pdf[pdf['Time'] <= pd.Timestamp(cutoff_date)]
pdf_tail = pdf[pdf['Time'] >= pd.Timestamp(cutoff_date)]

# ── Top panel: both curves ──
ax1.plot(pdf_main['Time'], pdf_main['avg_normalized_views'], label='Global Wikipedia Normalized Views (All Langs)', linewidth=2.5, color='#1f77b4')
ax1.plot(pdf_main['Time'], pdf_main['avg_rsi'], label='Global Google Trends RSI (All Langs)', linewidth=2.5, color='#d62728', linestyle='--')

ax1.plot(pdf_tail['Time'], pdf_tail['avg_normalized_views'], linewidth=2.5, color='#1f77b4', linestyle=':', alpha=0.4)
ax1.plot(pdf_tail['Time'], pdf_tail['avg_rsi'], linewidth=2.5, color='#d62728', linestyle=':', alpha=0.4)

ax1.fill_between(pdf['Time'], pdf['avg_normalized_views'], pdf['avg_rsi'],
                 where=(pdf['avg_rsi'] > pdf['avg_normalized_views']),
                 interpolate=True, color='red', alpha=0.12, label='Google > Wiki')
ax1.fill_between(pdf['Time'], pdf['avg_normalized_views'], pdf['avg_rsi'],
                 where=(pdf['avg_rsi'] <= pdf['avg_normalized_views']),
                 interpolate=True, color='blue', alpha=0.12, label='Wiki > Google')

ax1.axvline(x=datetime.date(2025, 5, 14), color='grey', linestyle=':', linewidth=1.5, label='AI Overviews Rollout (approx)')
ax1.set_ylabel('Index (0-100 scale)', fontsize=12)
ax1.set_title('Global Average Divergence (All 10 Languages): Wikipedia Views vs Google Trends', fontsize=16, pad=15)
ax1.legend(loc='lower left', fontsize=10)
ax1.grid(True, alpha=0.3)

# ── Bottom panel: difference LINE ──
ax2.plot(pdf_main['Time'], pdf_main['mean_divergence'], color='#7b2d8e', linewidth=2.5, label='Global Mean Divergence (Google − Wiki)')
ax2.plot(pdf_tail['Time'], pdf_tail['mean_divergence'], color='#7b2d8e', linewidth=2.5, linestyle=':', alpha=0.4)

ax2.fill_between(pdf['Time'], pdf['mean_divergence'], 0,
                 where=(pdf['mean_divergence'] > 0),
                 interpolate=True, color='#d62728', alpha=0.15)
ax2.fill_between(pdf['Time'], pdf['mean_divergence'], 0,
                 where=(pdf['mean_divergence'] <= 0),
                 interpolate=True, color='#1f77b4', alpha=0.15)

ax2.axhline(y=0, color='black', linewidth=1)
ax2.axvline(x=datetime.date(2025, 5, 14), color='grey', linestyle=':', linewidth=1.5)
ax2.set_ylabel('Mean Divergence\n(RSI − Wiki)', fontsize=11)
ax2.set_xlabel('Time', fontsize=12)
ax2.legend(loc='upper left', fontsize=10)
ax2.grid(True, alpha=0.3)

ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
fig.autofmt_xdate()
plt.tight_layout()

os.makedirs("trend_divergence_plots_combined", exist_ok=True)
output_path = 'trend_divergence_plots_combined/global_average_divergence.png'
plt.savefig(output_path, dpi=150, bbox_inches='tight')
plt.close()
print(f"Plot saved successfully to {output_path}")
