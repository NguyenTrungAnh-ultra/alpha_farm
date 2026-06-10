import pandas as pd

for tf in ['10m', '30m', '5m']:
    filepath = f"data/DNSE_VN30F_{tf}.csv"
    df = pd.read_csv(filepath)
    print(f"File {filepath}:")
    print(f"  First 3 rows:")
    print(df.head(3))
    print(f"  First datetime: {df['Datetime'].iloc[0]}")
    print(f"  Last datetime: {df['Datetime'].iloc[-1]}")
