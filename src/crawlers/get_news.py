import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import os

stocks = ["VIC","HAG","TTF"]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

all_news = []

for stock in stocks:

    print(f"\n===== Crawling {stock} =====")

    page = 1

    while True:

        if page == 1:
            url = f"https://m.cafef.vn/tim-kiem.chn?keywords={stock}"
        else:
            url = f"https://m.cafef.vn/tim-kiem/trang-{page}.chn?keywords={stock}"

        print("Page:", page)

        try:
            r = requests.get(url, headers=headers, timeout=10)
        except:
            print("Connection error... retry")
            time.sleep(5)
            continue

        soup = BeautifulSoup(r.text,"html.parser")

        articles = soup.select("h3 a")

        if len(articles) == 0:
            print("No more articles")
            break

        for a in articles:

            title = a.text.strip()
            link = a["href"]

            if not link.startswith("http"):
                link = "https://cafef.vn" + link

            print("Collecting:", title[:80])

            all_news.append({
                "title": title,
                "url": link,
                "stock": stock
            })

        page += 1

        time.sleep(random.uniform(1.5,3))

df = pd.DataFrame(all_news)

print("\nBefore remove duplicate:",len(df))

df = df.drop_duplicates(subset=["url"])

print("After remove duplicate:",len(df))


output_dir = os.path.join("data", "raw")
output_file = os.path.join(output_dir, "news_stock_full.csv")

os.makedirs(output_dir, exist_ok=True)

df.to_csv(output_file, index=False, encoding="utf-8-sig")

print(f"\nSaved dataset: {output_file}")