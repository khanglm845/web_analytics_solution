import pandas as pd
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import DATA_PROCESSED_PATH
from src.database.db_connection import get_db_engine

OUTPUT_FILE = DATA_PROCESSED_PATH / "df_merged.csv"

def load_news_from_db(engine):

    query = """
        SELECT news_id, ticker, title, sapo, publish_time
        FROM raw_news
    """
    return pd.read_sql(query, engine)

def load_prices_from_db(engine):

    query = """
        SELECT ticker, time, open, high, low, close, volume
        FROM stock_prices
    """
    return pd.read_sql(query, engine)

def clean_news(df):

    df.fillna(value='unknown', inplace=True)

    df['publish_time'] = pd.to_datetime(df['publish_time'], errors='coerce')

    df.dropna(subset=['publish_time'], inplace=True)

    df = df[df['publish_time'] >= '2016-01-04']

    df['Target_Date'] = df['publish_time'].apply(
        lambda x: (x + pd.Timedelta(days=1)).date() if x.hour >= 15 else x.date()
    )
    df['Target_Date'] = pd.to_datetime(df['Target_Date'])
    df = df.sort_values('Target_Date')
    return df

def clean_prices(df):
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')
    return df

def merge_data(news_df, price_df):
    merged = pd.merge_asof(
        left=news_df,
        right=price_df,
        left_on='Target_Date',
        right_on='time',
        left_by='ticker',
        right_by='ticker',
        direction='forward'
    )
    merged.drop(columns=['time'], inplace=True, errors='ignore')
    merged.dropna(axis=0, inplace=True)
    return merged

def main():

    engine = get_db_engine()

    print("Loading news data from database...")
    news = load_news_from_db(engine)
    print(f"Raw news rows: {len(news)}")

    print("Loading price data from database...")
    prices = load_prices_from_db(engine)
    print(f"Raw price rows: {len(prices)}")

    print("Cleaning news data...")
    news_cleaned = clean_news(news)
    print(f"Cleaned news rows: {len(news_cleaned)}")

    print("Cleaning price data...")
    prices_cleaned = clean_prices(prices)
    print(f"Cleaned price rows: {len(prices_cleaned)}")

    print("Merging data...")
    merged = merge_data(news_cleaned, prices_cleaned)
    print(f"Merged rows: {len(merged)}")

    os.makedirs(DATA_PROCESSED_PATH, exist_ok=True)
    merged.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved merged data to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()