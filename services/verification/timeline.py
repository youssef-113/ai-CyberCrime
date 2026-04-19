"""Timeline Builder - Chronological event reconstruction"""
from typing import List, Dict
import re
from datetime import datetime

def build_timeline(text: str, entities: dict) -> List[dict]:
    """Build chronological timeline from evidence"""
    
    events = []
    
    # Extract dates with context
    dates = entities.get("dates", [])
    
    # Split text by sentences
    sentences = re.split(r'[.!?\n]', text)
    
    for i, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Check if sentence contains a date
        date_found = None
        for date in dates:
            if date["value"] in sentence:
                date_found = date["value"]
                break
        
        # Classify event type
        event_type = classify_event(sentence)
        
        if date_found or event_type != "general":
            events.append({
                "id": f"event_{i}",
                "date": date_found or "Unknown",
                "type": event_type,
                "description": sentence[:150],
                "source": "extracted"
            })
    
    # Sort by date if possible
    events.sort(key=lambda x: parse_date(x["date"]) or datetime.min)
    
    return events

def classify_event(text: str) -> str:
    """Classify event type from text"""
    
    text_lower = text.lower()
    
    if any(w in text_lower for w in ["threat", "blackmail", "extort", "demand"]):
        return "threat"
    elif any(w in text_lower for w in ["payment", "transfer", "send money", "pay"]):
        return "financial"
    elif any(w in text_lower for w in ["contact", "message", "call", "text", "chat"]):
        return "communication"
    elif any(w in text_lower for w in ["photo", "image", "video", "picture"]):
        return "media"
    else:
        return "general"

def parse_date(date_str: str):
    """Try to parse date string"""
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    return None
