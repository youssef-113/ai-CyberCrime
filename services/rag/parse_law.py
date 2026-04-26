"""Parse law documents into structured JSON with Markdown conversion

Always convert documents into clean, structured Markdown before indexing.
This is especially critical for legal and financial data.
Messy PDFs (broken tables, scattered headings) will ruin embeddings.
"""
import json
import re
import os
from typing import List, Dict, Optional


# Arabic article patterns
AR_ARTICLE_PATTERN = re.compile(
    r'المادة\s+(\d+)\s*[:-]?\s*([^\n]+?)(?:\n|$)',
    re.IGNORECASE
)

# English article patterns
EN_ARTICLE_PATTERN = re.compile(
    r'Article\s+(\d+)\s*[:-]\s*([^\n]+)',
    re.IGNORECASE
)

# Penalty patterns (Arabic)
PENALTY_PATTERNS = [
    re.compile(r'(?:عقوب[ةه]|يعاق[ب]|الحبس|السجن|الغرام[ةه])[^\n.]+', re.IGNORECASE),
    re.compile(r'(?:punishment|penalty|imprisonment|fine)[^\n.]+', re.IGNORECASE),
]

# Law reference patterns
LAW_REF_PATTERN = re.compile(r'قانون\s+رقم\s+(\d+)\s*[/ل]\s*(\d+)|Law\s+(?:No\.?\s*)?(\d+)/(?:\d+)', re.IGNORECASE)


def _extract_law_ref(text: str) -> str:
    """Extract law reference from text."""
    match = LAW_REF_PATTERN.search(text)
    if match:
        if match.group(1):
            return f"Law {match.group(1)}/{match.group(2)}"
        return match.group(0)
    return "Unknown"


def _extract_penalties(text: str) -> str:
    """Extract penalty clauses from article text."""
    for pattern in PENALTY_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            return matches[0].strip()
    return ""


def _extract_keywords(text: str, existing_keywords: List[str] = None) -> List[str]:
    """Extract keywords from article text.

    Uses simple heuristics: legal terms, crime types, technology terms.
    """
    keywords = list(existing_keywords) if existing_keywords else []

    # Common cybercrime keywords (bilingual)
    cybercrime_terms = {
        "unauthorized access", "hacking", "information systems",
        "interception", "communications", "fraud", "identity theft",
        "phishing", "malware", "ransomware", "data breach",
        "cybercrime", "electronic fraud", "digital evidence",
        "الدخول غير المصرح", "اختراق", "أنظمة المعلومات",
        "اعتراض", "اتصالات", "احتيال", "سرقة الهوية",
        "تصيد", "برمجيات خبيثة", "ابتزاز", "اختراق بيانات",
        "جرائم إلكترونية", "احتيال إلكتروني", "أدلة رقمية",
    }

    text_lower = text.lower()
    for term in cybercrime_terms:
        if term in text_lower and term not in keywords:
            keywords.append(term)

    return keywords[:10]  # cap at 10


def _to_clean_markdown(article: Dict) -> str:
    """Convert article to clean Markdown format.

    Clean structured Markdown before indexing is critical
    for legal and financial data quality.
    """
    md_parts = []

    # Header
    law = article.get("law", "Unknown")
    art_num = article.get("article_number", "?")
    md_parts.append(f"## Article {art_num} — {law}")

    # Title
    title = article.get("title_en", "") or article.get("title_ar", "")
    if title:
        md_parts.append(f"**{title}**\n")

    # Arabic text
    text_ar = article.get("text_ar", "")
    if text_ar:
        md_parts.append(text_ar)

    # English text
    text_en = article.get("text_en", "")
    if text_en:
        md_parts.append(text_en)

    # Plain text fallback
    text = article.get("text", "")
    if text and not text_ar and not text_en:
        md_parts.append(text)

    # Penalty
    penalty = article.get("penalty_ar", "")
    if penalty:
        md_parts.append(f"\n*Penalty: {penalty}*")

    return "\n\n".join(md_parts)


def parse_law_text(text: str, law_ref: str = None) -> List[Dict]:
    """Parse plain law text into structured articles.

    Supports both Arabic and English article formats.
    """
    articles = []
    law_ref = law_ref or _extract_law_ref(text)

    # Try Arabic pattern first
    matches = list(AR_ARTICLE_PATTERN.finditer(text))
    if not matches:
        matches = list(EN_ARTICLE_PATTERN.finditer(text))

    for match in matches:
        article_num = match.group(1)
        article_text = match.group(2).strip()

        # Extend article text to next article or end
        start = match.start()
        end = matches[matches.index(match) + 1].start() if matches.index(match) + 1 < len(matches) else len(text)
        full_text = text[start:end].strip()

        penalty = _extract_penalties(full_text)
        keywords = _extract_keywords(full_text)

        article = {
            "article_id": f"law_{law_ref.replace('/', '_')}_art{article_num}",
            "article_number": article_num,
            "law": law_ref,
            "text": full_text,
            "text_ar": full_text if any('\u0600' <= c <= '\u06FF' for c in full_text) else "",
            "text_en": full_text if not any('\u0600' <= c <= '\u06FF' for c in full_text) else "",
            "title_ar": "",
            "title_en": "",
            "penalty_ar": penalty,
            "keywords": keywords,
            "crime_type": "general",
            "source_file": "",
        }

        articles.append(article)

    return articles


def parse_articles_json(data: List[Dict]) -> List[Dict]:
    """Parse existing articles.json into enriched format.

    Adds: keywords, summary, clean markdown, potential questions.
    """
    enriched = []

    for article in data:
        # Get best text
        text = article.get("text_ar", "") or article.get("text_en", "") or article.get("text", "")
        if not text:
            continue

        # Extract/enrich keywords
        existing_kw = article.get("keywords", [])
        keywords = _extract_keywords(text, existing_kw)

        # Build summary from title
        summary = article.get("title_ar", "") or article.get("title_en", "") or ""

        # Clean markdown version
        markdown = _to_clean_markdown(article)

        enriched.append({
            **article,
            "text": text,
            "keywords": keywords,
            "summary": summary,
            "markdown": markdown,
        })

    return enriched


def save_articles(articles: List[Dict], output_path: str):
    """Save parsed articles to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(articles)} articles to {output_path}")


if __name__ == "__main__":
    # Example: parse the existing articles.json and enrich it
    input_path = "/data/law/articles.json"
    output_path = "/data/law/parsed/articles_enriched.json"

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        enriched = parse_articles_json(data)
        save_articles(enriched, output_path)
        print(f"Enriched {len(enriched)} articles")
    except FileNotFoundError:
        # Fallback to sample
        sample_text = """
        Article 25: Punishment by imprisonment and fine for unauthorized access
        Article 26: Punishment for illegal interception of communications
        """
        articles = parse_law_text(sample_text)
        save_articles(articles, output_path)
