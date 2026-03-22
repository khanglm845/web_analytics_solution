import os
import sys
import logging
import subprocess
import pandas as pd
from sqlalchemy import text

# =========================
# CONFIG PATH
# =========================
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.config import DATA_PROCESSED_PATH, DATA_MODEL_PATH
from src.database.db_connection import get_db_engine

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =========================
# CONSTANTS
# =========================
INPUT_FILE = os.path.join(DATA_PROCESSED_PATH, "df_merged.csv")
OUTPUT_FILE = os.path.join(DATA_MODEL_PATH, "sentiment_scores.csv")

MODEL_REPO = "https://huggingface.co/mnguyn11/phobert-stock-sentiment-vn30"
LOCAL_MODEL_DIR = os.path.join(DATA_MODEL_PATH, "phobert-stock-sentiment-vn30")


# =========================
# MODEL WRAPPER
# =========================
class SentimentScorer:
    def __init__(self, model_dir: str = LOCAL_MODEL_DIR):
        self.model_dir = model_dir
        self.predictor = None

    def _clone_model(self):
        """Clone repo nếu chưa tồn tại"""
        if not os.path.exists(self.model_dir):
            logger.info("Cloning model repo...")

            subprocess.run([
                "git", "clone",
                MODEL_REPO,
                self.model_dir
            ], check=True)

    def _check_dependencies(self):
        """Check underthesea"""
        try:
            import underthesea  # noqa
        except ImportError:
            raise ImportError(
                "Thiếu thư viện 'underthesea'. Chạy: pip install underthesea"
            )

    def load_model(self):
        logger.info("Loading StockSentimentPredictor...")

        # 1. Clone repo
        self._clone_model()

        # 2. Check dependency
        self._check_dependencies()

        # 3. Kiểm tra file modeling.py
        modeling_path = os.path.join(self.model_dir, "modeling.py")
        if not os.path.exists(modeling_path):
            raise FileNotFoundError(f"modeling.py not found in {self.model_dir}")

        # 4. Add path
        sys.path.insert(0, os.path.abspath(self.model_dir))

        # 5. Load model (IMPORTANT: đổi working dir)
        current_dir = os.getcwd()

        try:
            os.chdir(self.model_dir)

            from modeling import StockSentimentPredictor
            self.predictor = StockSentimentPredictor()

        finally:
            os.chdir(current_dir)

        logger.info("Model loaded successfully")

    def predict_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.predictor is None:
            raise RuntimeError("Model not loaded")

        logger.info("Running prediction...")

        result_df = self.predictor.predict_batch(df)

        # =========================
        # Chuẩn hóa output
        # =========================
        if "prob_POS" in result_df.columns and "prob_NEG" in result_df.columns:
            result_df["sentiment_score"] = result_df["prob_POS"] - result_df["prob_NEG"]
        else:
            label_map = {"POS": 1, "NEU": 0, "NEG": -1}
            result_df["sentiment_score"] = result_df["pred_label"].map(label_map)

        return result_df


# =========================
# DATA PROCESSING
# =========================
def load_and_prepare_data(filepath: str) -> pd.DataFrame:
    logger.info(f"Loading data from {filepath}")
    df = pd.read_csv(filepath)

    required_cols = ["news_id", "ticker", "title", "sapo"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    df["title"] = df["title"].fillna("")
    df["sapo"] = df["sapo"].fillna("")
    df["text"] = df["title"] + " " + df["sapo"]

    df = df.rename(columns={"ticker": "stock"})
    df = df[["news_id", "stock", "text"]].copy()

    logger.info(f"Prepared {len(df)} rows")
    return df


# =========================
# SAVE CSV
# =========================
def save_to_csv(df: pd.DataFrame, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved CSV to {output_path}")


# =========================
# DATABASE
# =========================
def insert_to_database(df: pd.DataFrame, engine):
    rows = df[["news_id", "stock", "text", "pred_label", "sentiment_score"]] \
        .rename(columns={"stock": "ticker", "pred_label": "label"}) \
        .to_dict(orient="records")

    query = """
        INSERT INTO news_analytics (news_id, ticker, text, label, sentiment_score)
        VALUES (:news_id, :ticker, :text, :label, :sentiment_score)
        ON DUPLICATE KEY UPDATE
            ticker = VALUES(ticker),
            text = VALUES(text),
            label = VALUES(label),
            sentiment_score = VALUES(sentiment_score)
    """

    with engine.begin() as conn:
        conn.execute(text(query), rows)

    logger.info(f"Inserted {len(rows)} rows into database")


# =========================
# MAIN
# =========================
def main():
    # 1. Load data
    df = load_and_prepare_data(INPUT_FILE)

    # 2. Load model
    scorer = SentimentScorer()
    scorer.load_model()

    # 3. Predict
    df_scored = scorer.predict_dataframe(df)

    # 4. Save CSV
    save_to_csv(df_scored, OUTPUT_FILE)

    # 5. Insert DB
    try:
        engine = get_db_engine()
        insert_to_database(df_scored, engine)
    except Exception as e:
        logger.error(f"Database error: {e}")

    logger.info("Sentiment scoring completed successfully!")


# =========================
if __name__ == "__main__":
    main()