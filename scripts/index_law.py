"""
scripts/index_law.py
Indexes all Egyptian law articles from data/law/articles.json into ChromaDB
using multilingual-e5-large embeddings.

Run:
    python scripts/index_law.py
    # or via Makefile:
    make index-law
"""
import json
import os
import sys

ARTICLES_PATH = os.environ.get("ARTICLES_PATH", "data/law/articles.json")
CHROMA_PATH   = os.environ.get("CHROMA_PERSIST_PATH", "data/law_db")


def load_articles(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        articles = json.load(f)
    print(f"Loaded {len(articles)} articles from {path}")
    return articles


def build_index(articles: list, persist_dir: str) -> None:
    from langchain_community.vectorstores import Chroma
    from langchain_community.embeddings import HuggingFaceEmbeddings

    print(f"Loading embedding model: intfloat/multilingual-e5-large ...")
    print("(First run downloads ~1.1GB — subsequent runs use cache)")
    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Build texts: combine text_ar + title_ar for richer semantic matching
    texts = []
    metadatas = []
    for a in articles:
        text = a.get("text_ar", "")
        title = a.get("title_ar", "")
        keywords = " ".join(a.get("keywords", []))
        # Prefix: important for multilingual-e5 — models are trained with "query:" / "passage:" prefix
        passage = f"passage: {title} {text} {keywords}".strip()
        texts.append(passage)

        # Metadata stored in ChromaDB (used for filtering)
        metadatas.append({
            "article_id":     a["article_id"],
            "article_number": a["article_number"],
            "law":            a["law"],
            "crime_type":     a["crime_type"],
            "title_ar":       a.get("title_ar", ""),
            "penalty_ar":     a.get("penalty_ar", ""),
            "penalty_en":     a.get("penalty_en", ""),
            # Store keywords as pipe-separated string (Chroma metadata must be str/int/float/bool)
            "keywords":       "|".join(a.get("keywords", [])),
            "source_file":    a.get("source_file", ""),
        })

    os.makedirs(persist_dir, exist_ok=True)

    print(f"Building ChromaDB index at: {persist_dir}")
    print(f"Embedding {len(texts)} articles (this takes ~3–5 minutes on CPU)...")

    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        persist_directory=persist_dir,
        collection_name="egyptian_law",
    )

    vectorstore.persist()
    print(f"✓ Index built and persisted at: {persist_dir}")
    print(f"  Collection: egyptian_law")
    print(f"  Documents:  {len(texts)}")
    return vectorstore


def test_retrieval(vectorstore) -> None:
    """Quick smoke test: run 4 queries and confirm expected articles appear."""
    print("\n── Smoke tests ─────────────────────────────────────────────────────")
    tests = [
        ("ابتزاز صور خاصة", "blackmail",      ["law175_art26", "law175_art25", "law58_art375_مكرر"]),
        ("احتيال مالي إلكتروني", "scam",       ["law175_art23", "law58_art336"]),
        ("تشهير وقذف على الإنترنت", "defamation", ["law58_art302", "law58_art303", "law58_art308"]),
        ("اختراق حساب خاص سرقة هوية", "identity_theft", ["law175_art14", "law175_art24"]),
    ]
    for query, crime_type, expected_ids in tests:
        prefixed_query = f"query: {query}"
        results = vectorstore.similarity_search_with_score(
            prefixed_query, k=5,
            filter={"crime_type": crime_type}
        )
        found_ids = [r[0].metadata["article_id"] for r in results]
        hits = [e for e in expected_ids if e in found_ids]
        status = "✓" if hits else "✗"
        print(f"  {status} Query: '{query}'")
        print(f"    crime_type filter: {crime_type}")
        print(f"    Top 5: {found_ids}")
        print(f"    Expected hits: {hits}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("ACEB Legal Knowledge Base Indexer")
    print("=" * 60)

    if not os.path.exists(ARTICLES_PATH):
        print(f"ERROR: articles.json not found at {ARTICLES_PATH}")
        print("Run the law parser first: python parse_laws.py")
        sys.exit(1)

    articles = load_articles(ARTICLES_PATH)
    vectorstore = build_index(articles, CHROMA_PATH)
    test_retrieval(vectorstore)

    print("=" * 60)
    print("✓ Legal knowledge base ready")
    print(f"  To use: load from '{CHROMA_PATH}' with Chroma(persist_directory=...)")
    print("=" * 60)
