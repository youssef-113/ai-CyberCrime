"""
ACEB Law Parser
Reads all 10 Excel files → produces data/law/articles.json
"""
import pandas as pd
import json
import re
import os

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_article_number(raw: str) -> str:
    """Extract clean article number from 'المادة 23' or 'المادة 226 مكرر'"""
    if not isinstance(raw, str):
        return ""
    raw = raw.strip()
    m = re.search(r'(\d+)\s*(مكرر|bis)?', raw)
    if m:
        num = m.group(1)
        suffix = " مكرر" if m.group(2) else ""
        return num + suffix
    return raw

def clean_text(t) -> str:
    if not isinstance(t, str): return ""
    return t.strip()

def extract_penalty_ar(text_ar: str) -> str:
    """Try to extract penalty sentence(s) from article text."""
    if not text_ar: return ""
    patterns = [
        r'(يُعاقب[^.،]*(?:الحبس|الغرامة|السجن)[^.،]*[.،])',
        r'(العقوبة[^.،]*(?:الحبس|الغرامة|السجن)[^.،]*[.،])',
        r'(تكون العقوبة[^.]*?جنيه[^.]*\.)',
        r'(الحبس[^.،]*(?:جنيه|مدة)[^.،]*[.،])',
        r'(بالحبس[^.]*?جنيه[^.]*\.)',
        r'(بغرامة[^.]*?جنيه[^.]*\.)',
    ]
    for pat in patterns:
        matches = re.findall(pat, text_ar)
        if matches:
            return " | ".join(set(m.strip() for m in matches[:3]))
    # Fallback: first 200 chars
    return text_ar[:200] + "..." if len(text_ar) > 200 else text_ar

def map_crime_type(article_num: str, title: str, text: str, law: str, topic_hint: str = "") -> str:
    """Determine crime_type from article number, title, text, and topic hint."""
    n = article_num.strip()
    title_l = (title or "").lower()
    text_l  = (text  or "").lower()
    topic   = (topic_hint or "").lower()

    # Law 175/2018 articles — explicit mapping
    law175_map = {
        "1": "general", "2": "general", "3": "general",
        "13": "scam", "14": "identity_theft", "15": "identity_theft",
        "16": "privacy", "17": "general", "18": "general", "19": "general",
        "20": "identity_theft", "21": "general",
        "22": "identity_theft", "23": "scam",
        "24": "identity_theft",
        "25": "privacy", "26": "blackmail",
        "27": "threat", "28": "defamation",
        "29": "general", "30": "general", "31": "general",
        "34": "general", "35": "general", "36": "general",
        "37": "general", "38": "general", "39": "general",
        "40": "general", "41": "general", "42": "general",
    }

    # Law 151/2020 articles — explicit mapping
    law151_map = {
        "1 إصدار": "general", "2 إصدار": "general", "3 إصدار": "general",
        "1": "general", "2": "privacy", "3": "general",
        "4": "general", "5": "general", "7": "privacy",
        "12": "identity_theft", "14": "identity_theft",
        "17": "scam", "18": "scam",
        "36": "scam", "37": "scam", "38": "general",
        "39": "general", "40": "general",
        "41": "identity_theft", "42": "identity_theft",
        "43": "scam", "47": "general", "48": "general", "49": "general",
    }

    # Law 58/1937 Penal Code — explicit mapping
    law58_map = {
        "211": "identity_theft", "212": "identity_theft",
        "213": "identity_theft", "214": "identity_theft",
        "215": "identity_theft", "217": "identity_theft",
        "226 مكرر": "identity_theft", "226": "identity_theft",
        "302": "defamation", "303": "defamation",
        "306": "defamation", "307": "defamation", "308": "defamation",
        "309": "defamation", "309 مكرر": "privacy",
        "327": "threat",
        "336": "scam", "337": "scam", "338": "scam",
        "339": "scam", "340": "scam", "341": "general",
        "344": "scam", "345": "scam", "346": "scam",
        "350": "scam", "375": "blackmail", "375 مكرر": "blackmail",
    }

    if "175" in law:
        ct = law175_map.get(n, "")
        if ct: return ct
    if "151" in law:
        ct = law151_map.get(n, "")
        if ct: return ct
    if "58" in law or "عقوبات" in law:
        ct = law58_map.get(n, "")
        if ct: return ct

    # Topic-hint override
    if "سرقة_الهوية" in topic or "سرقة الهوية" in topic or "identity" in topic:
        return "identity_theft"
    if "احتيال" in topic or "scam" in topic or "نصب" in topic:
        return "scam"

    # Content-based heuristic
    if any(k in text_l for k in ["ابتزاز", "إكراه", "تهديد بنشر", "استغلال صور"]):
        return "blackmail"
    if any(k in text_l for k in ["احتيال", "نصب", "استيلاء على مال", "وسائل تدليس", "ربح وهمى"]):
        return "scam"
    if any(k in text_l for k in ["تهديد", "تلويح بالأذى", "تخويف"]):
        return "threat"
    if any(k in text_l for k in ["قذف", "سب", "تشهير", "كاذب"]):
        return "defamation"
    if any(k in text_l for k in ["خصوصية", "بيانات شخصية", "انتهاك حرمة"]):
        return "privacy"
    if any(k in text_l for k in ["انتحال", "سرقة هوية", "هوية مزيفة", "اختراق", "حساب خاص"]):
        return "identity_theft"
    return "general"

def extract_keywords(title_ar: str, text_ar: str, crime_type: str) -> list:
    """Extract relevant Arabic keywords from title and text."""
    kw_sets = {
        "blackmail":      ["ابتزاز", "تهديد", "إكراه", "صور خاصة", "نشر", "مواد مسيئة"],
        "scam":           ["احتيال", "نصب", "استيلاء", "بطاقات بنكية", "تدليس", "ربح وهمى", "انتحال صفة"],
        "threat":         ["تهديد", "تلويح", "خطر", "أذى", "إكراه"],
        "defamation":     ["قذف", "سب", "تشهير", "إساءة", "شرف", "اعتبار"],
        "privacy":        ["خصوصية", "بيانات شخصية", "انتهاك حرمة", "نشر معلومات", "رضا"],
        "identity_theft": ["انتحال", "هوية", "اختراق", "حساب خاص", "بيانات", "تزوير", "مزيف"],
        "general":        ["جريمة إلكترونية", "تقنية المعلومات", "شبكة معلوماتية"],
    }
    base = kw_sets.get(crime_type, [])
    # Also pull unique words from title
    extra = []
    if title_ar:
        words = [w.strip("،.") for w in title_ar.split() if len(w) > 3]
        extra = words[:4]
    combined = list(dict.fromkeys(base + extra))
    return combined[:8]

def english_penalty(penalty_ar: str) -> str:
    """Simple mapping of common penalty patterns to English."""
    if not penalty_ar: return ""
    p = penalty_ar
    patterns = [
        (r'الحبس مدة لا تقل عن (\d+) سنوات? ولا تجاوز (\d+) سنوات?', r'\1–\2 years imprisonment'),
        (r'الحبس مدة لا تقل عن (\d+) سنوات?', r'min. \1 year(s) imprisonment'),
        (r'الحبس مدة لا تقل عن (\d+) شهراً? ولا تجاوز (\d+) سنوات?', r'\1 months–\2 years imprisonment'),
        (r'الحبس مدة لا تقل عن (\d+) شهراً?', r'min. \1 month(s) imprisonment'),
        (r'بغرامة لا تقل عن (\d+[\d,]*) جنيه ولا تجاوز (\d+[\d,]*) جنيه', r'fine EGP \1–\2'),
        (r'بغرامة لا تقل عن ([\d,]+) جنيه', r'fine min. EGP \1'),
        (r'الأشغال الشاقة', 'hard labour'),
        (r'السجن المشدد', 'aggravated imprisonment'),
        (r'السجن', 'imprisonment'),
    ]
    result = p
    for pat, repl in patterns:
        result = re.sub(pat, repl, result)
    return result[:300] if len(result) < 300 else result[:297] + "..."

def english_summary(article_num: str, law: str, title_ar: str, crime_type: str) -> str:
    """Generate a brief English article label."""
    ct_map = {
        "blackmail": "Blackmail/Extortion",
        "scam": "Fraud/Scam",
        "threat": "Threats",
        "defamation": "Defamation/Slander",
        "privacy": "Privacy Violation",
        "identity_theft": "Identity Theft",
        "general": "General Provision",
    }
    ct_en = ct_map.get(crime_type, crime_type.title())
    return f"Article {article_num} — {ct_en}"


# ── Parsers for each file type ────────────────────────────────────────────────

def parse_topic_file(filepath: str, law_num: str, law_label: str, topic_hint: str) -> list:
    """
    Parse the topic-specific files (58_*, 151_*, 175_*)
    These have header row at index 3, data from row 4 onward.
    Columns: [رقم المادة, عنوان المادة, نص المادة, تاريخ الإصدار, رقم القانون]
    """
    df = pd.read_excel(filepath, header=None)
    # Find the header row (contains "رقم المادة")
    header_row = None
    for i, row in df.iterrows():
        if any("رقم المادة" in str(c) for c in row.values):
            header_row = i
            break
    if header_row is None:
        print(f"  WARNING: No header found in {filepath}")
        return []
    data = df.iloc[header_row+1:].reset_index(drop=True)
    data.columns = ["رقم المادة", "عنوان المادة", "نص المادة", "تاريخ الإصدار", "رقم القانون"]
    data = data.dropna(subset=["رقم المادة", "نص المادة"], how="all")
    articles = []
    for _, row in data.iterrows():
        raw_num = clean_text(str(row.get("رقم المادة", "")))
        if not raw_num or raw_num == "nan": continue
        art_num = extract_article_number(raw_num)
        title_ar = clean_text(str(row.get("عنوان المادة", ""))) if pd.notna(row.get("عنوان المادة")) else ""
        text_ar  = clean_text(str(row.get("نص المادة", "")))  if pd.notna(row.get("نص المادة"))  else ""
        if not text_ar: continue
        ct = map_crime_type(art_num, title_ar, text_ar, law_num, topic_hint)
        penalty_ar = extract_penalty_ar(text_ar)
        penalty_en = english_penalty(penalty_ar)
        art = {
            "article_id":   f"law{law_num}_art{art_num.replace(' ', '_')}",
            "article_number": art_num,
            "law":           law_label,
            "crime_type":    ct,
            "text_ar":       f"المادة {art_num}: {text_ar}",
            "text_en":       english_summary(art_num, law_num, title_ar, ct),
            "title_ar":      title_ar,
            "penalty_ar":    penalty_ar,
            "penalty_en":    penalty_en,
            "keywords":      extract_keywords(title_ar, text_ar, ct),
            "source_file":   os.path.basename(filepath),
        }
        articles.append(art)
    return articles


def parse_full_law_file(filepath: str, sheet_name: str, law_num: str, law_label: str) -> list:
    """
    Parse the full law files (قانون_تقنية_المعلومات_175_2018.xlsx, etc.)
    Columns: [رقم المادة, عنوان المادة, نص المادة, الأسئلة المتوقعة للمادة]
    """
    df = pd.read_excel(filepath, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    # Rename columns flexibly
    col_map = {}
    for c in df.columns:
        if "رقم المادة" in c: col_map[c] = "رقم المادة"
        elif "عنوان" in c:    col_map[c] = "عنوان المادة"
        elif "نص" in c:       col_map[c] = "نص المادة"
    df = df.rename(columns=col_map)
    df = df.dropna(subset=["نص المادة"], how="all")
    articles = []
    seen = set()
    for _, row in df.iterrows():
        raw_num = clean_text(str(row.get("رقم المادة", ""))) if pd.notna(row.get("رقم المادة")) else ""
        art_num = extract_article_number(raw_num)
        if not art_num or art_num == "nan": continue
        title_ar = clean_text(str(row.get("عنوان المادة", ""))) if pd.notna(row.get("عنوان المادة")) else ""
        text_ar  = clean_text(str(row.get("نص المادة", "")))
        if not text_ar: continue
        art_id = f"law{law_num}_art{art_num.replace(' ', '_')}"
        if art_id in seen: continue  # deduplicate
        seen.add(art_id)
        ct = map_crime_type(art_num, title_ar, text_ar, law_num, "")
        penalty_ar = extract_penalty_ar(text_ar)
        penalty_en = english_penalty(penalty_ar)
        art = {
            "article_id":     art_id,
            "article_number": art_num,
            "law":             law_label,
            "crime_type":      ct,
            "text_ar":         f"المادة {art_num}: {text_ar}",
            "text_en":         english_summary(art_num, law_num, title_ar, ct),
            "title_ar":        title_ar,
            "penalty_ar":      penalty_ar,
            "penalty_en":      penalty_en,
            "keywords":        extract_keywords(title_ar, text_ar, ct),
            "source_file":     os.path.basename(filepath),
        }
        articles.append(art)
    return articles


def parse_dataset_file(filepath: str) -> list:
    """
    Parse dataset_قوانين_2018_النهائية.xlsx
    Columns: [رقم المادة, عنوان المادة, نص المادة, نوع المادة]
    This covers Law 175/2018 articles with نوع المادة labels.
    """
    df = pd.read_excel(filepath, sheet_name="Sheet1")
    df.columns = [str(c).strip() for c in df.columns]
    articles = []
    seen = set()
    for _, row in df.iterrows():
        raw_num = str(row.get("رقم المادة", ""))
        art_num = extract_article_number(raw_num)
        if not art_num or art_num == "nan": continue
        title_ar = clean_text(str(row.get("عنوان المادة", ""))) if pd.notna(row.get("عنوان المادة")) else ""
        text_ar  = clean_text(str(row.get("نص المادة", "")))
        if not text_ar: continue
        art_id = f"law175_art{art_num.replace(' ', '_')}_dataset"
        if art_id in seen: continue
        seen.add(art_id)
        ct = map_crime_type(art_num, title_ar, text_ar, "175", "")
        penalty_ar = extract_penalty_ar(text_ar)
        penalty_en = english_penalty(penalty_ar)
        art = {
            "article_id":     f"law175_art{art_num.replace(' ', '_')}",
            "article_number": art_num,
            "law":             "175/2018",
            "crime_type":      ct,
            "text_ar":         f"المادة {art_num}: {text_ar}",
            "text_en":         english_summary(art_num, "175", title_ar, ct),
            "title_ar":        title_ar,
            "penalty_ar":      penalty_ar,
            "penalty_en":      penalty_en,
            "keywords":        extract_keywords(title_ar, text_ar, ct),
            "source_file":     "dataset_قوانين_2018_النهائية.xlsx",
        }
        articles.append(art)
    return articles


# ── Main build ────────────────────────────────────────────────────────────────

def build_all_articles():
    base = "/mnt/user-data/uploads/"
    all_articles = []
    seen_ids = {}

    # ── Block 1: Topic-specific files ────────────────────────────────────────
    topic_files = [
        ("58_الاحتيال_والنصب.xlsx",   "58",  "58/1937",   "احتيال_والنصب"),
        ("58_سرقة_الهوية.xlsx",        "58",  "58/1937",   "سرقة_الهوية"),
        ("151_الاحتيال_والنصب.xlsx",   "151", "151/2020",  "احتيال_والنصب"),
        ("151_سرقة_الهوية.xlsx",       "151", "151/2020",  "سرقة_الهوية"),
        ("175_الاحتيال_والنصب.xlsx",   "175", "175/2018",  "احتيال_والنصب"),
        ("175_سرقة_الهوية.xlsx",       "175", "175/2018",  "سرقة_الهوية"),
    ]
    for fname, law_num, law_label, topic in topic_files:
        fpath = base + fname
        print(f"Parsing topic file: {fname}")
        arts = parse_topic_file(fpath, law_num, law_label, topic)
        print(f"  → {len(arts)} articles")
        for art in arts:
            aid = art["article_id"]
            if aid not in seen_ids:
                seen_ids[aid] = art
                all_articles.append(art)
            else:
                # Merge: prefer longer text_ar
                existing = seen_ids[aid]
                if len(art["text_ar"]) > len(existing["text_ar"]):
                    idx = all_articles.index(existing)
                    all_articles[idx] = art
                    seen_ids[aid] = art

    # ── Block 2: Full law text files ─────────────────────────────────────────
    full_law_files = [
        ("قانون_تقنية_المعلومات_175_2018.xlsx",    "قانون تقنية المعلومات", "175", "175/2018"),
        ("قانون_حماية_البيانات_الشخصية_151_2020.xlsx","قانون حماية البيانات", "151", "151/2020"),
        ("قانون_العقوبات_المصري_v3.xlsx",          "قانون العقوبات",       "58",  "58/1937"),
    ]
    for fname, sheet, law_num, law_label in full_law_files:
        fpath = base + fname
        print(f"Parsing full law: {fname}")
        arts = parse_full_law_file(fpath, sheet, law_num, law_label)
        print(f"  → {len(arts)} articles")
        for art in arts:
            aid = art["article_id"]
            if aid not in seen_ids:
                seen_ids[aid] = art
                all_articles.append(art)
            else:
                existing = seen_ids[aid]
                if len(art["text_ar"]) > len(existing["text_ar"]):
                    idx = all_articles.index(existing)
                    all_articles[idx] = art
                    seen_ids[aid] = art

    # ── Block 3: Dataset file (Law 175/2018 additional) ──────────────────────
    dataset_path = base + "dataset_قوانين_2018_النهائية.xlsx"
    print(f"Parsing dataset: dataset_قوانين_2018_النهائية.xlsx")
    arts = parse_dataset_file(dataset_path)
    print(f"  → {len(arts)} articles")
    for art in arts:
        aid = art["article_id"]
        if aid not in seen_ids:
            seen_ids[aid] = art
            all_articles.append(art)
        else:
            existing = seen_ids[aid]
            if len(art["text_ar"]) > len(existing["text_ar"]):
                idx = all_articles.index(existing)
                all_articles[idx] = art
                seen_ids[aid] = art

    return all_articles


def main():
    print("=" * 60)
    print("ACEB Law Parser — Building articles.json")
    print("=" * 60)

    articles = build_all_articles()

    # Sort by law → article number
    def sort_key(a):
        law_order = {"58/1937": 1, "151/2020": 2, "175/2018": 3}
        n = re.sub(r'\D', '', a.get("article_number", "0"))
        return (law_order.get(a.get("law",""), 9), int(n) if n else 0)

    articles.sort(key=sort_key)

    # Filter: remove definition-only articles (very short texts < 50 chars in text_ar body)
    # Keep all — definitions are needed for RAG context

    # Save
    out_path = "/home/claude/data/law/articles.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    # ── Stats ─────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"✓ Total articles saved: {len(articles)}")
    print(f"  Output: {out_path}")
    print()

    by_law = {}
    by_ct = {}
    for a in articles:
        by_law[a["law"]] = by_law.get(a["law"], 0) + 1
        by_ct[a["crime_type"]] = by_ct.get(a["crime_type"], 0) + 1

    print("By law:")
    for k, v in sorted(by_law.items()):
        print(f"  Law {k}: {v} articles")
    print()
    print("By crime type:")
    for k, v in sorted(by_ct.items(), key=lambda x: -x[1]):
        print(f"  {k:20s}: {v} articles")
    print()

    # Show a sample of key ACEB articles
    key_articles = ["law175_art23", "law175_art25", "law175_art26", "law175_art27",
                    "law58_art336", "law58_art375_مكرر", "law58_art302", "law58_art327"]
    print("Key ACEB articles check:")
    for kid in key_articles:
        found = next((a for a in articles if a["article_id"] == kid), None)
        if found:
            print(f"  ✓ {kid:30s} crime_type={found['crime_type']:15s} law={found['law']}")
        else:
            # Try prefix match
            matches = [a for a in articles if a["article_id"].startswith(kid.replace("_مكرر",""))]
            if matches:
                print(f"  ~ {kid:30s} → found as: {matches[0]['article_id']}")
            else:
                print(f"  ✗ {kid:30s} NOT FOUND")

    return articles


if __name__ == "__main__":
    main()
