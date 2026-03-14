import polars as pl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime

# Load the combined data
df = pl.read_csv('Combined_view/ruwiki_comb_normalized_with_trends.csv')

# Convert Time to Date
df = df.with_columns(
    pl.col("Time").str.strptime(pl.Date)
)

# Average normalized_views and RSI across ALL articles per week
weekly = df.group_by("Time").agg([
    pl.col("normalized_views").mean().alias("avg_normalized_views"),
    pl.col("RSI").mean().alias("avg_rsi"),
    pl.len().alias("article_count")
]).sort("Time")

pdf = weekly.to_pandas()

# Compute divergence: RSI - Wiki Views
pdf['divergence'] = pdf['avg_rsi'] - pdf['avg_normalized_views']

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                gridspec_kw={'height_ratios': [3, 1]})

# ── Top panel: both curves ──
ax1.plot(pdf['Time'], pdf['avg_normalized_views'], label='Wikipedia Normalized Views (avg)', linewidth=2, color='#1f77b4')
ax1.plot(pdf['Time'], pdf['avg_rsi'], label='Google Trends RSI (avg)', linewidth=2, color='#d62728', linestyle='--')

ax1.fill_between(pdf['Time'], pdf['avg_normalized_views'], pdf['avg_rsi'],
                 where=(pdf['avg_rsi'] > pdf['avg_normalized_views']),
                 interpolate=True, color='red', alpha=0.12, label='Google > Wiki')
ax1.fill_between(pdf['Time'], pdf['avg_normalized_views'], pdf['avg_rsi'],
                 where=(pdf['avg_rsi'] <= pdf['avg_normalized_views']),
                 interpolate=True, color='blue', alpha=0.12, label='Wiki > Google')

ax1.axvline(x=datetime.date(2025, 5, 14), color='grey', linestyle=':', linewidth=1.5, label='AI Overviews Rollout (approx)')
ax1.set_ylabel('Index (0-100 scale)', fontsize=12)
ax1.set_title('Overall Divergence: Wikipedia Normalized Views vs Google Trends RSI\n(Averaged across all articles per week)', fontsize=14)
ax1.legend(loc='upper left', fontsize=9)
ax1.grid(True, alpha=0.3)

# ── Bottom panel: divergence line ──
ax2.bar(pdf['Time'], pdf['divergence'], width=5, color=['#d62728' if v > 0 else '#1f77b4' for v in pdf['divergence']], alpha=0.7)
ax2.axhline(y=0, color='black', linewidth=0.8)
ax2.axvline(x=datetime.date(2025, 5, 14), color='grey', linestyle=':', linewidth=1.5)
ax2.set_ylabel('Divergence\n(RSI − Wiki)', fontsize=11)
ax2.set_xlabel('Time', fontsize=12)
ax2.grid(True, alpha=0.3)

ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
fig.autofmt_xdate()
plt.tight_layout()
plt.savefig('trend_divergence_plots_ru/overall_divergence.png', dpi=150, bbox_inches='tight')
plt.close()
print("Plot saved to trend_divergence_plots/overall_divergence.png")
