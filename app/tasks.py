from app.core.celery_app import celery_app
import urllib.parse
import requests
from bs4 import BeautifulSoup

@celery_app.task(bind=True, max_retries=3)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    results = []

    # Modern browser headers with India regional preferences
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    # Force Bing to treat the request as originating from India
    cookies = {
        "SRCHHPGUSR": "SRCHLANG=en&NRSLT=20",
        "_EDGE_S": "mkt=en-in&F=1",
        "_SS": "SID=0"
    }

    proxies = {"http": proxy, "https": proxy} if proxy else None

    # --- ATTEMPT 1: BING INDIA ---
    try:
        bing_url = f"https://www.bing.com/search?q={encoded_query}&cc=IN&setlang=en-in"
        resp = requests.get(bing_url, headers=headers, cookies=cookies, proxies=proxies, timeout=12)

        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            for li in soup.select("li.b_algo"):
                h2 = li.select_one("h2")
                if not h2:
                    continue

                a_tag = h2.find("a")
                if not a_tag or not a_tag.get("href"):
                    continue

                href = a_tag["href"]

                # Remove nested attribution/breadcrumbs that mash into titles
                for extra in a_tag.select(".b_attribution, cite, span.c_tlbx, .b_algoSlug"):
                    extra.decompose()

                title = a_tag.get_text(separator=" ", strip=True)

                # Skip non-http and internal Bing redirects
                if not href.startswith("http") or "bing.com/ck/a" in href:
                    # If Bing masked it via redirect, check for actual target in container
                    continue

                parsed_domain = urllib.parse.urlparse(href).netloc
                if not parsed_domain or "bing.com" in parsed_domain:
                    continue

                if not any(r["url"] == href for r in results):
                    results.append({
                        "title": title,
                        "url": href,
                        "domain": parsed_domain
                    })
    except Exception:
        pass

    # --- ATTEMPT 2: YAHOO INDIA FALLBACK ---
    if not results:
        try:
            yahoo_url = f"https://in.search.yahoo.com/search?p={encoded_query}&ei=UTF-8"
            resp = requests.get(yahoo_url, headers=headers, proxies=proxies, timeout=12)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.select("h3.title a, div.compTitle h3 a"):
                    href = a_tag.get("href", "")
                    title = a_tag.get_text(strip=True)

                    if not href or not title:
                        continue

                    if "RU=" in href:
                        try:
                            ru_chunk = next((c for c in href.split("/") if c.startswith("RU=")), None)
                            if ru_chunk:
                                href = urllib.parse.unquote(ru_chunk[3:])
                        except Exception:
                            pass

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
        except Exception:
            pass

    # --- ATTEMPT 3: DUCKDUCKGO HTML INDIA FALLBACK ---
    if not results:
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}&kl=in-en"
            resp = requests.post(
                ddg_url,
                data={"q": keyword, "kl": "in-en"},
                headers=headers,
                proxies=proxies,
                timeout=12
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a_tag in soup.select(".result__a"):
                    href = a_tag.get("href", "")
                    title = a_tag.get_text(strip=True)
                    if not href or not title:
                        continue

                    if "duckduckgo.com/l/?uddg=" in href:
                        parsed_url = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed_url.query)
                        href = qs.get("uddg", [href])[0]

                    if not href.startswith("http"):
                        continue

                    parsed_domain = urllib.parse.urlparse(href).netloc
                    if not any(r["url"] == href for r in results):
                        results.append({
                            "title": title,
                            "url": href,
                            "domain": parsed_domain
                        })
        except Exception:
            pass

    if not results:
        raise self.retry(exc=Exception("Unable to retrieve search results. Retrying..."), countdown=5)

    return {
        "keyword": keyword,
        "status": "success",
        "count": len(results),
        "results": results
    }
