from app.core.celery_app import celery_app
import urllib.parse
import requests
from bs4 import BeautifulSoup

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    proxies = {"http": proxy, "https": proxy} if proxy else None
    results = []
    
    # --- ENGINE 1: BING (Primary) ---
    try:
        bing_url = f"https://www.bing.com/search?q={encoded_query}"
        resp = requests.get(bing_url, headers=headers, proxies=proxies, timeout=10)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Bing places results in <li> tags with class "b_algo"
            for li in soup.find_all("li", class_="b_algo"):
                a_tag = li.find("a")
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    title = a_tag.text.strip()
                    if href.startswith("http") and not any(r["url"] == href for r in results):
                        results.append({
                            "title": title,
                            "url": href,
                            "domain": urllib.parse.urlparse(href).netloc
                        })
    except Exception:
        pass # If Bing fails or blocks the request, silently pass to the fallback

    # --- ENGINE 2: YAHOO (Fallback) ---
    if not results:
        try:
            # Removed the n=30 parameter to prevent HTTP 500 server crashes
            yahoo_url = f"https://search.yahoo.com/search?p={encoded_query}"
            resp = requests.get(yahoo_url, headers=headers, proxies=proxies, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
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
        except Exception:
            pass
            
    # If both engines fail to return data, retry the background task
    if not results:
        raise self.retry(exc=Exception("Search blocked. Both primary and fallback engines rejected the request."), countdown=10)

    return {
        "keyword": keyword,
        "status": "success",
        "count": len(results),
        "results": results
    }
