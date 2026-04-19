OCR Service
EasyOCR runs on Arabic screenshots

Google Vision used as fallback when confidence <55%

Entity extraction for phones, amounts, and dates

Arabic text normalization applied

🎯 LLM Classification
Crime type classification: blackmail, scam, threat, defamation

Citation‑forcing prompt ensures 0 claims without block_id

Confidence score returned

Missing‑evidence list generated

🔍 Multi‑Agent Verification
Attacker agent identifies unsupported claims

Judge agent outputs: APPROVED / NEEDS REVISION

Unsupported claims auto‑removed

Maximum of 3 revision rounds enforced

📄 Arabic PDF
WeasyPrint + Amiri font functioning

Arabic RTL text renders correctly

All 6 PDF sections generated

Score badge + verification stamp included

🐳 Docker + CI/CD
docker-compose up launches all 8 services

All service health checks pass

GitHub Actions CI pipeline green

End‑to‑end pytest suite passes

📚 Legal Knowledge Base
Law 175/2018 (45 articles) indexed in ChromaDB

Egyptian Penal Code (Articles 302–336) indexed

Multilingual embeddings loaded

Citation validator operational

🔎 RAG Retrieval
Hard filter by crime_type functioning

Top‑5 articles returned per query

Citations validated before output

Full article text included in responses

📊 Evidence Scoring
Score calculated on a 0–100% scale

Grades assigned: STRONG / MEDIUM / WEAK

Category‑level breakdown returned

Missing‑evidence list accurate

🤖 Legal Chatbot
Answers in Arabic with law citations

Case‑aware: uses uploaded evidence

Zero invented article numbers

Session memory functioning