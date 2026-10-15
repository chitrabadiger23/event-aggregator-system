import sqlite3

conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT
        e.id,
        e.title,
        e.date,
        e.location,
        m.time,
        m.venue,
        m.city
    FROM events e
    LEFT JOIN event_metadata m
        ON e.id = m.event_id
    WHERE LOWER(e.title) LIKE '%room of memories%'
""")

rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()