from app.core.celery_app import celery_app
from app.parsers.google import GoogleParser
from curl_cffi import requests

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    # Target the HTML endpoint but prepare to use POST instead of GET
    target_url = "https://html.duckduckgo.com/html/"
    
    # Advanced headers to perfectly mimic a real Chrome browser submitting a form
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://html.duckduckgo.com",
        "Referer": "https://html.duckduckgo.com/",
    }
    
    # Send the search query securely in the request body, not the URL
    data = {"q": keyword}
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        # Use POST and upgrade the TLS fingerprint to a newer Chrome version
        response = requests.post(
            target_url,
            headers=headers,
            data=data,
            proxies=proxies,
            impersonate="chrome124", 
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
