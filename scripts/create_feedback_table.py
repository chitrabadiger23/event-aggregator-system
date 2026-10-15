import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(BASE_DIR, "events.db")


def create_feedback_table():
    conn = sqlite3.connect(DATABASE_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            feedback TEXT NOT NULL CHECK (
                feedback IN ('interested', 'not_interested')
            ),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    """)

    conn.commit()
    conn.close()

    print("SUCCESS: event_feedback table created.")
    print("Existing event data was NOT modified.")


if __name__ == "__main__":
    create_feedback_table()