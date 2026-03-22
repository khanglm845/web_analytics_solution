import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database.db_connection import get_db_engine, load_df_to_mysql

input_file = os.path.join("data", "raw", "news_stock_full.csv")

df = pd.read_csv(input_file)

data = []

for i, row in df.iterrows():
    url = row["url"]
    ticker = row["ticker"]

    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")

        title = soup.find("h1").text.strip()

        sapo = soup.find("h2", class_="sapo")
        sapo = sapo.text.strip() if sapo else ""

        content = soup.find("div", class_="detail-content")
        content = content.text.strip() if content else ""

        time_tag = soup.find("span", class_="pdate")
        publish_time = time_tag.text.strip() if time_tag else ""

        data.append({
            "stock": ticker,
            "title": title,
            "sapo": sapo,
            "content": content,
            "publish_time": publish_time,
            "url": url
        })

        print("Done:", i)
        time.sleep(1)

    except Exception as e:
        print("Error:", url, e)

df_news = pd.DataFrame(data)

output_dir = os.path.join("data", "raw")
os.makedirs(output_dir, exist_ok=True)  
output_file = os.path.join(output_dir, "df_news.csv")

# Save file
df_news.to_csv(output_file, index=False, encoding="utf-8-sig")
print(f"Saved to {output_file}")

# Load 
engine = get_db_engine()

if engine:
    load_df_to_mysql(df=df_news, table_name='raw_news', engine=engine, if_exists='append')



