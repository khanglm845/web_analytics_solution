import os
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from urllib.parse import quote_plus

load_dotenv()

def get_db_engine():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    database = os.getenv("DB_NAME", "web_analytics_project")

    encoded_password = quote_plus(password)

    connection_string = f"mysql+mysqlconnector://{user}:{encoded_password}@{host}:{port}/{database}?charset=utf8mb4"

    try:
        engine = create_engine(connection_string, pool_pre_ping=True)
        with engine.connect() as conn:
            print("MySQL connection established successfully via SQLAlchemy!")
        return engine
    except SQLAlchemyError as e:
        print(f"Database connection error: {e}")
        return None

def load_df_to_mysql(df, table_name, engine, if_exists='append'):
    if engine is None:
        print("Engine not initialized. Insert operation cancelled.")
        return False
    try:
        df.to_sql(name=table_name, con=engine, if_exists=if_exists, index=False)
        print(f"Successfully saved {len(df)} rows into table '{table_name}'.")
        return True
    except Exception as e:
        print(f"Error saving data to table {table_name}: {e}")
        return False