import sqlite3
import os
import requests
import json
import re
from bs4 import BeautifulSoup


# ============================================================
# DATABASE PATH
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DB_PATH = os.path.join(
    BASE_DIR,
    "events.db"
)


# ============================================================
# REQUEST SETTINGS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()


# Make sure metadata table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS event_metadata (
    event_id INTEGER PRIMARY KEY,
    time TEXT,
    venue TEXT,
    city TEXT,
    source TEXT,
    FOREIGN KEY(event_id) REFERENCES events(id)
)
""")

conn.commit()


# ============================================================
# JSON-LD
# ============================================================

def get_json_ld(soup):

    results = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )

    for script in scripts:

        try:

            content = script.string or script.get_text()

            if not content:
                continue

            data = json.loads(content)

            if isinstance(data, list):

                results.extend(data)

            elif isinstance(data, dict):

                if "@graph" in data:

                    graph = data["@graph"]

                    if isinstance(graph, list):
                        results.extend(graph)

                else:

                    results.append(data)

        except Exception:
            continue

    return results


# ============================================================
# EXTRACT DATE + TIME
# ============================================================

def extract_date_time(soup, title):

    date_value = "N/A"
    time_value = "N/A"


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    for item in get_json_ld(soup):

        if not isinstance(item, dict):
            continue

        start_date = item.get("startDate")

        if start_date:

            start_date = str(start_date)

            if "T" in start_date:

                date_value = start_date[:10]

                time_value = start_date.split("T")[1][:5]

            else:

                date_value = start_date[:10]

            return date_value, time_value


    # --------------------------------------------------------
    # META startDate
    # --------------------------------------------------------

    meta_date = soup.find(
        "meta",
        itemprop="startDate"
    )

    if meta_date:

        content = meta_date.get("content")

        if content:

            if "T" in content:

                date_value = content[:10]

                time_value = content.split("T")[1][:5]

            else:

                date_value = content[:10]


    # --------------------------------------------------------
    # TIME FROM TITLE
    #
    # Examples:
    # "Room of Memories 2PM"
    # "Room of Memories 11AM"
    # "Event 7:30 PM"
    # --------------------------------------------------------

    if time_value == "N/A" and title:

        match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b",
            title,
            re.IGNORECASE
        )

        if match:

            hour = int(match.group(1))

            minute = int(
                match.group(2) or 0
            )

            am_pm = match.group(3).upper()

            if am_pm == "PM" and hour != 12:
                hour += 12

            if am_pm == "AM" and hour == 12:
                hour = 0

            time_value = (
                f"{hour:02d}:{minute:02d}"
            )


    return date_value, time_value


# ============================================================
# EXTRACT VENUE + CITY
# ============================================================

def extract_venue_city(soup):

    venue = "N/A"
    city = "Bangalore"


    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    for item in get_json_ld(soup):

        if not isinstance(item, dict):
            continue

        location = item.get("location")

        if isinstance(location, dict):

            venue_name = location.get("name")

            if venue_name:

                venue = venue_name.strip()


            address = location.get("address")

            if isinstance(address, dict):

                city_value = (
                    address.get("addressLocality")
                    or address.get("addressRegion")
                )

                if city_value:
                    city = city_value.strip()

            elif isinstance(address, str):

                if "bengaluru" in address.lower():
                    city = "Bangalore"

                elif "bangalore" in address.lower():
                    city = "Bangalore"


            if venue != "N/A":
                return venue, city


    # --------------------------------------------------------
    # HTML ATTRIBUTES
    # --------------------------------------------------------

    selectors = [
        '[itemprop="location"]',
        '[itemprop="address"]',
        '[class*="venue"]'
    ]

    for selector in selectors:

        try:

            tag = soup.select_one(selector)

            if not tag:
                continue

            text = tag.get_text(
                " ",
                strip=True
            )

            if not text:
                continue

            if len(text) > 300:
                continue

            venue = text

            if "bengaluru" in text.lower():
                city = "Bangalore"

            elif "bangalore" in text.lower():
                city = "Bangalore"

            return venue, city

        except Exception:
            continue


    return venue, city


# ============================================================
# EXTRACT SOURCE
# ============================================================

def extract_source(url):

    try:

        from urllib.parse import urlparse

        domain = urlparse(url).netloc

        return domain.replace(
            "www.",
            ""
        )

    except Exception:

        return "Unknown"


# ============================================================
# GET EXISTING EVENTS
# ============================================================

cursor.execute("""
SELECT id, title, date, location, link
FROM events
ORDER BY id
""")

events = cursor.fetchall()


print()
print("=" * 70)
print("EVENT METADATA BACKFILL")
print("=" * 70)

print(
    f"Database: {DB_PATH}"
)

print(
    f"Events found: {len(events)}"
)

print("=" * 70)


# ============================================================
# PROCESS EVENTS
# ============================================================

updated = 0
failed = 0


for index, event in enumerate(
    events,
    start=1
):

    event_id = event[0]
    old_title = event[1]
    old_date = event[2]
    old_location = event[3]
    link = event[4]


    print()
    print(
        f"[{index}/{len(events)}] "
        f"Event ID: {event_id}"
    )

    print(
        f"URL: {link}"
    )


    if not link:

        print("⚠️ No URL")

        failed += 1

        continue


    try:

        response = requests.get(
            link,
            headers=HEADERS,
            timeout=15
        )


        if response.status_code != 200:

            print(
                f"❌ HTTP {response.status_code}"
            )

            failed += 1

            continue


        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )


        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = old_title or "N/A"

        h1 = soup.find("h1")

        if h1:

            scraped_title = h1.get_text(
                " ",
                strip=True
            )

            if scraped_title:
                title = scraped_title


        # ----------------------------------------------------
        # DATE + TIME
        # ----------------------------------------------------

        date_value, time_value = extract_date_time(
            soup,
            title
        )


        # Keep existing date if scraping didn't find one
        if date_value == "N/A" and old_date:

            date_value = old_date


        # ----------------------------------------------------
        # VENUE + CITY
        # ----------------------------------------------------

        venue, city = extract_venue_city(
            soup
        )


        # Keep old location if useful
        if venue == "N/A" and old_location:

            # Don't blindly trust page title as location
            if len(old_location) < 200:
                venue = old_location


        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        source = extract_source(link)


        # ----------------------------------------------------
        # SAVE METADATA
        # ----------------------------------------------------

        cursor.execute("""
        INSERT OR REPLACE INTO event_metadata
        (
            event_id,
            time,
            venue,
            city,
            source
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            event_id,
            time_value,
            venue,
            city,
            source
        ))


        conn.commit()


        updated += 1


        # ----------------------------------------------------
        # DISPLAY
        # ----------------------------------------------------

        print("✔ Updated")

        print(
            f"Title : {title}"
        )

        print(
            f"Date  : {date_value}"
        )

        print(
            f"Time  : {time_value}"
        )

        print(
            f"Venue : {venue}"
        )

        print(
            f"City  : {city}"
        )

        print(
            f"Source: {source}"
        )


    except requests.exceptions.Timeout:

        print("❌ Request timeout")

        failed += 1


    except requests.exceptions.RequestException as e:

        print(
            f"❌ Request error: {e}"
        )

        failed += 1


    except Exception as e:

        print(
            f"❌ Error: {e}"
        )

        failed += 1


# ============================================================
# FINISH
# ============================================================

conn.commit()
conn.close()


print()
print("=" * 70)
print("BACKFILL COMPLETE")
print("=" * 70)

print(
    f"Successfully updated: {updated}"
)

print(
    f"Failed: {failed}"
)

print("=" * 70)