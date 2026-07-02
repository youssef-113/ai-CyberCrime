# PDF Generation Service — System Design

## Overview

The PDF Generator produces professionally formatted complaint reports (Arabic/English) using WeasyPrint + Jinja2 HTML templates. It is the final output stage of the analysis pipeline.

**Mount point:** `/pdf`
**Source:** `backend/services/pdf/`

---

## Architecture

```
Pipeline Result (JSON)
       │
       │  POST /pdf/generate
       ▼
┌──────────────────────────────┐
│   PDFRequest Validation      │
│   case_id, crime_type,       │
│   evidence_summary, timeline,│
│   law_articles, score, grade,│
│   complainant_name, language │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│   Jinja2 Template Rendering  │
│                              │
│   Template selection:        │
│   ├── language == "ar"       │
│   │   └── complaint_ar.html  │
│   └── language == "en"       │
│       └── complaint_en.html  │
│                              │
│   Render with template vars: │
│   case_id, crime_type,       │
│   evidence_summary, timeline,│
│   law_articles, score, grade,│
│   complainant_name,          │
│   generated_date             │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│   WeasyPrint PDF Conversion  │
│                              │
│   Arabic (RTL):              │
│   ├── Amiri font             │
│   ├── direction: rtl         │
│   └── @page A4, 2cm margins  │
│                              │
│   English (LTR):             │
│   └── Segoe UI sans-serif    │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│   Output                     │
│                              │
│   POST /generate:            │
│   ├── Save to /outputs/      │
│   └── Return { status,       │
│        filename, path,       │
│        size_bytes,           │
│        pdf_base64 }          │
│                              │
│   POST /generate-download:   │
│   └── Return Response(       │
│        content=pdf_bytes,    │
│        media_type=pdf,       │
│        Content-Disposition)  │
└──────────────────────────────┘
```

---

## On-Demand Generation via API Gateway

The primary user-facing endpoint is `GET /api/pdf/{case_id}` in the API Gateway (`backend/services/api/main.py:678`). This endpoint:

1. Looks up the case by `case_id` and `user_id` (scoped)
2. Returns 400 if case status is not `"completed"`
3. Returns cached PDF if `pdf_path` exists on disk
4. Returns 404 if case result data is empty
5. Calls `POST /pdf/generate` with case result data
6. Stores the generated `pdf_path` back to Supabase
7. Streams the PDF bytes to the client

This lazy generation avoids storing PDFs until they are first requested.

---

## Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/pdf/health` | Liveness + WeasyPrint/output check | No |
| POST | `/pdf/generate` | Generate PDF, return base64 + metadata | No |
| POST | `/pdf/generate-download` | Generate PDF, stream as download | No |
| GET | `/api/pdf/{case_id}` | Gateway: on-demand PDF (user-scoped) | JWT |

---

## PDF Structure

### Arabic Template (`complaint_ar.html`)

```
┌─────────────────────────────────────┐
│         محضر بلاغ إلكتروني          │
│    نظام الذكاء الاصطناعي للجرائم    │
│         الإلكترونية                 │
│    قانون 175 لسنة 2018              │
├─────────────────────────────────────┤
│                                     │
│  ┌───────────────────────────────┐  │
│  │  معلومات البلاغ               │  │
│  ├───────────────────────────────┤  │
│  │ رقم القضية  │ نوع الجريمة     │  │
│  ├─────────────┼─────────────────┤  │
│  │ تاريخ التقديم│ مقدم البلاغ    │  │
│  └─────────────┴─────────────────┘  │
│                                     │
│  2. ملخص الأدلة                     │
│  ┌───────────────────────────────┐  │
│  │ evidence_summary              │  │
│  └───────────────────────────────┘  │
│                                     │
│  3. الخط الزمني للأحداث             │
│  ┌───────────────────────────────┐  │
│  │ ● event.date                  │  │
│  │   event.description           │  │
│  │ ● event.date                  │  │
│  │   event.description           │  │
│  └───────────────────────────────┘  │
│                                     │
│  4. المواد القانونية المطبقة       │
│  ┌───────────────────────────────┐  │
│  │ المادة X - القانون           │  │
│  │ article.text                  │  │
│  │ العقوبة: article.penalty_ar   │  │
│  └───────────────────────────────┘  │
│                                     │
│  5. تقييم قوة الأدلة               │
│  ┌───────────────────────────────┐  │
│  │    درجة قوة الأدلة            │  │
│  │        75/100                  │  │
│  │        STRONG                  │  │
│  │    تم التحقق من جميع          │  │
│  │    الادعاءات ضد الأدلة        │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ التوقيع:                      │  │
│  │ نظام الذكاء الاصطناعي         │  │
│  │ للجرائم الإلكترونية           │  │
│  │ جمهورية مصر العربية - 2026    │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### English Template (`complaint_en.html`)

Same structure but LTR layout with `border-left` accent instead of `border-right`, and English labels.

### PDF Styling

| Element | Style |
|---------|-------|
| Page | A4, 2cm margins, page numbers |
| Header | Centered, blue border-bottom, logo |
| Section titles | 14pt blue, bottom border |
| Info grid | 2-column CSS grid, blue right border (RTL) |
| Timeline | Vertical left border, bullet markers |
| Articles | Gold border, yellow background |
| Score | Gradient background (purple/blue), white text |
| Footer | Centered, thin top border |

---

## Text File Fast-Path

**Fonts:**
- **Amiri** (`Amiri-Regular.ttf`) — Arabic serif font for body text (RTL)
- **Cairo** — Arabic sans-serif (available for headings, in assets)
- **Segoe UI** / sans-serif — English template

Font files are stored in `backend/services/pdf/fonts/`.

---

## Data Model

### PDFRequest (input)

```python
class PDFRequest(BaseModel):
    case_id: str
    crime_type: str
    evidence_summary: str
    timeline: List[dict]          # [{date, description}, ...]
    law_articles: List[dict]      # [{article_number, law, text, penalty_ar}, ...]
    score: int                    # 0–100
    grade: str                    # STRONG | MEDIUM | WEAK
    complainant_name: str
    language: str                 # "ar" | "en"
```

### PDF Response (from /generate)

```python
{
    "status": "generated",
    "filename": "CASE_20240101_123456.pdf",
    "path": "/outputs/CASE_20240101_123456.pdf",
    "size_bytes": 123456,
    "pdf_base64": "<base64-encoded bytes>"
}
```

---

## Generation Flow

```python
def generate_complaint_pdf(...) -> bytes:
    # 1. Select template based on language
    template = env.get_template(f"complaint_{language}.html")

    # 2. Render with Jinja2
    html_content = template.render(
        case_id=case_id,
        crime_type=crime_type,
        evidence_summary=evidence_summary,
        timeline=timeline,
        law_articles=law_articles,
        score=score,
        grade=grade,
        complainant_name=complainant_name,
        generated_date=generated_date,
    )

    # 3. Convert to PDF with WeasyPrint
    html = HTML(string=html_content, base_url=...)
    if language == "ar":
        css = CSS(string=f"""
            @font-face {{
                font-family: 'Amiri';
                src: url('file://{font_path}');
            }}
            body {{ direction: rtl; font-family: 'Amiri', ...; }}
        """)
        pdf_bytes = html.write_pdf(stylesheets=[css])
    else:
        pdf_bytes = html.write_pdf()

    return pdf_bytes
```

---

## Output Storage

**Directory:** `/outputs/` (configurable via `OUTPUTS_DIR` env var)
**File naming:** `{case_id}_{YYYYMMDD_HHMMSS}.pdf` (from `/generate`)
**File naming (download):** `{case_id}_complaint.pdf` (from `/generate-download`)

The API Gateway stores the generated path in Supabase `cases.pdf_path` after successful generation so subsequent requests serve the cached file.

---

## Health Check

`GET /pdf/health` checks:

| Check | Method |
|-------|--------|
| Output directory | Create + write + delete `.health_check` file |
| WeasyPrint | Import `weasyprint.HTML` |
| Overall status | `"healthy"` if both pass, `"degraded"` otherwise |

---

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `OUTPUTS_DIR` | `/outputs` | PDF storage directory |
| `MONOLITH_BASE_URL` | `https://cyber-crime-production.up.railway.app` | Base for internal HTTP calls |

---

## Error Handling

| Scenario | HTTP Status | Behavior |
|----------|-------------|----------|
| Template not found | 500 | Jinja2 `TemplateNotFound` |
| WeasyPrint failure | 500 | HTML → PDF conversion error |
| File write failure | 500 | Output directory not writable |
| Case not completed | 400 | Gateway returns early |
| No result data | 404 | Gateway returns early |

---

## Dependencies

- **WeasyPrint** — HTML/CSS to PDF conversion
- **Jinja2** — HTML template engine
- **Amiri font** — Arabic serif typeface (OFL license)
- **Cairo font** — Arabic sans-serif typeface (OFL license)
