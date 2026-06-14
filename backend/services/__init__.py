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
    "api":          {"port": 8000, "module": "services.api.main:app"},
    "ocr":          {"port": 8001, "module": "services.ocr.main:app"},
    "classifier":   {"port": 8002, "module": "services.classifier.main:app"},
    "rag":          {"port": 8003, "module": "services.rag.main:app"},
    "verification": {"port": 8004, "module": "services.verification.main:app"},
    "pdf_gen":      {"port": 8005, "module": "services.pdf_gen.main:app"},
    "chatbot":      {"port": 8006, "module": "services.chatbot.main:app"},
}