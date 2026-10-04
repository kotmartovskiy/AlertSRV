from __future__ import annotations

import re

EVENT_CATEGORIES = (
    "weather",
    "hydrology",
    "air_threat",
    "emergency_mode",
    "quarantine",
    "public_safety",
    "infrastructure",
    "epidemiology",
    "other",
)

def classify_event(text: str, *, event_type: str = "") -> tuple[str, str]:
    value = re.sub(r"\s+", " ", f"{event_type} {text}".lower())

    if re.search(r"ракетн.*опасност|угроз.*ракет|воздушн.*опасност", value):
        return "air_threat", "missile_warning"
    if re.search(r"угроз.*атак.*бпла|атак.*беспилот|опасност.*бпла|беспилотн.*опасност", value):
        return "air_threat", "drone_warning"
    if re.search(r"бпла|беспилотн.*летательн", value):
        return "air_threat", "drone_activity"

    if re.search(r"режим.*чрезвычайн.*ситуац|введ[её]н.*режим.*чс|отмен[её].*режим.*чс", value):
        return "emergency_mode", "emergency_situation"
    if re.search(r"режим.*повышенн.*готовност|повышенн.*готовност", value):
        return "emergency_mode", "high_readiness"
    if re.search(r"режим.*чрезвычайн.*положени|чрезвычайн.*положени", value):
        return "emergency_mode", "emergency_regime"

    if re.search(r"карантин|ограничительн.*мероприяти", value):
        if re.search(r"животн|африканск.*чум|бешенств|ветеринар", value):
            return "quarantine", "animal_quarantine"
        if re.search(r"растен|фитосанитар", value):
            return "quarantine", "plant_quarantine"
        return "quarantine", "public_health_quarantine"

    if re.search(r"эпидеми|инфекционн.*заболев|вспышк.*заболев|отравлен", value):
        return "epidemiology", "epidemic_situation"

    if re.search(r"эвакуац|запрет.*движен|ограничен.*движен|комендантск", value):
        return "public_safety", "movement_restriction"

    if re.search(r"авари.*электроснаб|отключен.*электр|газопровод|теплоснабж|водоснабж", value):
        return "infrastructure", "utility_disruption"

    return "other", "other"
