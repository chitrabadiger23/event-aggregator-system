import sqlite3
import os
import re
from rapidfuzz.fuzz import token_set_ratio


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "events.db")


# ============================================================
# THRESHOLDS
# ============================================================

TITLE_STRONG_THRESHOLD = 85
TITLE_EXACT_THRESHOLD = 95


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    text = text.replace("bengaluru", "bangalore")

    text = re.sub(r"[^\w\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# NORMALIZE DATE
# ============================================================

def normalize_date(value):

    if not value:
        return ""

    value = str(value).strip()

    if value.upper() == "N/A":
        return ""

    return value[:10]


# ============================================================
# NORMALIZE TIME
# ============================================================

def normalize_time(value):

    if not value:
        return ""

    value = str(value).strip()

    if value.upper() == "N/A":
        return ""

    match = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        value
    )

    if match:

        hour = int(match.group(1))
        minute = match.group(2)

        return f"{hour:02d}:{minute}"

    return value


# ============================================================
# TITLE SIMILARITY
# ============================================================

def title_similarity(title1, title2):

    a = normalize_text(title1)
    b = normalize_text(title2)

    if not a or not b:
        return 0

    return token_set_ratio(a, b)


# ============================================================
# VENUE MATCH
# ============================================================

def venues_match(venue1, venue2):

    a = normalize_text(venue1)
    b = normalize_text(venue2)

    if not a or not b:
        return False

    if a in ("n a", "na"):
        return False

    if b in ("n a", "na"):
        return False

    if a == b:
        return True

    if len(a) > 10 and len(b) > 10:

        if a in b or b in a:
            return True

    return False


# ============================================================
# BUILD EVENT
# ============================================================

def build_event(row):

    return {

        "id": row[0],

        "title": row[1] or "",

        "date": row[2] or "",

        "location": row[3] or "",

        "link": row[4] or "",

        "time": row[5] or "N/A",

        "venue": row[6] or "N/A",

        "city": row[7] or "Bangalore",

        "source": row[8] or ""
    }


# ============================================================
# GET DATABASE EVENTS
# ============================================================

def get_database_events():

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            e.id,
            e.title,
            e.date,
            e.location,
            e.link,
            m.time,
            m.venue,
            m.city,
            m.source
        FROM events e
        LEFT JOIN event_metadata m
            ON e.id = m.event_id
    """)

    rows = cursor.fetchall()

    conn.close()

    return [
        build_event(row)
        for row in rows
    ]


# ============================================================
# DIAGNOSTIC DUPLICATE CHECK
# ============================================================

def is_duplicate(new_event, diagnostic=False):

    existing_events = get_database_events()

    new_link = str(
        new_event.get("link", "")
    ).strip()

    new_title = str(
        new_event.get("title", "")
    ).strip()

    new_date = normalize_date(
        new_event.get("date", "")
    )

    new_time = normalize_time(
        new_event.get("time", "")
    )

    new_venue = str(
        new_event.get("venue", "")
    ).strip()

    new_city = normalize_text(
        new_event.get("city", "Bangalore")
    )


    # ========================================================
    # LEVEL 1 — EXACT URL
    # ========================================================

    for existing in existing_events:

        existing_link = str(
            existing.get("link", "")
        ).strip()

        if (
            new_link
            and existing_link
            and new_link == existing_link
        ):

            if diagnostic:

                print()
                print("=" * 70)
                print("⚠️ EXACT URL DUPLICATE")
                print("=" * 70)

                print(
                    "New:",
                    new_title
                )

                print(
                    "Existing:",
                    existing["title"]
                )

                print(
                    "URL:",
                    new_link
                )

                print("=" * 70)

            return True, existing


    # ========================================================
    # LEVEL 2 — SAME DATE ONLY
    # ========================================================

    if not new_date:

        return False, None


    for existing in existing_events:

        existing_date = normalize_date(
            existing.get("date", "")
        )

        # Different date = NOT duplicate
        if new_date != existing_date:

            continue


        # ====================================================
        # CITY CHECK
        # ====================================================

        existing_city = normalize_text(
            existing.get("city", "")
        )

        if (
            new_city
            and existing_city
            and new_city != existing_city
        ):

            continue


        # ====================================================
        # TIME CHECK
        #
        # If both are known and different,
        # they are definitely different events.
        # ====================================================

        existing_time = normalize_time(
            existing.get("time", "")
        )

        if (
            new_time
            and existing_time
            and new_time != existing_time
        ):

            continue


        # ====================================================
        # TITLE
        # ====================================================

        existing_title = existing.get(
            "title",
            ""
        )

        score = title_similarity(
            new_title,
            existing_title
        )


        # ====================================================
        # VENUE
        # ====================================================

        existing_venue = existing.get(
            "venue",
            ""
        )

        same_venue = venues_match(
            new_venue,
            existing_venue
        )


        # ====================================================
        # RULE 1
        #
        # Same date
        # Same time
        # Same venue
        # Strong title
        # ====================================================

        if (
            new_time
            and existing_time
            and new_time == existing_time
            and same_venue
            and score >= TITLE_STRONG_THRESHOLD
        ):

            if diagnostic:

                print_match(
                    new_event,
                    existing,
                    score,
                    "SAME DATE + SAME TIME + SAME VENUE + STRONG TITLE"
                )

            return True, existing


        # ====================================================
        # RULE 2
        #
        # Same venue
        # Very high title similarity
        # ====================================================

        if (
            same_venue
            and score >= TITLE_EXACT_THRESHOLD
        ):

            if diagnostic:

                print_match(
                    new_event,
                    existing,
                    score,
                    "SAME DATE + SAME VENUE + VERY HIGH TITLE"
                )

            return True, existing


        # ====================================================
        # RULE 3
        #
        # Same time
        # Very high title similarity
        # ====================================================

        if (
            new_time
            and existing_time
            and new_time == existing_time
            and score >= TITLE_EXACT_THRESHOLD
        ):

            if diagnostic:

                print_match(
                    new_event,
                    existing,
                    score,
                    "SAME DATE + SAME TIME + VERY HIGH TITLE"
                )

            return True, existing


    return False, None


# ============================================================
# PRINT MATCH
# ============================================================

def print_match(
    new_event,
    existing,
    score,
    reason
):

    print()
    print("=" * 70)
    print("⚠️ FUZZY DUPLICATE MATCH")
    print("=" * 70)

    print()
    print("NEW EVENT")
    print("-" * 70)

    print(
        "ID: NEW"
    )

    print(
        "Title:",
        new_event.get("title")
    )

    print(
        "Date:",
        new_event.get("date")
    )

    print(
        "Time:",
        new_event.get("time")
    )

    print(
        "Venue:",
        new_event.get("venue")
    )

    print(
        "City:",
        new_event.get("city")
    )

    print(
        "Link:",
        new_event.get("link")
    )


    print()
    print("EXISTING EVENT")
    print("-" * 70)

    print(
        "ID:",
        existing.get("id")
    )

    print(
        "Title:",
        existing.get("title")
    )

    print(
        "Date:",
        existing.get("date")
    )

    print(
        "Time:",
        existing.get("time")
    )

    print(
        "Venue:",
        existing.get("venue")
    )

    print(
        "City:",
        existing.get("city")
    )

    print(
        "Link:",
        existing.get("link")
    )


    print()
    print("MATCH ANALYSIS")
    print("-" * 70)

    print(
        "Title similarity:",
        round(score, 2)
    )

    print(
        "Same date:",
        normalize_date(
            new_event.get("date")
        )
        ==
        normalize_date(
            existing.get("date")
        )
    )

    print(
        "Same time:",
        normalize_time(
            new_event.get("time")
        )
        ==
        normalize_time(
            existing.get("time")
        )
    )

    print(
        "Same venue:",
        venues_match(
            new_event.get("venue"),
            existing.get("venue")
        )
    )

    print()
    print(
        "Reason:",
        reason
    )

    print("=" * 70)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("DUPLICATE DETECTOR DIAGNOSTIC TEST")
    print("=" * 70)

    print(
        "Database:",
        DB_PATH
    )

    events = get_database_events()

    print(
        "Existing events:",
        len(events)
    )

    print("=" * 70)

    # --------------------------------------------------------
    # TEST EVENT
    # --------------------------------------------------------

    test_event = {

        "title":
            "Sri Krishna Janmashtami Ananda Mahotsava 2026",

        "date":
            "2026-09-04",

        "time":
            "10:00",

        "venue":
            "KARNATAKA TRADE PROMOTION ORGANISATION",

        "city":
            "Bangalore",

        "link":
            "https://example.com/test-event"

    }

    duplicate, existing = is_duplicate(
        test_event,
        diagnostic=True
    )

    print()

    if duplicate:

        print(
            "RESULT: ⚠️ DUPLICATE"
        )

    else:

        print(
            "RESULT: ✅ NOT A DUPLICATE"
        )

    print("=" * 70)