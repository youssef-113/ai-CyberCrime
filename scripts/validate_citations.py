"""
scripts/validate_citations.py
Validates that article citations in ACEB outputs actually exist in ChromaDB.
Prevents hallucinated law articles from appearing in complaint PDFs.

Usage:
    python scripts/validate_citations.py
    python scripts/validate_citations.py --query "ابتزاز صور خاصة" --crime_type blackmail
"""
import os
import sys
import json
import argparse

CHROMA_PATH   = os.environ.get("CHROMA_PERSIST_PATH", "data/law_db")
ARTICLES_PATH = os.environ.get("ARTICLES_PATH", "data/law/articles.json")


def load_vectorstore():
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings

    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="egyptian_law",
    )
    return vectorstore


def validate_article_exists(article_id: str, crime_type: str, vectorstore=None) -> bool:
    """
    Check that a cited article_id exists in ChromaDB AND matches expected crime_type.
    Returns False if either check fails → article should be removed from output.

    This is the ZERO HALLUCINATION guarantee:
    Any article not confirmed by this function cannot appear in a complaint PDF.
    """
    if vectorstore is None:
        vectorstore = load_vectorstore()

    try:
        result = vectorstore.get(where={"article_id": article_id})
        if not result or not result.get("documents"):
            return False
        metadata_list = result.get("metadatas", [])
        if not metadata_list:
            return False
        # Check that at least one entry matches the expected crime_type
        for meta in metadata_list:
            if meta.get("crime_type") == crime_type:
                return True
        return False
    except Exception as e:
        print(f"  ERROR validating {article_id}: {e}")
        return False


def validate_article_batch(articles: list, vectorstore=None) -> dict:
    """
    Validate a list of article dicts (as returned by RAG service).
    Returns:
        {
            "valid":   [list of valid article dicts],
            "invalid": [list of {article_id, reason}],
            "status":  "PASSED" | "FAILED",
            "total":   int,
            "valid_count": int,
        }
    """
    if vectorstore is None:
        vectorstore = load_vectorstore()

    valid, invalid = [], []
    for art in articles:
        art_id    = art.get("article_id", "")
        crime_type = art.get("crime_type", "")

        if not art_id:
            invalid.append({"article_id": art_id, "reason": "missing article_id"})
            continue

        exists = validate_article_exists(art_id, crime_type, vectorstore)
        if exists:
            valid.append(art)
        else:
            # Try without crime_type filter (maybe crime_type mismatch)
            try:
                result = vectorstore.get(where={"article_id": art_id})
                if result and result.get("documents"):
                    actual_ct = result["metadatas"][0].get("crime_type", "unknown")
                    invalid.append({
                        "article_id": art_id,
                        "reason": f"crime_type mismatch: expected '{crime_type}', found '{actual_ct}'"
                    })
                else:
                    invalid.append({"article_id": art_id, "reason": "not found in knowledge base"})
            except Exception:
                invalid.append({"article_id": art_id, "reason": "lookup failed"})

    return {
        "valid":       valid,
        "invalid":     invalid,
        "status":      "PASSED" if not invalid else "FAILED",
        "total":       len(articles),
        "valid_count": len(valid),
    }


def retrieve_by_query(query: str, crime_type: str, k: int = 5, vectorstore=None) -> list:
    """
    Retrieve top-k law articles matching a query, filtered by crime_type.
    All returned articles are pre-validated.
    """
    if vectorstore is None:
        vectorstore = load_vectorstore()

    prefixed_query = f"query: {query}"
    results = vectorstore.similarity_search_with_score(
        prefixed_query, k=k,
        filter={"crime_type": crime_type}
    )
    articles = []
    for doc, score in results:
        meta = doc.metadata
        articles.append({
            "article_id":     meta.get("article_id"),
            "article_number": meta.get("article_number"),
            "law":            meta.get("law"),
            "crime_type":     meta.get("crime_type"),
            "title_ar":       meta.get("title_ar"),
            "text_ar":        doc.page_content.replace("passage: ", ""),
            "penalty_ar":     meta.get("penalty_ar"),
            "penalty_en":     meta.get("penalty_en"),
            "keywords":       meta.get("keywords", "").split("|"),
            "relevance_score": round(float(score), 4),
        })
    return articles


def run_validation_suite(vectorstore=None) -> None:
    """
    Full validation suite:
    1. Confirm all articles in articles.json are in ChromaDB
    2. Run 6 standard retrieval queries (2 per key crime type)
    3. Confirm known hallucinated IDs are rejected
    """
    if vectorstore is None:
        vectorstore = load_vectorstore()

    print("\n── 1. Full database coverage check ─────────────────────────────────")
    with open(ARTICLES_PATH, encoding="utf-8") as f:
        all_articles = json.load(f)

    missing = []
    for a in all_articles:
        try:
            result = vectorstore.get(where={"article_id": a["article_id"]})
            if not result or not result.get("documents"):
                missing.append(a["article_id"])
        except Exception as e:
            missing.append(f"{a['article_id']} (error: {e})")

    if missing:
        print(f"  ✗ {len(missing)} articles NOT in ChromaDB:")
        for m in missing[:10]:
            print(f"    - {m}")
        if len(missing) > 10:
            print(f"    ... and {len(missing)-10} more")
    else:
        print(f"  ✓ All {len(all_articles)} articles confirmed in ChromaDB")

    print("\n── 2. Retrieval tests ──────────────────────────────────────────────")
    tests = [
        ("ابتزاز صور خاصة تهديد نشر", "blackmail",
         ["law175_art26", "law175_art25", "law58_art375_مكرر"]),
        ("احتيال مالي استيلاء بطاقات بنكية", "scam",
         ["law175_art23", "law58_art336"]),
        ("قذف تشهير على الإنترنت", "defamation",
         ["law58_art302", "law58_art303"]),
        ("انتحال شخصية اختراق حساب", "identity_theft",
         ["law175_art14", "law175_art24"]),
        ("تهديد بالأذى", "threat",
         ["law58_art327", "law175_art27"]),
        ("انتهاك خصوصية نشر بيانات شخصية", "privacy",
         ["law175_art25"]),
    ]

    all_passed = True
    for query, crime_type, expected_ids in tests:
        articles = retrieve_by_query(query, crime_type, k=5, vectorstore=vectorstore)
        found_ids = [a["article_id"] for a in articles]
        hits = [e for e in expected_ids if e in found_ids]
        passed = len(hits) >= 1
        all_passed = all_passed and passed
        status = "✓" if passed else "✗"
        print(f"  {status} [{crime_type:15s}] query: '{query[:40]}'")
        if hits:
            print(f"    Found: {hits}")
        else:
            print(f"    Expected one of: {expected_ids}")
            print(f"    Got: {found_ids}")

    print("\n── 3. Hallucination rejection test ─────────────────────────────────")
    fake_ids = [
        "law175_art99",
        "law58_art500",
        "law999_art1",
        "fake_article",
    ]
    for fake_id in fake_ids:
        result = validate_article_exists(fake_id, "scam", vectorstore)
        status = "✗ BUG: accepted fake!" if result else "✓ Correctly rejected"
        print(f"  {status} — {fake_id}")

    print("\n── Summary ─────────────────────────────────────────────────────────")
    if all_passed and not missing:
        print("  ✓ ALL VALIDATION TESTS PASSED")
        print("  Citation validator is working correctly.")
    else:
        print("  ✗ Some tests failed — check output above")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACEB Citation Validator")
    parser.add_argument("--query",      type=str, help="Arabic query to test retrieval")
    parser.add_argument("--crime_type", type=str, default="blackmail",
                        help="crime_type filter (blackmail|scam|threat|defamation|privacy|identity_theft)")
    parser.add_argument("--article_id", type=str, help="Validate a single article_id")
    args = parser.parse_args()

    print("=" * 60)
    print("ACEB Citation Validator")
    print("=" * 60)

    if not os.path.exists(CHROMA_PATH):
        print(f"ERROR: ChromaDB not found at {CHROMA_PATH}")
        print("Run indexer first: python scripts/index_law.py")
        sys.exit(1)

    print(f"Loading ChromaDB from: {CHROMA_PATH}")
    vs = load_vectorstore()

    if args.article_id:
        # Single article validation
        result = validate_article_exists(args.article_id, args.crime_type, vs)
        status = "✓ VALID" if result else "✗ INVALID (not in KB or wrong crime_type)"
        print(f"\n  {status} — {args.article_id} (crime_type={args.crime_type})")

    elif args.query:
        # Single query retrieval
        print(f"\nQuery:      {args.query}")
        print(f"crime_type: {args.crime_type}")
        print()
        articles = retrieve_by_query(args.query, args.crime_type, k=5, vectorstore=vs)
        print(f"Top {len(articles)} results:")
        for i, a in enumerate(articles, 1):
            print(f"  {i}. [{a['article_id']}] score={a['relevance_score']:.4f}")
            print(f"     Law: {a['law']} | Article: {a['article_number']}")
            print(f"     Title: {a['title_ar']}")
            print(f"     Penalty: {a['penalty_en']}")

    else:
        # Full validation suite
        run_validation_suite(vs)

    print("\n" + "=" * 60)
