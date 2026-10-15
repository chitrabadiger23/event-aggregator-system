from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import time
import sqlite3
import re
import requests
import json
import os

from bs4 import BeautifulSoup
from urllib.parse import urlparse

# NEW:
# Use the tested duplicate detector instead of keeping
# duplicate logic inside scraper.py
from duplicate_detector import is_duplicate
from data_validator import validate_event

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE_NAME = os.path.join(
    BASE_DIR,
    "events.db"
)

START_URL = "https://allevents.in/bangalore"


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

conn = sqlite3.connect(
    DATABASE_NAME
)

cursor = conn.cursor()


# ============================================================
# EVENTS TABLE
# ============================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    date TEXT,
    location TEXT,
    link TEXT UNIQUE,
    image TEXT
    )
""")


# ============================================================
# EVENT METADATA TABLE
# ============================================================

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
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower().strip()

    text = text.replace(
        "bengaluru",
        "bangalore"
    )

    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# EXTRACT TITLE
# ============================================================

def extract_title(soup):

    # --------------------------------------------------------
    # H1
    # --------------------------------------------------------

    tag = soup.find("h1")

    if tag:

        text = tag.get_text(
            " ",
            strip=True
        )

        if text:
            return text


    # --------------------------------------------------------
    # OG TITLE
    # --------------------------------------------------------

    meta = soup.find(
        "meta",
        property="og:title"
    )

    if meta and meta.get("content"):

        return meta["content"].strip()


    return "N/A"


# ============================================================
# JSON-LD EXTRACTION
# ============================================================

def get_json_ld(soup):

    results = []

    scripts = soup.find_all(
        "script",
        type="application/ld+json"
    )


    for script in scripts:

        try:

            content = (
                script.string
                or script.get_text()
            )

            if not content:
                continue


            data = json.loads(
                content
            )


            # ------------------------------------------------
            # JSON-LD LIST
            # ------------------------------------------------

            if isinstance(data, list):

                results.extend(
                    data
                )


            # ------------------------------------------------
            # JSON-LD DICTIONARY
            # ------------------------------------------------

            elif isinstance(data, dict):

                # @graph
                if "@graph" in data:

                    graph = data["@graph"]

                    if isinstance(
                        graph,
                        list
                    ):

                        results.extend(
                            graph
                        )

                else:

                    results.append(
                        data
                    )


        except Exception:

            continue


    return results


# ============================================================
# EXTRACT DATE + TIME
# ============================================================

def extract_date_and_time(soup):

    date_value = "N/A"
    time_value = "N/A"


    # ========================================================
    # METHOD 1 — JSON-LD
    # ========================================================

    json_items = get_json_ld(
        soup
    )


    for item in json_items:

        if not isinstance(
            item,
            dict
        ):
            continue


        start_date = item.get(
            "startDate"
        )


        if start_date:

            start_date = str(
                start_date
            )


            # Example:
            #
            # 2026-09-04T10:00:00+05:30
            #

            if "T" in start_date:

                date_value = (
                    start_date[:10]
                )

                time_part = (
                    start_date
                    .split("T")[1]
                )

                time_value = (
                    time_part[:5]
                )


            else:

                date_value = (
                    start_date[:10]
                )


            return (
                date_value,
                time_value
            )


    # ========================================================
    # METHOD 2 — META startDate
    # ========================================================

    meta_date = soup.find(
        "meta",
        itemprop="startDate"
    )


    if meta_date:

        content = meta_date.get(
            "content"
        )


        if content:

            if "T" in content:

                date_value = (
                    content[:10]
                )

                time_value = (
                    content
                    .split("T")[1][:5]
                )

            else:

                date_value = (
                    content[:10]
                )


    return (
        date_value,
        time_value
    )


# ============================================================
# EXTRACT VENUE + CITY
# ============================================================

def extract_venue_and_city(soup):

    venue = "N/A"

    city = "Bangalore"


    # ========================================================
    # METHOD 1 — JSON-LD
    # ========================================================

    json_items = get_json_ld(
        soup
    )


    for item in json_items:

        if not isinstance(
            item,
            dict
        ):
            continue


        location = item.get(
            "location"
        )


        if isinstance(
            location,
            dict
        ):

            # ------------------------------------------------
            # VENUE NAME
            # ------------------------------------------------

            venue_name = location.get(
                "name"
            )


            if venue_name:

                venue = venue_name.strip()


            # ------------------------------------------------
            # ADDRESS
            # ------------------------------------------------

            address = location.get(
                "address"
            )


            if isinstance(
                address,
                dict
            ):

                city_value = (
                    address.get(
                        "addressLocality"
                    )
                    or
                    address.get(
                        "addressRegion"
                    )
                )


                if city_value:

                    city = city_value.strip()


            elif isinstance(
                address,
                str
            ):

                address_lower = (
                    address.lower()
                )


                if (
                    "bengaluru"
                    in address_lower
                ):

                    city = "Bangalore"


                elif (
                    "bangalore"
                    in address_lower
                ):

                    city = "Bangalore"


            if venue != "N/A":

                return (
                    venue,
                    city
                )


    # ========================================================
    # METHOD 2 — HTML SEMANTIC ATTRIBUTES
    # ========================================================

    selectors = [
        '[itemprop="location"]',
        '[itemprop="address"]',
        '[class*="venue"]',
        '[class*="location"]'
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

            # Avoid very large text blocks
            if len(text) > 150:
                continue

            text_lower = text.lower()

            # ====================================================
            # REJECT TEXT THAT IS CLEARLY NOT A VENUE
            # ====================================================

            bad_patterns = [
                "attend ",
                "in bangalore on",
                "allevents",
                "tickets",
                "•",
                " to ",
                " at ",
                "on october",
                "on september",
                "on november",
                "on december",
                "2026",
                "2027",
                "am",
                "pm"
            ]

            if any(
                pattern in text_lower
                for pattern in bad_patterns
            ):
                continue

            # Reject obvious date-like text
            if re.search(
                r"\b\d{1,2}[:.]\d{2}\s*(am|pm)?\b",
                text_lower
            ):
                continue

            # ====================================================
            # ACCEPT AS VENUE
            # ====================================================

            venue = text

            if "bengaluru" in text_lower:
                city = "Bangalore"

            elif "bangalore" in text_lower:
                city = "Bangalore"

            return (
                venue,
                city
            )

        except Exception:
            continue

    # No usable venue was found.
    # Always return a tuple so the caller can safely unpack it.
    return venue, city


# ============================================================
# EXTRACT IMAGE
# ============================================================

def extract_image(soup):

    # ========================================================
    # OG IMAGE
    # ========================================================

    meta = soup.find(
        "meta",
        property="og:image"
    )


    if (
        meta
        and meta.get("content")
    ):

        return meta["content"]


    # ========================================================
    # TWITTER IMAGE
    # ========================================================

    meta = soup.find(
        "meta",
        property="twitter:image"
    )


    if (
        meta
        and meta.get("content")
    ):

        return meta["content"]


    # ========================================================
    # NORMAL IMAGE
    # ========================================================

    img = soup.find(
        "img"
    )


    if img:

        image = (
            img.get("src")
            or
            img.get("data-src")
            or
            img.get("data-lazy-src")
        )


        if image:

            return image


    return "N/A"


# ============================================================
# SOURCE
# ============================================================

def extract_source(link):

    try:

        domain = urlparse(
            link
        ).netloc


        return domain.replace(
            "www.",
            ""
        )


    except Exception:

        return "Unknown"


# ============================================================
# SELENIUM EVENT PAGE FALLBACK
# ============================================================

def fetch_event_page_with_selenium(url):
    """
    Fetch an event page with Selenium when requests encounters
    a redirect loop.

    Returns:
        HTML string, or None if Selenium cannot load the page.
    """

    fallback_driver = None

    try:

        fallback_options = Options()

        fallback_options.add_argument("--headless")
        fallback_options.add_argument("--no-sandbox")
        fallback_options.add_argument("--disable-dev-shm-usage")
        fallback_options.add_argument("--disable-gpu")
        fallback_options.add_argument("--window-size=1920,1080")

        fallback_driver = webdriver.Chrome(
            options=fallback_options
        )

        fallback_driver.set_page_load_timeout(30)

        print("🔄 Selenium fallback:", url)

        fallback_driver.get(url)

        time.sleep(3)

        html = fallback_driver.page_source

        if not html:
            return None

        return html

    except Exception as e:

        print("❌ Selenium fallback failed:", type(e).__name__)
        print("   Message:", e)

        return None

    finally:

        if fallback_driver is not None:

            try:
                fallback_driver.quit()
            except Exception:
                pass


# ============================================================
# SELENIUM
# ============================================================

print()
print("🚀 Starting Selenium...")


options = Options()

options.add_argument(
    "--headless"
)

options.add_argument(
    "--no-sandbox"
)

options.add_argument(
    "--disable-dev-shm-usage"
)

options.add_argument(
    "--disable-gpu"
)

options.add_argument(
    "--window-size=1920,1080"
)


driver = webdriver.Chrome(
    options=options
)


driver.set_page_load_timeout(
    30
)


try:

    driver.get(
        START_URL
    )


except Exception as e:

    print(
        "❌ Selenium error:",
        e
    )

    driver.quit()

    conn.close()

    raise


# ============================================================
# SCROLL
# ============================================================

print(
    "📜 Scrolling..."
)


for _ in range(6):

    driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);"
    )

    time.sleep(2)


# ============================================================
# GET EVENT LINKS
# ============================================================

cards = driver.find_elements(
    By.XPATH,
    "//a[contains(@href, '/bangalore/')]"
)


clean_links = set()


for card in cards:

    try:

        link = card.get_attribute(
            "href"
        )


        if not link:
            continue


        # Remove query parameters
        link = link.split("?")[0]

        # Remove fragments
        link = link.split("#")[0]


        # Skip ticket pages
        if "/tickets/" in link:
            continue


        # Keep event URLs
        if re.search(
            r"/\d{6,}",
            link
        ):

            clean_links.add(
                link
            )


    except Exception:

        continue


links = list(
    clean_links
)


driver.quit()


print(
    f"✅ Unique links found: {len(links)}"
)


# ============================================================
# SCRAPING COUNTERS
# ============================================================

saved = 0

duplicates = 0

failed = 0

url_duplicates = 0

# Keep detailed information about failed events so they can
# be diagnosed after the scraper finishes.
failed_events = []


# ============================================================
# SCRAPE EVENTS
# ============================================================

for index, link in enumerate(
    links,
    start=1
):

    print(
        "\n"
        + "=" * 60
    )

    print(
        f"Event {index}/{len(links)}"
    )

    print(
        "=" * 60
    )


    try:

        # ====================================================
        # REQUEST
        # ====================================================

        response = None
        page_html = None

        try:

            response = requests.get(
                link,
                headers=HEADERS,
                timeout=15
            )

            page_html = response.text

        except requests.exceptions.TooManyRedirects as e:

            print("⚠️ Requests redirect loop.")
            print("   Trying Selenium fallback...")

            page_html = fetch_event_page_with_selenium(link)

            if page_html is None:

                print("❌ Selenium fallback could not load page.")

                failed += 1

                failed_events.append({
                    "url": link,
                    "error": f"Too many redirects: {e}"
                })

                continue

        if response is not None and response.status_code != 200:

            print("❌ HTTP:", response.status_code)
            print("   URL:", link)

            failed += 1

            failed_events.append({
                "url": link,
                "error": f"HTTP {response.status_code}"
            })

            continue


        # ====================================================
        # BEAUTIFULSOUP
        # ====================================================

        soup = BeautifulSoup(
            page_html,
            "html.parser"
        )


        # ====================================================
        # EXTRACT EVENT DATA
        # ====================================================

        title = extract_title(
            soup
        )


        date, event_time = (
            extract_date_and_time(
                soup
            )
        )


        venue, city = (
            extract_venue_and_city(
                soup
            )
        )


        image = extract_image(
            soup
        )


        source = extract_source(
            link
        )


        # ====================================================
        # DISPLAY
        # ====================================================

        print()
        print("📌 EVENT")

        print(
            "Title:",
            title
        )

        print(
            "Date:",
            date
        )

        print(
            "Time:",
            event_time
        )

        print(
            "Venue:",
            venue
        )

        print(
            "City:",
            city
        )

        print(
            "Source:",
            source
        )


        # ====================================================
        # CREATE EVENT OBJECT
        # ====================================================

        new_event = {

            "title": title,

            "date": date,

            "location": venue,

            "link": link,

            "image": image,

            "time": event_time,

            "venue": venue,

            "city": city,

            "source": source

        }

        # ============================================================
        # ============================================================
        # DATA VALIDATION
        # ============================================================

        validation = validate_event(new_event)

        if not validation["valid"]:

            print()
            print("❌ INVALID EVENT - SKIPPED")

            for error in validation["errors"]:
                print("   ERROR:", error)

            failed += 1
            continue

        # Show warnings but keep the event
        if validation["warnings"]:

            print()
            print("⚠️ DATA QUALITY WARNINGS")

            for warning in validation["warnings"]:
                print("   WARNING:", warning)

        # DUPLICATE CHECK
        # ====================================================
        #
        # Uses:
        #
        # duplicate_detector.py
        #
        # The detector performs:
        #
        # 1. Text normalization
        # 2. Date comparison
        # 3. Time comparison
        # 4. Venue similarity
        # 5. City similarity
        # 6. Fuzzy title matching
        # 7. Weighted scoring
        #
        # IMPORTANT:
        # Different known times are treated as separate events.
        #
        # Example:
        #
        # 11:00 != 14:00
        #
        # ====================================================

        duplicate, existing_event = (
            is_duplicate(
                new_event
            )
        )


        if duplicate:

            duplicates += 1


            print()
            print(
                "⚠️ DUPLICATE EVENT"
            )


            if existing_event:

                print(
                    "Existing ID:",
                    existing_event.get(
                        "id"
                    )
                )

                print(
                    "Existing title:",
                    existing_event.get(
                        "title"
                    )
                )

                print(
                    "Existing date:",
                    existing_event.get(
                        "date"
                    )
                )

                print(
                    "Existing time:",
                    existing_event.get(
                        "time"
                    )
                )

                print(
                    "Existing venue:",
                    existing_event.get(
                        "venue"
                    )
                )


            print(
                "⏭️ Duplicate skipped."
            )


            continue


        # ====================================================
        # INSERT EVENT
        # ====================================================

        cursor.execute("""
            INSERT OR IGNORE INTO events
            (
                title,
                date,
                location,
                link,
                image
            )
            VALUES (?, ?, ?, ?, ?)
        """, (

            title,

            date,

            venue,

            link,

            image

        ))


        # ====================================================
        # URL ALREADY EXISTS
        # ====================================================

        if cursor.rowcount == 0:

            url_duplicates += 1


            print(
                "ℹ️ URL already exists."
            )


            continue


        # ====================================================
        # GET EVENT ID
        # ====================================================

        event_id = cursor.lastrowid


        # ====================================================
        # INSERT METADATA
        # ====================================================

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

            event_time,

            venue,

            city,

            source

        ))


        # ====================================================
        # COMMIT
        # ====================================================

        conn.commit()


        saved += 1


        print()
        print(
            f"✔ Saved: {title}"
        )

        print(
            f"   Database ID: {event_id}"
        )


    # ========================================================
    # TIMEOUT
    # ========================================================

    except requests.exceptions.TooManyRedirects as e:

        print(
            "❌ Too many redirects"
        )

        print(
            "   Message:",
            e
        )

        print(
            "   URL:",
            link
        )

        failed += 1

        failed_events.append({
            "url": link,
            "error": f"Too many redirects: {e}"
        })


    except requests.exceptions.Timeout:

        print(
            "❌ Request timeout"
        )

        print(
            "   URL:",
            link
        )

        failed += 1

        failed_events.append({
            "url": link,
            "error": "Request timeout"
        })


    # ========================================================
    # REQUEST ERROR
    # ========================================================

    except requests.exceptions.RequestException as e:

        print(
            "❌ Request error:",
            e
        )

        print(
            "   URL:",
            link
        )

        failed += 1

        failed_events.append({
            "url": link,
            "error": f"Request error: {e}"
        })


    # ========================================================
    # OTHER ERROR
    # ========================================================

    except Exception as e:

        print(
            "❌ Unexpected error:",
            type(e).__name__
        )

        print(
            "   Message:",
            e
        )

        print(
            "   URL:",
            link
        )

        failed += 1

        failed_events.append({
            "url": link,
            "error": f"{type(e).__name__}: {e}"
        })


# ============================================================
# FINAL COMMIT
# ============================================================

conn.commit()


# ============================================================
# CLOSE DATABASE
# ============================================================

conn.close()


# ============================================================
# FAILED EVENTS REPORT
# ============================================================

if failed_events:

    print()
    print("=" * 60)
    print("❌ FAILED EVENTS")
    print("=" * 60)

    for i, item in enumerate(
        failed_events,
        start=1
    ):

        print()
        print(
            f"{i}. {item['error']}"
        )

        print(
            f"   URL: {item['url']}"
        )


# ============================================================
# FINAL REPORT
# ============================================================

print()
print()
print("=" * 60)
print(
    "🎉 SCRAPING COMPLETED"
)
print("=" * 60)


print(
    f"Links found           : {len(links)}"
)


print(
    f"New events saved      : {saved}"
)


print(
    f"Fuzzy duplicates      : {duplicates}"
)


print(
    f"Same URL duplicates   : {url_duplicates}"
)


print(
    f"Failed                : {failed}"
)


print("=" * 60)