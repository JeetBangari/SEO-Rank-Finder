from app.core.celery_app import celery_app
import urllib.parse
import requests
from bs4 import BeautifulSoup

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    
    # Using only Yahoo Search (without the n=30 parameter to prevent 500 errors)
    url = f"https://search.yahoo.com/search?p={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        
        if response.status_code != 200:
            raise Exception(f"Search failed with status {response.status_code}")
            
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        # Yahoo places search results inside <h3> tags with the class "title"
        for h3 in soup.find_all("h3", class_="title"):
            a_tag = h3.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                title = a_tag.text.strip()
                
                # Clean Yahoo's tracking wrapper from the URL
                if "RU=" in href:
                    try:
                        ru_chunk = next((chunk for chunk in href.split('/') if chunk.startswith('RU=')), None)
                        if ru_chunk:
                            href = urllib.parse.unquote(ru_chunk[3:])
                    except:
                        pass
                        
                if href.startswith("http") and not any(r["url"] == href for r in results):
                    results.append({
                        "title": title,
                        "url": href,
                        "domain": urllib.parse.urlparse(href).netloc
                    })
                    
        if len(results) == 0:
            raise Exception("Search engine returned 0 results. Retrying...")

        return {
            "keyword": keyword,
            "status": "success",
            "count": len(results),
            "results": results
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
