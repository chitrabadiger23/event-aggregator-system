from flask import Flask, render_template, request, session, redirect
from scripts.recommendation import load_events, recommend
import sqlite3
from scripts.nlp_search import parse_query
from datetime import datetime, timedelta
import os
import re


app = Flask(__name__)

# Used to store search history in the browser session
app.secret_key = "event-aggregator-secret-key"

print("🔥 Starting Flask App...")


# ============================================================
# DATABASE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "events.db")


# ============================================================
# CHECK IF EVENT IS UPCOMING
# ============================================================

def is_upcoming(date_str, time_str=None):

    if not date_str:
        return False

    try:
        event_date = datetime.strptime(
            str(date_str)[:10],
            "%Y-%m-%d"
        ).date()

    except (ValueError, TypeError):
        return False

    now = datetime.now()
    today = now.date()

    # Future date
    if event_date > today:
        return True

    # Past date
    if event_date < today:
        return False

    # Today but no time
    if not time_str:
        return True

    time_str = str(time_str).strip().lower()

    hour = None
    minute = None

    # Example:
    # 10:30
    match = re.search(
        r"\b(\d{1,2}):(\d{2})\b",
        time_str
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2))

    else:

        # Examples:
        # 10am
        # 10 pm
        # 10:30pm
        match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
            time_str
        )

        if match:

            hour = int(match.group(1))
            minute = int(match.group(2) or 0)

            period = match.group(3)

            if period == "pm" and hour != 12:
                hour += 12

            elif period == "am" and hour == 12:
                hour = 0

    # Unknown time format
    if hour is None:
        return True

    try:

        event_datetime = datetime(
            today.year,
            today.month,
            today.day,
            hour,
            minute
        )

        return event_datetime >= now

    except ValueError:

        return True


# ============================================================
# SEARCH HISTORY
# ============================================================

def save_search_history(search):

    if not search:
        return

    search = search.strip()

    if not search:
        return

    history = session.get("search_history", [])

    # Don't store the same search twice
    if search in history:
        history.remove(search)

    # Newest search first
    history.insert(0, search)

    # Keep latest 10 searches
    history = history[:10]

    session["search_history"] = history


def get_search_history():

    return session.get("search_history", [])


# ============================================================
# NORMALIZE SEARCH
# ============================================================

def normalize_search_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    # Treat Bangalore and Bengaluru as the same
    text = text.replace("bangalore", "bengaluru")

    return text


# ============================================================
# NATURAL-LANGUAGE SEARCH
# ============================================================

CATEGORY_ALIASES = {
    "technology": "Technology",
    "tech": "Technology",
    "ai": "Technology",
    "artificial intelligence": "Technology",
    "machine learning": "Technology",
    "data science": "Technology",
    "software": "Technology",
    "coding": "Technology",
    "programming": "Technology",
    "business": "Business",
    "startup": "Business",
    "startups": "Business",
    "entrepreneurship": "Business",
    "education": "Education",
    "learning": "Education",
    "music": "Music",
    "concert": "Music",
    "dance": "Music",
    "comedy": "Comedy",
    "standup": "Comedy",
    "stand-up": "Comedy",
    "sports": "Sports",
    "sport": "Sports",
    "cricket": "Sports",
    "football": "Sports",
    "art": "Art",
    "painting": "Art",
    "photography": "Art",
    "theatre": "Theatre",
    "theater": "Theatre",
    "drama": "Theatre",
    "food": "Food",
    "cooking": "Food",
    "workshop": "Workshop",
    "workshops": "Workshop",
    "festival": "Festival",
    "festivals": "Festival",
}

CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "hubli": "Hubballi",
    "hubballi": "Hubballi",
    "mysore": "Mysuru",
    "mysuru": "Mysuru",
}

NATURAL_LANGUAGE_STOP_WORDS = {
    "find", "show", "give", "get", "search", "looking", "look",
    "for", "me", "some", "any", "the", "a", "an", "events",
    "event", "in", "at", "near", "around", "this", "next",
    "on", "of", "please", "can", "you", "i", "want", "to",
    "with", "and", "from", "available", "upcoming", "happening",
}


def parse_natural_language_query(query):
    """
    Extract useful filters from a natural-language event query.

    Examples:
        "Find technology events in Bangalore this week"
        -> Technology + Bengaluru + week

        "Show comedy events tomorrow"
        -> Comedy + tomorrow

    Returns a dictionary while keeping ordinary keyword search supported.
    """

    original = str(query or "").strip()
    normalized = normalize_search_text(original)

    result = {
        "original": original,
        "category": None,
        "city": None,
        "filter": None,
        "keywords": []
    }

    if not normalized:
        return result

    working = normalized

    # --------------------------------------------------------
    # Detect category. Long phrases are checked first.
    # --------------------------------------------------------
    category_items = sorted(
        CATEGORY_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True
    )

    for phrase, category in category_items:
        if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", working):
            result["category"] = category
            working = re.sub(
                r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
                " ",
                working
            )
            break

    # --------------------------------------------------------
    # Detect city.
    # --------------------------------------------------------
    for city_alias, city_name in sorted(
        CITY_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):
        if re.search(r"(?<!\w)" + re.escape(city_alias) + r"(?!\w)", working):
            result["city"] = city_name
            working = re.sub(
                r"(?<!\w)" + re.escape(city_alias) + r"(?!\w)",
                " ",
                working
            )
            break

    # --------------------------------------------------------
    # Detect date/time intent.
    # --------------------------------------------------------
    filter_patterns = [
        ("tomorrow", "tomorrow"),
        ("today", "today"),
        ("this weekend", "weekend"),
        ("weekend", "weekend"),
        ("this week", "week"),
        ("next 7 days", "week"),
        ("this month", "month"),
        ("next 30 days", "month"),
    ]

    for phrase, filter_name in filter_patterns:
        if phrase in working:
            result["filter"] = filter_name
            working = working.replace(phrase, " ")
            break

    # --------------------------------------------------------
    # Keep meaningful words as normal keyword search.
    # --------------------------------------------------------
    words = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", working)

    result["keywords"] = [
        word
        for word in words
        if word not in NATURAL_LANGUAGE_STOP_WORDS and len(word) >= 2
    ]

    return result


# ============================================================
# NLP QUERY DISPLAY / DEBUGGING
# ============================================================

def print_nlp_intent(parsed_query):
    """Print the detected NLP intent for easy testing/debugging."""
    print()
    print("=" * 60)
    print("🧠 NLP SEARCH INTENT")
    print("=" * 60)
    print("Original query :", parsed_query.get("original"))
    print("Category       :", parsed_query.get("category") or "None")
    print("City           :", parsed_query.get("city") or "None")
    print("Date filter    :", parsed_query.get("filter") or "None")
    print("Keywords       :", parsed_query.get("keywords") or "None")
    print("=" * 60)


# ============================================================
# GET EVENTS
# ============================================================

def get_events(search=None, category=None, city=None):

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    query = """
        SELECT
            e.title,
            e.date,
            e.location,
            e.link,
            e.image,
            m.time
        FROM events e
        LEFT JOIN event_metadata m
            ON e.id = m.event_id
        LEFT JOIN event_categories c
            ON e.id = c.event_id
    """

    params = []
    conditions = []

    # ========================================================
    # KEYWORD SEARCH
    # ========================================================

    if search:

        normalized_search = normalize_search_text(search)

        words = normalized_search.split()

        for word in words:

            if len(word) < 2:
                continue

            pattern = "%" + word + "%"

            conditions.append(
                """
                (
                    LOWER(COALESCE(e.title, '')) LIKE ?
                    OR LOWER(COALESCE(e.location, '')) LIKE ?
                    OR LOWER(COALESCE(m.venue, '')) LIKE ?
                    OR LOWER(COALESCE(m.city, '')) LIKE ?
                    OR LOWER(COALESCE(m.time, '')) LIKE ?
                    OR LOWER(COALESCE(c.category, '')) LIKE ?
                )
                """
            )

            params.extend([
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern
            ])

    # ========================================================
    # EXACT CATEGORY FILTER
    # ========================================================

    if category:
        conditions.append("LOWER(COALESCE(c.category, '')) = ?")
        params.append(str(category).lower())

    # ========================================================
    # EXACT CITY FILTER
    # ========================================================

    if city:
        city_value = str(city).lower()
        if city_value == "bengaluru":
            conditions.append("LOWER(COALESCE(m.city, '')) IN ('bengaluru', 'bangalore')")
        else:
            conditions.append("LOWER(COALESCE(m.city, '')) = ?")
            params.append(city_value)

    if conditions:
        # All keyword/category/city conditions must match.
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY e.id DESC
    """

    cursor.execute(query, params)

    events = cursor.fetchall()

    conn.close()

    return events


# ============================================================
# FEEDBACK PREFERENCES
# ============================================================

def get_feedback_preferences():
    """
    Read the user's event feedback and convert it into simple
    category preferences.

    Returns:
        category_preferences: category -> preference boost
        not_interested_ids: event IDs the user rejected
    """

    category_counts = {}
    not_interested_ids = set()

    try:
        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute("""
            SELECT
                f.event_id,
                f.feedback,
                COALESCE(c.category, 'Other')
            FROM event_feedback f
            LEFT JOIN event_categories c
                ON f.event_id = c.event_id
        """).fetchall()

        conn.close()

    except sqlite3.Error as e:
        print("⚠️ Could not load feedback:", e)
        return {}, set()

    for event_id, feedback_type, category in rows:

        category = str(category or "Other").strip().lower()

        if feedback_type == "interested":
            category_counts[category] = category_counts.get(category, 0) + 1

        elif feedback_type == "not_interested":
            category_counts[category] = category_counts.get(category, 0) - 1
            not_interested_ids.add(event_id)

    # Convert feedback counts into a small ranking adjustment.
    # The adjustment is intentionally limited so feedback improves
    # TF-IDF recommendations instead of completely replacing them.
    category_preferences = {}

    for category, count in category_counts.items():
        boost = count * 0.10
        boost = max(-0.25, min(0.25, boost))
        category_preferences[category] = boost

    return category_preferences, not_interested_ids


# ============================================================
# GET PERSONALIZED RECOMMENDATIONS
# ============================================================

def get_history_recommendations(
    search_history,
    excluded_links=None,
    top_n=6
):

    if not search_history:
        return []

    if excluded_links is None:
        excluded_links = set()

    # --------------------------------------------------------
    # Use the most recent searches.
    #
    # Example:
    #
    # Search 1 -> technology
    # Search 2 -> workshop
    # Search 3 -> music
    #
    # Recommendation profile:
    # technology + workshop + music
    # --------------------------------------------------------

    recent_history = search_history[:5]

    # Convert recent natural-language searches into meaningful interests.
    parsed_interests = []
    for previous_search in recent_history:
        parsed = parse_natural_language_query(previous_search)

        if parsed.get("category"):
            parsed_interests.append(parsed["category"])

        parsed_interests.extend(parsed.get("keywords", []))

    interests = " ".join(parsed_interests).strip()

    # Fall back to the original searches if the parser found no terms.
    if not interests:
        interests = " ".join(recent_history)

    print()
    print("=" * 60)
    print("🔎 Recent search history:")
    print(recent_history)

    print("🧠 Recommendation profile:")
    print(interests)
    print("=" * 60)

    try:

        # Load upcoming events from recommendation.py
        all_events = load_events()

        print(
            f"📊 Upcoming events available for recommendation: "
            f"{len(all_events)}"
        )

        # Run TF-IDF + cosine similarity.
        # We request extra candidates because feedback will re-rank them.
        results = recommend(
            events=all_events,
            interests=interests,
            top_n=top_n + 30
        )

    except Exception as e:

        print("❌ Recommendation error:")
        print(type(e).__name__)
        print(e)

        return []

    # --------------------------------------------------------
    # Apply user feedback
    # --------------------------------------------------------

    category_preferences, not_interested_ids = get_feedback_preferences()

    if category_preferences:
        print("👍 Category feedback preferences:")
        print(category_preferences)

    if not_interested_ids:
        print(
            f"👎 Rejected events excluded: {len(not_interested_ids)}"
        )

    # Re-rank TF-IDF results using feedback.
    feedback_ranked_results = []

    for score, event in results:

        event_id = event.get("id")

        # Never recommend an event the user explicitly rejected.
        if event_id in not_interested_ids:
            continue

        category = str(event.get("category") or "Other").strip().lower()
        feedback_boost = category_preferences.get(category, 0.0)
        adjusted_score = score + feedback_boost

        feedback_ranked_results.append((adjusted_score, score, event))

    # Highest adjusted score first. Base score is used as a tie-breaker.
    feedback_ranked_results.sort(
        key=lambda item: (item[0], item[1]),
        reverse=True
    )

    recommended_events = []

    for adjusted_score, base_score, event in feedback_ranked_results:

        link = event.get("link")

        # ----------------------------------------------------
        # Don't recommend events already visible in
        # the current search results.
        # ----------------------------------------------------

        if link in excluded_links:
            continue

        # ----------------------------------------------------
        # Don't add duplicate recommendation links.
        # ----------------------------------------------------

        already_added = any(
            item["link"] == link
            for item in recommended_events
        )

        if already_added:
            continue

        # ----------------------------------------------------
        # Create a dictionary for events.html
        # ----------------------------------------------------

        recommended_events.append({

            "id": event.get("id"),

            "title": event.get("title"),

            "date": event.get("date"),

            "time": event.get("time"),

            "venue": (
                event.get("venue")
                or event.get("location")
            ),

            "city": event.get("city"),

            "category": event.get("category") or "Other",

            "link": link,

            "image": event.get("image")

        })

        if len(recommended_events) >= top_n:
            break

    print(
        f"✨ Recommendations generated: "
        f"{len(recommended_events)}"
    )

    for item in recommended_events:

        print(
            f"   → {item['title']}"
        )

    return recommended_events


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    all_events = get_events()

    upcoming_events = [

        event

        for event in all_events

        if is_upcoming(
            event[1],
            event[5]
        )

    ]

    # Show first 6 upcoming events
    events = upcoming_events[:6]

    # Remove time before sending to home.html
    events = [
        event[:5]
        for event in events
    ]

    return render_template(
        "home.html",
        events=events
    )

# ============================================================
# EVENTS
# ============================================================

@app.route("/events")
def events_page():

    filter_type = request.args.get("filter")

    search = request.args.get("search")

    # --------------------------------------------------------
    # UNDERSTAND NATURAL-LANGUAGE SEARCH
    # --------------------------------------------------------

    parsed_query = parse_natural_language_query(search)

    if search:
        print_nlp_intent(parsed_query)

    if parsed_query["filter"]:
        filter_type = parsed_query["filter"]

    keyword_search = " ".join(parsed_query["keywords"])

    print("🗣️ Natural-language query:", parsed_query)
    print("🔎 Database keyword search:", keyword_search or "None")

    # --------------------------------------------------------
    # SAVE ORIGINAL SEARCH
    # --------------------------------------------------------

    if search:
        save_search_history(search)

    # --------------------------------------------------------
    # GET SEARCH RESULTS
    # --------------------------------------------------------

    all_events = get_events(
        search=keyword_search,
        category=parsed_query["category"],
        city=parsed_query["city"]
    )

    # --------------------------------------------------------
    # REMOVE COMPLETED EVENTS
    # --------------------------------------------------------

    upcoming_events = [

        event

        for event in all_events

        if is_upcoming(
            event[1],
            event[5]
        )

    ]

    # --------------------------------------------------------
    # DATE FILTER
    # --------------------------------------------------------

    filtered_events = []

    today = datetime.now().date()

    for event in upcoming_events:

        date_str = event[1]

        try:

            event_date = datetime.strptime(
                str(date_str)[:10],
                "%Y-%m-%d"
            ).date()

        except (ValueError, TypeError):

            continue

        # ----------------------------------------------------
        # Today
        # ----------------------------------------------------

        if filter_type == "today":

            if event_date == today:
                filtered_events.append(event)

        # ----------------------------------------------------
        # Tomorrow
        # ----------------------------------------------------

        elif filter_type == "tomorrow":

            tomorrow = today + timedelta(days=1)

            if event_date == tomorrow:

                filtered_events.append(event)

        # ----------------------------------------------------
        # This weekend
        # ----------------------------------------------------

        elif filter_type == "weekend":

            days_until_saturday = (5 - today.weekday()) % 7
            saturday = today + timedelta(days=days_until_saturday)
            sunday = saturday + timedelta(days=1)

            if saturday <= event_date <= sunday:
                filtered_events.append(event)

        # ----------------------------------------------------
        # Next 7 days
        # ----------------------------------------------------

        elif filter_type == "week":

            if today <= event_date <= today + timedelta(days=7):

                filtered_events.append(event)

        # ----------------------------------------------------
        # Next 30 days
        # ----------------------------------------------------

        elif filter_type == "month":

            if today <= event_date <= today + timedelta(days=30):

                filtered_events.append(event)

        # ----------------------------------------------------
        # All
        # ----------------------------------------------------

        else:

            filtered_events.append(event)

    # --------------------------------------------------------
    # LINKS OF CURRENT SEARCH RESULTS
    # --------------------------------------------------------

    current_result_links = {

        event[3]

        for event in filtered_events

        if event[3]

    }

    # --------------------------------------------------------
    # SEARCH HISTORY
    # --------------------------------------------------------

    search_history = get_search_history()

    # --------------------------------------------------------
    # RECOMMENDATIONS
    #
    # Start after the FIRST search.
    #
    # First search:
    #   recommendation based on that search.
    #
    # More searches:
    #   recommendation based on recent search history.
    # --------------------------------------------------------

    recommended_events = []

    if len(search_history) >= 1:

        recommended_events = get_history_recommendations(

            search_history,

            excluded_links=current_result_links,

            top_n=6

        )

    # --------------------------------------------------------
    # REMOVE TIME BEFORE SENDING NORMAL EVENTS TO HTML
    # --------------------------------------------------------

    filtered_events = [

        event[:5]

        for event in filtered_events

    ]

    # --------------------------------------------------------
    # RENDER EVENTS PAGE
    # --------------------------------------------------------

    return render_template(

        "events.html",

        events=filtered_events,

        recommended_events=recommended_events,

        search_history=search_history

    )
# ============================================================
# EVENT FEEDBACK
# ============================================================

@app.route("/feedback", methods=["POST"])
def feedback():
    event_id = request.form.get("event_id")
    feedback_type = request.form.get("feedback")

    # Validate the feedback
    if feedback_type not in ["interested", "not_interested"]:
        return "Invalid feedback", 400

    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return "Invalid event ID", 400

    conn = sqlite3.connect(DB_PATH)

    # Check that the event exists
    event_exists = conn.execute(
        "SELECT 1 FROM events WHERE id = ?",
        (event_id,)
    ).fetchone()

    if not event_exists:
        conn.close()
        return "Event not found", 404

    # Save the latest feedback for this event.
    # If the same event was rated before, replace the previous choice.
    existing_feedback = conn.execute(
        "SELECT id FROM event_feedback WHERE event_id = ?",
        (event_id,)
    ).fetchone()

    if existing_feedback:
        conn.execute("""
            UPDATE event_feedback
            SET feedback = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (feedback_type, existing_feedback[0]))
    else:
        conn.execute("""
            INSERT INTO event_feedback (event_id, feedback)
            VALUES (?, ?)
        """, (event_id, feedback_type))

    conn.commit()
    conn.close()

    # Return the user to the previous page
    return redirect(request.referrer or "/events")

# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 5000)
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )