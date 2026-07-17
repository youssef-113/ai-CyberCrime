"""Citation validation against ChromaDB with strict law and tenant isolation."""

import logging
from typing import Any, Dict, List, Optional

from .config import config

logger = logging.getLogger("rag.citations")


def _get_chroma_client():
    from .retriever import _get_chroma

    return _get_chroma()


def _collection_name_for_tenant(tenant_id: str) -> str:
    if config.multi_tenant.enabled and tenant_id != "default":
        return f"{config.multi_tenant.namespace_prefix}{tenant_id}"
    return config.chroma.collection_name


def _normalise(value: Any) -> str:
    return str(value or "").strip().casefold()


def validate_citations(
    articles: List[Dict[str, Any]],
    crime_type: str,
    tenant_id: str = "default",
) -> Dict[str, Any]:
    """Validate cited articles by article number, law, tenant, and crime type."""
    if not articles:
        return {
            "valid": [],
            "invalid": [],
            "status": "FAILED",
            "validation_details": {
                "total_checked": 0,
                "found": 0,
                "valid": 0,
                "missing": 0,
                "crime_type_mismatch": 0,
                "tenant_mismatch": 0,
                "validation_errors": 0,
            },
        }

    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    found_count = 0
    missing_count = 0
    mismatch_count = 0
    tenant_mismatch_count = 0
    validation_error_count = 0

    collection_name = _collection_name_for_tenant(tenant_id)

    try:
        client = _get_chroma_client()
        collection = client.get_collection(name=collection_name)
    except Exception as exc:
        logger.exception(
            "Citation validation could not open Chroma collection %s",
            collection_name,
        )
        reason = f"Collection unavailable: {exc}"
        return {
            "valid": [],
            "invalid": [{"article": article, "reason": reason} for article in articles],
            "status": "FAILED",
            "validation_details": {
                "total_checked": len(articles),
                "found": 0,
                "valid": 0,
                "missing": 0,
                "crime_type_mismatch": 0,
                "tenant_mismatch": 0,
                "validation_errors": len(articles),
            },
        }

    for article in articles:
        article_number = str(article.get("article_number") or "").strip()
        law = str(article.get("law") or "").strip()

        if not article_number:
            invalid.append({"article": article, "reason": "Missing article_number"})
            missing_count += 1
            continue

        if not law:
            invalid.append({"article": article, "reason": "Missing law"})
            missing_count += 1
            continue

        where: Dict[str, Any] = {
            "$and": [
                {"article_number": article_number},
                {"law": law},
            ]
        }

        try:
            result = collection.get(where=where, include=["metadatas"])
            ids = result.get("ids") or []
            metadatas = result.get("metadatas") or []

            if not ids or not metadatas:
                invalid.append(
                    {
                        "article": article,
                        "reason": f"Article {article_number} in {law} not found",
                    }
                )
                missing_count += 1
                continue

            found_count += 1
            matching_metadata: List[Dict[str, Any]] = []

            for metadata in metadatas:
                if not isinstance(metadata, dict):
                    continue

                stored_tenant = str(metadata.get("tenant_id") or "default")
                if stored_tenant != tenant_id:
                    continue

                matching_metadata.append(metadata)

            if not matching_metadata:
                invalid.append(
                    {
                        "article": article,
                        "reason": (
                            f"Tenant mismatch for article {article_number} in {law}"
                        ),
                    }
                )
                tenant_mismatch_count += 1
                continue

            expected_crime_type = _normalise(crime_type)
            if expected_crime_type:
                crime_types = {
                    _normalise(meta.get("crime_type") or meta.get("category"))
                    for meta in matching_metadata
                }
                crime_types.discard("")

                if not crime_types:
                    invalid.append(
                        {
                            "article": article,
                            "reason": "Stored citation has no crime_type metadata",
                        }
                    )
                    mismatch_count += 1
                    continue

                if expected_crime_type not in crime_types:
                    invalid.append(
                        {
                            "article": article,
                            "reason": (
                                f"Crime type mismatch: expected {crime_type}, "
                                f"found {sorted(crime_types)}"
                            ),
                        }
                    )
                    mismatch_count += 1
                    continue

            valid.append(article)

        except Exception as exc:
            logger.exception(
                "Error validating article %s in law %s",
                article_number,
                law,
            )
            invalid.append(
                {
                    "article": article,
                    "reason": f"Validation error: {exc}",
                }
            )
            validation_error_count += 1

    return {
        "valid": valid,
        "invalid": invalid,
        "status": "PASSED" if len(valid) == len(articles) else "FAILED",
        "validation_details": {
            "total_checked": len(articles),
            "found": found_count,
            "valid": len(valid),
            "missing": missing_count,
            "crime_type_mismatch": mismatch_count,
            "tenant_mismatch": tenant_mismatch_count,
            "validation_errors": validation_error_count,
        },
    }
#end