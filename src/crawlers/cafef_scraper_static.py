import os
import requests
import time
import random
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

def scrape_cafef_article(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            title_tag = soup.find("h1", class_="title")
            title = title_tag.text.strip() if title_tag else None
            time_tag = soup.find("span", class_="pdate")
            publish_time = time_tag.text.strip() if time_tag else None
            sapo_tag = soup.find("h2", class_="sapo")
            sapo = sapo_tag.text.strip() if sapo_tag else None
            content_div = soup.find("div", class_="detail-content")
            content = " ".join([p.text.strip() for p in content_div.find_all("p")]) if content_div else None
            return {
                "PublishTime": publish_time,
                "Title": title,
                "Sapo": sapo,
                "Content": content
            }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
    return None

def get_news_links_by_ticker(ticker, num_pages=5):
    links_data = []
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"Scanning news list for {ticker}...")
    for page in range(num_pages):
        start_index = page * 20
        ajax_url = f"https://s.cafef.vn/Ajax/Events_RelatedNews_New.aspx?symbol={ticker}&startIndex={start_index}&PageSize=20"
        try:
            response = requests.get(ajax_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                a_tags = soup.find_all("a", href=True)
                for tag in a_tags:
                    href = tag['href']
                    if ".chn" in href and "/du-lieu/" not in href and "javascript" not in href:
                        full_url = "https://cafef.vn" + href if not href.startswith("http") else href
                        if full_url not in links_data:
                            links_data.append(full_url)
            else:
                break
        except Exception as e:
            print(f"Error fetching page {page} for {ticker}: {e}")
            break
        time.sleep(random.uniform(1, 2))
    return links_data

def scrape_cafef_news(stocks, since_date=None, delay_between_articles=1.0):
    """
    Crawl news from CafeF for given stocks.
    If since_date is provided (string 'YYYY-MM-DD'), only keep articles with publish_time >= since_date.
    """
    if since_date and isinstance(since_date, str):
        since_date = datetime.strptime(since_date, '%Y-%m-%d')
    
    all_articles = []
    for ticker in stocks:
        news_urls = get_news_links_by_ticker(ticker, num_pages=5)
        print(f"Found {len(news_urls)} clean articles for {ticker}.")
        for url in news_urls:
            detail_data = scrape_cafef_article(url)
            if detail_data and detail_data["Title"]:
                # Parse publish_time
                pub_str = detail_data["PublishTime"]
                pub_time = None
                if pub_str:
                    # Có thể có định dạng "23-03-2026 - 17:42 PM" hoặc "20-03-2026 - 21:15 PM"
                    # Tách ngày và giờ
                    try:
                        # Loại bỏ " PM"/" AM"
                        clean = pub_str.replace(" PM", "").replace(" AM", "")
                        parts = clean.split(" - ")
                        if len(parts) == 2:
                            date_part, time_part = parts
                            pub_time = datetime.strptime(f"{date_part} {time_part}", "%d-%m-%Y %H:%M")
                        else:
                            pub_time = datetime.strptime(clean, "%d-%m-%Y")
                    except:
                        pass
                if since_date and pub_time and pub_time < since_date:
                    continue
                all_articles.append({
                    "stock": ticker,
                    "title": detail_data["Title"],
                    "sapo": detail_data["Sapo"],
                    "content": detail_data["Content"],
                    "publish_time": pub_time.strftime("%Y-%m-%d %H:%M:%S") if pub_time else None,
                    "url": url
                })
            time.sleep(delay_between_articles)
    
    if not all_articles:
        print("No news fetched.")
        return pd.DataFrame()
    
    df_full = pd.DataFrame(all_articles)
    # Lọc lại theo since_date (nếu có)
    if since_date and 'publish_time' in df_full.columns:
        df_full['publish_time'] = pd.to_datetime(df_full['publish_time'], errors='coerce')
        original_len = len(df_full)
        df_full = df_full[df_full['publish_time'] >= since_date]
        print(f"Filtered by since_date ({since_date}): kept {len(df_full)} out of {original_len} rows")
    
    # Lưu CSV
    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "df_news.csv")
    df_full.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved to {output_file}")
    
    # Insert vào DB
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