import sqlite3

conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute("""
DELETE FROM events
WHERE id NOT IN (
    SELECT MIN(id)
    FROM events
    GROUP BY link
)
""")

conn.commit()
conn.close()

print("✅ Old duplicates removed!")