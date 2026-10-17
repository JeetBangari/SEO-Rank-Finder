from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse

class GoogleParser:
    @staticmethod
    def parse_results(html_content: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html_content, "html.parser")
        results = []
        
        # SearXNG wraps each search result in an <article class="result"> tag
        for result_div in soup.select("article.result"):
            # The title and actual link are nested inside an <h4> tag
            header = result_div.select_one("h4 a")
            
            if not header or not header.get("href"):
                continue
                
            href = header["href"]
            title = header.get_text(strip=True)
                
            if not href.startswith("http"):
                continue
                
            # Prevent duplicate URLs in the final results list
            if not any(r["url"] == href for r in results):
                results.append({
                    "title": title,
                    "url": href,
                    "domain": urllib.parse.urlparse(href).netloc
                })
                
        return results
