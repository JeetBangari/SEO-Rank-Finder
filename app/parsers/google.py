import json
from typing import List, Dict
import urllib.parse

class GoogleParser:
    @staticmethod
    def parse_results(json_content: str) -> List[Dict[str, str]]:
        results = []
        try:
            # We parse the raw JSON returned by SearXNG
            data = json.loads(json_content)
            
            for item in data.get("results", []):
                href = item.get("url")
                title = item.get("title")
                
                if not href or not title:
                    continue
                    
                if not href.startswith("http"):
                    continue
                    
                if not any(r["url"] == href for r in results):
                    results.append({
                        "title": title,
                        "url": href,
                        "domain": urllib.parse.urlparse(href).netloc
                    })
                    
        except json.JSONDecodeError:
            pass 
            
        return results
