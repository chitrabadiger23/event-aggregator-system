from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import sqlite3
import re
import requests
from bs4 import BeautifulSoup

# ==============================
# 🔥 DATABASE
# ==============================
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

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


# ==============================
# 🚀 SELENIUM → GET LINKS
# ==============================
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=options)
driver.get("https://allevents.in/bangalore")
time.sleep(5)
driver.set_page_load_timeout(15)

# Scroll
for _ in range(6):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

cards = driver.find_elements(By.XPATH, "//a[contains(@href, '/bangalore/')]")

clean_links = set()

for card in cards:
    link = card.get_attribute("href")
    if not link:
        continue

    link = link.split("?")[0]

    if "/tickets/" in link or re.search(r'/\d{6,}', link):
        clean_links.add(link)

links = list(clean_links)

driver.quit()

print("✅ Unique links found:", len(links))

# ==============================
# 🔥 SCRAPE DETAILS
# ==============================
headers = {"User-Agent": "Mozilla/5.0"}

saved = 0

for link in links:   # ✅ REMOVE LIMIT (IMPORTANT)
    try:
        res = requests.get(link, headers=headers, timeout=10)

        if res.status_code != 200:
            print("❌ Failed:", link)
            continue
        soup = BeautifulSoup(res.text, "html.parser")

        # 🎯 TITLE
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "N/A"

        # 🎯 DATE
        date = "N/A"
        meta_date = soup.find("meta", itemprop="startDate")
        if meta_date:
            date = meta_date.get("content", "N/A")

        # 🎯 LOCATION (FIXED LOGIC)
        location = "N/A"
        try:
            texts = list(soup.stripped_strings)

            for t in texts:
                t = t.strip()

                if "," in t and len(t) < 100:
                    if any(x in t.lower() for x in [
                        "open menu", "login", "host", "control",
                        "create", "app", "help", "suggestions",
                        "feedback", "sign in", "chat"
                    ]):
                        continue

                    location = t
                    break
        except:
            pass

        # fallback
        if location == "N/A":
            for tag in soup.find_all(["div", "span"]):
                text = tag.get_text(strip=True)
                if "bangalore" in text.lower() or "bengaluru" in text.lower():
                    location = text
                    break

        # 🎯 IMAGE
        image = "N/A"

        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            image = meta["content"]

        if image == "N/A":
            meta = soup.find("meta", property="twitter:image")
            if meta:
                image = meta.get("content")

        if image == "N/A":
            img = soup.find("img")
            if img and img.get("src"):
                image = img.get("src")

        # ✅ NEVER SKIP DATA
        if not title:
            title = "N/A"

        if not date:
            date = "N/A"

        if not location:
            location = "N/A"

        if not image:
            image = "N/A"

        # 💾 SAVE
        cursor.execute("""
        INSERT OR IGNORE INTO events (title, date, location, link, image)
        VALUES (?, ?, ?, ?, ?)
        """, (title, date, location, link, image))

        saved += 1
        print(f"✔ Saved: {title}")

    except Exception as e:
        print("❌ Error:", e)
        continue

# SAVE
conn.commit()
conn.close()

print(f"🎉 Scraping completed! Total saved: {saved}")