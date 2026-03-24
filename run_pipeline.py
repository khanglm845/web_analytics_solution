import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import text

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from src.database.db_connection import get_db_engine
from src.crawlers.cafef_scraper import scrape_cafef_news
from src.crawlers.vnstock_api import get_price_data, save_to_db as save_price_to_db

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "pipeline.log"
LAST_RUN_FILE = BASE_DIR / "last_run.txt"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_last_run():
    if LAST_RUN_FILE.exists():
        try:
            with open(LAST_RUN_FILE, 'r') as f:
                last_run_str = f.read().strip()
                if last_run_str:
                    return datetime.fromisoformat(last_run_str)
        except Exception as e:
            logger.warning(f"Error reading last_run file: {e}")
    return None

def set_last_run(timestamp):
    try:
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(timestamp.isoformat())
        logger.info(f"Updated last_run to {timestamp.isoformat()}")
    except Exception as e:
        logger.error(f"Failed to write last_run file: {e}")

def check_database():
    engine = get_db_engine()
    if engine is None:
        logger.error("Cannot connect to database. Pipeline stopped.")
        sys.exit(1)
    logger.info("Database connection OK.")
    return engine

def run_crawler(since_date=None):
    logger.info("Starting crawler...")
    stocks = ["VIC", "HAG", "TTF"]

    if since_date:
        since_str = since_date.strftime('%Y-%m-%d')
        logger.info(f"Crawling news from {since_str}")
    else:
        since_str = None
        logger.info("Crawling all news (first run)")

    try:
        scrape_cafef_news(stocks, since_date=since_str)
    except Exception as e:
        logger.error(f"News crawler failed: {e}", exc_info=True)
        return False

    try:
        if since_date:
            start = since_date.strftime('%Y-%m-%d')
        else:
            start = "2016-01-01"
        end = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Crawling prices from {start} to {end}")
        df_price = get_price_data(stocks, start, end)
        if not df_price.empty:
            save_price_to_db(df_price, start, end)
        else:
            logger.warning("No price data returned.")
    except Exception as e:
        logger.error(f"Price crawler failed: {e}", exc_info=True)
        return False

    logger.info("Crawler completed successfully.")
    return True

def run_sentiment(since_date=None):
    from src.models.sentiment_scorer import main as sentiment_main
    logger.info("Starting sentiment scoring...")
    try:
        sentiment_main(since_date)
        logger.info("Sentiment scoring completed.")
        return True
    except Exception as e:
        logger.error(f"Sentiment scoring failed: {e}", exc_info=True)
        return False

def run_full_pipeline():
    last_run = get_last_run()
    if last_run:
        since = last_run - timedelta(days=1)
        logger.info(f"Last successful run: {last_run}. Crawling data from {since}")
        if not run_crawler(since_date=since):
            logger.error("Crawler failed, pipeline aborted.")
            return False
        if not run_sentiment(since_date=since):
            logger.error("Sentiment scoring failed, pipeline aborted.")
            return False
    else:
        logger.info("No previous run. Crawling all data.")
        if not run_crawler():
            logger.error("Crawler failed, pipeline aborted.")
            return False
        if not run_sentiment():
            logger.error("Sentiment scoring failed, pipeline aborted.")
            return False

    now = datetime.now()
    set_last_run(now)
    logger.info(f"Pipeline completed successfully. Last run updated to {now}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Run the VN30 News Quantifier pipeline.")
    parser.add_argument(
        "--step",
        choices=["all", "crawl", "sentiment"],
        default="all",
        help="Choose which step to run. Default: all"
    )
    args = parser.parse_args()

    check_database()

    if args.step == "all":
        if not run_full_pipeline():
            sys.exit(1)
    elif args.step == "crawl":
        run_crawler()
    elif args.step == "sentiment":
        run_sentiment()

if __name__ == "__main__":
    main()