import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "events.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    UPDATE events
    SET location = (
        SELECT venue
        FROM event_metadata
        WHERE event_metadata.event_id = events.id
    )
    WHERE id IN (45, 56)
""")

conn.commit()

print("Locations updated successfully.")

cursor.execute("""
    SELECT
        e.id,
        e.title,
        e.location,
        m.venue
    FROM events e
    LEFT JOIN event_metadata m
        ON e.id = m.event_id
    WHERE e.id IN (45, 56)
""")

for row in cursor.fetchall():
    print(row)

conn.close()