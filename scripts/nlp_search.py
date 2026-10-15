import re


# ============================================================
# CATEGORY ALIASES
# ============================================================

CATEGORY_ALIASES = {

    # ---------------- TECHNOLOGY ----------------

    "technology": "Technology",
    "technical": "Technology",
    "tech": "Technology",
    "ai": "Technology",
    "artificial intelligence": "Technology",
    "machine learning": "Technology",
    "ml": "Technology",
    "data science": "Technology",
    "data analytics": "Technology",
    "software": "Technology",
    "coding": "Technology",
    "programming": "Technology",
    "python": "Technology",
    "deep learning": "Technology",
    "cloud computing": "Technology",
    "cloud": "Technology",
    "cyber security": "Technology",
    "cybersecurity": "Technology",

    # ---------------- BUSINESS ----------------

    "business": "Business",
    "startup": "Business",
    "startups": "Business",
    "entrepreneurship": "Business",
    "entrepreneur": "Business",
    "entrepreneurs": "Business",

    # ---------------- EDUCATION ----------------

    "education": "Education",
    "educational": "Education",
    "learning": "Education",

    # ---------------- MUSIC ----------------

    "music": "Music",
    "concert": "Music",
    "concerts": "Music",

    # ---------------- COMEDY ----------------

    "comedy": "Comedy",
    "standup": "Comedy",
    "stand-up": "Comedy",

    # ---------------- SPORTS ----------------

    "sports": "Sports",
    "sport": "Sports",
    "cricket": "Sports",
    "football": "Sports",

    # ---------------- ART ----------------

    "art": "Art",
    "painting": "Art",
    "photography": "Art",

    # ---------------- THEATRE ----------------

    "theatre": "Theatre",
    "theater": "Theatre",
    "drama": "Theatre",

    # ---------------- FOOD ----------------

    "food": "Food",
    "cooking": "Food",

    # ---------------- WORKSHOP ----------------

    "workshop": "Workshop",
    "workshops": "Workshop",

    # ---------------- FESTIVAL ----------------

    "festival": "Festival",
    "festivals": "Festival",
}


# ============================================================
# CITY ALIASES
# ============================================================

CITY_ALIASES = {

    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",

    "hubli": "Hubballi",
    "hubballi": "Hubballi",

    "mysore": "Mysuru",
    "mysuru": "Mysuru",

    "mumbai": "Mumbai",
    "pune": "Pune",
    "delhi": "Delhi",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {

    "find",
    "show",
    "give",
    "get",
    "search",
    "looking",
    "look",
    "for",
    "me",
    "some",
    "any",

    "the",
    "a",
    "an",

    "events",
    "event",

    "in",
    "at",
    "near",
    "around",

    "this",
    "next",
    "on",
    "of",

    "please",
    "can",
    "you",

    "i",
    "want",
    "to",
    "with",
    "and",
    "from",

    "available",
    "upcoming",
    "happening",
}


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text


# ============================================================
# EXTRACT CATEGORY
# ============================================================

def extract_category(text):

    category_items = sorted(
        CATEGORY_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True
    )

    for phrase, category in category_items:

        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )

        if re.search(pattern, text):

            cleaned_text = re.sub(
                pattern,
                " ",
                text
            )

            return category, cleaned_text

    return None, text


# ============================================================
# EXTRACT CITY
# ============================================================

def extract_city(text):

    city_items = sorted(
        CITY_ALIASES.items(),
        key=lambda item: len(item[0]),
        reverse=True
    )

    for phrase, city in city_items:

        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )

        if re.search(pattern, text):

            cleaned_text = re.sub(
                pattern,
                " ",
                text
            )

            return city, cleaned_text

    return None, text


# ============================================================
# EXTRACT DATE FILTER
# ============================================================

def extract_date_filter(text):

    date_patterns = [

        ("next 30 days", "month"),

        ("this month", "month"),

        ("next 7 days", "week"),

        ("this weekend", "weekend"),

        ("weekend", "weekend"),

        ("this week", "week"),

        ("tomorrow", "tomorrow"),

        ("today", "today"),
    ]

    for phrase, filter_name in date_patterns:

        pattern = (
            r"(?<!\w)"
            + re.escape(phrase)
            + r"(?!\w)"
        )

        if re.search(pattern, text):

            cleaned_text = re.sub(
                pattern,
                " ",
                text
            )

            return filter_name, cleaned_text

    return None, text


# ============================================================
# EXTRACT KEYWORDS
# ============================================================

def extract_keywords(text):

    words = re.findall(
        r"[a-z0-9]+(?:[-'][a-z0-9]+)?",
        text
    )

    keywords = []

    for word in words:

        if (
            word not in STOP_WORDS
            and len(word) >= 2
        ):

            keywords.append(word)

    return keywords


# ============================================================
# MAIN NLP FUNCTION
# ============================================================

def parse_query(query):

    original_query = str(query or "").strip()

    text = normalize_text(original_query)

    result = {

        "original": original_query,

        "category": None,

        "city": None,

        "filter": None,

        "keywords": []
    }

    if not text:

        return result


    # ========================================================
    # CATEGORY
    # ========================================================

    result["category"], text = extract_category(text)


    # ========================================================
    # CITY
    # ========================================================

    result["city"], text = extract_city(text)


    # ========================================================
    # DATE FILTER
    # ========================================================

    result["filter"], text = extract_date_filter(text)


    # ========================================================
    # KEYWORDS
    # ========================================================

    result["keywords"] = extract_keywords(text)


    return result


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("NATURAL LANGUAGE EVENT SEARCH")
    print("=" * 60)

    while True:

        query = input("\nEnter your query: ").strip()

        if not query:
            break

        result = parse_query(query)

        print("\nDetected Information")
        print("-" * 40)

        print("Category :", result["category"])
        print("City     :", result["city"])
        print("Filter   :", result["filter"])
        print("Keywords :", result["keywords"])