"""AI Cybercrime Services Package

Services:
  - api         : API Gateway / Orchestrator  (port 8000)
  - ocr         : OCR & Entity Extraction      (port 8001)
  - classifier  : Crime Classification         (port 8002)
  - rag         : Legal Retrieval (ChromaDB)   (port 8003)
  - verification: Attacker+Judge Verification  (port 8004)
  - pdf_gen     : PDF Generation (WeasyPrint)  (port 8005)
  - chatbot     : Legal Chatbot (Arabic)       (port 8006)
"""

SERVICES = {
    "api":          {"port": 8000, "module": "services.api.main:router"},
    "ocr":          {"port": 8001, "module": "services.ocr.main:router"},
    "classifier":   {"port": 8002, "module": "services.classifier.main:router"},
    "rag":          {"port": 8003, "module": "services.rag.main:router"},
    "verification": {"port": 8004, "module": "services.verification.main:router"},
    "pdf":          {"port": 8005, "module": "services.pdf.main:router"},
    "chat":         {"port": 8006, "module": "services.chat.main:router"},
}