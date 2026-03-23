# dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date
import sys
import os
from pathlib import Path
import re
from collections import Counter
from underthesea import word_tokenize

sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.database.db_connection import get_db_engine

st.set_page_config(page_title="Stock News Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 0;
        color: #1E3A8A;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-top: -0.5rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: transform 0.3s;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-label {
        font-size: 0.9rem;
        color: #f0f0f0;
        opacity: 0.9;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: white;
    }
    .metric-delta {
        font-size: 0.9rem;
        color: #c3e0ff;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
        border-radius: 20px;
        padding: 0.5rem 1.5rem;
        font-weight: bold;
    }
    .stButton button:hover {
        background-color: #45a049;
    }
</style>
""", unsafe_allow_html=True)

engine = get_db_engine()
if engine is None:
    st.error("❌ Cannot connect to database. Please check your connection.")
    st.stop()

# =========================
# STOPWORDS 
# =========================
basic_stopwords = set("""
và là của có trong một những các đã đang sẽ cho khi thì mà được với về từ này kia đó đây ấy vì do nên nếu cũng chỉ lại ra lên xuống vào đi đến rồi như
tôi nhà đầu tư thị trường người công ty doanh nghiệp đơn vị tổ chức vẫn trên trước sau cùng hơn ông bà
""".split())

news_stopwords = set("""
theo cho biết ghi nhận cho rằng nhận định đánh giá thông tin dữ liệu báo cáo công bố
cập nhật tin tức phiên ngày tháng năm quý sáng chiều hôm nay hôm qua
trong đó liên quan bao gồm đối với tại đây hiện nay vừa qua thời gian gần đây
ngày tuần tháng quý năm
""".split())

finance_neutral = set("""
cổ phiếu cp mã chứng khoán sàn hose hnx upcom vnindex vn30 index
thị trường thanh khoản khối lượng giao dịch nhà đầu tư dòng tiền
niêm yết đăng ký giao dịch vốn điều lệ cổ đông doanh nghiệp
""".split())

tickers_stopwords = set("""
hag ttf acb bcm bid bvh ctg fpt gas gvr hdb hpg mbb msn mwg plx pow sab shb ssb ssi stb tcb tpb vcb vhm vib vic vjc vnm vpb vre
""".split())

numeric_stopwords = set("""
tỷ triệu nghìn phần trăm đồng vnđ usd lần
""".split())

neutral_verbs = set("""
tăng giảm đi lên đi xuống biến động điều chỉnh giao dịch mua bán
ghi nhận đạt mức dao động mở cửa đóng cửa
""".split())

special_words = set(['chứng_khoán', 'giao_dịch', 'thị_trường', 'vingroup','công_ty', 'cổ_phiếu'])

stopwords_raw = (
    basic_stopwords
    | news_stopwords
    | finance_neutral
    | tickers_stopwords
    | numeric_stopwords
    | neutral_verbs
    | special_words
)

# Tokenize stopwords
stopwords_final = set()
for w in stopwords_raw:
    tokens = word_tokenize(w, format="text").split()
    stopwords_final.update(tokens)

# =========================
# TEXT CLEANING FUNCTIONS
# =========================
def clean_text(text):
    text = text.lower()
    text = re.sub(r'\d+', ' ', text)         
    text = re.sub(r'[^\w\s]', ' ', text)   
    return text

def process_text(text):
    text = clean_text(text)
    tokens = word_tokenize(text, format="text").split()
    tokens = [w for w in tokens if w not in stopwords_final and len(w) > 1]
    return tokens

def get_token_frequencies(df_texts):
    """Từ danh sách các chuỗi text, trả về Counter của các token đã xử lý."""
    all_tokens = []
    for text in df_texts:
        tokens = process_text(text)
        all_tokens.extend(tokens)
    return Counter(all_tokens)

# =========================
# LOAD DATA
# =========================
@st.cache_data(ttl=3600)
def load_news_analytics():
    query = """
        SELECT na.news_id, na.ticker, na.text, na.label, na.sentiment_score,
               rn.publish_time, rn.title, rn.url
        FROM news_analytics na
        JOIN raw_news rn ON na.news_id = rn.news_id
        WHERE na.ticker IN ('VIC', 'HAG', 'TTF')
        ORDER BY rn.publish_time DESC
    """
    df = pd.read_sql(query, engine)
    df['publish_time'] = pd.to_datetime(df['publish_time'])
    return df

@st.cache_data(ttl=3600)
def load_stock_prices(tickers):
    placeholders = ','.join([f"'{t}'" for t in tickers])
    query = f"""
        SELECT ticker, time, close
        FROM stock_prices
        WHERE ticker IN ({placeholders})
        ORDER BY time
    """
    df = pd.read_sql(query, engine)
    df['time'] = pd.to_datetime(df['time'])
    return df

all_tickers = ['VIC', 'HAG', 'TTF']
df_news = load_news_analytics()
df_prices = load_stock_prices(all_tickers)

# Sidebar
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=80)
st.sidebar.markdown("## Filters")
ticker = st.sidebar.selectbox("Stock", all_tickers, index=0)

# Date range
min_date = df_news['publish_time'].min().date()
max_date = df_news['publish_time'].max().date()
default_start = max_date - timedelta(days=30)
start_date = st.sidebar.date_input("Start date", default_start, min_value=min_date, max_value=max_date)
end_date = st.sidebar.date_input("End date", max_date, min_value=min_date, max_value=max_date)

# Label filter
label_filter = st.sidebar.multiselect("Label", ["POS", "NEU", "NEG"], default=["POS", "NEU", "NEG"])

st.sidebar.markdown("---")
st.sidebar.caption("Data updated daily | Powered by AI")

# Filter data
df_news_filtered = df_news[
    (df_news['ticker'] == ticker) &
    (df_news['publish_time'].dt.date >= start_date) &
    (df_news['publish_time'].dt.date <= end_date) &
    (df_news['label'].isin(label_filter))
].copy()

df_prices_filtered = df_prices[
    (df_prices['ticker'] == ticker) &
    (df_prices['time'].dt.date >= start_date) &
    (df_prices['time'].dt.date <= end_date)
].copy()

# Header
st.markdown('<p class="main-header">Stock News Intelligence</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Real-time sentiment analysis powered by PhoBERT</p>', unsafe_allow_html=True)

# KPI Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    if not df_prices_filtered.empty:
        last_price = df_prices_filtered.iloc[-1]['close']
        first_price = df_prices_filtered.iloc[0]['close']
        pct_change = ((last_price - first_price) / first_price) * 100 if first_price != 0 else 0
        delta = f"{pct_change:+.2f}%"
        delta_color = "🔴" if pct_change < 0 else "🟢"
    else:
        last_price = 0
        delta = "0%"
        delta_color = "⚪️"
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Price</div>
            <div class="metric-value">{last_price:,.0f} VND</div>
            <div class="metric-delta">{delta_color} {delta}</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    avg_sentiment = df_news_filtered['sentiment_score'].mean() if not df_news_filtered.empty else 0
    sent_color = "🟢" if avg_sentiment > 0 else ("🔴" if avg_sentiment < 0 else "⚪️")
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Sentiment</div>
            <div class="metric-value">{avg_sentiment:.3f}</div>
            <div class="metric-delta">{sent_color} from -1 to +1</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    news_volume = len(df_news_filtered)
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">News Volume</div>
            <div class="metric-value">{news_volume}</div>
            <div class="metric-delta">📰 articles</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    neg_count = len(df_news_filtered[df_news_filtered['label'] == 'NEG'])
    st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Negative Alerts</div>
            <div class="metric-value">{neg_count}</div>
            <div class="metric-delta">🔴 articles with negative sentiment</div>
        </div>
    """, unsafe_allow_html=True)

# Word Clouds: Positive và Negative (sử dụng preprocessing từ EDA)
st.markdown("### ☁️ Sentiment Word Clouds (Cleaned)")
col_wc1, col_wc2 = st.columns(2)

with col_wc1:
    st.markdown("#### 🔴 Negative News")
    neg_news = df_news_filtered[df_news_filtered['label'] == 'NEG']['text']
    if not neg_news.empty:
        neg_freq = get_token_frequencies(neg_news)
        if neg_freq:
            wordcloud_neg = WordCloud(width=600, height=400, background_color='white',
                                      colormap='Reds', max_words=100).generate_from_frequencies(neg_freq)
            fig_neg, ax_neg = plt.subplots(figsize=(8, 5))
            ax_neg.imshow(wordcloud_neg, interpolation='bilinear')
            ax_neg.axis('off')
            st.pyplot(fig_neg)
        else:
            st.info("No negative news tokens to display.")
    else:
        st.info("No negative news in selected period.")

with col_wc2:
    st.markdown("#### 🟢 Positive News")
    pos_news = df_news_filtered[df_news_filtered['label'] == 'POS']['text']
    if not pos_news.empty:
        pos_freq = get_token_frequencies(pos_news)
        if pos_freq:
            wordcloud_pos = WordCloud(width=600, height=400, background_color='white',
                                      colormap='Greens', max_words=100).generate_from_frequencies(pos_freq)
            fig_pos, ax_pos = plt.subplots(figsize=(8, 5))
            ax_pos.imshow(wordcloud_pos, interpolation='bilinear')
            ax_pos.axis('off')
            st.pyplot(fig_pos)
        else:
            st.info("No positive news tokens to display.")
    else:
        st.info("No positive news in selected period.")

# News Feed Table
st.markdown("### 📰 Latest News")
if not df_news_filtered.empty:
    display_df = df_news_filtered.sort_values('publish_time', ascending=False)[
        ['publish_time', 'title', 'label', 'sentiment_score', 'url']
    ].copy()
    display_df['publish_time'] = display_df['publish_time'].dt.strftime('%Y-%m-%d %H:%M')
    def color_label(label):
        if label == 'POS':
            return '🟢 POS'
        elif label == 'NEG':
            return '🔴 NEG'
        else:
            return '⚪️ NEU'
    display_df['label'] = display_df['label'].apply(color_label)
    display_df['sentiment_score'] = display_df['sentiment_score'].apply(lambda x: f"{x:.3f}")
    display_df['url'] = display_df['url'].apply(lambda x: f'<a href="{x}" target="_blank">🔗</a>')
    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No news available for selected filters.")

# Footer
st.markdown("---")
st.caption("Data sources: CafeF, vnstock | Model: PhoBERT fine-tuned")