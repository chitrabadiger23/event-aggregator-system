"""
Improved Event Categorization Script
------------------------------------
Reads events from events.db and creates/updates ONLY event_categories.

It does NOT delete or modify existing events.

Run from project root:
    python scripts/categorize_events.py
"""

import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(BASE_DIR, "events.db")

# More comprehensive keywords.
CATEGORY_KEYWORDS = {
    "Technology": [
        "technology", "tech", "python", "java", "javascript", "react",
        "machine learning", "ml", "artificial intelligence", "artificial intelligence",
        "ai", "data science", "data analytics", "analytics", "cloud",
        "aws", "azure", "oracle", "cyber security", "cybersecurity",
        "coding", "programming", "developer", "software", "web development",
        "app development", "blockchain", "robotics", "hackathon", "computer",
        "it ", "information technology", "generative ai", "genai", "llm",
        "deep learning", "devops", "database", "sql", "power bi", "tableau",
        "digital transformation", "startup tech", "tech meetup", "tech talk",
    ],

    "Business": [
        "business", "startup", "start-up", "entrepreneur", "entrepreneurship",
        "marketing", "finance", "investment", "investing", "leadership",
        "management", "networking", "founder", "sales", "corporate",
        "career", "job fair", "recruitment", "professional", "commerce",
        "brand", "branding", "business meetup", "pitch", "funding",
        "venture", "workplace", "hr", "human resources",
    ],

    "Education": [
        "education", "seminar", "lecture", "conference", "training",
        "learning", "student", "college", "university", "academic",
        "exam", "scholarship", "study", "knowledge", "orientation",
        "webinar", "tutorial", "certification", "course", "career guidance",
        "awareness session",
    ],

    "Music": [
        "music", "concert", "live music", "singer", "singing", "dj",
        "band", "guitar", "piano", "drum", "musical", "jazz", "rock",
        "classical", "karaoke", "melody", "acoustic", "live performance",
        "music night", "open mic", "rap", "hip hop", "indie music",
    ],

    "Sports": [
        "sport", "sports", "cricket", "football", "soccer", "basketball",
        "badminton", "tennis", "volleyball", "marathon", "cycling",
        "running", "yoga", "fitness", "swimming", "kabaddi", "chess",
        "table tennis", "boxing", "wrestling", "athletics", "tournament",
        "league", "race", "5k", "10k", "half marathon", "gym",
    ],

    "Comedy": [
        "comedy", "standup", "stand-up", "stand up", "comedian",
        "funny", "roast", "improv", "improvisation", "humour", "humor",
        "comic", "comedy night",
    ],

    "Theatre": [
        "theatre", "theater", "drama", "stage play", "stage", "acting",
        "performing arts", "performance", "play", "musical theatre",
        "dance performance", "dance show", "ballet", "mime",
        "storytelling", "live show",
    ],

    "Art": [
        "art", "painting", "drawing", "sketch", "craft", "creative",
        "photography", "exhibition", "gallery", "sculpture", "pottery",
        "ceramic", "ceramics", "oil pastel", "watercolor", "water colour",
        "calligraphy", "illustration", "design", "diy", "handmade",
        "art workshop", "painting workshop", "craft workshop",
        "photography workshop", "rangoli", "mandala",
    ],

    "Workshop": [
        "workshop", "masterclass", "hands-on", "hands on", "bootcamp",
        "boot camp", "training workshop", "skill workshop", "interactive session",
    ],

    "Food": [
        "food", "cooking", "cook", "baking", "bake", "culinary",
        "chef", "restaurant", "tasting", "cake", "chocolate", "brownie",
        "recipe", "kitchen", "food festival", "food walk", "food tour",
        "wine tasting", "coffee", "barbecue", "bbq", "dessert",
    ],

    "Festival": [
        "festival", "fest", "celebration", "celebrate", "janmashtami",
        "krishna", "ganesh", "ganesha", "diwali", "deepavali", "holi",
        "navratri", "dussehra", "christmas", "new year", "independence day",
        "republic day", "ugadi", "onam", "pongal", "eid", "ramzan",
        "raksha bandhan", "durga puja", "navaratri", "cultural festival",
        "cultural celebration",
    ],
}

# Strong phrases should influence classification more than generic words.
STRONG_PHRASES = {
    "Technology": [
        "machine learning", "data science", "artificial intelligence",
        "generative ai", "cyber security", "web development",
        "software development", "coding workshop", "hackathon",
        "tech meetup", "python workshop", "ai workshop",
    ],
    "Business": [
        "startup meetup", "business networking", "entrepreneur meetup",
        "investor meetup", "career fair", "job fair", "business conference",
    ],
    "Music": [
        "live music", "music concert", "live concert", "music night",
        "dj night", "open mic", "live band",
    ],
    "Comedy": [
        "stand up comedy", "stand-up comedy", "comedy night", "open mic comedy",
    ],
    "Sports": [
        "cricket tournament", "football tournament", "badminton tournament",
        "marathon", "half marathon", "cycling event", "fitness event",
    ],
    "Art": [
        "painting workshop", "art workshop", "pottery workshop",
        "ceramic workshop", "photography workshop", "craft workshop",
        "oil pastel workshop",
    ],
    "Food": [
        "cooking workshop", "baking workshop", "food festival",
        "food walk", "cake workshop", "chocolate workshop",
    ],
    "Festival": [
        "cultural festival", "festival celebration", "ganesh festival",
        "diwali celebration", "christmas celebration",
    ],
}


def normalize_text(value):
    if value is None:
        return ""

    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9+#.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_phrase(text, phrase):
    phrase = normalize_text(phrase)

    if not phrase:
        return False

    pattern = r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])"
    return bool(re.search(pattern, text))


def get_matches(text, keywords):
    return [keyword for keyword in keywords if contains_phrase(text, keyword)]


def categorize_event(title, venue="", city="", source=""):
    """
    Returns:
        category, confidence, matched_keywords

    Confidence is a heuristic score, NOT an ML probability.
    """

    title_text = normalize_text(title)

    # Title is intentionally dominant.
    scores = {}
    matched = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        title_matches = get_matches(title_text, keywords)

        # Supporting text is used only as a small secondary signal.
        supporting_text = normalize_text(
            " ".join(
                str(x) for x in [venue, city, source]
                if x
            )
        )
        support_matches = get_matches(supporting_text, keywords)

        score = len(title_matches) * 5 + len(support_matches)

        # Strong phrases receive an additional boost.
        strong_matches = [
            phrase
            for phrase in STRONG_PHRASES.get(category, [])
            if contains_phrase(title_text, phrase)
        ]

        score += len(strong_matches) * 8

        if score > 0:
            scores[category] = score
            matched[category] = list(
                dict.fromkeys(title_matches + strong_matches + support_matches)
            )

    if not scores:
        return "Other", 0.0, []

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    best_category, best_score = ranked[0]

    # If two categories are close, prefer the one with the strongest
    # title evidence. Workshop is treated as a format, so if the
    # title clearly describes Art/Music/Food/Technology, that category
    # is preferred over generic Workshop.
    if len(ranked) > 1:
        second_category, second_score = ranked[1]

        if best_category == "Workshop" and second_category != "Workshop":
            if second_score >= best_score * 0.35:
                best_category = second_category
                best_score = second_score

    total_score = sum(scores.values())
    confidence = best_score / total_score if total_score else 0.0

    # Avoid forcing weak matches.
    if confidence < 0.40:
        return "Other", round(confidence, 3), matched[ranked[0][0]]

    return (
        best_category,
        round(min(confidence, 1.0), 3),
        matched.get(best_category, []),
    )


def main():
    print("=" * 72)
    print("IMPROVED EVENT CATEGORIZATION")
    print("=" * 72)
    print("Database:", DATABASE_NAME)
    print("Existing events will NOT be modified.")

    if not os.path.exists(DATABASE_NAME):
        print("\nERROR: events.db not found.")
        return

    connection = sqlite3.connect(DATABASE_NAME)

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS event_categories (
                event_id INTEGER PRIMARY KEY,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY(event_id) REFERENCES events(id)
            )
            """
        )

        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.location,
                COALESCE(m.venue, ''),
                COALESCE(m.city, ''),
                COALESCE(m.source, '')
            FROM events e
            LEFT JOIN event_metadata m
                ON e.id = m.event_id
            ORDER BY e.id
            """
        )

        events = cursor.fetchall()

        print("Events found:", len(events))

        if not events:
            connection.commit()
            print("\nNo events found.")
            return

        counts = {}

        for event_id, title, location, venue, city, source in events:
            actual_venue = venue.strip() if venue else location

            category, confidence, matches = categorize_event(
                title=title,
                venue=actual_venue,
                city=city,
                source=source,
            )

            cursor.execute(
                """
                INSERT INTO event_categories
                    (event_id, category, confidence)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id)
                DO UPDATE SET
                    category = excluded.category,
                    confidence = excluded.confidence
                """,
                (event_id, category, confidence),
            )

            counts[category] = counts.get(category, 0) + 1

            print(
                f"{event_id:4d} | "
                f"{category:12s} | "
                f"{confidence:.2f} | "
                f"{title}"
            )

        connection.commit()

        print("\n" + "=" * 72)
        print("NEW CATEGORY SUMMARY")
        print("=" * 72)

        for category, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0])
        ):
            percentage = (count / len(events)) * 100
            print(
                f"{category:15s}: "
                f"{count:3d} ({percentage:5.1f}%)"
            )

        print("\nTotal categorized:", len(events))
        print("SUCCESS: event_categories table updated.")
        print("Existing events were NOT modified.")

    except Exception as error:
        connection.rollback()
        print("\nERROR:", type(error).__name__)
        print("Message:", error)
        print("Changes were rolled back.")

    finally:
        connection.close()


if __name__ == "__main__":
    main()
