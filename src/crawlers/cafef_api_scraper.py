"""
src/crawlers/cafef_api_scraper.py
Crawl tin tức từ CafeF bằng API trực tiếp (Ajax) và bóc tách chi tiết.
"""

import os
import requests
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database.db_connection import get_db_engine

def scrape_cafef_article(url):
    """Bóc tách chi tiết bài báo từ URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        title_tag = soup.find("h1", class_="title")
        title = title_tag.text.strip() if title_tag else None
        time_tag = soup.find("span", class_="pdate")
        publish_time = time_tag.text.strip() if time_tag else None
        sapo_tag = soup.find("h2", class_="sapo")
        sapo = sapo_tag.text.strip() if sapo_tag else None
        content_div = soup.find("div", class_="detail-content")
        content = " ".join([p.text.strip() for p in content_div.find_all("p")]) if content_div else None
        return {"PublishTime": publish_time, "Title": title, "Sapo": sapo, "Content": content}
    except Exception:
        return None

def get_news_links_by_ticker(ticker, num_pages=1):
    """
    Lấy danh sách URL bài báo chuẩn (có .chn, không chứa /du-lieu/, không javascript).
    num_pages: số trang (mỗi trang 20 bài). Có thể tăng để lấy nhiều hơn.
    """
    links_data = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for page in range(num_pages):
        start_index = page * 20
        ajax_url = f"https://s.cafef.vn/Ajax/Events_RelatedNews_New.aspx?symbol={ticker}&startIndex={start_index}&PageSize=20"
        try:
            response = requests.get(ajax_url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
            soup = BeautifulSoup(response.content, "html.parser")
            a_tags = soup.find_all("a", href=True)
            for tag in a_tags:
                href = tag['href']
                if ".chn" in href and "/du-lieu/" not in href and "javascript" not in href:
                    full_url = "https://cafef.vn" + href if not href.startswith("http") else href
                    if full_url not in links_data:
                        links_data.append(full_url)
        except Exception:
            continue
        time.sleep(0.5)  # tránh quá tải server
    return links_data

def scrape_cafef_api(stocks, since_date=None, num_pages=1, delay_between_articles=1.0):
    """
    Crawl tin tức cho danh sách stocks.
    since_date: datetime object hoặc string 'YYYY-MM-DD' – chỉ lấy tin mới hơn ngày này.
    num_pages: số trang danh sách (mỗi trang 20 bài). Với lần crawl đầu nên đặt lớn hơn (ví dụ 10) để lấy lịch sử.
    """
    if since_date and isinstance(since_date, str):
        since_date = datetime.strptime(since_date, '%Y-%m-%d')

    all_articles = []
    for ticker in stocks:
        print(f"\n===== Crawling {ticker} via API =====")
        news_urls = get_news_links_by_ticker(ticker, num_pages=num_pages)
        print(f"-> Found {len(news_urls)} clean articles for {ticker}.")
        for url in news_urls:
            detail = scrape_cafef_article(url)
            if detail and detail["Title"] is not None:
                # Xử lý publish_time
                pub_time_str = detail["PublishTime"]
                pub_time = None
                if pub_time_str:
                    try:
                        # Dạng "23/03/2026 17:42"
                        pub_time = datetime.strptime(pub_time_str, "%d/%m/%Y %H:%M")
                    except:
                        try:
                            # Dạng "23/03/2026"
                            pub_time = datetime.strptime(pub_time_str, "%d/%m/%Y")
                        except:
                            pass
                # Lọc theo since_date nếu cần
                if since_date and pub_time and pub_time < since_date:
                    continue
                all_articles.append({
                    "stock": ticker,
                    "title": detail["Title"],
                    "sapo": detail["Sapo"],
                    "content": detail["Content"],
                    "publish_time": pub_time.strftime("%Y-%m-%d %H:%M:%S") if pub_time else None,
                    "url": url
                })
            time.sleep(delay_between_articles)

    if not all_articles:
        print("No news fetched.")
        return pd.DataFrame()

    df_full = pd.DataFrame(all_articles)
    # Lọc lần cuối (nếu publish_time vẫn bị lỗi)
    if since_date and 'publish_time' in df_full.columns:
        df_full['publish_time'] = pd.to_datetime(df_full['publish_time'], errors='coerce')
        df_full = df_full[df_full['publish_time'] >= since_date]

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

if __name__ == "__main__":
    # Test
    stocks = ["VIC", "HAG", "TTF"]
    df = scrape_cafef_api(stocks, num_pages=1)  # lấy 1 trang
    print(df.head())