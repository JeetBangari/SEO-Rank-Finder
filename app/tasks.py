from app.core.celery_app import celery_app
from duckduckgo_search import DDGS
import urllib.parse

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    try:
        results = []
        
        # DDGS connects directly to the internal API, natively bypassing frontend blocks
        with DDGS(proxy=proxy) as ddgs:
            # Fetch up to 30 results to give your pagination plenty of data
            search_results = list(ddgs.text(keyword, max_results=30))
            
            for item in search_results:
                href = item.get("href")
                title = item.get("title")
                
                if href and title:
                    results.append({
                        "title": title,
                        "url": href,
                        "domain": urllib.parse.urlparse(href).netloc
                    })

        return {
            "keyword": keyword,
            "status": "success",
            "count": len(results),
            "results": results
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
