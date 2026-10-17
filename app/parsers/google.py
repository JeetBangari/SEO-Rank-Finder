from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse

class GoogleParser:
    @staticmethod
    def parse_results(html_content: str) -> List[Dict[str, str]]:
        # Using html.parser to avoid requiring the external lxml library
        soup = BeautifulSoup(html_content, "html.parser")
        results = []
        
        # DuckDuckGo HTML version puts results inside <div class="result">
        for result_div in soup.select(".result"):
            a_tag = result_div.select_one(".result__a")
            if not a_tag or not a_tag.get("href"):
                continue
                
            href = a_tag["href"]
            title = a_tag.get_text(strip=True)
            
            # Clean DuckDuckGo redirect wrappers if present
            if "duckduckgo.com/l/?uddg=" in href:
                parsed_url = urllib.parse.urlparse(href)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                href = query_params.get("uddg", [href])[0]
                
            if not href.startswith("http"):
                continue
                
            if not any(r["url"] == href for r in results):
                results.append({
                    "title": title,
                    "url": href,
                    "domain": urllib.parse.urlparse(href).netloc
                })
                
        return results
