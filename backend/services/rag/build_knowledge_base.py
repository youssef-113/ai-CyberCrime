"""Build a ChromaDB knowledge base from validated law article JSON."""

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("rag.build_kb")


def _default_articles_path() -> Path:
    env_path = os.getenv("ARTICLES_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "law" / "articles.json"


def _load_articles(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Articles file does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"Articles path is not a file: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, dict) and isinstance(payload.get("articles"), list):
        payload = payload["articles"]

    if not isinstance(payload, list):
        raise ValueError("Articles JSON must be a list or an object containing an 'articles' list")

    return payload


def _prepare_articles(
    articles: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []

    for index, raw_article in enumerate(articles):
        if not isinstance(raw_article, dict):
            invalid.append({"index": index, "reason": "Article must be an object"})
            continue

        article = dict(raw_article)
        article_number = str(article.get("article_number") or "").strip()
        law = str(article.get("law") or "").strip()
        has_text = any(
            str(article.get(field) or "").strip()
            for field in ("text_ar", "text_en", "text")
        )

        missing = []
        if not article_number:
            missing.append("article_number")
        if not law:
            missing.append("law")
        if not has_text:
            missing.append("text_ar/text_en/text")

        if missing:
            invalid.append(
                {
                    "index": index,
                    "article_number": article_number,
                    "reason": f"Missing required fields: {', '.join(missing)}",
                }
            )
            continue

        article.setdefault("article_id", f"{law}:{article_number}")
        article.setdefault(
            "summary",
            article.get("title_ar") or article.get("title_en") or "",
        )
        article["keywords"] = article.get("keywords") or []
        valid.append(article)

    return valid, invalid


def build_knowledge_base(
    articles_path: Optional[str] = None,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    from .ingestion import index_articles

    path = Path(articles_path).expanduser().resolve() if articles_path else _default_articles_path()
    loaded_articles = _load_articles(path)
    valid_articles, invalid_articles = _prepare_articles(loaded_articles)

    if not valid_articles:
        raise ValueError("No valid law articles were found; indexing was not started")

    logger.info(
        "Loaded %s articles from %s; valid=%s invalid=%s tenant=%s",
        len(loaded_articles),
        path,
        len(valid_articles),
        len(invalid_articles),
        tenant_id,
    )

    result = index_articles(valid_articles, tenant_id=tenant_id)
    result.update(
        {
            "source_path": str(path),
            "articles_loaded": len(loaded_articles),
            "articles_valid": len(valid_articles),
            "articles_invalid": len(invalid_articles),
            "invalid_articles": invalid_articles,
        }
    )
    logger.info("Knowledge-base build completed: %s", result)
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the RAG knowledge base")
    parser.add_argument("articles_path", nargs="?", default=None)
    parser.add_argument("--tenant-id", default="default")
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    build_knowledge_base(args.articles_path, tenant_id=args.tenant_id)
#end