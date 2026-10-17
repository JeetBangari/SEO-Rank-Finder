from app.core.celery_app import celery_app
import urllib.parse
import requests
from bs4 import BeautifulSoup
import re

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    target_url = f"https://search.yahoo.com/search?p={encoded_query}&ei=UTF-8"

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    })

    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    try:
        response = session.get(target_url, timeout=12)

        if response.status_code != 200:
            raise Exception(f"Yahoo Search returned HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        # Target all common Yahoo result title selectors across variations
        candidate_tags = soup.select("h3.title a, div.compTitle h3 a, li div.compTitle a, li div.dd h3 a")

        for a_tag in candidate_tags:
            href = a_tag.get("href", "")
            title = a_tag.get_text(strip=True)

            if not href or not title:
                continue

            # Extract destination URL from Yahoo redirect wrapper
            if "RU=" in href:
                match = re.search(r"RU=([^/]+)", href)
                if match:
                    href = urllib.parse.unquote(match.group(1))

            # Filter out internal Yahoo helper links or navigation tabs
            if not href.startswith("http"):
                continue
            parsed_domain = urllib.parse.urlparse(href).netloc
            if "yahoo.com" in parsed_domain:
                continue

            if not any(r["url"] == href for r in results):
                results.append({
                    "title": title,
                    "url": href,
                    "domain": parsed_domain
                })

        if not results:
            raise Exception("Search engine returned 0 results. Page layout did not match or bot prompt encountered.")

        return {
            "keyword": keyword,
            "status": "success",
            "count": len(results),
            "results": results
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=4)
