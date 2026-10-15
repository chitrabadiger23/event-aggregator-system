"""
BookMyShow Bengaluru Extraction Diagnostic V3
------------------------------------------------
READ-ONLY diagnostic tool.

Purpose:
- Inspect what BookMyShow actually renders for the Bengaluru events page.
- Diagnose why event-detail links are not being discovered.
- Does NOT modify events.db.
- Does NOT insert/update/delete any database records.

Run:
    python scripts/bookmyshow_test_v3.py

Output:
- rendered page URL/title
- number of anchors
- examples of hrefs
- /events/ candidates
- event-like text/card information
- whether /events/ appears anywhere in rendered HTML
- saves rendered HTML for inspection
"""

import os
import re
import time
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


LISTING_URL = "https://in.bookmyshow.com/explore/events-bengaluru"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_DIR = os.path.join(BASE_DIR, "bookmyshow_debug")
os.makedirs(DEBUG_DIR, exist_ok=True)


def clean_url(url):
    """Remove query string and fragment while preserving the useful path."""
    if not url:
        return None

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = urljoin("https://in.bookmyshow.com", url)

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return None

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            "",
            "",
        )
    )


def build_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-IN")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(45)
    return driver


def print_section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def main():
    driver = None

    try:
        print_section("BOOKMYSHOW BENGALURU DIAGNOSTIC V3")
        print("READ-ONLY — events.db will NOT be modified.")
        print(f"Listing URL: {LISTING_URL}")

        driver = build_driver()

        print("\nOpening BookMyShow...")
        try:
            driver.get(LISTING_URL)
        except TimeoutException:
            print("⚠️ Page load timeout — stopping page load and continuing.")
            try:
                driver.execute_script("window.stop();")
            except Exception:
                pass

        time.sleep(5)

        print_section("PAGE INFORMATION")

        print("Current URL :", driver.current_url)
        print("Page title  :", driver.title)

        try:
            print("Body text length :", len(driver.find_element(By.TAG_NAME, "body").text))
        except Exception:
            print("Body text length : [UNAVAILABLE]")

        # Save rendered HTML.
        html = driver.page_source or ""
        html_path = os.path.join(DEBUG_DIR, "bookmyshow_listing_rendered.html")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        print("Rendered HTML saved to:")
        print(html_path)
        print("Rendered HTML length:", len(html))

        print_section("URL /EVENTS/ SEARCH")

        lower_html = html.lower()

        event_positions = [
            match.start()
            for match in re.finditer(r"/events/", lower_html)
        ]

        print("Occurrences of '/events/' in rendered HTML:",
              len(event_positions))

        if event_positions:
            print("\nExamples around '/events/':")

            shown = 0

            for position in event_positions:
                start = max(0, position - 250)
                end = min(len(html), position + 500)

                snippet = re.sub(r"\s+", " ", html[start:end])

                print("\n--- occurrence", shown + 1, "---")
                print(snippet[:750])

                shown += 1

                if shown >= 10:
                    break
        else:
            print("❌ '/events/' does not appear in rendered HTML.")

        print_section("ALL ANCHOR TAGS")

        anchors = driver.find_elements(By.TAG_NAME, "a")

        print("Total <a> elements:", len(anchors))

        hrefs = []

        for index, anchor in enumerate(anchors[:200], start=1):
            try:
                href = anchor.get_attribute("href")
                text = anchor.text.strip()
                aria = anchor.get_attribute("aria-label")

                if href:
                    hrefs.append(href)

                    print(
                        f"{index:03d}. "
                        f"href={href!r} | "
                        f"text={text[:100]!r} | "
                        f"aria={aria!r}"
                    )

            except Exception:
                continue

        print_section("EVENT-LIKE HREF CANDIDATES")

        candidates = []

        for href in hrefs:
            clean = clean_url(href)

            if not clean:
                continue

            path = urlparse(clean).path.lower()

            if (
                "/events/" in path
                or "/event/" in path
                or "event" in path
            ):
                if clean not in candidates:
                    candidates.append(clean)

        print("Event-like href candidates:", len(candidates))

        if candidates:
            for candidate in candidates[:100]:
                print(candidate)
        else:
            print("❌ No event-like href candidates found.")

        print_section("ELEMENTS WITH EVENT-LIKE ATTRIBUTES")

        # Look for useful attributes commonly used by React/card implementations.
        event_attribute_elements = []

        selectors = [
            "[href*='/events/']",
            "[href*='/event/']",
            "[data-testid*='event' i]",
            "[data-test*='event' i]",
            "[class*='event' i]",
            "[id*='event' i]",
        ]

        seen = set()

        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue

            for element in elements[:100]:
                try:
                    key = (
                        element.tag_name,
                        element.get_attribute("outerHTML")[:500],
                    )

                    if key in seen:
                        continue

                    seen.add(key)
                    event_attribute_elements.append(element)

                except Exception:
                    continue

        print(
            "Elements matching event-related selectors:",
            len(event_attribute_elements),
        )

        for index, element in enumerate(event_attribute_elements[:50], start=1):
            try:
                text = re.sub(r"\s+", " ", element.text.strip())
                outer = element.get_attribute("outerHTML") or ""

                print(f"\n--- element {index} ---")
                print("TAG :", element.tag_name)
                print("TEXT:", text[:300])
                print("HTML:", re.sub(r"\s+", " ", outer[:1200]))

            except Exception:
                continue

        print_section("BODY TEXT SAMPLE")

        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            body_text = re.sub(r"\n{3,}", "\n\n", body_text)

            print(body_text[:10000])

        except Exception as e:
            print("Could not read body text:", e)

        print_section("SCRIPT / NEXT.JS DATA CHECK")

        scripts = driver.find_elements(By.TAG_NAME, "script")

        print("Script elements:", len(scripts))

        interesting_scripts = 0

        for index, script in enumerate(scripts, start=1):
            try:
                text = script.get_attribute("textContent") or ""

                if not text:
                    continue

                lower = text.lower()

                keywords = [
                    "/events/",
                    "eventid",
                    "event_id",
                    "eventname",
                    "eventname",
                    "eventurl",
                    "eventurl",
                    "bengaluru",
                    "bengalore",
                ]

                matched = [k for k in keywords if k in lower]

                if matched:
                    interesting_scripts += 1

                    print(
                        f"\n--- interesting script {index} ---"
                    )
                    print("Matched:", matched)
                    print("Length:", len(text))
                    print(re.sub(r"\s+", " ", text[:2500]))

                    if interesting_scripts >= 10:
                        break

            except Exception:
                continue

        print(
            "\nInteresting scripts found:",
            interesting_scripts,
        )

        print_section("DIAGNOSTIC RESULT")

        if candidates:
            print(
                "✅ Event-detail URLs ARE present in the rendered page."
            )
            print(
                "The next scraper can use these discovered URLs."
            )
        elif event_positions:
            print(
                "⚠️ '/events/' exists in the HTML, but Selenium "
                "did not expose usable anchor hrefs."
            )
            print(
                "This likely means URLs are embedded in page data "
                "or generated by JavaScript."
            )
        elif interesting_scripts:
            print(
                "⚠️ Event-related data appears inside scripts, "
                "but not as normal links."
            )
            print(
                "The next version should extract event data from "
                "the embedded application state."
            )
        else:
            print(
                "❌ No obvious event-detail URLs or event-related "
                "embedded data were found."
            )
            print(
                "The saved rendered HTML and body text are the "
                "important diagnostic artifacts."
            )

        print("\nDebug directory:")
        print(DEBUG_DIR)

        print("\nDone.")

    except WebDriverException as e:
        print("\n❌ Selenium/WebDriver error:")
        print(type(e).__name__, e)

    except Exception as e:
        print("\n❌ Unexpected error:")
        print(type(e).__name__, e)

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
