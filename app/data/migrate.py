import os
import psycopg2
import pandas as pd
from tqdm import tqdm

DATABASE_URL = os.getenv("DATABASE_URL", default="postgresql://postgres:hOyPRiWxvaAWMCVuipaAUVlTiXGFLkpH@hayabusa.proxy.rlwy.net:35856/railway")
print(f"Connecting to: {DATABASE_URL}")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beer (
            id SERIAL PRIMARY KEY,
            brewery_name TEXT,
            beer_name TEXT,
            beer_style TEXT,
            abv FLOAT,
            ibu FLOAT,
            description TEXT
        )
    """)
    
    beer_df = pd.read_csv('beer_with_description.csv')
    cursor.execute("DELETE FROM beer")
    
    for _, row in tqdm(beer_df.iterrows(), total=beer_df.shape[0]):
        cursor.execute(
            "INSERT INTO beer (brewery_name, beer_name, beer_style, abv, ibu, description) VALUES (%s, %s, %s, %s, %s, %s)",
            (row['brewery_name'], row['beer_name'], row['beer_style'], row['abv'], row['ibu'], row.get('description', ''))
        )
    
    conn.commit()
    print("✅ Готово!")
except Exception as e:
    print(f"❌ Ошибка: {e}")