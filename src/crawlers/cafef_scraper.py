# src/crawlers/cafef_scraper.py
import os
import requests
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

def fetch_news_list(symbol, page_size=20, timeout=10):
    """
    Fetch the latest 20 news articles from CafeF AJAX API.
    Returns list of dicts: {'time_str', 'title', 'url'}
    """
    url = f"https://cafef.vn/du-lieu/Ajax/Events_RelatedNews_New.aspx?symbol={symbol}&startIndex=0&PageSize={page_size}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://cafef.vn/",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching list for {symbol}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    # Each article structure:
    # <span class="timeTitle">23/03/2026 17:42</span>
    # <a class="docnhanhTitle" href="/...">Title</a>
    for time_span, a_tag in zip(soup.find_all("span", class_="timeTitle"),
                                 soup.find_all("a", class_="docnhanhTitle")):
        time_str = time_span.text.strip()
        title = a_tag.text.strip()
        href = a_tag.get("href", "")
        if href and not href.startswith("http"):
            href = "https://cafef.vn" + href
        items.append({
            "time_str": time_str,
            "title": title,
            "url": href
        })
    return items

def parse_publish_time(time_str):
    """
    Convert time string "23/03/2026 17:42" to datetime.
    """
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(time_str, fmt)
        except:
            continue
    return None

def scrape_article_detail(url, timeout=10):
    """Fetch detailed content of an article."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    title_tag = soup.find("h1", class_="title")
    title = title_tag.text.strip() if title_tag else None
    sapo_tag = soup.find("h2", class_="sapo")
    sapo = sapo_tag.text.strip() if sapo_tag else None
    content_div = soup.find("div", class_="detail-content")
    if content_div:
        content = " ".join(p.text.strip() for p in content_div.find_all("p"))
    else:
        content = None
    return title, sapo, content

def scrape_cafef_news(stocks, delay_between_articles=1.0):
    """
    Crawl the latest 20 articles for each stock in stocks.
    Only fetches articles not already in DB (based on URL).
    """
    engine = get_db_engine()
    if engine is None:
        print("Cannot connect to DB. Stopping crawler.")
        return pd.DataFrame()

    # Get existing URLs from DB to avoid re-crawling
    with engine.connect() as conn:
        existing_urls = set(row[0] for row in conn.execute(text("SELECT url FROM raw_news")).fetchall())

    all_articles = []
    for ticker in stocks:
        print(f"\n===== Crawling {ticker} =====")
        items = fetch_news_list(ticker, page_size=20)
        if not items:
            print(f"No news list retrieved for {ticker}")
            continue
        print(f"Found {len(items)} articles.")

        for item in items:
            url = item["url"]
            if url in existing_urls:
                print(f"Already exists, skipping: {item['title'][:50]}")
                continue

            # Get article details
            title, sapo, content = scrape_article_detail(url)
            if not title:
                print(f"Failed to fetch content: {url}")
                continue

            pub_time = parse_publish_time(item["time_str"])
            if not pub_time:
                print(f"Cannot parse time: {item['time_str']}, skipping.")
                continue

            all_articles.append({
                "stock": ticker,
                "title": title,
                "sapo": sapo or "",
                "content": content or "",
                "publish_time": pub_time.strftime("%Y-%m-%d %H:%M:%S"),
                "url": url
            })
            time.sleep(delay_between_articles)

    if not all_articles:
        print("No new articles.")
        return pd.DataFrame()

    df_full = pd.DataFrame(all_articles)

    # Save CSV
    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "df_news.csv")
    df_full.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved CSV: {output_file}")

    # Insert into DB (INSERT IGNORE based on url)
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
    print(f"Added {len(df_full)} new articles to database.")
    return df_full