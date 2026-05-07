"""Build knowledge base from law articles - ChromaDB with Rich Metadata

Each chunk includes:
- Short 1-2 line summary
- Keywords
- Source document info
- Parent-child relationships for context expansion
"""
import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag.build_kb")


def build_knowledge_base(
    articles_path: str = None,
    tenant_id: str = "default",
):
    """Index law articles into ChromaDB with rich metadata and parent-child chunking."""
    from .ingestion import index_articles

    articles_path = articles_path or os.getenv(
        "ARTICLES_PATH",
        "/data/law/articles.json"
    )

    try:
        with open(articles_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
        logger.info(f"Loaded {len(articles)} articles from {articles_path}")
    except FileNotFoundError:
        logger.warning("No articles.json found. Creating sample data...")
        articles = [
            {
                "article_id": "law175_art25",
                "article_number": "25",
                "law": "Law 175/2018",
                "crime_type": "unauthorized_access",
                "text_ar": "",
                "text_en": "",
                "text": "Punishment by imprisonment and fine for unauthorized access to information systems",
                "title_ar": "الدخول غير المصرح به في أنظمة المعلومات",
                "title_en": "Unauthorized Access to Information Systems",
                "penalty_ar": "الحبس و الغرامة",
                "keywords": ["unauthorized access", "information systems", "hacking", "الدخول غير المصرح"],
                "source_file": "sample",
            },
            {
                "article_id": "law175_art26",
                "article_number": "26",
                "law": "Law 175/2018",
                "crime_type": "interception",
                "text_ar": "",
                "text_en": "",
                "text": "Punishment for illegal interception of communications",
                "title_ar": "اعتراض الاتصالات غير القانوني",
                "title_en": "Illegal Interception of Communications",
                "penalty_ar": "الحبس مدة لا تقل عن سنة",
                "keywords": ["interception", "communications", "eavesdropping", "اعتراض"],
                "source_file": "sample",
            },
        ]

    for article in articles:
        if not article.get("text"):
            article["text"] = article.get("text_ar", "") or article.get("text_en", "") or ""

        if not article.get("summary"):
            article["summary"] = article.get("title_ar", "") or article.get("title_en", "") or ""

        if not article.get("keywords"):
            article["keywords"] = []

    result = index_articles(articles, tenant_id=tenant_id)

    logger.info(f"Build complete: {result}")
    return result


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    build_knowledge_base(articles_path=path)