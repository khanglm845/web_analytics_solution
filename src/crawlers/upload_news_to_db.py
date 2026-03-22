import os
import sys
import pandas as pd
import argparse

# Thêm thư mục gốc vào sys.path để import được src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.db_connection import get_db_engine, load_df_to_mysql

def upload_news_to_db(csv_path='data/raw/df_news.csv', table_name='raw_news'):

    # Kiểm tra file tồn tại
    if not os.path.exists(csv_path):
        print(f"❌ File không tồn tại: {csv_path}")
        return False

    # Đọc dữ liệu
    print(f"📂 Đang đọc file: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ Lỗi đọc file CSV: {e}")
        return False
    print(f"✅ Đã đọc {len(df)} dòng dữ liệu.")
    print(f"📋 Các cột: {list(df.columns)}")

    # Kết nối database
    engine = get_db_engine()
    if engine is None:
        print("❌ Không thể kết nối database.")
        return False

    # Upload (thêm dữ liệu vào bảng, nếu bảng chưa tồn tại sẽ tự tạo)
    success = load_df_to_mysql(df=df, table_name=table_name, engine=engine, if_exists='append')
    if success:
        print(f"✅ Upload thành công {len(df)} dòng vào bảng '{table_name}'.")
    else:
        print(f"❌ Upload thất bại.")
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Upload news CSV to MySQL.')
    parser.add_argument('--csv', type=str, default='data/raw/df_news.csv',
                        help='Đường dẫn file CSV (mặc định: data/raw/df_news.csv)')
    parser.add_argument('--table', type=str, default='raw_news',
                        help='Tên bảng đích (mặc định: raw_news)')
    args = parser.parse_args()

    upload_news_to_db(csv_path=args.csv, table_name=args.table)