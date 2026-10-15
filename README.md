# 🎉 Event Aggregator System

A full-stack web application that scrapes local event data, stores it in a database, and displays it through a dynamic Flask web interface.

🔗 **Live Demo:** https://event-aggregator-system.onrender.com
📂 **GitHub Repo:** https://github.com/chitrabadiger23/event-aggregator-system

---

## 🚀 Overview

This project automatically collects event information from websites, processes it, and presents it in a clean, user-friendly interface.

It solves the problem of discovering local events by aggregating them into one platform.


## 🖼️ Screenshots

### 🏠 Home Page
![Home Page](./screenshot-home1.png)
![Home Page](./screenshot-home2.png)
### 📅 Events Page

![Events Page](./screenshot-events1.png)
![Events Page](./screenshot-events2.png)


## ⚙️ Tech Stack

* **Backend:** Python, Flask
* **Web Scraping:** Selenium, BeautifulSoup
* **Database:** SQLite
* **Frontend:** HTML, CSS
* **Deployment:** Render

---

## ✨ Key Features

* 🔍 Scrapes real-time event data
* 📅 Displays upcoming events
* 🖼️ Shows event images
* 🔎 Search functionality
* 🎯 Filter events (Tomorrow, Week, Month)
* 🌐 Live deployed web application
* ⚡ Fast and lightweight

---

## 🧠 How It Works

1. Selenium opens the event website and collects event links
2. BeautifulSoup extracts:

   * Title
   * Date
   * Location
   * Image
3. Data is stored in a SQLite database (`events.db`)
4. Flask reads the database and renders events on the website
5. Users can browse, search, and filter events

---

## 🛠️ How to Run Locally

### 1️⃣ Clone the repository

```
git clone https://github.com/chitrabadiger23/event-aggregator-system.git
cd event-aggregator-system
```

### 2️⃣ Install dependencies

```
pip install -r requirements.txt
```

### 3️⃣ Run scraper

```
python scraper.py
```

### 4️⃣ Run Flask app

```
python app.py
```

### 5️⃣ Open in browser

```
http://127.0.0.1:5000
```

---

## 🌍 Deployment (Render)

1. Push your project to GitHub
2. Go to https://render.com
3. Create a new **Web Service**
4. Connect your GitHub repository
5. Set:

```
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
```

6. Deploy 🚀

---

## 📂 Project Structure

```
event-aggregator-system/
│
├── app.py
├── scraper.py
├── events.db
├── requirements.txt
├── templates/
├── static/
└── scripts/
```

---

## ⚠️ Notes

* Selenium scraper runs locally
* Database must be updated before deployment
* Render free tier may sleep after inactivity

---

## 👨‍💻 Author

**Chitra**
GitHub: https://github.com/chitrabadiger23

---

## ⭐ If you like this project

Give it a ⭐ on GitHub!
