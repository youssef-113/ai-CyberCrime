
"""Parse law documents into structured JSON with Markdown conversion.

The parser expects text that has already been extracted from the original
document. PDF extraction, OCR, table reconstruction, header/footer removal,
and layout cleanup should happen before calling this module.
"""

import json
import logging
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)


DEFAULT_MAX_KEYWORDS = 10
DEFAULT_TENANT_ID = "default"
DEFAULT_CHUNK_TYPE = "parent"


# ---------------------------------------------------------------------------
# Article patterns
# ---------------------------------------------------------------------------

# Supports examples such as:
# المادة 25:
# المادة (25)
# المادة رقم 25
# المادة 25 مكرر
# المادة 25/أ
AR_ARTICLE_PATTERN = re.compile(
    r"""
    ^\s*
    المادة
    \s*
    (?:رقم\s*)?
    [\(\[]?
    (?P<number>\d+)
    [\)\]]?
    \s*
    (?P<suffix>
        مكرر(?:\s+\d+)?
        |
        bis
        |
        /[\u0600-\u06FFA-Za-z0-9]+
    )?
    \s*
    [:\-–—.]?
    \s*
    (?P<title>[^\n]*)
    $
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


# Supports examples such as:
# Article 25:
# Article (25)
# Article No. 25
# Article 25 bis
# Article 25-A
EN_ARTICLE_PATTERN = re.compile(
    r"""
    ^\s*
    Article
    \s*
    (?:No\.?\s*)?
    [\(\[]?
    (?P<number>\d+)
    [\)\]]?
    \s*
    (?P<suffix>
        bis
        |
        [\-/][A-Za-z0-9]+
    )?
    \s*
    [:\-–—.]?
    \s*
    (?P<title>[^\n]*)
    $
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Penalty patterns
# ---------------------------------------------------------------------------

PENALTY_PATTERNS = [
    re.compile(
        r"""
        (?:
            يعاقب
            |
            عقوبة
            |
            العقوبة
            |
            الحبس
            |
            السجن
            |
            الغرامة
        )
        .*?
        (?=
            \n\s*\n
            |
            المادة\s+(?:رقم\s*)?[\(\[]?\d+
            |
            Article\s+(?:No\.?\s*)?[\(\[]?\d+
            |
            $
        )
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE,
    ),
    re.compile(
        r"""
        (?:
            punishment
            |
            penalty
            |
            punishable
            |
            imprisonment
            |
            fine
        )
        .*?
        (?=
            \n\s*\n
            |
            Article\s+(?:No\.?\s*)?[\(\[]?\d+
            |
            المادة\s+(?:رقم\s*)?[\(\[]?\d+
            |
            $
        )
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE,
    ),
]


# ---------------------------------------------------------------------------
# Law-reference patterns
# ---------------------------------------------------------------------------

LAW_REF_PATTERN = re.compile(
    r"""
    (?:
        قانون
        \s+رقم
        \s+(?P<ar_number>\d+)
        \s*
        (?:
            /
            |
            ل(?:سنة)?
        )
        \s*(?P<ar_year>\d{4})
    )
    |
    (?:
        Law
        \s+
        (?:No\.?\s*)?
        (?P<en_number>\d+)
        \s*/\s*
        (?P<en_year>\d{4})
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Keyword configuration
# ---------------------------------------------------------------------------

CYBERCRIME_TERMS: Tuple[str, ...] = (
    "unauthorized access",
    "hacking",
    "information systems",
    "interception",
    "communications",
    "fraud",
    "identity theft",
    "phishing",
    "malware",
    "ransomware",
    "data breach",
    "cybercrime",
    "electronic fraud",
    "digital evidence",
    "الدخول غير المصرح",
    "الدخول غير المصرح به",
    "اختراق",
    "أنظمة المعلومات",
    "انظمة المعلومات",
    "اعتراض",
    "اتصالات",
    "احتيال",
    "سرقة الهوية",
    "تصيد",
    "برمجيات خبيثة",
    "ابتزاز",
    "اختراق بيانات",
    "جرائم إلكترونية",
    "جرائم الكترونية",
    "احتيال إلكتروني",
    "احتيال الكتروني",
    "أدلة رقمية",
    "ادلة رقمية",
)


_ARABIC_NORMALIZE_MAP = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
        "ـ": "",
        "َ": "",
        "ً": "",
        "ُ": "",
        "ٌ": "",
        "ِ": "",
        "ٍ": "",
        "ْ": "",
        "ّ": "",
    }
)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def _normalize_whitespace(text: str) -> str:
    """Normalize line endings, spaces, and excessive blank lines."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _normalize_for_matching(text: str) -> str:
    """Normalize text for case-insensitive bilingual keyword matching."""
    if not text:
        return ""

    normalized = text.lower().translate(_ARABIC_NORMALIZE_MAP)
    normalized = re.sub(r"[^\w\u0600-\u06FF]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _contains_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text or ""))


def _contains_english(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", text or ""))


def _deduplicate_strings(values: Sequence[str]) -> List[str]:
    """Deduplicate non-empty strings while preserving their order."""
    result: List[str] = []
    seen = set()

    for value in values:
        cleaned = _normalize_whitespace(str(value))

        if not cleaned:
            continue

        identity = _normalize_for_matching(cleaned)

        if identity in seen:
            continue

        seen.add(identity)
        result.append(cleaned)

    return result


def _sanitize_identifier(value: str) -> str:
    """Convert arbitrary metadata into a stable identifier component."""
    cleaned = _normalize_whitespace(value or "unknown")
    cleaned = cleaned.replace("/", "_").replace("\\", "_")
    cleaned = re.sub(r"[^\w\u0600-\u06FF.-]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)

    return cleaned.strip("_.") or "unknown"


# ---------------------------------------------------------------------------
# Law and penalty extraction
# ---------------------------------------------------------------------------

def _extract_law_ref(text: str) -> str:
    """Extract and normalize a law reference from text."""
    match = LAW_REF_PATTERN.search(text or "")

    if not match:
        return "Unknown"

    if match.group("ar_number"):
        number = match.group("ar_number")
        year = match.group("ar_year")
    else:
        number = match.group("en_number")
        year = match.group("en_year")

    return f"Law {number}/{year}"


def _extract_penalties(text: str) -> List[str]:
    """Extract all distinct penalty clauses from article text."""
    penalties: List[str] = []

    for pattern in PENALTY_PATTERNS:
        for match in pattern.finditer(text or ""):
            penalty = _normalize_whitespace(match.group(0))

            if penalty:
                penalties.append(penalty)

    return _deduplicate_strings(penalties)


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def _extract_keywords(
    text: str,
    existing_keywords: Optional[List[str]] = None,
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
) -> List[str]:
    """Extract bilingual legal/cybercrime keywords.

    Matching uses normalized Arabic and case-insensitive English text.
    Existing keywords are preserved first, then newly detected terms are added.
    """
    if max_keywords < 1:
        return []

    keywords: List[str] = []

    if isinstance(existing_keywords, list):
        keywords.extend(
            str(keyword).strip()
            for keyword in existing_keywords
            if str(keyword).strip()
        )

    normalized_text = _normalize_for_matching(text)

    for term in CYBERCRIME_TERMS:
        normalized_term = _normalize_for_matching(term)

        if normalized_term and normalized_term in normalized_text:
            keywords.append(term)

    return _deduplicate_strings(keywords)[:max_keywords]


# ---------------------------------------------------------------------------
# Language separation
# ---------------------------------------------------------------------------

def _split_bilingual_text(text: str) -> Tuple[str, str]:
    """Separate Arabic and English lines without assuming one document language.

    Mixed lines are preserved in both outputs because automatically splitting
    their meaning would be unsafe.
    """
    arabic_lines: List[str] = []
    english_lines: List[str] = []

    for line in (text or "").splitlines():
        cleaned_line = line.strip()

        if not cleaned_line:
            continue

        has_arabic = _contains_arabic(cleaned_line)
        has_english = _contains_english(cleaned_line)

        if has_arabic:
            arabic_lines.append(cleaned_line)

        if has_english:
            english_lines.append(cleaned_line)

    return (
        _normalize_whitespace("\n".join(arabic_lines)),
        _normalize_whitespace("\n".join(english_lines)),
    )


def _classify_title(title: str) -> Tuple[str, str]:
    """Assign an extracted article title to Arabic and/or English fields."""
    cleaned_title = _normalize_whitespace(title)

    if not cleaned_title:
        return "", ""

    title_ar = cleaned_title if _contains_arabic(cleaned_title) else ""
    title_en = cleaned_title if _contains_english(cleaned_title) else ""

    return title_ar, title_en


# ---------------------------------------------------------------------------
# Article boundary parsing
# ---------------------------------------------------------------------------

def _collect_article_matches(text: str) -> List[re.Match]:
    """Collect Arabic and English article headings in source order."""
    matches: List[re.Match] = []

    matches.extend(AR_ARTICLE_PATTERN.finditer(text))
    matches.extend(EN_ARTICLE_PATTERN.finditer(text))
    matches.sort(key=lambda item: item.start())

    # Protect against overlapping or duplicated matches.
    unique_matches: List[re.Match] = []
    seen_positions = set()

    for match in matches:
        position_key = (match.start(), match.end())

        if position_key in seen_positions:
            continue

        seen_positions.add(position_key)
        unique_matches.append(match)

    return unique_matches


def _build_article_number(match: re.Match) -> str:
    """Build an article number while preserving suffixes such as bis or مكرر."""
    number = match.group("number")
    suffix = _normalize_whitespace(match.group("suffix") or "")

    if not suffix:
        return number

    if suffix.startswith(("/", "-")):
        return f"{number}{suffix}"

    return f"{number} {suffix}"


def _extract_article_body(full_text: str, match: re.Match) -> str:
    """Remove the article heading line and return only the article body."""
    relative_heading_end = match.end() - match.start()
    body = full_text[relative_heading_end:]

    return _normalize_whitespace(body)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _to_clean_markdown(article: Dict) -> str:
    """Convert one structured article into clean Markdown."""
    md_parts: List[str] = []

    law = article.get("law") or "Unknown"
    article_number = article.get("article_number") or "Unknown"

    md_parts.append(f"## Article {article_number} — {law}")

    title_ar = _normalize_whitespace(article.get("title_ar", ""))
    title_en = _normalize_whitespace(article.get("title_en", ""))

    titles = _deduplicate_strings([title_ar, title_en])

    for title in titles:
        md_parts.append(f"**{title}**")

    text_ar = _normalize_whitespace(article.get("text_ar", ""))
    text_en = _normalize_whitespace(article.get("text_en", ""))
    fallback_text = _normalize_whitespace(article.get("text", ""))

    body_parts = _deduplicate_strings([text_ar, text_en])

    if body_parts:
        md_parts.extend(body_parts)
    elif fallback_text:
        md_parts.append(fallback_text)

    penalties = article.get("penalties", [])

    if not penalties:
        legacy_penalty = article.get("penalty_ar", "")

        if legacy_penalty:
            penalties = [legacy_penalty]

    if penalties:
        md_parts.append("### Penalties")

        for penalty in _deduplicate_strings(penalties):
            md_parts.append(f"- {penalty}")

    return "\n\n".join(part for part in md_parts if part).strip()


# ---------------------------------------------------------------------------
# Public parsing functions
# ---------------------------------------------------------------------------

def parse_law_text(
    text: str,
    law_ref: Optional[str] = None,
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    chunk_type: str = DEFAULT_CHUNK_TYPE,
    parent_id: Optional[str] = None,
    source_file: str = "",
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
) -> List[Dict]:
    """Parse law text into structured article records.

    Args:
        text:
            Extracted and cleaned document text.
        law_ref:
            Explicit law reference. If missing, the parser tries to extract it.
        tenant_id:
            Tenant ownership metadata.
        chunk_type:
            Record type used by the retrieval pipeline, normally ``parent``.
        parent_id:
            Optional parent identifier. Parent articles normally use ``None``.
        source_file:
            Original source filename.
        max_keywords:
            Maximum number of stored keywords per article.
    """
    cleaned_text = _normalize_whitespace(text)

    if not cleaned_text:
        return []

    resolved_law_ref = law_ref or _extract_law_ref(cleaned_text)
    matches = _collect_article_matches(cleaned_text)

    if not matches:
        logger.warning("No article headings were detected")
        return []

    articles: List[Dict] = []
    source_identifier = _sanitize_identifier(
        source_file or resolved_law_ref or "unknown_source"
    )

    for index, match in enumerate(matches):
        start = match.start()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(cleaned_text)
        )

        full_text = _normalize_whitespace(cleaned_text[start:end])
        body_text = _extract_article_body(full_text, match)

        article_number = _build_article_number(match)
        article_title = _normalize_whitespace(match.group("title") or "")
        title_ar, title_en = _classify_title(article_title)

        # If there is no body after the heading, preserve the captured title
        # as the available article text rather than producing an empty record.
        effective_text = body_text or article_title or full_text

        text_ar, text_en = _split_bilingual_text(effective_text)
        penalties = _extract_penalties(effective_text)
        keywords = _extract_keywords(
            effective_text,
            max_keywords=max_keywords,
        )

        article_id = (
            f"{source_identifier}"
            f"_article_{_sanitize_identifier(article_number)}"
        )

        article = {
            "article_id": article_id,
            "article_number": article_number,
            "law": resolved_law_ref,
            "title_ar": title_ar,
            "title_en": title_en,
            "text": effective_text,
            "text_ar": text_ar,
            "text_en": text_en,
            "penalties": penalties,
            # Legacy compatibility until downstream code migrates.
            "penalty_ar": penalties[0] if penalties else "",
            "keywords": keywords,
            "summary": title_ar or title_en,
            "crime_type": "general",
            "source_file": source_file,
            "tenant_id": tenant_id or DEFAULT_TENANT_ID,
            "chunk_type": chunk_type or DEFAULT_CHUNK_TYPE,
            "parent_id": parent_id,
        }

        article["markdown"] = _to_clean_markdown(article)
        articles.append(article)

    return articles


def parse_articles_json(
    data: List[Dict],
    *,
    tenant_id: str = DEFAULT_TENANT_ID,
    chunk_type: str = DEFAULT_CHUNK_TYPE,
    max_keywords: int = DEFAULT_MAX_KEYWORDS,
) -> List[Dict]:
    """Validate and enrich existing article dictionaries."""
    if not isinstance(data, list):
        raise TypeError("data must be a list of article dictionaries")

    enriched_articles: List[Dict] = []

    for index, raw_article in enumerate(data):
        if not isinstance(raw_article, dict):
            logger.warning(
                "Skipping article at index %s because it is not a dictionary",
                index,
            )
            continue

        text = (
            raw_article.get("text")
            or raw_article.get("text_ar")
            or raw_article.get("text_en")
            or ""
        )
        text = _normalize_whitespace(str(text))

        if not text:
            logger.warning(
                "Skipping article at index %s because it has no text",
                index,
            )
            continue

        text_ar = _normalize_whitespace(raw_article.get("text_ar", ""))
        text_en = _normalize_whitespace(raw_article.get("text_en", ""))

        # Reclassify only when language-specific fields are missing.
        if not text_ar and not text_en:
            text_ar, text_en = _split_bilingual_text(text)

        penalties = raw_article.get("penalties")

        if not isinstance(penalties, list):
            legacy_penalty = raw_article.get("penalty_ar", "")
            penalties = [legacy_penalty] if legacy_penalty else []

        penalties = _deduplicate_strings(penalties)

        keywords = _extract_keywords(
            text,
            raw_article.get("keywords"),
            max_keywords=max_keywords,
        )

        title_ar = _normalize_whitespace(raw_article.get("title_ar", ""))
        title_en = _normalize_whitespace(raw_article.get("title_en", ""))

        summary = (
            _normalize_whitespace(raw_article.get("summary", ""))
            or title_ar
            or title_en
        )

        enriched_article = {
            **raw_article,
            "text": text,
            "text_ar": text_ar,
            "text_en": text_en,
            "title_ar": title_ar,
            "title_en": title_en,
            "penalties": penalties,
            "penalty_ar": penalties[0] if penalties else "",
            "keywords": keywords,
            "summary": summary,
            "tenant_id": raw_article.get("tenant_id") or tenant_id,
            "chunk_type": raw_article.get("chunk_type") or chunk_type,
            "parent_id": raw_article.get("parent_id"),
            "source_file": raw_article.get("source_file", ""),
        }

        enriched_article["markdown"] = _to_clean_markdown(
            enriched_article
        )

        enriched_articles.append(enriched_article)

    return enriched_articles


def save_articles(articles: List[Dict], output_path: str) -> None:
    """Save parsed articles as UTF-8 JSON."""
    if not output_path or not output_path.strip():
        raise ValueError("output_path cannot be empty")

    output_path = os.path.abspath(output_path)
    output_directory = os.path.dirname(output_path)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)

    temporary_path = f"{output_path}.tmp"

    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(
                articles,
                file,
                ensure_ascii=False,
                indent=2,
            )

        # Atomic replacement protects the target from partial writes.
        os.replace(temporary_path, output_path)

    except Exception:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)

        logger.exception("Failed to save articles to %s", output_path)
        raise

    logger.info(
        "Saved %s articles to %s",
        len(articles),
        output_path,
    )


def main() -> None:
    input_path = "/data/law/articles.json"
    output_path = "/data/law/parsed/articles_enriched.json"

    try:
        with open(input_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        enriched = parse_articles_json(
            data,
            tenant_id=DEFAULT_TENANT_ID,
            chunk_type=DEFAULT_CHUNK_TYPE,
        )
        save_articles(enriched, output_path)

        logger.info("Enriched %s articles", len(enriched))

    except FileNotFoundError:
        logger.warning(
            "Input file was not found; processing the sample text instead"
        )

        sample_text = """
        Law No. 10/2023

        Article 25: Unauthorized access
        A person who accesses an information system without authorization
        shall be punishable by imprisonment and a fine.

        المادة (26): اعتراض الاتصالات
        يعاقب بالحبس وبالغرامة كل من اعترض الاتصالات دون تصريح.
        """

        articles = parse_law_text(
            sample_text,
            tenant_id=DEFAULT_TENANT_ID,
            chunk_type=DEFAULT_CHUNK_TYPE,
            source_file="sample_law.txt",
        )
        save_articles(articles, output_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    main()

