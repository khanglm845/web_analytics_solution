import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DATA_MODEL_DIR = DATA_DIR / "model" 

os.makedirs(DATA_RAW_DIR, exist_ok=True)
os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)
os.makedirs(DATA_MODEL_DIR, exist_ok=True)

PORT = ['VIC', 'HAG', 'TTF']

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "web_analytics_project"),
    "charset": "utf8mb4"
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

SENTIMENT_MODEL_NAME = "mnguyn11/phobert-stock-sentiment-vn30"

MAX_SEQ_LEN = 256

BATCH_SIZE = 32

DATA_RAW_PATH = DATA_RAW_DIR
DATA_PROCESSED_PATH = DATA_PROCESSED_DIR
DATA_MODEL_PATH = DATA_MODEL_DIR