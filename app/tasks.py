from app.core.celery_app import celery_app
from ddgs import DDGS
import urllib.parse
import re

# Ordered list of clean search engines (excludes Bing/Yahoo to prevent fake honeypot results)
SEARCH_BACKENDS = ["duckduckgo", "brave", "google", "startpage"]

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    # Extract meaningful words from the keyword to verify result relevance
    stop_words = {"the", "and", "for", "near", "from", "with", "best", "top", "in", "of", "to"}
    query_tokens = [
        w.lower() for w in re.findall(r"\w+", keyword)
        if len(w) >= 3 and w.lower() not in stop_words
    ]

    last_error = None

    for backend_name in SEARCH_BACKENDS:
        try:
            ddgs = DDGS(proxy=proxy, timeout=15)
            # region="in-en" forces authentic Indian search rankings
            raw_results = ddgs.text(
                keyword,
                region="in-en",
                safesearch="off",
                max_results=30,
                backend=backend_name
            )

            if not raw_results:
                continue

            cleaned_results = []
            relevant_hits = 0

            for item in raw_results:
                href = (item.get("href") or item.get("url") or "").strip()
                title = (item.get("title") or "").strip()
                body = (item.get("body") or "").strip()

                if not href.startswith("http") or not title:
                    continue

                # Clean any accidental breadcrumb text if present
                if " › " in title:
                    title = title.split(" › ")[-1].strip()

                parsed_domain = urllib.parse.urlparse(href).netloc
                if not parsed_domain:
                    continue

                # Check if this result is genuinely related to the searched keyword
                combined_text = f"{title} {href} {body}".lower()
                if not query_tokens or any(token in combined_text for token in query_tokens):
                    relevant_hits += 1

                if not any(r["url"] == href for r in cleaned_results):
                    cleaned_results.append({
                        "title": title,
                        "url": href,
                        "domain": parsed_domain
                    })

            # Only accept the results if they pass the relevance check (blocks bot honeypots)
            if cleaned_results and relevant_hits > 0:
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(cleaned_results),
                    "results": cleaned_results
                }

        except Exception as e:
            last_error = str(e)
            continue

    raise self.retry(
        exc=Exception(f"Search engines temporarily unreachable. Last error: {last_error}"),
        countdown=5
    )
