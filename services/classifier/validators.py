from typing import Dict, List

from .crime_definitions import CRIME_DEFINITIONS


def validate_required_entities(crime_type: str, entities: Dict) -> List[str]:
    crime_definition = CRIME_DEFINITIONS.get(crime_type, CRIME_DEFINITIONS["unknown"])
    required_entities = crime_definition.get("required_entities", [])

    missing_entities = []

    for entity_name in required_entities:
        entity_values = entities.get(entity_name, [])
        if not entity_values:
            missing_entities.append(entity_name)

    return missing_entities


def build_validation_notes(crime_type: str, entities: Dict) -> List[str]:
    missing_entities = validate_required_entities(crime_type, entities)

    if not missing_entities:
        return []

    return [
        f"Missing required entity for {crime_type}: {entity_name}"
        for entity_name in missing_entities
    ]