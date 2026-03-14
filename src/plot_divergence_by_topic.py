import polars as pl
import matplotlib.pyplot as plt
import seaborn as sns
import os
import datetime

# Load the combined data (Google Trends + Wikipedia pageviews)
df = pl.read_csv('Combined_view/ruwiki_comb_normalized_with_trends.csv')

# The predicted_labels column has a string format like:
# "Culture.Media.Films:0.984, Culture.Media.Media*:0.973, ..."
# Let's extract the top topic (highest probability) for each article.
# We take the first item before the colon since the string is sorted by probability in the original JSON.

df = df.with_columns(
    pl.col("predicted_labels").str.split(", ").list.first().str.split(":").list.first().str.split(".").list.first().alias("top_topic")
)


# Convert Time to Date
df = df.with_columns(
    pl.col("Time").str.strptime(pl.Date)
)

# Aggregate data by topic and week
# Average RSI and normalized_views per topic per week
topic_trends = df.group_by(["top_topic", "Time"]).agg([
    pl.col("normalized_views").mean().alias("avg_normalized_views"),
    pl.col("RSI").mean().alias("avg_rsi"),
    pl.len().alias("article_count")
]).sort(["top_topic", "Time"])

# Filter out topics with too few articles for a robust signal (e.g., < 5)
topic_counts = df.select(["page_id", "top_topic"]).unique().group_by("top_topic").len()
large_topics = topic_counts.filter(pl.col("len") >= 5)["top_topic"].to_list()

print(f"Analyzing {len(large_topics)} major topics...")

# Create plot directory
os.makedirs("trend_divergence_plots", exist_ok=True)


# plot the whole timeline and draw a vertical line tracking AI Overview Rollout (approx. mid-May).
# The divergence measure gives us insights directly.

sns.set_theme(style="whitegrid")

for topic in large_topics:
    # Handle potentially null topic
    if topic is None:
        continue
        
    topic_data = topic_trends.filter(pl.col("top_topic") == topic).to_pandas()
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    
    ax1.plot(topic_data['Time'], topic_data['avg_normalized_views'], label='Wiki Normalized Views', linewidth=2, color='tab:blue')
    ax1.plot(topic_data['Time'], topic_data['avg_rsi'], label='Google Trends (RSI)', linewidth=2, color='tab:red', linestyle='--')
    
    # Add vertical line for potential divergence point
    ax1.axvline(x=datetime.date(2025, 5, 14), color='black', linestyle=':', label='AI Overview Rollout (Approx)')
    

    ax1.fill_between(topic_data['Time'], topic_data['avg_normalized_views'], topic_data['avg_rsi'], 
                     where=(topic_data['avg_rsi'] > topic_data['avg_normalized_views']), 
                     interpolate=True, color='red', alpha=0.1, label='RSI > Wiki Views')
                     
    ax1.fill_between(topic_data['Time'], topic_data['avg_normalized_views'], topic_data['avg_rsi'], 
                     where=(topic_data['avg_rsi'] <= topic_data['avg_normalized_views']), 
                     interpolate=True, color='blue', alpha=0.1, label='Wiki Views > RSI')                     
    
    ax1.set_title(f"Trend Divergence: Wikipedia vs Google Trends\nTopic: {topic}", fontsize=14)
    ax1.set_xlabel("Time", fontsize=12)
    ax1.set_ylabel("Index (0-100 scale)", fontsize=12)
    ax1.legend(loc='upper left')
    
    # Save the plot
    safe_topic_name = topic.replace(".", "_").replace("*", "")
    plt.savefig(f"trend_divergence_plots_ru/{safe_topic_name}.png", bbox_inches='tight', dpi=150)
    plt.close()

print("Plots saved to trend_divergence_plots/")
