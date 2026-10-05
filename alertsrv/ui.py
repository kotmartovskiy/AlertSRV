from __future__ import annotations

from html import escape
from urllib.parse import quote

from .models import Alert, AlertState
from .service import AlertService


REGION_NAMES = {"37": "Ивановская область"}


def _area_values(alert: Alert, level: str) -> list[str]:
    values: list[str] = []
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict) or area.get("level") != level:
                continue
            name = area.get("name")
            if name and name not in values:
                values.append(str(name))
    return values


def _region_code(alert: Alert) -> str | None:
    for evidence in reversed(alert.evidence):
        value = evidence.payload.get("region_code")
        if value:
            return str(value)
    return None


def _matches_municipality(alert: Alert, municipality: str) -> bool:
    wanted = municipality.casefold()
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict):
                continue
            if area.get("level") == "municipality" and str(area.get("name", "")).casefold() == wanted:
                return True
            if area.get("level") == "settlement" and str(
                area.get("parent_name") or area.get("municipality") or area.get("district") or ""
            ).casefold() == wanted:
                return True
    return False


def _region_options(alerts: list[Alert]) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    for alert in alerts:
        code = _region_code(alert)
        if code:
            found.setdefault(code, REGION_NAMES.get(code, f"Регион {code}"))
    return sorted(found.items(), key=lambda item: item[1])


def _municipality_options(alerts: list[Alert], region: str | None) -> list[str]:
    values: set[str] = set()
    for alert in alerts:
        if region and _region_code(alert) != region:
            continue
        values.update(_area_values(alert, "municipality"))
        for evidence in alert.evidence:
            for area in evidence.payload.get("affected_areas", []) or []:
                if isinstance(area, dict) and area.get("level") == "settlement":
                    parent = area.get("parent_name") or area.get("municipality") or area.get("district")
                    if parent:
                        values.add(str(parent))
    return sorted(values, key=str.casefold)


def _severity_class(value: str) -> str:
    return {"critical": "critical", "warning": "warning", "info": "info"}.get(value, "info")


def _alert_card(alert: Alert) -> str:
    areas: list[str] = []
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict):
                continue
            name = area.get("name")
            if name:
                parent = area.get("parent_name") or area.get("municipality") or area.get("district")
                label = f"{name} ({parent})" if parent else str(name)
                if label not in areas:
                    areas.append(label)
    location = escape(", ".join(areas[:8]))
    if len(areas) > 8:
        location += f" и ещё {len(areas) - 8}"
    expiry = escape(alert.expires_at.isoformat()) if alert.expires_at else "не задано"
    authority = escape(alert.source_authority)
    return f"""
    <article class="card {_severity_class(alert.severity.value)}">
      <div class="card-head">
        <span class="badge">{escape(alert.severity.value.upper())}</span>
        <span class="state">{escape(alert.state.value)}</span>
      </div>
      <h2>{escape(alert.title or "Без названия")}</h2>
      <dl>
        <dt>Начало</dt><dd>{escape(alert.started_at.isoformat())}</dd>
        <dt>Обновлено</dt><dd>{escape(alert.updated_at.isoformat())}</dd>
        <dt>Достоверность</dt><dd>{alert.confidence:.0%}</dd>
        <dt>Источник</dt><dd>{authority}</dd>
        <dt>Истекает</dt><dd>{expiry}</dd>
      </dl>
      {f'<p class="location"><b>Зона:</b> {location}</p>' if location else ''}
    </article>
    """


def render_alerts_page(service: AlertService, region: str | None = None, municipality: str | None = None) -> str:
    all_active = service.list(AlertState.ACTIVE)
    regions = _region_options(all_active)
    if region and region not in {code for code, _ in regions}:
        region = None

    municipalities = _municipality_options(all_active, region)
    if municipality and municipality not in municipalities:
        municipality = None

    alerts = [
        alert for alert in all_active
        if (not region or _region_code(alert) == region)
        and (not municipality or _matches_municipality(alert, municipality))
    ]
    alerts.sort(key=lambda item: (item.severity.rank, item.updated_at), reverse=True)

    region_options = ['<option value="">Все регионы</option>']
    for code, name in regions:
        selected = " selected" if code == region else ""
        region_options.append(f'<option value="{escape(code)}"{selected}>{escape(name)} ({escape(code)})</option>')

    municipality_options = ['<option value="">Все муниципалитеты</option>']
    for name in municipalities:
        selected = " selected" if name == municipality else ""
        municipality_options.append(f'<option value="{escape(name)}"{selected}>{escape(name)}</option>')

    cards = "".join(_alert_card(alert) for alert in alerts)
    empty = '<div class="empty">Активных предупреждений по выбранным условиям нет.</div>' if not alerts else ""

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlertSRV — предупреждения</title>
<style>
:root {{ color-scheme: light dark; font-family: system-ui,-apple-system,"Segoe UI",sans-serif; }}
body {{ margin:0; background:#f3f5f7; color:#18212b; }}
main {{ max-width:1100px; margin:0 auto; padding:28px 18px 48px; }}
header {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:22px; }}
h1 {{ margin:0; font-size:30px; }}
.subtitle {{ color:#64717d; margin-top:6px; }}
.filters {{ display:flex; gap:10px; flex-wrap:wrap; padding:14px; background:#fff; border:1px solid #dce2e7; border-radius:12px; margin-bottom:18px; }}
select {{ min-width:230px; padding:9px 10px; border:1px solid #c8d0d7; border-radius:8px; background:inherit; color:inherit; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
.card {{ background:#fff; border:1px solid #dce2e7; border-left:5px solid #8b98a5; border-radius:12px; padding:16px; box-shadow:0 2px 7px #0000000d; }}
.card.critical {{ border-left-color:#b42318; }}
.card.warning {{ border-left-color:#b54708; }}
.card.info {{ border-left-color:#175cd3; }}
.card-head {{ display:flex; justify-content:space-between; font-size:12px; }}
.badge {{ font-weight:700; }}
.state {{ color:#66737f; }}
h2 {{ font-size:20px; margin:12px 0; }}
dl {{ display:grid; grid-template-columns:auto 1fr; gap:5px 12px; font-size:13px; margin:0; }}
dt {{ color:#697783; }} dd {{ margin:0; overflow-wrap:anywhere; }}
.location {{ font-size:13px; margin:14px 0 0; }}
.empty {{ background:#fff; border:1px dashed #c8d0d7; border-radius:12px; padding:30px; text-align:center; color:#66737f; }}
@media (prefers-color-scheme: dark) {{
 body {{ background:#101418; color:#e8edf1; }}
 .filters,.card,.empty {{ background:#171d22; border-color:#2c363f; }}
 .subtitle,dt,.state {{ color:#9aa7b2; }}
 select {{ border-color:#3b4650; }}
}}
</style>
</head>
<body>
<main>
<header>
  <div>
    <h1>AlertSRV</h1>
    <div class="subtitle">Активные предупреждения</div>
  </div>
  <strong>{len(alerts)}</strong>
</header>
<form class="filters" method="get" action="/ui">
  <select name="region" aria-label="Регион" onchange="this.form.submit()">
    {"".join(region_options)}
  </select>
  <select name="municipality" aria-label="Муниципалитет" onchange="this.form.submit()">
    {"".join(municipality_options)}
  </select>
  <noscript><button type="submit">Показать</button></noscript>
</form>
<section class="grid">{cards}</section>
{empty}
</main>
</body>
</html>"""
