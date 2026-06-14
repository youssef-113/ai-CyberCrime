from typing import List, Dict

CRIME_TO_ARTICLES = {
    "blackmail": [
        {"article_number": "25", "law": "175/2018", "relevance": "primary"},
        {"article_number": "26", "law": "175/2018", "relevance": "primary"},
    ],
    "sextortion": [
        {"article_number": "25", "law": "175/2018", "relevance": "primary"},
        {"article_number": "306", "law": "Penal Code", "relevance": "supporting"},
    ],
    "financial_fraud": [
        {"article_number": "23", "law": "175/2018", "relevance": "primary"},
        {"article_number": "336", "law": "Penal Code", "relevance": "primary"},
    ],
    "phishing": [
        {"article_number": "23", "law": "175/2018", "relevance": "primary"},
    ],
    "identity_theft": [
        {"article_number": "76", "law": "175/2018", "relevance": "primary"},
    ],
    "cyber_threat": [
        {"article_number": "24", "law": "175/2018", "relevance": "primary"},
    ],
    "defamation": [
        {"article_number": "302", "law": "Penal Code", "relevance": "primary"},
    ],
    "hate_speech": [
        {"article_number": "25", "law": "175/2018", "relevance": "primary"},
    ],
    "privacy_violation": [
        {"article_number": "25", "law": "175/2018", "relevance": "primary"},
        {"article_number": "76", "law": "175/2018", "relevance": "primary"},
    ],
    "data_breach": [
        {"article_number": "76", "law": "175/2018", "relevance": "primary"},
        {"article_number": "309", "law": "Penal Code", "relevance": "supporting"},
    ],
    "account_hacking": [
        {"article_number": "2", "law": "175/2018", "relevance": "primary"},
        {"article_number": "76", "law": "175/2018", "relevance": "primary"},
    ],
    "unknown": [],
}
def get_suggested_articles(crime_type: str, confidence: float) -> List[Dict]:

    articles = CRIME_TO_ARTICLES.get(crime_type, [])

    if confidence >= 0.8:
        return [a for a in articles if a["relevance"] == "primary"]
    else:
        return articles