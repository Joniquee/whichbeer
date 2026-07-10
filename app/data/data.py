import sqlite3
import pandas as pd

def pd_to_sql():
    conn = sqlite3.connect('beer1.db')

    beer_df = pd.read_csv('app/data/beer_with_description.csv')
    beer_df.to_sql('beer', conn, if_exists='replace', index=False)
    conn.close()

def get_row(beer_name):
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    query = "SELECT * FROM beer WHERE beer_name = ?"
    cursor.execute(query, (beer_name,))
    row = cursor.fetchone()

    conn.close()
    return row

def beer_exists(beer_name):
    return get_row(beer_name) is not None

def get_names():
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    query = "SELECT beer_name FROM beer"
    cursor.execute(query)
    rows = cursor.fetchall()

    conn.close()
    return [row[0] for row in rows]

def search_beers(query, limit=20):
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    like = f"%{query}%"
    sql = (
        "SELECT brewery_name, beer_name, beer_style, abv, ibu "
        "FROM beer WHERE beer_name LIKE ? OR brewery_name LIKE ? "
        "LIMIT ?"
    )
    cursor.execute(sql, (like, like, limit))
    rows = cursor.fetchall()

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
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    query = "SELECT description FROM beer WHERE beer_name = ?"
    cursor.execute(query, (beer_name,))
    row = cursor.fetchone()

    conn.close()
    return row[0] if row else None

def add_beer(beer_data):
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    sql = (
        "INSERT INTO beer (brewery_name, beer_name, beer_style, abv, ibu, description) "
        "VALUES (?, ?, ?, ?, ?, ?)"
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
    conn.close()

def is_beer_in_db(beer_name):
    conn = sqlite3.connect('beer1.db')
    cursor = conn.cursor()

    query = "SELECT 1 FROM beer WHERE beer_name = ?"
    cursor.execute(query, (beer_name,))
    exists = cursor.fetchone() is not None

    conn.close()
    return exists

