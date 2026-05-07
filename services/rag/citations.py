"""Citation Validation - Verify articles exist in ChromaDB with matching crime_type"""
import logging
from typing import List, Dict, Any

import chromadb
from .config import config

logger = logging.getLogger("rag.citations")


def _get_chroma_client():
    """Get ChromaDB client instance."""
    return chromadb.HttpClient(
        host=config.chroma.host,
        port=config.chroma.port,
    )


def validate_citations(
    articles: List[Dict[str, Any]],
    crime_type: str,
    tenant_id: str = "default"
) -> Dict[str, Any]:
    """Validate that cited articles exist in ChromaDB with matching crime_type.

    Args:
        articles: List of article dicts with article_number and law
        crime_type: Expected crime type to validate against
        tenant_id: Multi-tenant namespace

    Returns:
        {
            "valid": [...],           # Articles found in ChromaDB
            "invalid": [...],         # Articles not found or mismatched
            "status": "PASSED|FAILED",
            "validation_details": {
                "total_checked": int,
                "found": int,
                "missing": int,
                "crime_type_mismatch": int
            }
        }
    """
    if not articles:
        return {
            "valid": [],
            "invalid": [],
            "status": "FAILED",
            "validation_details": {
                "total_checked": 0,
                "found": 0,
                "missing": 0,
                "crime_type_mismatch": 0
            }
        }

    valid = []
    invalid = []
    found_count = 0
    missing_count = 0
    mismatch_count = 0

    try:
        client = _get_chroma_client()

        # Determine collection name (handle multi-tenant)
        collection_name = config.chroma.collection_name
        if config.multi_tenant.enabled and tenant_id != "default":
            collection_name = f"{config.multi_tenant.namespace_prefix}{tenant_id}"

        collection = client.get_or_create_collection(name=collection_name)

        for article in articles:
            article_number = article.get("article_number")
            law = article.get("law", "Unknown")

            if not article_number:
                invalid.append({
                    "article": article,
                    "reason": "Missing article_number"
                })
                missing_count += 1
                continue

            # Query ChromaDB for article_id match
            try:
                result = collection.get(
                    where={"article_number": str(article_number)},
                    include=["metadatas"]
                )

                documents = result.get("documents") or []
                metadatas = result.get("metadatas") or []

                if not documents or not metadatas:
                    invalid.append({
                        "article": article,
                        "reason": f"Article {article_number} not found in ChromaDB"
                    })
                    missing_count += 1
                    continue

                found_count += 1

                # Check crime_type match in metadata
                article_crime_type = None
                for meta in metadatas:
                    if meta and isinstance(meta, dict):
                        article_crime_type = meta.get("crime_type") or meta.get("category")
                        break

                # Validate crime_type if available
                if crime_type and article_crime_type:
                    if article_crime_type.lower() != crime_type.lower():
                        invalid.append({
                            "article": article,
                            "reason": f"Crime type mismatch: expected {crime_type}, found {article_crime_type}"
                        })
                        mismatch_count += 1
                        continue

                valid.append(article)

            except Exception as e:
                logger.warning(f"Error validating article {article_number}: {e}")
                invalid.append({
                    "article": article,
                    "reason": f"Validation error: {str(e)}"
                })
                missing_count += 1

    except Exception as e:
        logger.error(f"ChromaDB connection failed during citation validation: {e}")
        return {
            "valid": [],
            "invalid": [{"article": a, "reason": f"ChromaDB error: {str(e)}"} for a in articles],
            "status": "FAILED",
            "validation_details": {
                "total_checked": len(articles),
                "found": 0,
                "missing": len(articles),
                "crime_type_mismatch": 0
            }
        }

    status = "PASSED" if len(valid) == len(articles) else "FAILED"

    return {
        "valid": valid,
        "invalid": invalid,
        "status": status,
        "validation_details": {
            "total_checked": len(articles),
            "found": found_count,
            "missing": missing_count,
            "crime_type_mismatch": mismatch_count
        }
    }
