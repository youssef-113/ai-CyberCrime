import re


def normalize_arabic(text: str) -> str:
    # Normalize Arabic text to reduce variation
    if not text:
        return text
    text = re.sub(r"[إأآا]", "ا", text)

    text = re.sub(r"[يى]", "ي", text)

    text = re.sub(r"[ًٌٍَُِّْ]", "", text)

    text = re.sub(r"ـ", "", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text