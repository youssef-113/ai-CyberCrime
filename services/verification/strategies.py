from abc import ABC, abstractmethod
import re
from typing import List, Optional


# ─────────────────────────────────────────────
# Arabic text normalisation for keyword matching
# ─────────────────────────────────────────────

# Common Arabic character variants that should be treated as equivalent
# Handles hamza forms (أ/إ/آ ≈ ا), taa marbuta (ة ≈ ه), etc.
_ARABIC_NORMALIZE = str.maketrans(
    {
        "أ": "ا", "إ": "ا", "آ": "ا",  # hamza variants → bare alif
        "ة": "ه",                        # taa marbuta → haa
        "ى": "ي",                        # alif maqsura → yaa
    }
)


def _normalize_arabic(text: str) -> str:
    """Normalise Arabic text for fuzzy keyword matching."""
    return text.translate(_ARABIC_NORMALIZE)


# ─────────────────────────────────────────────
# Base Strategy
# ─────────────────────────────────────────────

class AttackerStrategy(ABC):
    """Abstract base class for all crime-type attacker strategies."""

    @abstractmethod
    def generate_challenges(
        self,
        claims: List[dict],
        evidence_blocks: List[dict],
    ) -> List[str]:
        """Return a list of challenge strings that attack weak points in the claims."""
        pass

    # ── shared helpers ──────────────────────────────────────────────────────

    def _text_of(self, blocks: List[dict]) -> str:
        """Concatenate all normalised text from evidence blocks."""
        raw = " ".join(b.get("normalized_text", "") for b in blocks).lower()
        return _normalize_arabic(raw)

    def _keyword_match(self, text: str, keywords: tuple) -> bool:
        """Check if any keyword appears in text, with Arabic normalisation."""
        norm_text = _normalize_arabic(text.lower())
        norm_keywords = [_normalize_arabic(kw.lower()) for kw in keywords]
        return any(kw in norm_text for kw in norm_keywords)

    def _claim_amounts(self, claims: List[dict]) -> List[float]:
        amounts = []
        for c in claims:
            raw = c.get("amount") or c.get("value")
            if raw is not None:
                try:
                    amounts.append(float(str(raw).replace(",", "")))
                except ValueError:
                    pass
        return amounts
 
    def _evidence_amounts(self, evidence_blocks: List[dict]) -> List[float]:
        amounts = []
        for b in evidence_blocks:
            for entity in b.get("entities", {}).get("amounts", []):
                try:
                    amounts.append(float(str(entity["value"]).replace(",", "")))
                except (ValueError, KeyError):
                    pass
        return amounts
 
 
# ─────────────────────────────────────────────
# Financial Fraud Strategy
# ─────────────────────────────────────────────
 
class FinancialFraudAttacker(AttackerStrategy):
    """Challenges for financial-fraud claims."""
 
    RECEIPT_KEYWORDS = (
        "receipt", "transaction", "transfer", "wire", "ايصال", "إيصال",
        "تحويل", "حواله", "حوالة", "عمليه", "عملية",
    )
    FRAUD_KEYWORDS = (
        "fraud", "احتيال", "غش", "blacklisted", "suspended",
        "frozen", "محظور", "مجمد",
    )
 
    def generate_challenges(self, claims: List[dict], evidence_blocks: List[dict]) -> List[str]:
        challenges: List[str] = []
        text = self._text_of(evidence_blocks)
 
        if not self._has_transaction_receipt(text):
            challenges.append(
                "No bank transfer receipt or transaction proof found. "
                "Provide an official receipt with transaction ID, date, and amount."
            )
 
        if not self._has_verified_fraudulent_account(text):
            challenges.append(
                "The suspect account has not been verified as fraudulent. "
                "Attach bank confirmation or an official complaint acknowledgment."
            )
 
        if not self._amounts_consistent(claims, evidence_blocks):
            challenges.append(
                "Claimed monetary amounts are inconsistent with documented evidence. "
                "Reconcile all figures before submission."
            )
 
        if not self._has_identity_of_suspect(evidence_blocks):
            challenges.append(
                "Suspect identity (name, national ID, or account number) is missing from evidence."
            )
 
        return challenges
 
    # ── internal checks ─────────────────────────────────────────────────────
 
    def _has_transaction_receipt(self, text: str) -> bool:
        return self._keyword_match(text, self.RECEIPT_KEYWORDS)
 
    def _has_verified_fraudulent_account(self, text: str) -> bool:
        return self._keyword_match(text, self.FRAUD_KEYWORDS)
 
    def _amounts_consistent(self, claims: List[dict], evidence_blocks: List[dict]) -> bool:
        claim_amounts = self._claim_amounts(claims)
        evidence_amounts = self._evidence_amounts(evidence_blocks)
        if not claim_amounts or not evidence_amounts:
            return False
        # Every claimed amount must appear (±5 %) in evidence
        for ca in claim_amounts:
            if not any(abs(ea - ca) / max(ca, 1) <= 0.05 for ea in evidence_amounts):
                return False
        return True
 
    def _has_identity_of_suspect(self, evidence_blocks: List[dict]) -> bool:
        for b in evidence_blocks:
            entities = b.get("entities", {})
            if entities.get("persons") or entities.get("account_numbers"):
                return True
        return False
 
 
# ─────────────────────────────────────────────
# Blackmail Strategy
# ─────────────────────────────────────────────
 
class BlackmailAttacker(AttackerStrategy):
    """Challenges for blackmail / extortion claims."""
 
    THREAT_KEYWORDS = (
        "will expose", "will publish", "سأنشر", "سانشر", "سأكشف", "ساكشف",
        "unless", "إلا إذا", "الا اذا", "demand", "أطالب", "اطالب", "pay or",
        "ادفع وإلا", "ادفع والا",
    )
    CONTENT_KEYWORDS = (
        "photo", "video", "صورة", "صوره", "فيديو", "recording",
        "تسجيل", "screenshot", "لقطة شاشة", "لقطه شاشه", "document", "وثيقة", "وثيقه",
    )
    DEMAND_KEYWORDS = (
        "pay", "transfer", "ادفع", "حول", "send money",
        "أرسل", "ارسل", "جنيه", "egp", "dollar", "$", "€",
    )
 
    def generate_challenges(self, claims: List[dict], evidence_blocks: List[dict]) -> List[str]:
        challenges: List[str] = []
        text = self._text_of(evidence_blocks)
 
        if not self._has_explicit_threat(text):
            challenges.append(
                "No explicit threat language detected in evidence. "
                "Provide screenshots or recordings containing the actual threat."
            )
 
        if not self._has_content_reference(text):
            challenges.append(
                "No evidence that compromising content actually exists. "
                "Document proof that the blackmailer possesses the alleged material."
            )
 
        if not self._has_clear_demand(text):
            challenges.append(
                "The demand is not clearly stated in evidence. "
                "Include communication showing a specific monetary or other demand."
            )
 
        if not self._has_communication_chain(evidence_blocks):
            challenges.append(
                "No communication chain (messages, emails, call logs) was provided "
                "to establish an ongoing blackmail pattern."
            )
 
        return challenges
 
    # ── internal checks ─────────────────────────────────────────────────────
 
    def _has_explicit_threat(self, text: str) -> bool:
        return self._keyword_match(text, self.THREAT_KEYWORDS)

    def _has_content_reference(self, text: str) -> bool:
        return self._keyword_match(text, self.CONTENT_KEYWORDS)

    def _has_clear_demand(self, text: str) -> bool:
        return self._keyword_match(text, self.DEMAND_KEYWORDS)
 
    def _has_communication_chain(self, evidence_blocks: List[dict]) -> bool:
        comm_types = {"whatsapp", "sms", "email", "chat", "message", "رسالة", "واتساب"}
        for b in evidence_blocks:
            if b.get("doc_type", "").lower() in comm_types:
                return True
            if any(ct in b.get("normalized_text", "").lower() for ct in comm_types):
                return True
        return False
 
 
# ─────────────────────────────────────────────
# Forgery Strategy
# ─────────────────────────────────────────────
 
class ForgeryAttacker(AttackerStrategy):
    """Challenges for document forgery / impersonation claims."""
 
    def generate_challenges(self, claims: List[dict], evidence_blocks: List[dict]) -> List[str]:
        challenges: List[str] = []
        text = self._text_of(evidence_blocks)
 
        if not self._has_original_document(evidence_blocks):
            challenges.append(
                "Original (unaltered) document not provided for comparison."
            )
 
        if not self._has_expert_opinion(text):
            challenges.append(
                "No forensic or expert opinion on document authenticity included."
            )
 
        if not self._has_issuing_authority_confirmation(text):
            challenges.append(
                "No confirmation from the issuing authority that the document is forged."
            )
 
        return challenges

    def _has_original_document(self, evidence_blocks: List[dict]) -> bool:
        return any(b.get("is_original", False) for b in evidence_blocks)

    def _has_expert_opinion(self, text: str) -> bool:
        keywords = ("expert", "forensic", "خبير", "فحص", "تقرير خبره", "تقرير خبرة")
        return self._keyword_match(text, keywords)

    def _has_issuing_authority_confirmation(self, text: str) -> bool:
        keywords = ("authority", "ministry", "وزاره", "وزارة", "جهه اصدار", "جهة إصدار", "official denial")
        return self._keyword_match(text, keywords)


# ─────────────────────────────────────────────
# Harassment Strategy
# ─────────────────────────────────────────────

class HarassmentAttacker(AttackerStrategy):
    """Challenges for harassment / stalking claims."""
 
    def generate_challenges(self, claims: List[dict], evidence_blocks: List[dict]) -> List[str]:
        challenges: List[str] = []
        text = self._text_of(evidence_blocks)
 
        if not self._has_repeated_incidents(evidence_blocks):
            challenges.append(
                "Only a single incident documented; harassment typically requires a pattern. "
                "Provide evidence of repeated incidents."
            )
 
        if not self._has_witness_or_report(text):
            challenges.append(
                "No witness statement or prior police report included."
            )
 
        if not self._has_perpetrator_identity(evidence_blocks):
            challenges.append(
                "Perpetrator's identity not established in evidence."
            )
 
        return challenges
 
    def _has_repeated_incidents(self, evidence_blocks: List[dict]) -> bool:
        dated = [b for b in evidence_blocks if b.get("date")]
        unique_dates = {b["date"] for b in dated}
        return len(unique_dates) >= 2
 
    def _has_witness_or_report(self, text: str) -> bool:
        keywords = ("witness", "شاهد", "police report", "بلاغ", "محضر")
        return self._keyword_match(text, keywords)
 
    def _has_perpetrator_identity(self, evidence_blocks: List[dict]) -> bool:
        for b in evidence_blocks:
            if b.get("entities", {}).get("persons"):
                return True
        return False
 
 
# ─────────────────────────────────────────────
# Generic / Fallback Strategy
# ─────────────────────────────────────────────
 
class GenericAttacker(AttackerStrategy):
    """Fallback attacker for unrecognised crime types."""
 
    def generate_challenges(self, claims: List[dict], evidence_blocks: List[dict]) -> List[str]:
        challenges: List[str] = []
        text = self._text_of(evidence_blocks)
 
        if not claims:
            challenges.append("No structured claims provided.")
 
        if not evidence_blocks:
            challenges.append("No evidence blocks submitted.")
        elif len(evidence_blocks) < 2:
            challenges.append(
                "Only one evidence block found; corroborating evidence is recommended."
            )
 
        claim_amounts = self._claim_amounts(claims)
        evidence_amounts = self._evidence_amounts(evidence_blocks)
        if claim_amounts and not evidence_amounts:
            challenges.append(
                "Monetary amounts are mentioned in claims but not found in any evidence block."
            )
 
        return challenges
 
 
# ─────────────────────────────────────────────
# Strategy Registry
# ─────────────────────────────────────────────
 
STRATEGY_MAP: dict[str, AttackerStrategy] = {
    "financial_fraud": FinancialFraudAttacker(),
    "blackmail": BlackmailAttacker(),
    "extortion": BlackmailAttacker(),       # alias
    "forgery": ForgeryAttacker(),
    "harassment": HarassmentAttacker(),
    "stalking": HarassmentAttacker(),       # alias
}
 
 
def get_strategy(crime_type: str) -> AttackerStrategy:
    """Return the appropriate strategy, falling back to GenericAttacker."""
    return STRATEGY_MAP.get(crime_type.lower().strip(), GenericAttacker())
