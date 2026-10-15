import os
import re
import sqlite3
from urllib.parse import urlsplit

from rapidfuzz.fuzz import token_set_ratio


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(BASE_DIR, "events.db")

STRONG_TITLE_THRESHOLD = 85
POSSIBLE_TITLE_THRESHOLD = 90


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_text(value):
    """Normalize text for comparison."""
    if not value:
        return ""

    value = str(value).lower().strip()

    # Common city spelling
    value = value.replace("bengaluru", "bangalore")

    # Remove punctuation
    value = re.sub(r"[^a-z0-9\s]", " ", value)

    # Remove extra spaces
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_date(value):
    """Extract YYYY-MM-DD from date/time strings."""
    if not value:
        return ""

    value = str(value).strip()

    match = re.search(r"\d{4}-\d{2}-\d{2}", value)

    if match:
        return match.group(0)

    return ""


def normalize_time(value):
    """Convert common time formats to HH:MM."""
    if not value:
        return ""

    value = str(value).strip().lower()

    # Already HH:MM
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", value)

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))

        if 0 <= hour <= 23:
            return f"{hour:02d}:{minute:02d}"

    # 10am / 10 pm
    match = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        value
    )

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == "pm" and hour != 12:
            hour += 12

        if period == "am" and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    return ""


def normalize_url(url):
    """Normalize URL for exact duplicate comparison."""
    if not url:
        return ""

    try:
        parsed = urlsplit(url)

        return (
            parsed.scheme.lower()
            + "://"
            + parsed.netloc.lower()
            + parsed.path.rstrip("/")
        )

    except Exception:
        return str(url).strip().lower()


def same_venue(venue1, venue2):
    """Check whether two venues are effectively the same."""
    v1 = normalize_text(venue1)
    v2 = normalize_text(venue2)

    if not v1 or not v2:
        return False

    if v1 == v2:
        return True

    # One venue string contains the other
    if v1 in v2 or v2 in v1:
        return True

    return False


# ============================================================
# LOAD EVENTS
# ============================================================

def load_events():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
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
            m.source
        FROM events e
        LEFT JOIN event_metadata m
            ON e.id = m.event_id
        ORDER BY e.id
    """)

    events = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return events


# ============================================================
# EXACT URL DUPLICATE CHECK
# ============================================================

def find_exact_url_duplicates(events):
    """Find duplicate URLs in the database."""

    groups = {}

    for event in events:
        url = normalize_url(event.get("link"))

        if not url:
            continue

        groups.setdefault(url, []).append(event)

    duplicates = []

    for url, items in groups.items():
        if len(items) > 1:
            duplicates.append((url, items))

    return duplicates


# ============================================================
# COMPARE TWO EVENTS
# ============================================================

def compare_events(event1, event2):
    """
    Compare two events.

    Returns:
        classification
        score
        reason
    """

    title1 = normalize_text(event1.get("title"))
    title2 = normalize_text(event2.get("title"))

    date1 = normalize_date(event1.get("date"))
    date2 = normalize_date(event2.get("date"))

    time1 = normalize_time(event1.get("time"))
    time2 = normalize_time(event2.get("time"))

    venue1 = event1.get("venue") or event1.get("location")
    venue2 = event2.get("venue") or event2.get("location")

    city1 = normalize_text(event1.get("city"))
    city2 = normalize_text(event2.get("city"))

    # --------------------------------------------------------
    # DIFFERENT DATES = NOT DUPLICATE
    # --------------------------------------------------------

    if date1 and date2 and date1 != date2:
        return "NOT DUPLICATE", 0, "Different dates"

    # --------------------------------------------------------
    # DIFFERENT KNOWN TIMES = NOT DUPLICATE
    # --------------------------------------------------------

    if time1 and time2 and time1 != time2:
        return "NOT DUPLICATE", 0, "Different times"

    # --------------------------------------------------------
    # DIFFERENT KNOWN CITIES = NOT DUPLICATE
    # --------------------------------------------------------

    if city1 and city2 and city1 != city2:
        return "NOT DUPLICATE", 0, "Different cities"

    # --------------------------------------------------------
    # TITLE SIMILARITY
    # --------------------------------------------------------

    title_score = token_set_ratio(title1, title2)

    venue_match = same_venue(venue1, venue2)
    time_match = bool(time1 and time2 and time1 == time2)
    date_match = bool(date1 and date2 and date1 == date2)

    # --------------------------------------------------------
    # STRONG DUPLICATE
    #
    # Same date + same time + same venue + strong title
    # --------------------------------------------------------

    if (
        date_match
        and time_match
        and venue_match
        and title_score >= STRONG_TITLE_THRESHOLD
    ):
        return (
            "STRONG DUPLICATE",
            title_score,
            "Same date + same time + same venue + strong title"
        )

    # --------------------------------------------------------
    # STRONG DUPLICATE
    #
    # Same date + same time + very strong title
    # when venue is missing
    # --------------------------------------------------------

    if (
        date_match
        and time_match
        and not venue1
        and not venue2
        and title_score >= 95
    ):
        return (
            "STRONG DUPLICATE",
            title_score,
            "Same date + same time + very strong title"
        )

    # --------------------------------------------------------
    # POSSIBLE DUPLICATE
    #
    # Same date + same venue + high title similarity
    # but time information is incomplete.
    # --------------------------------------------------------

    if (
        date_match
        and venue_match
        and not (time1 and time2)
        and title_score >= POSSIBLE_TITLE_THRESHOLD
    ):
        return (
            "POSSIBLE DUPLICATE",
            title_score,
            "Same date + same venue + high title similarity, "
            "but time information is incomplete"
        )

    # --------------------------------------------------------
    # POSSIBLE DUPLICATE
    #
    # Same date + same time + high title similarity
    # but venue information is incomplete.
    # --------------------------------------------------------

    if (
        date_match
        and time_match
        and not venue1
        and not venue2
        and title_score >= POSSIBLE_TITLE_THRESHOLD
    ):
        return (
            "POSSIBLE DUPLICATE",
            title_score,
            "Same date + same time + high title similarity, "
            "but venue information is missing"
        )

    # --------------------------------------------------------
    # POSSIBLE DUPLICATE
    #
    # Same date + very high title similarity.
    # This is deliberately conservative.
    # --------------------------------------------------------

    if (
        date_match
        and title_score >= 97
        and (venue_match or time_match)
    ):
        return (
            "POSSIBLE DUPLICATE",
            title_score,
            "Same date + very high title similarity"
        )

    return "NOT DUPLICATE", title_score, "No strong duplicate evidence"


# ============================================================
# PRINT EVENT
# ============================================================

def print_event(event):
    print(f"ID     : {event.get('id')}")
    print(f"Title  : {event.get('title')}")
    print(f"Date   : {event.get('date')}")
    print(f"Time   : {event.get('time')}")
    print(f"Venue  : {event.get('venue') or event.get('location')}")
    print(f"City   : {event.get('city')}")
    print(f"Link   : {event.get('link')}")


# ============================================================
# MAIN AUDIT
# ============================================================

def main():

    print("=" * 70)
    print("EVENT DUPLICATE AUDIT")
    print("=" * 70)

    print(f"Database: {DATABASE_NAME}")

    if not os.path.exists(DATABASE_NAME):
        print("\nERROR: events.db was not found.")
        print("Make sure duplicate_audit.py is in the same folder as events.db.")
        return

    events = load_events()

    print(f"Events found: {len(events)}")
    print("=" * 70)

    if len(events) < 2:
        print("\nNot enough events to perform duplicate detection.")
        return

    # ========================================================
    # EXACT URL DUPLICATES
    # ========================================================

    exact_duplicates = find_exact_url_duplicates(events)

    print("\nEXACT URL DUPLICATES")
    print("-" * 70)

    if not exact_duplicates:
        print("None found.")
    else:
        print(f"Found {len(exact_duplicates)} duplicate URL groups.")

        for url, items in exact_duplicates:

            print("\nURL:")
            print(url)

            for event in items:
                print(
                    f"  ID {event['id']} - "
                    f"{event.get('title')}"
                )

    # ========================================================
    # PAIRWISE AUDIT
    # ========================================================

    strong_duplicates = []
    possible_duplicates = []

    rejected_different_dates = 0
    rejected_different_times = 0
    rejected_different_cities = 0

    total_comparisons = 0

    for i in range(len(events)):

        for j in range(i + 1, len(events)):

            event1 = events[i]
            event2 = events[j]

            total_comparisons += 1

            date1 = normalize_date(event1.get("date"))
            date2 = normalize_date(event2.get("date"))

            time1 = normalize_time(event1.get("time"))
            time2 = normalize_time(event2.get("time"))

            city1 = normalize_text(event1.get("city"))
            city2 = normalize_text(event2.get("city"))

            # ----------------------------------------------
            # Different dates
            # ----------------------------------------------

            if date1 and date2 and date1 != date2:
                rejected_different_dates += 1
                continue

            # ----------------------------------------------
            # Different times
            # ----------------------------------------------

            if time1 and time2 and time1 != time2:
                rejected_different_times += 1
                continue

            # ----------------------------------------------
            # Different cities
            # ----------------------------------------------

            if city1 and city2 and city1 != city2:
                rejected_different_cities += 1
                continue

            classification, score, reason = compare_events(
                event1,
                event2
            )

            if classification == "STRONG DUPLICATE":

                strong_duplicates.append({
                    "event1": event1,
                    "event2": event2,
                    "score": score,
                    "reason": reason
                })

            elif classification == "POSSIBLE DUPLICATE":

                possible_duplicates.append({
                    "event1": event1,
                    "event2": event2,
                    "score": score,
                    "reason": reason
                })

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n")
    print("=" * 70)
    print("AUDIT SUMMARY")
    print("=" * 70)

    print(f"Total events                  : {len(events)}")
    print(f"Total pair comparisons        : {total_comparisons}")
    print(f"Exact URL duplicate groups    : {len(exact_duplicates)}")
    print(f"Strong duplicates             : {len(strong_duplicates)}")
    print(f"Possible duplicates           : {len(possible_duplicates)}")
    print(f"Rejected - different dates    : {rejected_different_dates}")
    print(f"Rejected - different times    : {rejected_different_times}")
    print(f"Rejected - different cities   : {rejected_different_cities}")

    # ========================================================
    # STRONG DUPLICATES
    # ========================================================

    print("\n")
    print("=" * 70)
    print("STRONG DUPLICATES")
    print("=" * 70)

    if not strong_duplicates:
        print("None found.")
    else:

        for index, match in enumerate(strong_duplicates, 1):

            event1 = match["event1"]
            event2 = match["event2"]

            print("\n" + "-" * 70)
            print(f"MATCH #{index}")
            print("-" * 70)

            print("\nEVENT A")
            print("-" * 70)
            print_event(event1)

            print("\nEVENT B")
            print("-" * 70)
            print_event(event2)

            print("\nMATCH ANALYSIS")
            print("-" * 70)
            print(f"Title similarity : {match['score']:.1f}")
            print(f"Reason           : {match['reason']}")

    # ========================================================
    # POSSIBLE DUPLICATES
    # ========================================================

    print("\n")
    print("=" * 70)
    print("POSSIBLE DUPLICATES")
    print("=" * 70)

    if not possible_duplicates:
        print("None found.")
    else:

        for index, match in enumerate(possible_duplicates, 1):

            event1 = match["event1"]
            event2 = match["event2"]

            print("\n" + "-" * 70)
            print(f"MATCH #{index}")
            print("-" * 70)

            print("\nEVENT A")
            print("-" * 70)
            print_event(event1)

            print("\nEVENT B")
            print("-" * 70)
            print_event(event2)

            print("\nMATCH ANALYSIS")
            print("-" * 70)
            print(f"Title similarity : {match['score']:.1f}")
            print(f"Reason           : {match['reason']}")

    # ========================================================
    # FINAL MESSAGE
    # ========================================================

    print("\n")
    print("=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)

    print("\nIMPORTANT:")
    print("This script is READ-ONLY.")
    print("It does NOT delete, update, or insert any events.")
    print("Review the strong/possible matches before removing anything.")

    print("=" * 70)


if __name__ == "__main__":
    main()