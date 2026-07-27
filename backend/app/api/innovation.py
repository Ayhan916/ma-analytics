from __future__ import annotations
import json
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from groq import Groq

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/innovation", tags=["innovation"])
log = structlog.get_logger(__name__)


class InnovationRequest(BaseModel):
    mode: str = "competitor"       # "competitor" | "innovation"
    scope: str = "all"             # "all" | "industry" | "datasource"
    industry: str | None = None
    datasource_ids: list[str] | None = None
    market: str | None = None      # country code filter
    user_hypothesis: str | None = None  # optional strategic brief from user


class FeatureSignal(BaseModel):
    feature: str
    total_mentions: int
    fr_mentions: int
    app_count: int
    affected_apps: list[str]
    top_narrative: str | None


class ProductFeature(BaseModel):
    name: str
    mentions: int
    priority: str


class InnovationBrief(BaseModel):
    product_name: str
    tagline: str
    core_problem: str
    market_gap: str
    features: list[ProductFeature]
    target_audience: str
    differentiation: str
    risk: str
    risk_level: str
    hypothesis_check: str | None = None   # only when user_hypothesis was provided
    hypothesis_alignment: str | None = None  # "stark" | "mittel" | "schwach"
    total_demand: int
    apps_analyzed: int
    sources: list[FeatureSignal]


def _build_where(
    scope: str,
    industry: str | None,
    datasource_ids: list[str] | None,
    market: str | None,
    user_id: str,
) -> tuple[str, dict]:
    conditions = ["ds.user_id = :user_id"]
    params: dict = {"user_id": user_id}

    if scope == "industry" and industry:
        conditions.append("ds.industry = :industry")
        params["industry"] = industry
    elif scope == "datasource" and datasource_ids:
        placeholders = ", ".join(f":ds_{i}" for i in range(len(datasource_ids)))
        conditions.append(f"ds.id IN ({placeholders})")
        for i, did in enumerate(datasource_ids):
            params[f"ds_{i}"] = did

    if market:
        conditions.append("ds.scrape_country = :market")
        params["market"] = market

    return " AND ".join(conditions), params


async def _aggregate_signals(
    db: AsyncSession,
    where: str,
    params: dict,
) -> list[dict]:
    sql = text(f"""
        SELECT
            rs.feature,
            COUNT(*) AS total_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') AS fr_mentions,
            COUNT(DISTINCT rs.datasource_id) AS app_count,
            ARRAY_AGG(DISTINCT ds.name ORDER BY ds.name) AS affected_apps,
            MAX(fn.feature_request_narrative) AS top_narrative
        FROM review_signals rs
        JOIN datasources ds ON rs.datasource_id = ds.id
        LEFT JOIN feature_narratives fn
            ON fn.datasource_id = rs.datasource_id AND fn.feature = rs.feature
        WHERE {where}
          AND rs.feature IS NOT NULL
          AND rs.signal_type IN ('feature_request', 'bug', 'ux', 'performance')
        GROUP BY rs.feature
        HAVING COUNT(*) >= 5
        ORDER BY
            COUNT(DISTINCT rs.datasource_id) DESC,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') DESC,
            COUNT(*) DESC
        LIMIT 40
    """)
    rows = (await db.execute(sql, params)).fetchall()
    return [
        {
            "feature": r.feature,
            "total_mentions": r.total_mentions,
            "fr_mentions": r.fr_mentions,
            "app_count": r.app_count,
            "affected_apps": list(r.affected_apps or []),
            "top_narrative": r.top_narrative,
        }
        for r in rows
    ]


def _build_prompt(mode: str, signals: list[dict], meta: dict, user_hypothesis: str | None) -> str:
    top = signals[:20]
    signals_text = "\n".join(
        f"- {s['feature']}: {s['fr_mentions']} Feature-Wünsche, {s['total_mentions']} Gesamterwähnungen, "
        f"{s['app_count']} App(s) betroffen [{', '.join(s['affected_apps'][:3])}]"
        + (f"\n  Nutzer sagen: {s['top_narrative'][:200]}" if s['top_narrative'] else "")
        for s in top
    )

    scope_desc = meta.get("scope_desc", "dem analysierten Markt")

    if user_hypothesis:
        # Hypothesis validation mode — guided analysis
        instruction = (
            f"Du bist ein erfahrener Produktstratege und Marktanalyst. "
            f"Der Nutzer hat folgende Produkthypothese oder -idee:\n\n"
            f"NUTZER-HYPOTHESE: \"{user_hypothesis}\"\n\n"
            f"Deine Aufgabe: Validiere diese Hypothese anhand echter Nutzerdaten aus {scope_desc} "
            f"({meta['apps_analyzed']} Apps, {meta['total_reviews']} Reviews). "
            f"Entwickle dann ein konkretes Produktkonzept, das die Hypothese des Nutzers mit den "
            f"tatsächlichen Marktdaten verbindet — bestätige was funktioniert, korrigiere was nicht "
            f"durch Daten gedeckt ist, und ergänze was der Nutzer übersehen hat.\n\n"
            f"Modus: {'Konkurrenzprodukt (greife Schwächen bestehender Apps an)' if mode == 'competitor' else 'Innovationsprodukt (finde unbesetzte Marktlücken)'}\n"
        )
        hypothesis_fields = (
            '  "hypothesis_check": "2-3 Sätze: Wie gut stimmt die Nutzerhypothese mit den Daten überein? '
            'Was ist stark validiert, was sollte angepasst werden, welche blinden Flecken gibt es?",\n'
            '  "hypothesis_alignment": "stark" | "mittel" | "schwach",'
        )
    else:
        # Free analysis mode — purely data-driven
        if mode == "competitor":
            instruction = (
                f"Du bist ein Produktstratege. Basierend auf diesen echten Nutzerbeschwerden und Feature-Wünschen aus {scope_desc} "
                f"({meta['apps_analyzed']} Apps, {meta['total_reviews']} Reviews) "
                f"entwickle ein konkretes Konkurrenzprodukt, das gezielt die größten Schwächen der bestehenden Apps löst.\n\n"
                "Das Produkt soll:\n"
                "- Die 3–5 häufigsten ungelösten Probleme als Kernfeatures haben\n"
                "- Einen klaren Wettbewerbsvorteil gegenüber den analysierten Apps haben\n"
                "- Realistisch umsetzbar sein\n"
            )
        else:
            instruction = (
                f"Du bist ein Innovationsstratege. Basierend auf diesen echten Nutzerwünschen aus {scope_desc} "
                f"({meta['apps_analyzed']} Apps, {meta['total_reviews']} Reviews) "
                f"identifiziere die größte Marktlücke und entwickle eine innovative Produktidee, "
                f"die bisher von keinem Anbieter bedient wird.\n\n"
                "Das Produkt soll:\n"
                "- Einen noch unbesetzten Marktbereich adressieren\n"
                "- Auf echter, quantifizierter Nachfrage basieren\n"
                "- Innovativer sein als reine Feature-Kopien\n"
            )
        hypothesis_fields = ""

    json_schema = f"""{{
  "product_name": "Prägnanter Produktname (max 4 Wörter)",
  "tagline": "Ein Satz der das Alleinstellungsmerkmal beschreibt",
  "core_problem": "Das eine Kernproblem das du löst (1-2 Sätze)",
  "market_gap": "Warum kein bestehender Anbieter dieses Problem löst (1-2 Sätze)",
  "features": [
    {{"name": "Feature-Name", "mentions": 1234, "priority": "hoch"}},
    {{"name": "Feature-Name", "mentions": 567, "priority": "mittel"}},
    {{"name": "Feature-Name", "mentions": 234, "priority": "niedrig"}}
  ],
  "target_audience": "Wer die Hauptzielgruppe ist und warum (1 Satz)",
  "differentiation": "Konkret wie du besser bist als alle analysierten Apps (1-2 Sätze)",
  "risk": "Hauptrisiko bei der Umsetzung (1 Satz)",
  "risk_level": "hoch" | "mittel" | "niedrig"{(chr(44) + chr(10) + "  " + hypothesis_fields.strip()) if hypothesis_fields else ""}
}}"""

    return f"""{instruction}

NUTZERDATEN (echte Signale, sortiert nach Relevanz):
{signals_text}

Antworte AUSSCHLIESSLICH als valides JSON-Objekt mit dieser exakten Struktur:
{json_schema}

Nur JSON, kein erklärender Text davor oder danach."""


def _call_groq(prompt: str) -> dict:
    api_key = settings.GROQ_API_KEY or settings.GROQ_API_KEY_2
    if not api_key:
        raise HTTPException(status_code=503, detail="Kein Groq API Key konfiguriert.")
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1800,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


@router.post("/generate", response_model=InnovationBrief)
async def generate_innovation_brief(
    body: InnovationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where, params = _build_where(
        body.scope, body.industry, body.datasource_ids, body.market, current_user.id
    )

    signals = await _aggregate_signals(db, where, params)
    if not signals:
        raise HTTPException(
            status_code=422,
            detail="Nicht genug Daten für diese Filtereinstellung. Bitte mehr Apps hinzufügen oder den Scope erweitern."
        )

    meta_sql = text(f"""
        SELECT
            COUNT(DISTINCT ds.id) AS app_count,
            COUNT(DISTINCT r.id) AS review_count,
            STRING_AGG(DISTINCT ds.industry, ', ') AS industries,
            STRING_AGG(DISTINCT ds.name, ', ' ORDER BY ds.name) AS app_names
        FROM datasources ds
        LEFT JOIN reviews r ON r.datasource_id = ds.id
        WHERE {where}
    """)
    meta_row = (await db.execute(meta_sql, params)).fetchone()

    scope_desc = meta_row.app_names or "dem Markt"
    if body.industry:
        scope_desc = f"der Branche '{body.industry}'"
    if body.scope == "all":
        scope_desc = "dem gesamten analysierten Markt"

    meta = {
        "apps_analyzed": meta_row.app_count or 0,
        "total_reviews": meta_row.review_count or 0,
        "scope_desc": scope_desc,
    }

    hypothesis = body.user_hypothesis.strip() if body.user_hypothesis and body.user_hypothesis.strip() else None
    prompt = _build_prompt(body.mode, signals, meta, hypothesis)

    try:
        brief = _call_groq(prompt)
    except json.JSONDecodeError as exc:
        log.error("groq_json_parse_error", error=str(exc))
        raise HTTPException(status_code=500, detail="KI-Antwort konnte nicht verarbeitet werden. Bitte erneut versuchen.")
    except Exception as exc:
        log.error("groq_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Groq-Fehler: {str(exc)[:200]}")

    total_demand = sum(s["fr_mentions"] for s in signals[:10])

    return InnovationBrief(
        product_name=brief.get("product_name", "Unbekannt"),
        tagline=brief.get("tagline", ""),
        core_problem=brief.get("core_problem", ""),
        market_gap=brief.get("market_gap", ""),
        features=[
            ProductFeature(
                name=f["name"],
                mentions=f.get("mentions", 0),
                priority=f.get("priority", "mittel"),
            )
            for f in brief.get("features", [])[:6]
        ],
        target_audience=brief.get("target_audience", ""),
        differentiation=brief.get("differentiation", ""),
        risk=brief.get("risk", ""),
        risk_level=brief.get("risk_level", "mittel"),
        hypothesis_check=brief.get("hypothesis_check") if hypothesis else None,
        hypothesis_alignment=brief.get("hypothesis_alignment") if hypothesis else None,
        total_demand=total_demand,
        apps_analyzed=meta["apps_analyzed"],
        sources=[
            FeatureSignal(
                feature=s["feature"],
                total_mentions=s["total_mentions"],
                fr_mentions=s["fr_mentions"],
                app_count=s["app_count"],
                affected_apps=s["affected_apps"],
                top_narrative=s["top_narrative"],
            )
            for s in signals[:15]
        ],
    )
