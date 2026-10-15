import sqlite3
import os
import re
from rapidfuzz.fuzz import token_set_ratio


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_PATH = os.path.join(
    BASE_DIR,
    "events.db"
)


# ============================================================
# SETTINGS
# ============================================================

THRESHOLD = 88

# If two events have known different times,
# treat them as separate sessions.
REJECT_DIFFERENT_TIMES = True

# If two events have known different dates,
# they are normally separate events.
REJECT_DIFFERENT_DATES = True


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    # Normalize Bengaluru/Bangalore
    text = text.replace(
        "bengaluru",
        "bangalore"
    )

    # Remove punctuation
    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# NORMALIZE TIME
# ============================================================

def normalize_time(time):

    if not time:
        return ""

    time = str(time).strip().upper()

    if time in ["N/A", "NA", "NONE", "NULL"]:
        return ""

    # 10:00 AM
    match = re.match(
        r"^(\d{1,2}):(\d{2})\s*(AM|PM)$",
        time
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)

        if period == "PM" and hour != 12:
            hour += 12

        if period == "AM" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"


    # 10 AM
    match = re.match(
        r"^(\d{1,2})\s*(AM|PM)$",
        time
    )

    if match:

        hour = int(match.group(1))
        period = match.group(2)

        if period == "PM" and hour != 12:
            hour += 12

        if period == "AM" and hour == 12:
            hour = 0

        return f"{hour:02d}:00"


    # 10:00
    match = re.match(
        r"^(\d{1,2}):(\d{2})$",
        time
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2))

        return f"{hour:02d}:{minute:02d}"


    return normalize_text(time)


# ============================================================
# NORMALIZE DATE
# ============================================================

def normalize_date(date):

    if not date:
        return ""

    date = str(date).strip()

    if date.upper() in [
        "N/A",
        "NA",
        "NONE",
        "NULL"
    ]:
        return ""

    # ISO date:
    # 2026-09-04T10:00:00+05:30
    if len(date) >= 10:

        possible_date = date[:10]

        if re.match(
            r"^\d{4}-\d{2}-\d{2}$",
            possible_date
        ):
            return possible_date

    return date


# ============================================================
# TEXT SIMILARITY
# ============================================================

def similarity(a, b):

    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0

    return token_set_ratio(a, b)


# ============================================================
# DATE SIMILARITY
# ============================================================

def date_similarity(a, b):

    a = normalize_date(a)
    b = normalize_date(b)

    if not a or not b:
        return 0

    return 100 if a == b else 0


# ============================================================
# TIME SIMILARITY
# ============================================================

def time_similarity(a, b):

    a = normalize_time(a)
    b = normalize_time(b)

    if not a or not b:
        return 0

    return 100 if a == b else 0


# ============================================================
# VENUE SIMILARITY
# ============================================================

def venue_similarity(a, b):

    a = normalize_text(a)
    b = normalize_text(b)

    if not a or not b:
        return 0

    return token_set_ratio(a, b)


# ============================================================
# DUPLICATE SCORE
# ============================================================

def duplicate_score(a, b):

    title_score = similarity(
        a["title"],
        b["title"]
    )

    venue_score = venue_similarity(
        a["venue"],
        b["venue"]
    )

    city_score = similarity(
        a["city"],
        b["city"]
    )

    date_score = date_similarity(
        a["date"],
        b["date"]
    )

    time_score = time_similarity(
        a["time"],
        b["time"]
    )

    # --------------------------------------------------------
    # BASE SCORE
    # --------------------------------------------------------

    score = (

        title_score * 0.40

        + date_score * 0.25

        + venue_score * 0.20

        + city_score * 0.10

        + time_score * 0.05

    )


    # --------------------------------------------------------
    # PENALIZE CLEARLY DIFFERENT VENUES
    # --------------------------------------------------------

    venue_a = normalize_text(
        a["venue"]
    )

    venue_b = normalize_text(
        b["venue"]
    )

    if (
        venue_a
        and venue_b
    ):

        if venue_score < 40:

            score *= 0.65


    return round(
        score,
        2
    )


# ============================================================
# HARD DUPLICATE CHECK
# ============================================================

def should_compare(a, b):

    date_a = normalize_date(
        a["date"]
    )

    date_b = normalize_date(
        b["date"]
    )

    time_a = normalize_time(
        a["time"]
    )

    time_b = normalize_time(
        b["time"]
    )


    # --------------------------------------------------------
    # DIFFERENT KNOWN DATES
    # --------------------------------------------------------

    if (
        REJECT_DIFFERENT_DATES
        and date_a
        and date_b
        and date_a != date_b
    ):

        return False, "different dates"


    # --------------------------------------------------------
    # DIFFERENT KNOWN TIMES
    #
    # Example:
    #
    # Room of Memories 11:00
    # Room of Memories 14:00
    #
    # Same event title, but separate sessions.
    # --------------------------------------------------------

    if (
        REJECT_DIFFERENT_TIMES
        and time_a
        and time_b
        and time_a != time_b
    ):

        return False, "different times"


    return True, ""


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(
    DB_PATH
)

cursor = conn.cursor()


cursor.execute("""
SELECT
    e.id,
    e.title,
    e.date,
    e.link,
    m.time,
    m.venue,
    m.city,
    m.source
FROM events e
LEFT JOIN event_metadata m
ON e.id = m.event_id
ORDER BY e.id
""")


rows = cursor.fetchall()

conn.close()


# ============================================================
# BUILD EVENTS
# ============================================================

events = []


for row in rows:

    events.append({

        "id": row[0],

        "title": row[1] or "",

        "date": row[2] or "",

        "link": row[3] or "",

        "time": row[4] or "N/A",

        "venue": row[5] or "N/A",

        "city": row[6] or "Bangalore",

        "source": row[7] or ""

    })


# ============================================================
# HEADER
# ============================================================

print()

print("=" * 70)

print(
    "DUPLICATE EVENT AUDIT - VERSION 3"
)

print("=" * 70)

print(
    "Database:",
    DB_PATH
)

print(
    "Total events:",
    len(events)
)

print("=" * 70)


# ============================================================
# COMPARE EVENTS
# ============================================================

duplicates_found = 0

highest_score = 0

best_pair = None

rejected_time_pairs = 0

rejected_date_pairs = 0


for i in range(
    len(events)
):

    for j in range(
        i + 1,
        len(events)
    ):

        event1 = events[i]

        event2 = events[j]


        # ----------------------------------------------------
        # HARD RULES
        # ----------------------------------------------------

        allowed, reason = should_compare(
            event1,
            event2
        )


        if not allowed:

            if reason == "different times":
                rejected_time_pairs += 1

            elif reason == "different dates":
                rejected_date_pairs += 1

            continue


        # ----------------------------------------------------
        # CALCULATE SCORE
        # ----------------------------------------------------

        score = duplicate_score(
            event1,
            event2
        )


        # ----------------------------------------------------
        # TRACK HIGHEST VALID SCORE
        # ----------------------------------------------------

        if score > highest_score:

            highest_score = score

            best_pair = (
                event1,
                event2
            )


        # ----------------------------------------------------
        # POSSIBLE DUPLICATE
        # ----------------------------------------------------

        if score >= THRESHOLD:

            duplicates_found += 1

            print()

            print(
                "⚠️ POSSIBLE DUPLICATE"
            )

            print("-" * 70)


            # Event 1

            print(
                f"Event 1 ID: "
                f"{event1['id']}"
            )

            print(
                f"Title: "
                f"{event1['title']}"
            )

            print(
                f"Date: "
                f"{event1['date']}"
            )

            print(
                f"Time: "
                f"{event1['time']}"
            )

            print(
                f"Venue: "
                f"{event1['venue']}"
            )

            print(
                f"Source: "
                f"{event1['source']}"
            )


            print()


            # Event 2

            print(
                f"Event 2 ID: "
                f"{event2['id']}"
            )

            print(
                f"Title: "
                f"{event2['title']}"
            )

            print(
                f"Date: "
                f"{event2['date']}"
            )

            print(
                f"Time: "
                f"{event2['time']}"
            )

            print(
                f"Venue: "
                f"{event2['venue']}"
            )

            print(
                f"Source: "
                f"{event2['source']}"
            )


            print()


            print(
                f"Similarity Score: "
                f"{score}"
            )

            print(
                "-" * 70
            )


# ============================================================
# HIGHEST MATCH
# ============================================================

print()

print("=" * 70)

print(
    "HIGHEST VALID SIMILARITY FOUND"
)

print("=" * 70)

print(
    f"Highest score: "
    f"{highest_score}"
)


if best_pair:

    print()

    print(
        "Event 1:",
        best_pair[0]["title"]
    )

    print(
        "Event 2:",
        best_pair[1]["title"]
    )

    print(
        "Date 1:",
        best_pair[0]["date"]
    )

    print(
        "Date 2:",
        best_pair[1]["date"]
    )

    print(
        "Venue 1:",
        best_pair[0]["venue"]
    )

    print(
        "Venue 2:",
        best_pair[1]["venue"]
    )

    print(
        "Time 1:",
        best_pair[0]["time"]
    )

    print(
        "Time 2:",
        best_pair[1]["time"]
    )


# ============================================================
# STATISTICS
# ============================================================

print()

print("=" * 70)

print(
    "FILTER STATISTICS"
)

print("=" * 70)

print(
    "Pairs rejected because of different dates:",
    rejected_date_pairs
)

print(
    "Pairs rejected because of different times:",
    rejected_time_pairs
)


# ============================================================
# SUMMARY
# ============================================================

print()

print("=" * 70)

print(
    "AUDIT COMPLETE"
)

print("=" * 70)

print(
    f"Possible duplicate pairs: "
    f"{duplicates_found}"
)


if duplicates_found == 0:

    print(
        "✅ No possible duplicates found."
    )

else:

    print(
        "⚠️ Review the pairs before deleting anything."
    )


print("=" * 70)