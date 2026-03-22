# dashboard/app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, date  # thêm date
import sys
import os
from pathlib import Path

# Thêm đường dẫn gốc dự án để import config và db_connection
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.config import PORT
from src.database.db_connection import get_db_engine

# Thiết lập trang
st.set_page_config(page_title="News Quantifier Dashboard", layout="wide")

# Kết nối DB
engine = get_db_engine()
if engine is None:
    st.error("Cannot connect to database. Please check your connection.")
    st.stop()

# Hàm load dữ liệu từ database (có cache)
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
    # Lấy giá cổ phiếu (close) cho các ticker
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

# Load dữ liệu
tickers = ['VIC', 'HAG', 'TTF']
df_news = load_news_analytics()
df_prices = load_stock_prices(tickers)

# ==================== Sidebar Filters ====================
st.sidebar.header("Filters")

# Ticker slicer: checkbox
selected_tickers = st.sidebar.multiselect(
    "Select Ticker(s)",
    options=tickers,
    default=tickers,
    help="Choose one or more stocks"
)

# Time slicer: date range picker
if not df_news.empty:
    min_date = df_news['publish_time'].min().date()
    max_date = df_news['publish_time'].max().date()
else:
    min_date = datetime.now().date()
    max_date = datetime.now().date()

default_start = max_date - timedelta(days=7)

date_range = st.sidebar.date_input(
    "Date Range",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date
)

# Xử lý giá trị trả về (có thể là tuple hoặc single date)
if isinstance(date_range, (date,)):  # sửa thành date
    start_date = date_range
    end_date = date_range
elif len(date_range) == 1:
    start_date = date_range[0]
    end_date = date_range[0]
elif len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = default_start, max_date

# Lọc dữ liệu theo filters
df_news_filtered = df_news[
    (df_news['ticker'].isin(selected_tickers)) &
    (df_news['publish_time'].dt.date >= start_date) &
    (df_news['publish_time'].dt.date <= end_date)
]

# ==================== KPI Cards ====================
st.header("KPI Dashboard")

# Tính các chỉ số dựa trên dữ liệu đã lọc
if not df_news_filtered.empty:
    # Average Sentiment Score (24h qua) – tính cho ngày cuối cùng trong khoảng
    last_day = end_date
    df_last_day = df_news_filtered[df_news_filtered['publish_time'].dt.date == last_day]
    avg_sentiment_last_day = df_last_day['sentiment_score'].mean() if not df_last_day.empty else 0.0

    # Negative Alerts: số lượng bài Negative trong khoảng thời gian
    negative_count = df_news_filtered[df_news_filtered['label'] == 'NEG'].shape[0]

    # Portfolio Return: % biến động giá trung bình của danh mục trong khoảng thời gian
    price_changes = []
    for ticker in selected_tickers:
        df_ticker = df_prices[df_prices['ticker'] == ticker]
        df_ticker = df_ticker[(df_ticker['time'].dt.date >= start_date) & (df_ticker['time'].dt.date <= end_date)]
        if not df_ticker.empty:
            first_price = df_ticker.iloc[0]['close']
            last_price = df_ticker.iloc[-1]['close']
            if first_price != 0:
                change = (last_price - first_price) / first_price * 100
                price_changes.append(change)
    portfolio_return = sum(price_changes) / len(price_changes) if price_changes else 0.0

    # Top Mover: mã cổ phiếu có số lượng bài Negative cao nhất
    neg_by_ticker = df_news_filtered[df_news_filtered['label'] == 'NEG'].groupby('ticker').size()
    if not neg_by_ticker.empty:
        top_mover = neg_by_ticker.idxmax()
    else:
        top_mover = "None"
else:
    avg_sentiment_last_day = 0.0
    negative_count = 0
    portfolio_return = 0.0
    top_mover = "N/A"

# Hiển thị KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Avg Sentiment Score (24h)", f"{avg_sentiment_last_day:.2f}", delta_color="inverse" if avg_sentiment_last_day < 0 else "normal")
with col2:
    st.metric("Negative Alerts", negative_count)
with col3:
    st.metric("Portfolio Return (%)", f"{portfolio_return:.2f}%")
with col4:
    st.metric("Top Mover", top_mover)

# ==================== Main Visuals ====================
st.header("Main Visuals")

# Biểu đồ 1: Sentiment vs Price (Dual-axis)
st.subheader("Sentiment vs Price")
selected_ticker_for_chart = st.selectbox("Select Ticker for Chart", selected_tickers if selected_tickers else tickers, key="ticker_chart")

# Lấy dữ liệu cho ticker được chọn
df_ticker_news = df_news_filtered[df_news_filtered['ticker'] == selected_ticker_for_chart].copy()
df_ticker_news['date'] = df_ticker_news['publish_time'].dt.date
# Tính sentiment trung bình theo ngày
sentiment_daily = df_ticker_news.groupby('date')['sentiment_score'].mean().reset_index()
sentiment_daily['date'] = pd.to_datetime(sentiment_daily['date'])

# Lấy dữ liệu giá cho ticker được chọn
df_ticker_price = df_prices[df_prices['ticker'] == selected_ticker_for_chart].copy()
df_ticker_price['date'] = df_ticker_price['time'].dt.date
price_daily = df_ticker_price.groupby('date')['close'].last().reset_index()
price_daily['date'] = pd.to_datetime(price_daily['date'])

# Merge dữ liệu sentiment và giá trên ngày
merged = pd.merge(sentiment_daily, price_daily, on='date', how='inner')
if not merged.empty:
    fig = go.Figure()
    # Cột sentiment
    colors = ['red' if x < 0 else 'green' for x in merged['sentiment_score']]
    fig.add_trace(go.Bar(
        x=merged['date'],
        y=merged['sentiment_score'],
        name='Sentiment Score',
        marker_color=colors,
        yaxis='y'
    ))
    # Đường giá
    fig.add_trace(go.Scatter(
        x=merged['date'],
        y=merged['close'],
        name='Close Price',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='blue')
    ))
    fig.update_layout(
        title=f"{selected_ticker_for_chart} - Sentiment vs Price",
        xaxis_title="Date",
        yaxis=dict(title="Sentiment Score", side="left", range=[-1, 1]),
        yaxis2=dict(title="Close Price", side="right", overlaying='y'),
        legend=dict(x=0, y=1.1),
        hovermode='x unified'
    )
    st.plotly_chart(fig, width='stretch')
else:
    st.info("No data available for the selected ticker and time range.")

# Biểu đồ 2: Scatter Plot – Hiệu ứng bất đối xứng (sentiment score vs price change)
st.subheader("Asymmetry Effect")
if not merged.empty:
    # Tính % thay đổi giá từ ngày trước
    merged['price_change'] = merged['close'].pct_change() * 100
    merged = merged.dropna(subset=['price_change'])
    # Tạm thời tắt trendline để tránh lỗi statsmodels (có thể cài statsmodels sau)
    fig2 = px.scatter(
        merged, x='sentiment_score', y='price_change',
        title="Sentiment Score vs Price Change (%)",
        labels={'sentiment_score': 'Sentiment Score', 'price_change': 'Price Change (%)'},
        # trendline="ols"  # Uncomment nếu đã cài statsmodels
    )
    st.plotly_chart(fig2, width='stretch')
else:
    st.info("Insufficient data for scatter plot.")

# ==================== Diagnostic View ====================
st.header("Diagnostic View")

# Word Cloud: lấy các tin Negative trong ngày cuối cùng
if not df_news_filtered.empty:
    # Lấy các tin Negative trong ngày cuối cùng
    last_day_neg = df_last_day[df_last_day['label'] == 'NEG'] if 'df_last_day' in locals() else pd.DataFrame()
    if not last_day_neg.empty:
        # Ghép tất cả title và sapo (text) để tạo word cloud
        text = " ".join(last_day_neg['text'].fillna('').tolist())
        if text.strip():
            wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
            fig_wc, ax = plt.subplots(figsize=(10, 5))
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            st.pyplot(fig_wc)
        else:
            st.info("No text data for negative news in the last day.")
    else:
        st.info("No negative news in the last day.")
else:
    st.info("No news data available for the selected filters.")

# Bảng báo cáo luồng tin
st.subheader("News Feed")
# Chọn các cột hiển thị
cols_to_show = ['publish_time', 'ticker', 'title', 'label', 'sentiment_score', 'url']
if not df_news_filtered.empty:
    # Sắp xếp theo thời gian mới nhất
    display_df = df_news_filtered.sort_values('publish_time', ascending=False)[cols_to_show]
    # Định dạng thời gian
    display_df['publish_time'] = display_df['publish_time'].dt.strftime('%Y-%m-%d %H:%M')
    # Hiển thị bảng
    st.dataframe(display_df, width='stretch')
else:
    st.info("No news data available for the selected filters.")