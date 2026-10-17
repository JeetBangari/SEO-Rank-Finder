from app.core.celery_app import celery_app
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import urllib.parse
import re


def clean_title_text(raw_title: str) -> str:
    """Removes glued breadcrumb URLs and normalizes spacing in titles."""
    cleaned = re.sub(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*(https?://[^\s]+)?", "", raw_title)
    if " › " in cleaned:
        cleaned = cleaned.split(" › ")[-1]
    if " > " in cleaned:
        cleaned = cleaned.split(" > ")[-1]
    return " ".join(cleaned.split()).strip()


def is_relevant_serp(results: list, keyword: str) -> bool:
    """Verifies the search engine returned results matching the query (blocks bot honeypots)."""
    if not results:
        return False
    stop_words = {"the", "and", "for", "near", "from", "with", "best", "top", "in", "of", "to"}
    tokens = [
        w.lower() for w in re.findall(r"\w+", keyword)
        if len(w) >= 3 and w.lower() not in stop_words
    ]
    if not tokens:
        return True
    matches = sum(
        1 for r in results
        if any(t in f"{r['title']} {r['url']}".lower() for t in tokens)
    )
    return matches > 0


@celery_app.task(bind=True, max_retries=2)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    proxies = {"http": proxy, "https": proxy} if proxy else None

    # --- LAYER 1: JINA READER PROXY -> DUCKDUCKGO INDIA ---
    try:
        ddg_target = f"https://html.duckduckgo.com/html/?q={encoded_query}&kl=in-en"
        jina_url = f"https://r.jina.ai/{ddg_target}"
        jina_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Return-Format": "html",
        }
        resp = cffi_requests.get(
            jina_url,
            headers=jina_headers,
            proxies=proxies,
            impersonate="chrome120",
            timeout=15
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for a_tag in soup.select(".result__a"):
                href = a_tag.get("href", "").strip()
                title = a_tag.get_text(separator=" ", strip=True)
                if "duckduckgo.com/l/?uddg=" in href:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = qs.get("uddg", [href])[0]
                if href.startswith("http") and title:
                    domain = urllib.parse.urlparse(href).netloc
                    if domain and "duckduckgo.com" not in domain and not any(r["url"] == href for r in results):
                        results.append({
                            "title": clean_title_text(title),
                            "url": href,
                            "domain": domain
                        })
            if is_relevant_serp(results, keyword):
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(results),
                    "results": results
                }
    except Exception:
        pass

    # --- LAYER 2: BRAVE SEARCH INDIA ---
    try:
        brave_url = f"https://search.brave.com/search?q={encoded_query}&country=in"
        brave_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
        }
        resp = cffi_requests.get(
            brave_url,
            headers=brave_headers,
            proxies=proxies,
            impersonate="chrome120",
            timeout=12
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for snippet in soup.select("div.snippet"):
                a_tag = snippet.select_one("a.svelte-14r20fy, a[href^='http']")
                if not a_tag or not a_tag.get("href"):
                    continue
                href = a_tag["href"].strip()
                title_el = snippet.select_one(".title, .snippet-title")
                raw_title = title_el.get_text(separator=" ", strip=True) if title_el else a_tag.get_text(separator=" ", strip=True)
                title = clean_title_text(raw_title)
                if href.startswith("http") and title:
                    domain = urllib.parse.urlparse(href).netloc
                    if domain and "brave.com" not in domain and not any(r["url"] == href for r in results):
                        results.append({
                            "title": title,
                            "url": href,
                            "domain": domain
                        })
            if is_relevant_serp(results, keyword):
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(results),
                    "results": results
                }
    except Exception:
        pass

    # --- LAYER 3: YAHOO INDIA WITH CHROME TLS IMPERSONATION ---
    yahoo_urls = [
        f"https://in.search.yahoo.com/search?p={encoded_query}&vc=in&ei=UTF-8",
        f"https://search.yahoo.com/search?p={encoded_query}&ei=UTF-8",
    ]
    for y_url in yahoo_urls:
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            }
            resp = cffi_requests.get(
                y_url,
                headers=headers,
                proxies=proxies,
                impersonate="chrome120",
                timeout=12
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []
                for comp in soup.select("div.compTitle, h3.title"):
                    a_tag = comp.find("a") if comp.name != "a" else comp
                    if not a_tag or not a_tag.get("href"):
                        continue
                    href = a_tag["href"].strip()

                    for junk in a_tag.select("span.d-ib, span.fz-ms, span.tc, cite, div"):
                        junk.decompose()

                    title = clean_title_text(a_tag.get_text(separator=" ", strip=True))
                    if not title:
                        continue

                    if "RU=" in href:
                        match = re.search(r"RU=([^/]+)", href)
                        if match:
                            href = urllib.parse.unquote(match.group(1))

                    if not href.startswith("http"):
                        continue
                    domain = urllib.parse.urlparse(href).netloc
                    if not domain or "yahoo.com" in domain or "bing.com" in domain:
                        continue

                    if not any(r["url"] == href for r in results):
                        results.append({
                            "title": title,
                            "url": href,
                            "domain": domain
                        })

                if is_relevant_serp(results, keyword):
                    return {
                        "keyword": keyword,
                        "status": "success",
                        "count": len(results),
                        "results": results
                    }
        except Exception:
            continue

    # --- LAYER 4: DDGS METASEARCH FALLBACK ---
    for backend_opt in ["auto", "yahoo", "brave", "mojeek", "yandex"]:
        try:
            raw_ddgs = DDGS(proxy=proxy, timeout=12).text(
                keyword,
                region="in-en",
                safesearch="off",
                max_results=25,
                backend=backend_opt
            )
            results = []
            for item in (raw_ddgs or []):
                href = (item.get("href") or item.get("url") or "").strip()
                title = clean_title_text(item.get("title") or "")
                if href.startswith("http") and title:
                    domain = urllib.parse.urlparse(href).netloc
                    if domain and not any(r["url"] == href for r in results):
                        results.append({
                            "title": title,
                            "url": href,
                            "domain": domain
                        })
            if is_relevant_serp(results, keyword):
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(results),
                    "results": results
                }
        except Exception:
            continue

    raise self.retry(exc=Exception("Search engines rate-limited the request. Retrying..."), countdown=3)
