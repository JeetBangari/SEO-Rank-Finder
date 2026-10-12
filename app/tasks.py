from app.core.celery_app import celery_app
from app.parsers.google import GoogleParser
from curl_cffi import requests
import urllib.parse

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    # Target DuckDuckGo HTML Lite version (lightweight, zero blocks)
    target_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.get(
            target_url,
            headers=headers,
            proxies=proxies,
            impersonate="chrome120",
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP request failed with status {response.status_code}.")

        parsed_items = GoogleParser.parse_results(response.text)
        
        return {
            "keyword": keyword,
            "status": "success",
            "count": len(parsed_items),
            "results": parsed_items
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)