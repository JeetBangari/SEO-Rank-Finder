# SEO Rank Finder 🚀

A custom, fully free SEO rank tracking API and web dashboard. This tool allows users to track search engine rankings for specific commercial keywords and calculate the exact ranking position of target domains.

Built to bypass aggressive anti-bot mechanisms without spending money on paid proxies or commercial SERP APIs, this project relies on a lightweight DuckDuckGo HTML parser for clean, uninterrupted data extraction.

## ✨ Features
* **Zero-Cost Scraping:** Utilizes DuckDuckGo's HTML-only search engine to bypass IP bans and CAPTCHAs without needing paid proxies.
* **Asynchronous Processing:** Built with Celery and Redis to handle background scraping tasks without freezing the web interface.
* **Interactive Dashboard:** A single-page web app served directly by FastAPI that polls job status and renders results in real-time.
* **Auto-Highlighting:** Automatically detects and highlights target domains (e.g., *outletmallofindia.com*) and specific brand names in the search results.

## 🛠️ Tech Stack
* **Backend:** Python, FastAPI
* **Background Tasks:** Celery, Redis
* **Scraping & Parsing:** `curl_cffi` (for TLS fingerprinting), `beautifulsoup4`
* **Frontend:** HTML, CSS, Vanilla JavaScript

## 🚀 Local Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/yourusername/seo-rank-finder.git](https://github.com/yourusername/seo-rank-finder.git)
   cd seo-rank-finder

2. **Install Dependencies:**
    pip install -r requirements.txt

3. **Start the Redis Server**
    docker run -d -p 6379:6379 redis

4. **Run the Application**
    # Terminal 1: Start Celery Worker
celery -A app.core.celery_app worker --loglevel=info

# Terminal 2: Start FastAPI Server
uvicorn app.main:app --reload

5. **Accessthe Dashboard:**
   http://localhost:8000/
