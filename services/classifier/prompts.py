"""LLM Prompts for Crime Classification"""

CLASSIFICATION_PROMPT = """You are a legal expert specializing in Egyptian cybercrime law (Law 175/2018).

Analyze the following evidence and classify the crime type:

EVIDENCE TEXT:
{text}

EXTRACTED ENTITIES:
{entities}

Classify this case into one of: blackmail, scam, threat, defamation, privacy_violation, or unknown.

Respond in JSON format:
{{
    "crime_type": "string",
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "suggested_articles": ["Article X - Law Y"],
    "missing_evidence": ["what would strengthen the case"]
}}

Rules:
- Blackmail: Threats to expose unless demands met
- Scam: Financial fraud, deception for money
- Threat: Direct threats of harm
- Defamation: False statements damaging reputation
- Privacy violation: Unauthorized sharing of private content"""

VERIFICATION_PROMPT = """You are verifying legal claims against evidence.

CLAIM: {claim}
EVIDENCE: {evidence}

Is this claim fully supported by the evidence? 
Respond: APPROVED, NEEDS_REVISION, or NEEDS_USER_REVIEW with explanation."""
