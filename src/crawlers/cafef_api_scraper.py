import os
import requests
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

def fetch_news_list(symbol, start_index=0, page_size=20, timeout=10):
    url = f"https://s.cafef.vn/Ajax/Events_RelatedNews_New.aspx?symbol={symbol}&startIndex={start_index}&PageSize={page_size}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching list for {symbol} at index {start_index}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.find_all("a")
    news_items = []
    for a in articles:
        href = a.get("href")
        if not href or not href.startswith("/tin-tuc/"):
            continue
        full_url = "https://cafef.vn" + href
        text_content = a.get_text(strip=True)
        if not text_content or " - " not in text_content:
            continue
        parts = text_content.split(" - ", 1)
        if len(parts) == 2:
            publish_time_str, title = parts
        else:
            publish_time_str = ""
            title = text_content
        news_items.append({
            "title": title,
            "url": full_url,
            "publish_time_str": publish_time_str
        })
    return news_items

def get_news_details(url, timeout=10):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching detail {url}: {e}")
        return None, None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.text.strip() if title_tag else ""
    sapo_tag = soup.find("h2", class_="sapo")
    sapo = sapo_tag.text.strip() if sapo_tag else ""
    content_tag = soup.find("div", class_="detail-content")
    content = content_tag.text.strip() if content_tag else ""
    return title, sapo, content, url

def scrape_cafef_api(stocks, since_date=None, delay_between_articles=1.0, page_size=20):
    if since_date and isinstance(since_date, str):
        since_date = datetime.strptime(since_date, '%Y-%m-%d')
    
    all_news = []
    for symbol in stocks:
        print(f"\n===== Crawling {symbol} via API =====")
        start_index = 0
        empty_count = 0
        while True:
            print(f"Fetching page {start_index // page_size + 1} (startIndex={start_index})")
            items = fetch_news_list(symbol, start_index=start_index, page_size=page_size)
            if not items:
                empty_count += 1
                if empty_count >= 2:
                    print("No more items, stopping.")
                    break
                start_index += page_size
                continue
            empty_count = 0

            filtered_items = []
            for item in items:
                try:
                    pub_time = datetime.strptime(item["publish_time_str"], "%d/%m/%Y %H:%M")
                except:
                    pub_time = None
                if since_date and pub_time and pub_time < since_date:
                    continue
                filtered_items.append({
                    "stock": symbol,
                    "title": item["title"],
                    "url": item["url"],
                    "publish_time": pub_time.strftime("%Y-%m-%d %H:%M:%S") if pub_time else None
                })

            for item in filtered_items:
                print(f"Fetching detail: {item['title'][:80]}")
                title, sapo, content, url = get_news_details(item["url"])
                all_news.append({
                    "stock": item["stock"],
                    "title": title or item["title"],
                    "sapo": sapo,
                    "content": content,
                    "publish_time": item["publish_time"],
                    "url": url
                })
                time.sleep(delay_between_articles)

            if len(items) < page_size:
                print("Reached last page.")
                break
            start_index += page_size
            time.sleep(1) 

    df_full = pd.DataFrame(all_news)
    if df_full.empty:
        print("No news fetched.")
        return df_full

    if since_date and 'publish_time' in df_full.columns:
        df_full['publish_time'] = pd.to_datetime(df_full['publish_time'], errors='coerce')
        original_len = len(df_full)
        df_full = df_full[df_full['publish_time'] >= since_date]
        print(f"Filtered by since_date ({since_date}): kept {len(df_full)} out of {original_len} rows")

    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "df_news.csv")
    df_full.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved to {output_file}")

    engine = get_db_engine()
    if engine:
        with engine.connect() as conn:
            for _, row in df_full.iterrows():
                conn.execute(text("""
                    INSERT IGNORE INTO raw_news (ticker, title, sapo, content, publish_time, url)
                    VALUES (:ticker, :title, :sapo, :content, :publish_time, :url)
                """), {
                    "ticker": row['stock'],
                    "title": row['title'],
                    "sapo": row['sapo'],
                    "content": row['content'],
                    "publish_time": row['publish_time'],
                    "url": row['url']
                })
            conn.commit()
        print("Loaded to MySQL table 'raw_news' with IGNORE duplicates")
    return df_full