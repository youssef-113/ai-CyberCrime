import pandas as pd
import json
import os
import re

file_path = r"D:\downloads\dataset__2018_.xlsx"
output_path = r"C:\Users\A\ai-CyberCrime\data\law\articles.json"

df = pd.read_excel(file_path)
df = df.dropna(how="all")

CYBERCRIME_KEYWORDS = {
    "اختراق": ["اختراق", "دخول غير مصرح"],
    "احتيال": ["احتيال", "نصب", "غش إلكتروني"],
    "تشهير": ["تشهير", "سب", "قذف"],
    "ابتزاز": ["ابتزاز", "تهديد"],
    "بيانات": ["بيانات", "معلومات شخصية", "خصوصية"],
    "عقوبة": ["حبس", "سجن", "غرامة", "عقوبة"],
}

def extract_keywords(text):
    keywords = []
    for kw, variants in CYBERCRIME_KEYWORDS.items():
        for v in variants:
            if v in text:
                keywords.append(kw)
                break
    return list(set(keywords))

def extract_crime_type(text, title):
    combined = text + " " + title
    if any(w in combined for w in ["اختراق", "دخول غير مصرح", "وصول"]):
        return "unauthorized_access"
    elif any(w in combined for w in ["احتيال", "نصب", "غش"]):
        return "fraud"
    elif any(w in combined for w in ["ابتزاز", "تهديد"]):
        return "extortion"
    elif any(w in combined for w in ["تشهير", "سب", "قذف"]):
        return "defamation"
    elif any(w in combined for w in ["بيانات", "خصوصية"]):
        return "data_privacy"
    return "general"

articles = []
for _, row in df.iterrows():
    article_number = str(row.iloc[0]).strip()
    title = str(row.iloc[1]).strip() if str(row.iloc[1]).lower() != "nan" else ""
    text = str(row.iloc[2]).strip() if str(row.iloc[2]).lower() != "nan" else ""

    if not text:
        continue

    articles.append({
        "article_number": article_number,
        "law": "Law 175/2018",
        "crime_type": extract_crime_type(text, title),
        "text": text,
        "text_ar": text,
        "title_ar": title,
        "keywords": extract_keywords(text),
        "penalty_ar": next((s.strip() for s in re.split(r'[.،]', text) if any(w in s for w in ["حبس", "غرامة", "سجن"])), ""),
        "source_file": "dataset__2018_.xlsx"
    })

os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(articles, f, ensure_ascii=False, indent=2)

print(f"Saved {len(articles)} articles to {output_path}")