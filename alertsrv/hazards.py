from __future__ import annotations

import re

HAZARD_CLASSES = (
    "wind",
    "heavy_rain",
    "snow_blizzard",
    "ice",
    "fog",
    "thunderstorm",
    "heat",
    "frost",
    "hydrology",
    "fire_weather",
    "visibility",
    "other",
)

_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hydrology", ("павод", "половод", "подтоп", "уровень воды", "выход воды на пойму", "река", "ледоход")),
    ("wind", ("сильн.*ветер", "шквал", "порыв.*ветр", "ветер.*м/с", "ураган")),
    ("heavy_rain", ("сильн.*дожд", "ливн", "очень сильн.*дожд", "осадк.*мм")),
    ("snow_blizzard", ("снегопад", "сильн.*снег", "метель", "буран", "снежн.*занос")),
    ("ice", ("гололед", "гололедиц", "ледян.*дожд", "измороз", "налипан.*мокр.*снег")),
    ("fog", ("туман",)),
    ("thunderstorm", ("гроз", "молни",)),
    ("heat", ("аномальн.*жар", "сильн.*жар", "экстремальн.*высок.*температур")),
    ("frost", ("аномальн.*холод", "сильн.*мороз", "экстремальн.*низк.*температур")),
    ("fire_weather", ("пожарн.*опасност", "чрезвычайн.*пожарн", "класс пожарной опасности")),
)

def classify_hazard(text: str, *, event_type: str = "") -> str:
    value = re.sub(r"\s+", " ", f"{event_type} {text}".lower())
    for hazard, patterns in _PATTERNS:
        if any(re.search(pattern, value) for pattern in patterns):
            return hazard
    return "other"
