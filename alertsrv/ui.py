from __future__ import annotations

from html import escape

from .models import Alert, AlertState
from .service import AlertService


REGION_NAMES = {"37": "Ивановская область"}

SEVERITY_LABELS = {
    "critical": "Критическое",
    "warning": "Предупреждение",
    "info": "Информация",
}

STATE_LABELS = {
    "new": "Новое",
    "active": "Активно",
    "resolved": "Завершено",
    "expired": "Истекло",
    "cancelled": "Отменено",
    "superseded": "Заменено",
}


def _region_code(alert: Alert) -> str | None:
    for evidence in reversed(alert.evidence):
        value = evidence.payload.get("region_code")
        if value:
            return str(value)
    return None


def _area_values(alert: Alert, level: str) -> list[str]:
    values: list[str] = []
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict) or area.get("level") != level:
                continue
            name = area.get("name")
            if name and str(name) not in values:
                values.append(str(name))
    return values


def _matches_municipality(alert: Alert, municipality: str) -> bool:
    wanted = municipality.casefold()
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict):
                continue
            if area.get("level") == "municipality" and str(area.get("name", "")).casefold() == wanted:
                return True
            if area.get("level") == "settlement":
                parent = area.get("parent_name") or area.get("municipality") or area.get("district")
                if str(parent or "").casefold() == wanted:
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
    return value if value in {"critical", "warning", "info"} else "info"


def _severity_label(value: str) -> str:
    return SEVERITY_LABELS.get(value, value.title())


def _state_label(value: str) -> str:
    return STATE_LABELS.get(value, value.title())


def _alert_areas(alert: Alert) -> list[str]:
    areas: list[str] = []
    for evidence in alert.evidence:
        for area in evidence.payload.get("affected_areas", []) or []:
            if not isinstance(area, dict):
                continue
            name = area.get("name")
            if not name:
                continue
            parent = area.get("parent_name") or area.get("municipality") or area.get("district")
            label = f"{name} · {parent}" if parent else str(name)
            if label not in areas:
                areas.append(label)
    return areas


def _alert_card(alert: Alert) -> str:
    severity = _severity_class(alert.severity.value)
    areas = _alert_areas(alert)
    location = ", ".join(areas[:5])
    if len(areas) > 5:
        location += f" +{len(areas) - 5}"
    region = REGION_NAMES.get(_region_code(alert) or "", "Регион не указан")
    title = escape(alert.title or "Без названия")
    return f"""
    <a class="alert-link" href="/ui/alerts/{escape(alert.alert_id)}"><article class="alert-card {severity}">
      <div class="alert-top">
        <span class="severity-dot" aria-hidden="true"></span>
        <span class="severity">{escape(_severity_label(alert.severity.value))}</span>
        <span class="state">{escape(_state_label(alert.state.value))}</span>
      </div>
      <h2>{title}</h2>
      <div class="meta-row">
        <span>{escape(region)}</span>
        {f'<span>· {escape(location)}</span>' if location else ''}
      </div>
      <div class="details">
        <div><span>Обновлено</span><strong>{escape(alert.updated_at.strftime("%d.%m.%Y %H:%M"))}</strong></div>
        <div><span>Надёжность</span><strong>{alert.confidence:.0%}</strong></div>
        <div><span>Источников</span><strong>{len(alert.evidence)}</strong></div>
      </div>
    </article></a>
    """


def render_alert_detail_page(service: AlertService, alert_id: str) -> str:
    alert = service.get(alert_id)
    region = REGION_NAMES.get(_region_code(alert) or "", "Регион не указан")
    areas = _alert_areas(alert)
    evidence_rows = []
    for evidence in sorted(alert.evidence, key=lambda item: item.received_at, reverse=True):
        evidence_rows.append(
            f"""<div class="evidence">
              <div><strong>{escape(evidence.source_id)}</strong><span>{escape(evidence.received_at.strftime("%d.%m.%Y %H:%M"))}</span></div>
              <p>{escape(evidence.title or "Без названия")}</p>
              <small>Уверенность источника: {evidence.confidence:.0%}</small>
            </div>"""
        )
    timeline_rows = []
    for old_state, new_state, at, reason in reversed(alert.transition_history):
        timeline_rows.append(
            f"""<div class="timeline-item">
              <span class="timeline-dot"></span>
              <div><strong>{escape(_state_label(new_state.value))}</strong>
              <span>{escape(at.strftime("%d.%m.%Y %H:%M"))}</span>
              <p>{escape(reason)}</p></div>
            </div>"""
        )
    areas_html = "".join(f"<li>{escape(area)}</li>" for area in areas) or "<li>Не указаны</li>"
    evidence_html = "".join(evidence_rows) or '<p class="muted">Доказательств нет.</p>'
    timeline_html = "".join(timeline_rows) or '<p class="muted">История переходов отсутствует.</p>'
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlertSRV — {escape(alert.title or "Предупреждение")}</title>
<style>
:root {{ --bg:#f5f7fa;--panel:#fff;--text:#111827;--muted:#64748b;--line:#e2e8f0;--critical:#dc2626;--warning:#d97706;--info:#2563eb;font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
* {{box-sizing:border-box}} body {{margin:0;background:var(--bg);color:var(--text)}} main {{max-width:900px;margin:auto;padding:24px 18px 50px}}
.back {{display:inline-block;margin-bottom:18px;color:#2563eb;text-decoration:none;font-size:13px;font-weight:600}}
.panel {{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;box-shadow:0 10px 30px rgba(15,23,42,.06);margin-bottom:14px}}
.head {{border-top:4px solid var(--info)}} .head.critical {{border-top-color:var(--critical)}} .head.warning {{border-top-color:var(--warning)}}
.kicker {{font-size:12px;font-weight:700;text-transform:uppercase;color:var(--muted);letter-spacing:.05em}}
h1 {{font-size:29px;line-height:1.2;margin:9px 0}} h2 {{font-size:18px;margin:0 0 14px}}
.meta {{color:var(--muted);font-size:13px}} .chips {{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}
.chip {{padding:6px 9px;border:1px solid var(--line);border-radius:999px;font-size:12px;background:#f8fafc}}
.metrics {{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:20px}} .metric {{border-top:1px solid var(--line);padding-top:10px}}
.metric span,.evidence span,.timeline-item span {{display:block;color:var(--muted);font-size:11px}} .metric strong {{display:block;margin-top:3px;font-size:16px}}
.evidence {{padding:13px 0;border-top:1px solid var(--line)}} .evidence:first-child {{border-top:0}} .evidence div {{display:flex;justify-content:space-between;gap:12px}} .evidence p {{margin:5px 0;font-size:13px}} .evidence small {{color:var(--muted)}}
ul {{margin:0;padding-left:20px;color:var(--muted);font-size:13px}} .timeline-item {{display:flex;gap:12px;padding:0 0 18px}} .timeline-dot {{width:9px;height:9px;border-radius:50%;background:#2563eb;margin-top:5px;flex:0 0 auto}} .timeline-item strong {{font-size:13px}} .timeline-item p {{margin:4px 0 0;color:var(--muted);font-size:12px}} .muted {{color:var(--muted);font-size:13px}}
@media(max-width:650px) {{.metrics{{grid-template-columns:1fr 1fr}} h1{{font-size:24px}}}}
</style></head><body><main>
<a class="back" href="/ui">← Все активные предупреждения</a>
<section class="panel head {_severity_class(alert.severity.value)}">
<div class="kicker">{escape(_severity_label(alert.severity.value))} · {escape(_state_label(alert.state.value))}</div>
<h1>{escape(alert.title or "Без названия")}</h1>
<div class="meta">{escape(region)} · обновлено {escape(alert.updated_at.strftime("%d.%m.%Y %H:%M"))}</div>
<div class="chips"><span class="chip">ID: {escape(alert.alert_id)}</span><span class="chip">Correlation: {escape(alert.correlation_key)}</span></div>
<div class="metrics">
<div class="metric"><span>Уверенность</span><strong>{alert.confidence:.0%}</strong></div>
<div class="metric"><span>Источников</span><strong>{len(alert.evidence)}</strong></div>
<div class="metric"><span>Начало</span><strong>{escape(alert.started_at.strftime("%d.%m.%Y %H:%M"))}</strong></div>
<div class="metric"><span>Истекает</span><strong>{escape(alert.expires_at.strftime("%d.%m.%Y %H:%M") if alert.expires_at else "—")}</strong></div>
</div></section>
<section class="panel"><h2>Зона действия</h2><ul>{areas_html}</ul></section>
<section class="panel"><h2>Источники и доказательства</h2>{evidence_html}</section>
<section class="panel"><h2>Хронология</h2>{timeline_html}</section>
</main></body></html>"""

def render_alerts_page(
    service: AlertService,
    region: str | None = None,
    municipality: str | None = None,
) -> str:
    all_active = service.list(AlertState.ACTIVE)
    regions = _region_options(all_active)
    valid_regions = {code for code, _ in regions}
    if region and region not in valid_regions:
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

    critical = sum(a.severity.value == "critical" for a in alerts)
    warning = sum(a.severity.value == "warning" for a in alerts)
    info = sum(a.severity.value == "info" for a in alerts)
    source_health = service.sources()
    unhealthy = sum(getattr(state, "value", str(state)) not in {"healthy", "ok"} for state in source_health.values())

    region_options = ['<option value="">Все регионы</option>']
    for code, name in regions:
        selected = " selected" if code == region else ""
        region_options.append(
            f'<option value="{escape(code)}"{selected}>{escape(name)} ({escape(code)})</option>'
        )

    municipality_options = ['<option value="">Все муниципалитеты</option>']
    for name in municipalities:
        selected = " selected" if name == municipality else ""
        municipality_options.append(f'<option value="{escape(name)}"{selected}>{escape(name)}</option>')

    cards = "".join(_alert_card(alert) for alert in alerts)
    empty = """
    <div class="empty">
      <div class="empty-icon">✓</div>
      <h2>Активных предупреждений нет</h2>
      <p>По выбранным условиям сейчас нет зарегистрированных активных событий.</p>
    </div>
    """ if not alerts else ""

    monitoring = (
        f'<span class="system-ok"><i></i> Система работает</span>'
        if not unhealthy else
        f'<span class="system-warn"><i></i> Есть проблемы с источниками: {unhealthy}</span>'
    )

    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0f172a">
<title>AlertSRV — центр предупреждений</title>
<style>
:root {{
  color-scheme: light;
  --bg:#f5f7fa; --panel:#ffffff; --text:#111827; --muted:#64748b;
  --line:#e2e8f0; --accent:#2563eb; --critical:#dc2626; --warning:#d97706;
  --info:#2563eb; --shadow:0 10px 30px rgba(15,23,42,.06);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); }}
main {{ max-width:1180px; margin:0 auto; padding:28px 20px 56px; }}
.topbar {{ display:flex; align-items:center; justify-content:space-between; gap:20px; margin-bottom:28px; }}
.brand {{ display:flex; align-items:center; gap:12px; }}
.logo {{ width:42px; height:42px; display:grid; place-items:center; border-radius:12px; background:#0f172a; color:#fff; font-weight:800; font-size:19px; }}
.brand h1 {{ margin:0; font-size:23px; letter-spacing:-.02em; }}
.brand p {{ margin:2px 0 0; color:var(--muted); font-size:13px; }}
.system-ok,.system-warn {{ font-size:13px; font-weight:600; white-space:nowrap; }}
.system-ok {{ color:#15803d; }} .system-warn {{ color:#b45309; }}
.system-ok i,.system-warn i {{ display:inline-block; width:7px; height:7px; border-radius:50%; background:currentColor; margin-right:5px; }}
.hero {{ display:flex; align-items:flex-end; justify-content:space-between; gap:24px; margin-bottom:20px; }}
.hero h2 {{ margin:0; font-size:32px; letter-spacing:-.035em; }}
.hero p {{ margin:7px 0 0; color:var(--muted); }}
.hero-count {{ text-align:right; }}
.hero-count strong {{ display:block; font-size:42px; line-height:1; letter-spacing:-.05em; }}
.hero-count span {{ color:var(--muted); font-size:12px; }}
.stats {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:18px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:15px 17px; box-shadow:var(--shadow); }}
.stat-head {{ display:flex; align-items:center; gap:8px; color:var(--muted); font-size:12px; }}
.stat strong {{ display:block; margin-top:7px; font-size:25px; }}
.dot {{ width:8px; height:8px; border-radius:50%; }} .dot.critical {{ background:var(--critical); }}
.dot.warning {{ background:var(--warning); }} .dot.info {{ background:var(--info); }}
.filters {{ display:flex; gap:10px; flex-wrap:wrap; padding:12px; background:var(--panel); border:1px solid var(--line); border-radius:14px; margin-bottom:18px; }}
select {{ min-width:230px; padding:10px 34px 10px 12px; border:1px solid #cbd5e1; border-radius:9px; background:#fff; color:var(--text); font:inherit; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:14px; }}
.alert-card {{ background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--info); border-radius:14px; padding:18px; box-shadow:var(--shadow); transition:transform .15s ease,box-shadow .15s ease; }}
.alert-card:hover {{ transform:translateY(-1px); box-shadow:0 14px 34px rgba(15,23,42,.09); }}
.alert-card.critical {{ border-top-color:var(--critical); }} .alert-card.warning {{ border-top-color:var(--warning); }}
.alert-top {{ display:flex; align-items:center; gap:7px; font-size:12px; font-weight:700; }}
.severity-dot {{ width:8px; height:8px; border-radius:50%; background:var(--info); }}
.critical .severity-dot {{ background:var(--critical); }} .warning .severity-dot {{ background:var(--warning); }}
.severity {{ text-transform:uppercase; letter-spacing:.045em; }}
.state {{ margin-left:auto; color:var(--muted); font-weight:500; }}
.alert-card h2 {{ margin:12px 0 7px; font-size:19px; line-height:1.28; letter-spacing:-.015em; }}
.meta-row {{ min-height:20px; color:var(--muted); font-size:13px; }}
.details {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:17px; padding-top:14px; border-top:1px solid var(--line); }}
.details div {{ min-width:0; }} .details span {{ display:block; color:var(--muted); font-size:11px; }}
.details strong {{ display:block; margin-top:3px; font-size:13px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.empty {{ margin-top:4px; padding:50px 24px; text-align:center; background:var(--panel); border:1px dashed #cbd5e1; border-radius:14px; }}
.empty-icon {{ margin:0 auto 12px; width:44px; height:44px; display:grid; place-items:center; border-radius:50%; background:#dcfce7; color:#15803d; font-weight:800; }}
.empty h2 {{ margin:0; font-size:19px; }} .empty p {{ margin:7px 0 0; color:var(--muted); font-size:13px; }}
.footer {{ margin-top:28px; color:#94a3b8; font-size:11px; text-align:center; }}
@media (max-width:700px) {{
  main {{ padding:20px 14px 40px; }} .topbar,.hero {{ align-items:flex-start; flex-direction:column; }}
  .system-ok,.system-warn {{ align-self:flex-start; }} .hero-count {{ text-align:left; }}
  .stats {{ grid-template-columns:1fr 1fr; }} .stats .stat:last-child {{ grid-column:span 2; }}
  .grid {{ grid-template-columns:1fr; }} select {{ width:100%; min-width:0; }}
}}
</style>
</head>
<body>
<main>
  <header class="topbar">
    <div class="brand">
      <div class="logo">A</div>
      <div><h1>AlertSRV</h1><p>Локальный центр предупреждений</p></div>
    </div>
    {monitoring}
  </header>

  <section class="hero">
    <div>
      <h2>Текущая обстановка</h2>
      <p>Сводка активных предупреждений из подключённых источников.</p>
    </div>
    <div class="hero-count"><strong>{len(alerts)}</strong><span>активных событий</span></div>
  </section>

  <section class="stats" aria-label="Сводка">
    <div class="stat"><div class="stat-head"><i class="dot critical"></i>Критические</div><strong>{critical}</strong></div>
    <div class="stat"><div class="stat-head"><i class="dot warning"></i>Предупреждения</div><strong>{warning}</strong></div>
    <div class="stat"><div class="stat-head"><i class="dot info"></i>Информационные</div><strong>{info}</strong></div>
  </section>

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
  <div class="footer">AlertSRV · локальная обработка · без внешних библиотек</div>
</main>
</body>
</html>"""
