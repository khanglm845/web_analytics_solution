import pandas as pd
from vnstock import Quote
import sys
import os
from datetime import datetime
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.database.db_connection import get_db_engine, load_df_to_mysql

def get_price_data(portfolio, start_date, end_date):
    """
    Fetch historical stock price data for a list of tickers.
    """
    print(f"Fetching price data from {start_date} to {end_date}...")
    all_prices = []

    for ticker in portfolio:
        print(f"-> Loading ticker: {ticker}")
        try:
            quote = Quote(symbol=ticker, source='KBS')
            df_ticker = quote.history(
                start=start_date,
                end=end_date,
                interval='1D',
            )
            if not df_ticker.empty:
                df_ticker['ticker'] = ticker
                all_prices.append(df_ticker)
            else:
                print(f"[!] No data returned for {ticker}")
        except Exception as e:
            print(f"[!] Error fetching {ticker}: {e}")

    if all_prices:
        df_final_price = pd.concat(all_prices, ignore_index=True)

        return df_final_price
    else:
        return pd.DataFrame()

def save_to_db(df, start_date, end_date):
    engine = get_db_engine()
    if engine is None:
        print("Cannot connect to DB.")
        return

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM stock_prices WHERE time >= :start AND time <= :end"),
                     {"start": start_date, "end": end_date})
        conn.commit()

    load_df_to_mysql(df, 'stock_prices', engine, if_exists='append')

if __name__ == "__main__":
    portfolio = ["VIC", "HAG", "TTF"]
    start_date = "2016-01-01"
    end_date = "2026-02-28"

    df_price = get_price_data(portfolio, start_date, end_date)

    output_dir = os.path.join("data", "raw")
    output_file = os.path.join(output_dir, "df_price.csv")
    os.makedirs(output_dir, exist_ok=True)
    df_price.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nSaved dataset: {output_file}")

    save_to_db(df_price, start_date, end_date)