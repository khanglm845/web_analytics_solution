import os
import requests
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from src.database.db_connection import get_db_engine, load_df_to_mysql

def scrape_cafef_news(
    stocks,
    search_output="df_search.csv",
    detail_output="df_full.csv",
    delay_between_pages=(1.5, 3.0),
    delay_between_articles=1.0,
    max_empty_pages=3,
    timeout=10,
):

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://cafef.vn/",
    }

    session = requests.Session()
    session.headers.update(headers)

    # ---------------------------
    # Phase 1: Scrape search results
    # ---------------------------
    all_news = []

    for stock in stocks:
        print(f"\n===== Crawling {stock} =====")
        page = 1
        empty_count = 0

        while True:
            # Build URL for current page
            if page == 1:
                url = f"https://cafef.vn/tim-kiem.chn?keywords={stock}"
            else:
                url = f"https://cafef.vn/tim-kiem/trang-{page}.chn?keywords={stock}"

            print(f"Page: {page}")

            try:
                resp = session.get(url, timeout=timeout)
            except Exception as e:
                print(f"Connection error: {e} – retrying in 3s")
                time.sleep(3)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.select("h3 a")

            if len(articles) == 0:
                empty_count += 1
                print(f"Empty page {page} (try {empty_count})")
                if empty_count >= max_empty_pages:
                    print("No more articles -> stop")
                    break
                time.sleep(random.uniform(*delay_between_pages))
                continue
            else:
                empty_count = 0  # reset counter

            for a in articles:
                title = a.text.strip()
                link = a.get("href", "")

                if not link.startswith("http"):
                    link = "https://cafef.vn" + link

                print(f"Collecting: {title[:80]}")
                all_news.append({
                    "title": title,
                    "url": link,
                    "stock": stock,
                })

            page += 1
            time.sleep(random.uniform(*delay_between_pages))

    # Save intermediate results
    df_search = pd.DataFrame(all_news)
    print(f"\nBefore remove duplicate: {len(df_search)}")
    df_search = df_search.drop_duplicates(subset=["url"])
    print(f"After remove duplicate: {len(df_search)}")
    df_search.to_csv(search_output, index=False, encoding="utf-8-sig")
    print(f"Saved intermediate dataset: {search_output}")

    # ---------------------------
    # Phase 2: Scrape article details
    # ---------------------------
    df_links = pd.read_csv(search_output)
    full_data = []

    for idx, row in df_links.iterrows():
        url = row["url"]
        stock = row["stock"]

        print(f"Fetching {idx+1}/{len(df_links)}: {url[:80]}")

        try:
            resp = requests.get(url, headers={"User-Agent": headers["User-Agent"]}, timeout=timeout)
            soup = BeautifulSoup(resp.text, "html.parser")

            title_tag = soup.find("h1")
            title = title_tag.text.strip() if title_tag else ""

            sapo_tag = soup.find("h2", class_="sapo")
            sapo = sapo_tag.text.strip() if sapo_tag else ""

            content_tag = soup.find("div", class_="detail-content")
            content = content_tag.text.strip() if content_tag else ""

            time_tag = soup.find("span", class_="pdate")
            publish_time = time_tag.text.strip() if time_tag else ""

            full_data.append({
                "stock": stock,
                "title": title,
                "sapo": sapo,
                "content": content,
                "publish_time": publish_time,
                "url": url,
            })

            print("Done.")

        except Exception as e:
            print(f"Error fetching {url}: {e} – skipping")

        time.sleep(delay_between_articles)

    df_full = pd.DataFrame(full_data)
    df_full.to_csv(detail_output, index=False, encoding="utf-8-sig")
    print(f"\nSaved final dataset: {detail_output}")

    # ------------------------------------------------------------------
    # NEW: Save to structured data/raw folder and load to MySQL
    # ------------------------------------------------------------------

    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "df_news.csv")
    df_full.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved to {output_file}")

    try:
        engine = get_db_engine()
        if engine:
            load_df_to_mysql(df=df_full, table_name='raw_news', engine=engine, if_exists='append')
            print("Loaded to MySQL table 'raw_news'")
        else:
            print("No database engine – skipping MySQL load")
    except Exception as e:
        print(f"Could not load to MySQL: {e}")

    return df_search, df_full


if __name__ == "__main__":
    
    stocks = ["VIC", "HAG", "TTF"]
    df_search, df_full = scrape_cafef_news(stocks)