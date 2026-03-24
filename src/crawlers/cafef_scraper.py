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
    Lấy danh sách 20 bài báo mới nhất từ AJAX API của CafeF.
    Trả về list các dict: {'time_str', 'title', 'url'}
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
    """Chuyển đổi chuỗi thời gian "23/03/2026 17:42" thành datetime."""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(time_str, fmt)
        except:
            continue
    return None

def scrape_article_detail(url, timeout=10):
    """Lấy nội dung chi tiết của bài báo."""
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

def scrape_cafef_news(stocks, since_date=None, delay_between_articles=1.0):
    """
    Crawl 20 bài báo mới nhất cho mỗi mã trong stocks.
    Nếu since_date được cung cấp (string 'YYYY-MM-DD'), chỉ lấy bài có publish_time >= since_date.
    Chỉ lấy những bài chưa có trong DB (dựa trên URL).
    """
    engine = get_db_engine()
    if engine is None:
        print("Không thể kết nối DB. Dừng crawler.")
        return pd.DataFrame()

    # Nếu since_date là datetime, chuyển thành string
    if since_date and isinstance(since_date, datetime):
        since_date = since_date.strftime('%Y-%m-%d')

    # Lấy danh sách URL đã có trong DB để tránh crawl lại
    with engine.connect() as conn:
        existing_urls = set(row[0] for row in conn.execute(text("SELECT url FROM raw_news")).fetchall())

    all_articles = []
    for ticker in stocks:
        print(f"\n===== Crawling {ticker} =====")
        items = fetch_news_list(ticker, page_size=20)
        if not items:
            print(f"Không lấy được danh sách tin cho {ticker}")
            continue
        print(f"Tìm thấy {len(items)} bài báo.")

        for item in items:
            url = item["url"]
            if url in existing_urls:
                print(f"Đã tồn tại, bỏ qua: {item['title'][:50]}")
                continue

            # Lấy chi tiết bài báo
            title, sapo, content = scrape_article_detail(url)
            if not title:
                print(f"Không lấy được nội dung: {url}")
                continue

            pub_time = parse_publish_time(item["time_str"])
            if not pub_time:
                print(f"Không parse được thời gian: {item['time_str']}, bỏ qua.")
                continue

            # Lọc theo since_date
            if since_date:
                # Chuyển pub_time về string YYYY-MM-DD để so sánh
                if pub_time.strftime('%Y-%m-%d') < since_date:
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
        print("Không có bài báo mới.")
        return pd.DataFrame()

    df_full = pd.DataFrame(all_articles)

    # Lưu CSV
    output_dir = os.path.join("data", "raw")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "df_news.csv")
    df_full.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Lưu CSV: {output_file}")

    # Insert vào DB (INSERT IGNORE dựa trên url)
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
    print(f"Đã thêm {len(df_full)} bài mới vào database.")
    return df_full