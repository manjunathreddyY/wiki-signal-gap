import pandas as pd
import os

input_dir = '/Users/manju/Downloads/DataFest2026/google_trends_cache'
output_dir = '/Users/manju/Downloads/DataFest2026/google_trends_cache_svrescaled'
os.makedirs(output_dir, exist_ok=True)

for filename in os.listdir(input_dir):
    if not filename.endswith('.csv'):
        continue
        
    file_path = os.path.join(input_dir, filename)
    df = pd.read_csv(file_path)
    
    if 'RSI' not in df.columns:
        print(f"Skipping {filename}: Missing 'RSI' column")
        continue

    min_val = df['RSI'].min()
    max_val = df['RSI'].max()
    
    if max_val > min_val:
        df['RSI'] = ((df['RSI'] - min_val) / (max_val - min_val) * 100).round().astype(int)
    elif max_val == min_val:
        df['RSI'] = 0 if max_val == 0 else 100

    output_path = os.path.join(output_dir, filename)
    df.to_csv(output_path, index=False)
    print(f"Rescaled {filename}")

print("All files rescaled successfully!")
