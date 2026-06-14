CRIME_DEFINITIONS = {
    "blackmail": {
        "description": "Threat to expose private content unless demands are met",
        "required_entities": ["amounts", "phones"],
        "articles": ["law175_art25", "law175_art26"],
    },

    "sextortion": {
        "description": "Sexual blackmail using explicit content",
        "required_entities": ["sensitive_content"],
        "articles": ["law175_art25"],
    },

    "financial_fraud": {
        "description": "Fraud or deception to obtain money",
        "required_entities": ["amounts"],
        "articles": ["fraud_art1"],
    },

    "phishing": {
        "description": "Fake messages or links to steal sensitive data",
        "required_entities": ["links", "emails"],
        "articles": ["law175_art18"],
    },

    "identity_theft": {
        "description": "Using someone else's identity without permission",
        "required_entities": ["personal_data"],
        "articles": ["law175_art19"],
    },

    "cyber_threat": {
        "description": "Threats of harm, intimidation, or violence",
        "required_entities": [],
        "articles": ["threat_art1"],
    },

    "defamation": {
        "description": "Statements damaging someone's reputation",
        "required_entities": [],
        "articles": ["defamation_art1"],
    },

    "hate_speech": {
        "description": "Abusive or hateful language targeting individuals or groups",
        "required_entities": [],
        "articles": ["law175_art27"],
    },

    "privacy_violation": {
        "description": "Unauthorized sharing of private information",
        "required_entities": ["personal_data"],
        "articles": ["law175_art25"],
    },

    "data_breach": {
        "description": "Unauthorized access or exposure of confidential data",
        "required_entities": ["personal_data"],
        "articles": ["law175_art20"],
    },

    "account_hacking": {
        "description": "Unauthorized access to accounts or systems",
        "required_entities": ["emails", "phones"],
        "articles": ["law175_art18"],
    },

    "unknown": {
        "description": "Insufficient evidence to classify",
        "required_entities": [],
        "articles": [],
    },
}