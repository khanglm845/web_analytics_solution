# VNStock News Quantifier

**Sentiment analysis pipeline for Vietnamese stock news, using a fine-tuned PhoBERT model, with automated crawling and interactive dashboard.**

The system focuses on **three representative stocks**:
- **VIC** (High-cap) – Vingroup
- **HAG** (Mid-cap) – Hoàng Anh Gia Lai
- **TTF** (Low-cap) – Trường Thành Furniture

It collects news from CafeF, fetches daily price data, computes sentiment scores, stores everything in MySQL, and visualizes results via a Streamlit dashboard.

---

## ✨ Features

- **Automated daily pipeline** (incremental updates via `last_run.txt`)
- **Custom PhoBERT model** fine-tuned on Vietnamese financial news (`mnguyn11/phobert-stock-sentiment-vn30`)
- **Word clouds** with stopword removal and tokenization (using `underthesea`)
- **Interactive dashboard** with filters (stock, date, label), key metrics, and news feed
- **Easy extension** – just add tickers in `src/config.py`

---

## 📁 Project Structure
```text
VN30_News_Quantifier/
├── data/ # Local storage (ignored)
├── dashboard/ # Streamlit dashboard
│ └── app.py
├── src/
│ ├── config.py # Configuration (tickers, DB, etc.)
│ ├── crawlers/ # News & price scrapers
│ │ ├── cafef_scraper.py
│ │ └── vnstock_api.py
│ ├── database/ # DB connection utilities
│ ├── models/ # Sentiment scoring
│ │ └── sentiment_scorer.py
│ └── utils/ # Time mapping, helpers
├── .env.example
├── requirements.txt
├── run_pipeline.py
└── README.md
```
## ⚙️ Installation
1. Clone the repository
```text
git clone https://github.com/khangly845/Demo_Web_Analytics_Solutions.git
cd Demo_Web_Analytics_Solutions
```
2. Set up a virtual environment (optional but recommended)
```text
python -m venv .venv
# Activate on Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```
3. Install dependencies
```text
pip install -r requirements.txt
```
4. Configure environment variables 
+ **Option A (local MySQL):** Create a database and update .env with your local credentials.

+ **Option B (Clever Cloud):** After creating a MySQL instance on Clever Cloud, copy the connection details and update .env accordingly. Example:

```text
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=stock_news
```
5. Set up the MySQL database
Run the provided database_schema.sql to create the required tables:
```text
CREATE DATABASE IF NOT EXISTS database_name;
USE database_name;
-- (execute the schema script)
```
## 🚀 Usage
### Run the full pipeline manually
```text
python run_pipeline.py
```
This will:

+ Check for a last_run.txt file to determine the last successful execution.

+ Crawl news from CafeF and price data from vnstock for the selected stocks.

+ Merge news and price data (using time_mapping.py).

+ Run sentiment analysis and store results in the database.

+ Update last_run.txt with the current timestamp.

### Run individual steps
```text
python run_pipeline.py --step crawl          # only crawl new data
python run_pipeline.py --step time_mapping   # only merge news and price
python run_pipeline.py --step sentiment      # only run sentiment scoring
```

### Launch the dashboard
```text
streamlit run dashboard/app.py
```
#### Deployment on Streamlit Cloud
1. Push your code to GitHub.

2. Go to Streamlit Cloud, sign in with GitHub.

3. Click New app, select your repository, branch, and entry point (dashboard/app.py).

4. In Advanced settings, set Python version to 3.10.

5. Add Secrets (TOML format) with your database credentials:
```text
DB_USER = "u2csm0chlybzznu1"
DB_PASSWORD = "17WBU0XiFTDk3JiXAinZ"
DB_HOST = "bzuoyb19zgyn77emwisi-mysql.services.clever-cloud.com"
DB_PORT = "3306"
DB_NAME = "bzuoyb19zgyn77emwisi"
```
6. Click Deploy. The app will be available at ```https://your-app.streamlit.app.```

### Automation
#### Option A: Local
1. Open Task Scheduler.

2. Create a new task with a daily trigger (e.g., 7:00 AM).

3. Action: start program python.exe with argument run_pipeline.py in the project directory.

#### Option B: Cloud
1. Create GitHub Actions workflow
Create a file .github/workflows/daily_pipeline.yml in your repository with the following content:
```text
name: Daily Pipeline

on:
  schedule:
    # Runs at 7:00 AM UTC+7 (00:00 UTC) every day
    - cron: "0 0 * * *"
  workflow_dispatch:  # allows manual trigger

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pipeline
        run: python run_pipeline.py
        env:
          DB_USER: ${{ secrets.DB_USER }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PORT: ${{ secrets.DB_PORT }}
          DB_NAME: ${{ secrets.DB_NAME }}
```
2. Add repository secrets
Go to your GitHub repository → Settings → Secrets and variables → Actions → New repository secret.

## 📊 Dashboard Overview
+ **Filter Sidebar:** Stock ticker, date range, and sentiment label filter.

+ **Key Metrics:** Current price & change, average sentiment, news volume, and negative alerts.

+ **Word Clouds:** Separately generated from positive and negative news after stopword removal and tokenization.

+ **News Feed:** Sortable table with title, label, sentiment score, and direct link to the original article.

All visualizations update in real time based on the selected filters.

## 🧠 Sentiment Model
The sentiment model is a fine-tuned version of PhoBERT ```(wonrax/phobert-base-vietnamese-sentiment)``` trained on a custom dataset of Vietnamese financial news. It outputs three classes:

+ POS (positive)

+ NEU (neutral)

+ NEG (negative)

The sentiment score is defined as prob(POS) - prob(NEG).

## 🛠️ Customization
+ **Add more stocks:** Modify all_tickers in run_pipeline.py and the dashboard.

+ **Change the sentiment model:** Update MODEL_NAME in sentiment_scorer.py.

+ **Adjust crawling logic:** Edit cafef_scraper.py (e.g., different sources or pagination).

## 📦 Dependencies
Main libraries used:

+ pandas, numpy – data manipulation

+ requests, beautifulsoup4 – web scraping

+ sqlalchemy, mysql-connector-python – database integration

+ transformers, torch – sentiment model inference

+ underthesea – Vietnamese word tokenization

+ streamlit, plotly, wordcloud, matplotlib – dashboard and visualisation

+ vnstock – stock price data

+ python-dotenv – environment variable management

See requirements.txt for the full list.

## 🙌 Acknowledgements

+ [Cafef](https://cafef.vn/) for news content.

+ [vnstock](https://vnstocks.com/) for stock price API.

+ PhoBERT and the fine-tuned model by [mnguyn11](https://huggingface.co/mnguyn11).


