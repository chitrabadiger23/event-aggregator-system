from flask import Flask, render_template, request
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)

print("🔥 Starting Flask App...")

# ✅ FIX 1: Proper DB path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "events.db")


# 🏠 HOME PAGE
@app.route("/")
def home():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, date, location, link, image
        FROM events
        ORDER BY id DESC
        LIMIT 6
    """)

    events = cursor.fetchall()
    conn.close()

    return render_template("home.html", events=events)


# 📄 EVENTS PAGE
@app.route("/events")
def events_page():
    filter_type = request.args.get("filter")
    search = request.args.get("search")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT title, date, location, link, image FROM events"
    params = []

    if search:
        query += " WHERE LOWER(title) LIKE ?"
        params.append('%' + search.lower() + '%')

    query += " ORDER BY id DESC"

    cursor.execute(query, params)
    events = cursor.fetchall()
    conn.close()

    filtered_events = []
    today = datetime.now()

    for e in events:
        date_str = e[1]

        try:
            event_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
        except:
            if not filter_type:
                filtered_events.append(e)
            continue

        if filter_type == "tomorrow":
            if event_date.date() == (today + timedelta(days=1)).date():
                filtered_events.append(e)

        elif filter_type == "week":
            if today <= event_date <= today + timedelta(days=7):
                filtered_events.append(e)

        elif filter_type == "month":
            if today <= event_date <= today + timedelta(days=30):
                filtered_events.append(e)

        else:
            filtered_events.append(e)

    if not filter_type:
        filtered_events = events

    if filter_type and len(filtered_events) == 0:
        filtered_events = events

    return render_template("events.html", events=filtered_events)


# ✅ FIX 2: Render-compatible run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)