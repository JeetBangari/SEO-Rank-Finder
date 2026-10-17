from app.core.celery_app import celery_app
from app.parsers.google import GoogleParser
import urllib.parse
import requests 

# A list of reliable, public SearXNG instances that allow HTML scraping
SEARXNG_INSTANCES = [
    "https://searx.tiekoetter.com/search",
    "https://searx.work/search",
    "https://paulgo.io/search",
    "https://search.mdosch.de/search",
    "https://search.ononoki.org/search"
]

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    last_error = None
    
    # Loop through the instances until one successfully returns the results
    for base_url in SEARXNG_INSTANCES:
        target_url = f"{base_url}?q={encoded_query}"
        
        try:
            # Short 8-second timeout so it quickly moves to the next server if blocked
            response = requests.get(
                target_url,
                headers=headers,
                proxies=proxies,
                timeout=8
            )
            
            if response.status_code == 200:
                parsed_items = GoogleParser.parse_results(response.text)
                
                # Ensure the instance actually returned valid results before declaring success
                if len(parsed_items) > 0:
                    return {
                        "keyword": keyword,
                        "status": "success",
                        "count": len(parsed_items),
                        "results": parsed_items
                    }
                    
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            continue # Move to the next instance in the list

    # If all instances fail or block the request, retry the Celery task later
    raise self.retry(exc=Exception(f"All search instances failed. Last error: {last_error}"), countdown=10)
