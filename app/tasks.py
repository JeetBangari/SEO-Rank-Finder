from app.core.celery_app import celery_app
from app.parsers.google import GoogleParser
from curl_cffi import requests
import urllib.parse

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    
    # Target a public SearXNG instance requesting raw JSON instead of HTML
    target_url = f"https://searx.be/search?q={encoded_query}&format=json"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        response = requests.get(
            target_url,
            headers=headers,
            proxies=proxies,
            impersonate="chrome124", 
            timeout=15
        )
        
        # Automatic fallback to a backup instance if the first one fails
        if response.status_code != 200:
            target_url = f"https://opnxng.com/search?q={encoded_query}&format=json"
            response = requests.get(target_url, headers=headers, proxies=proxies, impersonate="chrome124", timeout=15)
            
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
