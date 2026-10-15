"""
Content-Based Event Recommendation System
------------------------------------------
Reads the existing SQLite event database and event_categories table.
Does NOT modify the database.

Usage:
    python scripts/recommendation.py
    python scripts/recommendation.py --interests "technology, workshop"
    python scripts/recommendation.py --interests "music, comedy" --top 5
    python scripts/recommendation.py --category Technology --top 5

Dependency:
    pip install scikit-learn
"""

import argparse
import os
import re
import sqlite3
from datetime import datetime

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    print("ERROR: scikit-learn is not installed.")
    print("Install it with: pip install scikit-learn")
    raise SystemExit(1)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(BASE_DIR, "events.db")


def parse_date(date_str):
    """Convert common ISO/date formats into a datetime object."""
    if not date_str:
        return None

    value = str(date_str).strip()

    # Handle ISO timestamps ending in Z.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(value)
        # Make timezone-aware values comparable with local naive time.
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def parse_time(time_str):
    """Convert a time such as 14:00 or 2:00 PM into a time object."""
    if not time_str:
        return None

    value = str(time_str).strip().upper()

    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue

    return None


def is_upcoming(date_str, time_str=None):
    """
    Keep future events.
    For today's events:
      - future time -> keep
      - past time -> remove
      - missing/invalid time -> keep
    """
    event_date = parse_date(date_str)

    if event_date is None:
        return False

    now = datetime.now()

    if event_date.date() > now.date():
        return True

    if event_date.date() < now.date():
        return False

    event_time = parse_time(time_str)

    if event_time is None:
        return True

    return event_time >= now.time()


def normalize_text(value):
    """Normalize text for matching and display."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def load_events():
    """Load upcoming events and their categories from SQLite."""
    if not os.path.exists(DATABASE_NAME):
        print(f"ERROR: Database not found: {DATABASE_NAME}")
        raise SystemExit(1)

    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            e.id,
            e.title,
            e.date,
            e.location,
            e.link,
            e.image,
            m.time,
            m.venue,
            m.city,
            m.source,
            c.category,
            c.confidence
        FROM events e
        LEFT JOIN event_metadata m
            ON e.id = m.event_id
        LEFT JOIN event_categories c
            ON e.id = c.event_id
        ORDER BY e.date ASC
    """

    rows = conn.execute(query).fetchall()
    conn.close()

    upcoming = []

    for row in rows:
        if not is_upcoming(row["date"], row["time"]):
            continue

        event = {
            "id": row["id"],
            "title": normalize_text(row["title"]) or "Untitled Event",
            "date": normalize_text(row["date"]),
            "location": normalize_text(row["location"]),
            "link": normalize_text(row["link"]),
            "image": normalize_text(row["image"]),
            "time": normalize_text(row["time"]),
            "venue": normalize_text(row["venue"]),
            "city": normalize_text(row["city"]),
            "source": normalize_text(row["source"]),
            "category": normalize_text(row["category"]) or "Other",
            "confidence": row["confidence"],
        }

        upcoming.append(event)

    return upcoming


def build_document(event):
    """
    Create a text representation of an event.

    Title and category are repeated to give them slightly more influence
    than venue/city/source in the TF-IDF representation.
    """
    title = event["title"]
    category = event["category"]
    venue = event["venue"] or event["location"]
    city = event["city"]
    source = event["source"]

    return " ".join([
        title, title, title,
        category, category, category,
        venue,
        city,
        source,
    ])


def tokenize_interests(interests):
    """Return clean comma-separated interest terms."""
    return [
        item.strip()
        for item in interests.split(",")
        if item.strip()
    ]


def recommend(events, interests, top_n=5, category=None):
    """Generate content-based recommendations using TF-IDF + cosine similarity."""
    if not events:
        return []

    interest_list = tokenize_interests(interests)
    if not interest_list:
        return []

    documents = [build_document(event) for event in events]

    # Add the user's interests as a final document.
    user_profile = " ".join(interest_list)
    documents.append(user_profile)

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
    )

    matrix = vectorizer.fit_transform(documents)

    user_vector = matrix[-1]
    event_vectors = matrix[:-1]

    similarities = cosine_similarity(user_vector, event_vectors).flatten()

    results = []

    requested_category = normalize_text(category).lower() if category else ""

    for index, event in enumerate(events):
        score = float(similarities[index])

        # A small, transparent boost for an exact requested category.
        if requested_category:
            if event["category"].lower() == requested_category:
                score += 0.15
            elif requested_category in event["category"].lower():
                score += 0.08

        results.append((score, event))

    results.sort(
        key=lambda item: (
            item[0],
            parse_date(item[1]["date"]) or datetime.max,
        ),
        reverse=True,
    )

    # Remove events with no similarity
    results = [
        (score, event)
        for score, event in results
        if score > 0
    ]

    return results[:top_n]


def print_recommendations(results):
    """Display recommendations in a terminal-friendly format."""
    print("\n" + "=" * 70)
    print("RECOMMENDED UPCOMING EVENTS")
    print("=" * 70)

    if not results:
        print("No matching events found.")
        return

    for rank, (score, event) in enumerate(results, start=1):
        print(f"\n{rank}. {event['title']}")
        print(f"   Category   : {event['category']}")
        print(f"   Date       : {event['date']}")
        print(f"   Time       : {event['time'] or 'Not available'}")
        print(f"   Venue      : {event['venue'] or event['location'] or 'Not available'}")
        print(f"   City       : {event['city'] or 'Not available'}")
        print(f"   Match Score: {score:.3f}")
        if event["link"]:
            print(f"   Link       : {event['link']}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Recommend upcoming events using TF-IDF and cosine similarity."
    )

    parser.add_argument(
        "--interests",
        type=str,
        help='Comma-separated interests, e.g. "technology, workshop"',
    )

    parser.add_argument(
        "--category",
        type=str,
        help='Optional category filter/boost, e.g. "Technology"',
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of recommendations to display (default: 5)",
    )

    args = parser.parse_args()

    interests = args.interests

    if not interests:
        print("CONTENT-BASED EVENT RECOMMENDER")
        print("-" * 40)
        interests = input(
            "Enter your interests (comma-separated): "
        ).strip()

    if not interests:
        print("Please enter at least one interest.")
        return

    top_n = max(1, args.top)

    events = load_events()

    print(f"\nUpcoming events available: {len(events)}")
    print(f"Your interests: {interests}")

    if args.category:
        print(f"Category preference: {args.category}")

    results = recommend(
        events=events,
        interests=interests,
        top_n=top_n,
        category=args.category,
    )

    print_recommendations(results)


if __name__ == "__main__":
    main()
