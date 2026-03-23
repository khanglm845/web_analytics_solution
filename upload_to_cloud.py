import pandas as pd
from sqlalchemy import create_engine
from src.database.db_connection import get_db_engine

local_engine = get_db_engine()

cloud_host = "bzuoyb19zgyn77emwisi-mysql.services.clever-cloud.com"
cloud_user = "u2csm0chlybzznu1"
cloud_pw = "17WBU0XiFTDk3JiXAinZ"
cloud_db = "bzuoyb19zgyn77emwisi"

cloud_engine = create_engine(f"mysql+pymysql://{cloud_user}:{cloud_pw}@{cloud_host}:3306/{cloud_db}")

tables = ['raw_news', 'stock_prices', 'news_analytics']
for table in tables:
    df = pd.read_sql(f"SELECT * FROM {table}", local_engine)
    df.to_sql(table, cloud_engine, if_exists='replace', index=False)
    print(f"Uploaded {table}: {len(df)} rows")