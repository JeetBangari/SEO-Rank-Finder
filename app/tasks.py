from app.core.celery_app import celery_app
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import urllib.parse
import requests
import re

# Known decoy/honeypot domains served by datacenter firewalls
HONEYPOT_DOMAINS = {
    "storeopeninghours.com",
    "ergonomicsnerd.com",
    "theworkspacehero.com",
    "ergonomiczone.com",
    "homehustlehub.com",
}

SKIP_DOMAINS = {
    "google.com",
    "www.google.com",
    "google.co.in",
    "www.google.co.in",
    "duckduckgo.com",
    "html.duckduckgo.com",
    "lite.duckduckgo.com",
    "r.jina.ai",
    "jina.ai",
    "bing.com",
    "www.bing.com",
    "yahoo.com",
    "search.yahoo.com",
    "in.search.yahoo.com",
}


def clean_title_text(raw_title: str) -> str:
    """Strips Markdown hashes, glued breadcrumb URLs, and extra whitespace."""
    cleaned = re.sub(r"^#+\s*", "", raw_title.strip())
    cleaned = re.sub(r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\s*(https?://[^\s]+)?", "", cleaned)
    if " › " in cleaned:
        cleaned = cleaned.split(" › ")[-1]
    if " > " in cleaned:
        cleaned = cleaned.split(" > ")[-1]
    return " ".join(cleaned.split()).strip()


def unwrap_url(href: str) -> str:
    """Extracts the destination URL from DuckDuckGo or Google redirect wrappers."""
    href = href.strip()
    if "duckduckgo.com/l/?" in href or "uddg=" in href:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in qs:
            href = qs["uddg"][0]
    elif "/url?" in href and ("q=" in href or "url=" in href):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        href = qs.get("q", qs.get("url", [href]))[0]
    return href


def is_valid_serp(results: list, keyword: str) -> bool:
    """Strictly validates that results are genuine, non-honeypot, and match the query."""
    if len(results) < 4:
        return False

    # Immediately reject if any known datacenter honeypot domain is present
    for r in results:
        if any(bad in r["domain"].lower() for bad in HONEYPOT_DOMAINS):
            return False

    stop_words = {"the", "and", "for", "near", "from", "with", "best", "top", "in", "of", "to"}
    tokens = [
        w.lower() for w in re.findall(r"\w+", keyword)
        if len(w) >= 3 and w.lower() not in stop_words
    ]
    if not tokens:
        return True

    combined_serp_text = " ".join(f"{r['title']} {r['url']}" for r in results).lower()

    # Every distinctive token in the last position (e.g., 'india', 'thane') must appear somewhere in the SERP
    if tokens[-1] not in combined_serp_text:
        return False

    # Require at least 60% of the query's meaningful words to appear in the SERP
    matched_tokens = sum(1 for t in tokens if t in combined_serp_text)
    return matched_tokens >= max(1, int(len(tokens) * 0.6))


def parse_ddg_html(html_text: str) -> list:
    """Parses standard DuckDuckGo HTML and Lite pages."""
    soup = BeautifulSoup(html_text, "html.parser")
    results = []
    for a_tag in soup.select(".result__a, a.result-link"):
        href = unwrap_url(a_tag.get("href", ""))
        title = clean_title_text(a_tag.get_text(separator=" ", strip=True))
        if not href.startswith("http") or not title:
            continue
        domain = urllib.parse.urlparse(href).netloc.lower()
        if not domain or any(skip in domain for skip in SKIP_DOMAINS):
            continue
        if not any(r["url"] == href for r in results):
            results.append({"title": title, "url": href, "domain": domain})
    return results


def parse_jina_markdown(md_text: str) -> list:
    """Parses Markdown links [Title](URL) returned by Jina Reader."""
    results = []
    pattern = re.compile(r"\[([^\[\]]+)\]\((https?://[^\s\)]+)\)")
    for raw_title, raw_url in pattern.findall(md_text):
        href = unwrap_url(raw_url)
        title = clean_title_text(raw_title)
        if not href.startswith("http") or len(title) < 4:
            continue
        if title.lower().startswith(("image", "logo", "cached", "similar", "feedback")):
            continue
        domain = urllib.parse.urlparse(href).netloc.lower()
        if not domain or any(skip in domain for skip in SKIP_DOMAINS):
            continue
        if not any(r["url"] == href for r in results):
            results.append({"title": title, "url": href, "domain": domain})
    return results


@celery_app.task(bind=True, max_retries=2)
def scrape_keyword_task(self, keyword: str, proxy: str = None):
    encoded_query = urllib.parse.quote_plus(keyword)
    ddg_india_url = f"https://html.duckduckgo.com/html/?q={encoded_query}&kl=in-en"
    google_india_url = f"https://www.google.com/search?q={encoded_query}&gl=in&hl=en"

    # --- LAYER 1: PROXY RELAYS -> DUCKDUCKGO INDIA HTML (Exact Day-1 HTML format) ---
    relay_urls = [
        f"https://api.codetabs.com/v1/proxy?quest={urllib.parse.quote(ddg_india_url, safe='')}",
        f"https://api.allorigins.win/raw?url={urllib.parse.quote(ddg_india_url, safe='')}",
    ]
    for relay_url in relay_urls:
        try:
            resp = requests.get(relay_url, timeout=12)
            if resp.status_code == 200:
                results = parse_ddg_html(resp.text)
                if is_valid_serp(results, keyword):
                    return {
                        "keyword": keyword,
                        "status": "success",
                        "count": len(results),
                        "results": results,
                    }
        except Exception:
            continue

    # --- LAYER 2: JINA READER MARKDOWN RELAY -> GOOGLE INDIA & DUCKDUCKGO INDIA ---
    jina_targets = [
        f"https://r.jina.ai/{google_india_url}",
        f"https://r.jina.ai/{ddg_india_url}",
    ]
    for jina_url in jina_targets:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "X-No-Cache": "true",
            }
            resp = requests.get(jina_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                results = parse_jina_markdown(resp.text)
                if is_valid_serp(results, keyword):
                    return {
                        "keyword": keyword,
                        "status": "success",
                        "count": len(results),
                        "results": results,
                    }
        except Exception:
            continue

    # --- LAYER 3: DUCKDUCKGO LITE INDIA (Direct POST with Chrome TLS Impersonation) ---
    try:
        lite_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://lite.duckduckgo.com",
            "Referer": "https://lite.duckduckgo.com/",
        }
        resp = cffi_requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": keyword, "kl": "in-en"},
            headers=lite_headers,
            impersonate="chrome120",
            timeout=12,
        )
        if resp.status_code == 200:
            results = parse_ddg_html(resp.text)
            if is_valid_serp(results, keyword):
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(results),
                    "results": results,
                }
    except Exception:
        pass

    # --- LAYER 4: DDGS METASEARCH WITH STRICT HONEYPOT FILTER ---
    for backend_opt in ["duckduckgo", "brave", "startpage", "mojeek", "auto"]:
        try:
            raw_ddgs = DDGS(proxy=proxy, timeout=12).text(
                keyword,
                region="in-en",
                safesearch="off",
                max_results=25,
                backend=backend_opt,
            )
            results = []
            for item in (raw_ddgs or []):
                href = unwrap_url(item.get("href") or item.get("url") or "")
                title = clean_title_text(item.get("title") or "")
                if href.startswith("http") and title:
                    domain = urllib.parse.urlparse(href).netloc.lower()
                    if domain and not any(skip in domain for skip in SKIP_DOMAINS):
                        if not any(r["url"] == href for r in results):
                            results.append({"title": title, "url": href, "domain": domain})
            if is_valid_serp(results, keyword):
                return {
                    "keyword": keyword,
                    "status": "success",
                    "count": len(results),
                    "results": results,
                }
        except Exception:
            continue

    raise self.retry(exc=Exception("All search relays busy. Retrying..."), countdown=3)
