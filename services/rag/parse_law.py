"""Parse law PDFs into structured JSON"""
import json
import re
from typing import List, Dict

def parse_law_text(text: str) -> List[Dict]:
    """Parse plain law text into articles"""
    articles = []
    
    # Pattern: Article X - text
    pattern = r'Article\s+(\d+)[:-]\s*([^\n]+)'
    matches = re.finditer(pattern, text, re.IGNORECASE)
    
    for match in matches:
        article_num = match.group(1)
        article_text = match.group(2).strip()
        
        articles.append({
            "article_number": article_num,
            "law": "Law 175/2018",
            "text": article_text,
            "penalty_ar": ""
        })
    
    return articles

def save_articles(articles: List[Dict], output_path: str):
    """Save parsed articles to JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(articles)} articles to {output_path}")

if __name__ == "__main__":
    # Example usage
    sample_text = """
    Article 25: Punishment by imprisonment and fine for unauthorized access
    Article 26: Punishment for illegal interception of communications
    """
    
    articles = parse_law_text(sample_text)
    save_articles(articles, "/data/law/parsed/articles.json")
