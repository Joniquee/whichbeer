import psycopg2
import pandas as pd
import os

# Connection string (для Railway: переменная DATABASE_URL)
DATABASE_URL = os.getenv("DATABASE_URL", default="postgresql://postgres:hOyPRiWxvaAWMCVuipaAUVlTiXGFLkpH@hayabusa.proxy.rlwy.net:35856/railway")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def ensure_embedding_column():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE beer ADD COLUMN IF NOT EXISTS embedding DOUBLE PRECISION[]")
    conn.commit()
    cursor.close()
    conn.close()

def pd_to_sql():
    conn = get_connection()
    cursor = conn.cursor()

    # Создать таблицу если не существует
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS beer (
            id SERIAL PRIMARY KEY,
            brewery_name TEXT,
            beer_name TEXT,
            beer_style TEXT,
            abv FLOAT,
            ibu FLOAT,
            description TEXT,
            embedding DOUBLE PRECISION[]
        )
    """)
    conn.commit()

    beer_df = pd.read_csv('app/data/beer_with_description.csv')

    # Очистить таблицу
    cursor.execute("DELETE FROM beer")

    # Вставить данные
    for _, row in beer_df.iterrows():
        cursor.execute(
            """INSERT INTO beer (brewery_name, beer_name, beer_style, abv, ibu, description)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (row['brewery_name'], row['beer_name'], row['beer_style'],
             row['abv'], row['ibu'], row.get('description', ''))
        )
    conn.commit()
    cursor.close()
    conn.close()

def get_row(beer_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM beer WHERE beer_name = %s", (beer_name,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row

def beer_exists(beer_name):
    return get_row(beer_name) is not None

def get_names():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT beer_name FROM beer")
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return [row[0] for row in rows]

def search_beers(query, limit=20):
    conn = get_connection()
    cursor = conn.cursor()

    like = f"%{query}%"
    sql = (
        "SELECT brewery_name, beer_name, beer_style, abv, ibu "
        "FROM beer WHERE beer_name ILIKE %s OR brewery_name ILIKE %s "
        "LIMIT %s"
    )
    cursor.execute(sql, (like, like, limit))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()
    return [
        {
            "brewery_name": row[0],
            "beer_name": row[1],
            "beer_style": row[2],
            "abv": row[3],
            "ibu": row[4],
        }
        for row in rows
    ]

def get_description(beer_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT description FROM beer WHERE beer_name = %s", (beer_name,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row[0] if row else None

def get_embedding(beer_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT embedding FROM beer WHERE beer_name = %s", (beer_name,))
    row = cursor.fetchone()

    cursor.close()
    conn.close()
    return row[0] if row else None

def add_beer(beer_data):
    conn = get_connection()
    cursor = conn.cursor()

    sql = (
        "INSERT INTO beer (brewery_name, beer_name, beer_style, abv, ibu, description) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    cursor.execute(sql, (
        beer_data['brewery_name'],
        beer_data['beer_name'],
        beer_data['beer_style'],
        beer_data['abv'],
        beer_data['ibu'],
        beer_data['description']
    ))
    conn.commit()
    cursor.close()
    conn.close()

def is_beer_in_db(beer_name):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM beer WHERE beer_name = %s", (beer_name,))
    exists = cursor.fetchone() is not None

    cursor.close()
    conn.close()
    return exists