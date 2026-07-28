from __future__ import annotations
import json
import structlog
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from groq import Groq
import anthropic as anthropic_sdk

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/innovation", tags=["innovation"])
log = structlog.get_logger(__name__)


class InnovationRequest(BaseModel):
    mode: str = "competitor"
    scope: str = "all"
    industry: Optional[str] = None
    datasource_ids: Optional[List[str]] = None
    market: Optional[str] = None
    user_hypothesis: Optional[str] = None
    excluded_signals: Optional[List[str]] = None


class SignalInfo(BaseModel):
    feature: str
    total_mentions: int
    fr_mentions: int
    bug_mentions: int
    app_count: int
    avg_severity: float


class FeatureSignal(BaseModel):
    feature: str
    total_mentions: int
    fr_mentions: int
    app_count: int
    affected_apps: List[str]
    top_narrative: Optional[str]


class ProductFeature(BaseModel):
    name: str
    mentions: int
    priority: str


class InnovationBrief(BaseModel):
    product_name: str
    tagline: str
    core_problem: str
    market_gap: str
    features: List[ProductFeature]
    target_audience: str
    differentiation: str
    risk: str
    risk_level: str
    hypothesis_check: Optional[str] = None
    hypothesis_alignment: Optional[str] = None
    total_demand: int
    apps_analyzed: int
    sources: List[FeatureSignal]
    concept_description: Optional[str] = None


def _build_where(
    scope: str,
    industry: Optional[str],
    datasource_ids: Optional[List[str]],
    market: Optional[str],
    user_id: str,
) -> tuple:
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


async def _get_excluded_signals(db: AsyncSession, user_id: str) -> List[str]:
    """
    Return signal feature labels that were the primary anchor in recent briefs.
    Excludes top-3 signals from each of the last 10 briefs so new generations
    explore different clusters instead of re-anchoring on the same dominant signal.
    """
    sql = text("""
        SELECT DISTINCT elem->>'feature' AS feature
        FROM (
            SELECT sources FROM innovation_briefs
            WHERE user_id = :uid
              AND sources IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 10
        ) recent,
        LATERAL jsonb_array_elements(sources) WITH ORDINALITY AS t(elem, pos)
        WHERE pos <= 3
          AND elem->>'feature' IS NOT NULL
    """)
    rows = (await db.execute(sql, {"uid": user_id})).fetchall()
    return [r.feature for r in rows if r.feature]


async def _compute_signal_graph(
    db: AsyncSession,
    signals: list,
    where: str,
    params: dict,
) -> dict:
    """
    Compute co-occurrence graph for the given signal set.
    Returns hub_signals (high connectivity = systemic OEM problems)
    and edges (co-occurrence pairs with count).
    """
    if not signals:
        return {"hub_signals": [], "edges": [], "hub_set": set()}

    feature_list = [s["feature"] for s in signals]
    # SQLAlchemy bindparams for IN list
    placeholders = ", ".join(f":f{i}" for i in range(len(feature_list)))
    feature_params = {f"f{i}": f for i, f in enumerate(feature_list)}

    co_sql = text(f"""
        SELECT
            a.feature AS sig_a,
            b.feature AS sig_b,
            COUNT(DISTINCT a.review_id) AS co_count
        FROM review_signals a
        JOIN review_signals b ON a.review_id = b.review_id AND a.feature < b.feature
        JOIN datasources ds ON a.datasource_id = ds.id
        WHERE {where}
          AND a.feature IN ({placeholders})
          AND b.feature IN ({placeholders})
        GROUP BY a.feature, b.feature
        HAVING COUNT(DISTINCT a.review_id) >= 10
        ORDER BY co_count DESC
        LIMIT 60
    """)
    edge_rows = (await db.execute(co_sql, {**params, **feature_params})).fetchall()
    edges = [{"a": r.sig_a, "b": r.sig_b, "count": r.co_count} for r in edge_rows]

    # Hub score = total co-occurrence weight per signal
    hub_scores: dict = {}
    for e in edges:
        hub_scores[e["a"]] = hub_scores.get(e["a"], 0) + e["count"]
        hub_scores[e["b"]] = hub_scores.get(e["b"], 0) + e["count"]

    total_weight = sum(hub_scores.values()) or 1
    # Signals with >20% of total co-occurrence weight are hubs
    hub_threshold = total_weight * 0.20
    hub_signals = [
        {"feature": f, "score": s, "connected_to": [
            e["b"] if e["a"] == f else e["a"]
            for e in edges if f in (e["a"], e["b"])
        ][:6]}
        for f, s in sorted(hub_scores.items(), key=lambda x: -x[1])
        if s >= hub_threshold
    ]
    hub_set = {h["feature"] for h in hub_signals}

    return {"hub_signals": hub_signals, "edges": edges[:20], "hub_set": hub_set}


def _embed_text(text: str) -> Optional[List[float]]:
    """Embed a text using the same model used for review embeddings."""
    try:
        from app.pipeline.ml import get_embedding_model
        model = get_embedding_model()
        if model is None:
            return None
        vec = model.encode([text], normalize_embeddings=True)[0]
        return vec.tolist()
    except Exception as e:
        log.warning("hypothesis_embed_failed", error=str(e))
        return None


async def _aggregate_signals(
    db: AsyncSession,
    where: str,
    params: dict,
    exclude_features: Optional[List[str]] = None,
) -> list[dict]:
    # Build exclusion clause — if excluding leaves < 5 signals, skip exclusion
    exclusion_clause = ""
    excl_params: dict = {}
    if exclude_features:
        excl_placeholders = ", ".join(f":excl_{i}" for i in range(len(exclude_features)))
        exclusion_clause = f"AND rs.feature NOT IN ({excl_placeholders})"
        excl_params = {f"excl_{i}": f for i, f in enumerate(exclude_features)}

    # Step 1: all signal clusters — no artificial cutoffs
    sql = text(f"""
        SELECT
            rs.feature,
            COUNT(*) AS total_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') AS fr_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'bug') AS bug_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'ux') AS ux_mentions,
            COUNT(DISTINCT rs.datasource_id) AS app_count,
            ARRAY_AGG(DISTINCT ds.name ORDER BY ds.name) AS affected_apps,
            AVG(rs.severity) AS avg_severity,
            MAX(fn.feature_request_narrative) AS top_narrative
        FROM review_signals rs
        JOIN datasources ds ON rs.datasource_id = ds.id
        LEFT JOIN feature_narratives fn
            ON fn.datasource_id = rs.datasource_id AND fn.feature = rs.feature
        WHERE {where}
          AND rs.feature IS NOT NULL
          AND rs.signal_type IN ('feature_request', 'bug', 'ux', 'performance')
          {exclusion_clause}
        GROUP BY rs.feature
        HAVING COUNT(*) >= 2
        ORDER BY
            COUNT(DISTINCT rs.datasource_id) DESC,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') DESC,
            COUNT(*) DESC
    """)
    rows = (await db.execute(sql, {**params, **excl_params})).fetchall()

    # Fallback: if exclusion left fewer than 5 signals, re-run without exclusion
    if len(rows) < 5 and exclusion_clause:
        log.info("signal_exclusion_fallback", reason="fewer than 5 signals after exclusion")
        sql_fb = text(f"""
            SELECT
                rs.feature,
                COUNT(*) AS total_mentions,
                COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') AS fr_mentions,
                COUNT(*) FILTER (WHERE rs.signal_type = 'bug') AS bug_mentions,
                COUNT(*) FILTER (WHERE rs.signal_type = 'ux') AS ux_mentions,
                COUNT(DISTINCT rs.datasource_id) AS app_count,
                ARRAY_AGG(DISTINCT ds.name ORDER BY ds.name) AS affected_apps,
                AVG(rs.severity) AS avg_severity,
                MAX(fn.feature_request_narrative) AS top_narrative
            FROM review_signals rs
            JOIN datasources ds ON rs.datasource_id = ds.id
            LEFT JOIN feature_narratives fn
                ON fn.datasource_id = rs.datasource_id AND fn.feature = rs.feature
            WHERE {where}
              AND rs.feature IS NOT NULL
              AND rs.signal_type IN ('feature_request', 'bug', 'ux', 'performance')
            GROUP BY rs.feature
            HAVING COUNT(*) >= 2
            ORDER BY
                COUNT(DISTINCT rs.datasource_id) DESC,
                COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') DESC,
                COUNT(*) DESC
        """)
        rows = (await db.execute(sql_fb, params)).fetchall()

    signals = [
        {
            "feature": r.feature,
            "total_mentions": r.total_mentions,
            "fr_mentions": r.fr_mentions,
            "bug_mentions": r.bug_mentions,
            "ux_mentions": r.ux_mentions,
            "app_count": r.app_count,
            "affected_apps": list(r.affected_apps or []),
            "avg_severity": round(float(r.avg_severity or 0), 1),
            "top_narrative": r.top_narrative,
            "reviews": [],
        }
        for r in rows
    ]

    if not signals:
        return signals

    # Step 2: enrich top signals with real review texts
    # Scale review count by signal rank: top signals get more reviews
    for i, sig in enumerate(signals):
        # Scale by rank: top signals get more reviews, lower ones fewer
        # No hard cap — take as many unique reviews as exist up to the limit
        if i < 3:
            n_reviews = 20
        elif i < 8:
            n_reviews = 12
        elif i < 15:
            n_reviews = 8
        else:
            n_reviews = 4

        review_sql = text(f"""
            SELECT DISTINCT ON (r.content)
                r.content,
                r.score,
                rs.severity,
                ds.name AS app_name
            FROM review_signals rs
            JOIN reviews r ON rs.review_id = r.id
            JOIN datasources ds ON rs.datasource_id = ds.id
            WHERE {where}
              AND rs.feature = :feature
              AND r.content IS NOT NULL
              AND length(r.content) > 60
              AND r.language IN ('de', 'en')
            ORDER BY r.content, r.score ASC, rs.severity DESC
            LIMIT :limit
        """)
        # Fetch a larger pool to allow proper deduplication and sorting
        p = {**params, "feature": sig["feature"], "limit": n_reviews * 5}
        review_rows = (await db.execute(review_sql, p)).fetchall()

        all_revs = [
            {
                "content": row.content,
                "score": row.score,
                "severity": row.severity or 0,
                "app": row.app_name,
            }
            for row in review_rows
            if row.content and len(row.content.strip()) > 60
        ]

        # Sort: lowest score + highest severity first, then longest content
        all_revs.sort(key=lambda r: (r["score"], -r["severity"], -len(r["content"])))

        # Deduplicate on first 60 chars — remove near-identical reviews
        seen_prefixes: set = set()
        deduped = []
        for r in all_revs:
            prefix = r["content"][:60].lower().strip()
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                deduped.append(r)
            if len(deduped) >= n_reviews:
                break

        sig["reviews"] = deduped

    return signals


async def _aggregate_signals_hypothesis(
    db: AsyncSession,
    where: str,
    params: dict,
    hyp_embedding: List[float],
    exclude_features: Optional[List[str]] = None,
) -> list[dict]:
    """
    Hypothesis-guided signal aggregation:
    1. Vector search → top 500 reviews semantically closest to the hypothesis
    2. Aggregate signals FROM those reviews (not from the full corpus)
    3. Enrich each signal with reviews sorted by hypothesis relevance
    """
    hyp_vec = str(hyp_embedding)

    exclusion_clause = ""
    excl_params: dict = {}
    if exclude_features:
        excl_placeholders = ", ".join(f":excl_{i}" for i in range(len(exclude_features)))
        exclusion_clause = f"AND rs.feature NOT IN ({excl_placeholders})"
        excl_params = {f"excl_{i}": f for i, f in enumerate(exclude_features)}

    # Step 1: find hypothesis-relevant reviews via cosine similarity
    signal_sql = text(f"""
        WITH hypothesis_reviews AS (
            SELECT
                r.id,
                r.datasource_id,
                r.embedding <=> CAST(:hyp_vec AS vector) AS distance
            FROM reviews r
            JOIN datasources ds ON r.datasource_id = ds.id
            WHERE {where}
              AND r.embedding IS NOT NULL
            ORDER BY r.embedding <=> CAST(:hyp_vec AS vector)
            LIMIT 500
        )
        SELECT
            rs.feature,
            COUNT(DISTINCT hr.id)                                                        AS total_mentions,
            COUNT(DISTINCT hr.id) FILTER (WHERE rs.signal_type = 'feature_request')     AS fr_mentions,
            COUNT(DISTINCT hr.id) FILTER (WHERE rs.signal_type = 'bug')                 AS bug_mentions,
            COUNT(DISTINCT hr.id) FILTER (WHERE rs.signal_type = 'ux')                  AS ux_mentions,
            COUNT(DISTINCT hr.datasource_id)                                             AS app_count,
            ARRAY_AGG(DISTINCT ds.name ORDER BY ds.name)                                AS affected_apps,
            AVG(rs.severity)                                                             AS avg_severity,
            AVG(hr.distance)                                                             AS avg_distance,
            MAX(fn.feature_request_narrative)                                            AS top_narrative
        FROM hypothesis_reviews hr
        JOIN review_signals rs ON rs.review_id = hr.id
        JOIN datasources ds ON ds.id = hr.datasource_id
        LEFT JOIN feature_narratives fn
            ON fn.datasource_id = hr.datasource_id AND fn.feature = rs.feature
        WHERE rs.feature IS NOT NULL
          AND rs.signal_type IN ('feature_request', 'bug', 'ux', 'performance')
          {exclusion_clause}
        GROUP BY rs.feature
        HAVING COUNT(DISTINCT hr.id) >= 2
        ORDER BY
            AVG(hr.distance) ASC,
            COUNT(DISTINCT hr.id) FILTER (WHERE rs.signal_type = 'feature_request') DESC,
            COUNT(DISTINCT hr.id) DESC
    """)

    hyp_params = {**params, "hyp_vec": hyp_vec, **excl_params}
    rows = (await db.execute(signal_sql, hyp_params)).fetchall()

    signals = [
        {
            "feature": r.feature,
            "total_mentions": r.total_mentions,
            "fr_mentions": r.fr_mentions,
            "bug_mentions": r.bug_mentions,
            "ux_mentions": r.ux_mentions,
            "app_count": r.app_count,
            "affected_apps": list(r.affected_apps or []),
            "avg_severity": round(float(r.avg_severity or 0), 1),
            "avg_distance": round(float(r.avg_distance or 1), 4),
            "top_narrative": r.top_narrative,
            "reviews": [],
        }
        for r in rows
    ]

    if not signals:
        return signals

    # Step 2: enrich each signal with hypothesis-relevant review texts
    # Reviews are sorted by semantic closeness to hypothesis (not just severity)
    for i, sig in enumerate(signals):
        if i < 3:
            n_reviews = 20
        elif i < 8:
            n_reviews = 12
        elif i < 15:
            n_reviews = 8
        else:
            n_reviews = 4

        review_sql = text(f"""
            SELECT DISTINCT ON (r.content)
                r.content,
                r.score,
                rs.severity,
                ds.name AS app_name,
                r.embedding <=> CAST(:hyp_vec AS vector) AS distance
            FROM review_signals rs
            JOIN reviews r ON rs.review_id = r.id
            JOIN datasources ds ON rs.datasource_id = ds.id
            WHERE {where}
              AND rs.feature = :feature
              AND r.embedding IS NOT NULL
              AND r.content IS NOT NULL
              AND length(r.content) > 60
              AND r.language IN ('de', 'en')
            ORDER BY r.content, r.embedding <=> CAST(:hyp_vec AS vector) ASC
            LIMIT :limit
        """)
        p = {**params, "feature": sig["feature"], "hyp_vec": hyp_vec, "limit": n_reviews * 5}
        review_rows = (await db.execute(review_sql, p)).fetchall()

        all_revs = [
            {
                "content": row.content,
                "score": row.score,
                "severity": row.severity or 0,
                "app": row.app_name,
                "distance": float(row.distance),
            }
            for row in review_rows
            if row.content and len(row.content.strip()) > 60
        ]

        # Sort by hypothesis relevance first, then severity
        all_revs.sort(key=lambda r: (r["distance"], -r["severity"]))

        seen_prefixes: set = set()
        deduped = []
        for r in all_revs:
            prefix = r["content"][:60].lower().strip()
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                deduped.append(r)
            if len(deduped) >= n_reviews:
                break

        sig["reviews"] = deduped

    return signals


def _build_prompt(mode: str, signals: list, meta: dict, user_hypothesis: Optional[str], previous_concepts: Optional[List[str]] = None, focus_signal: Optional[str] = None, signal_graph: Optional[dict] = None) -> str:
    scope_desc = meta.get("scope_desc", "dem analysierten Markt")
    apps_analyzed = meta['apps_analyzed']
    total_reviews = meta['total_reviews']
    retrieval_mode = meta.get("retrieval_mode", "standard")
    retrieval_note = meta.get("retrieval_note", "")

    # ── Part A: Full signal overview (all clusters, compact) ──────────────
    overview_lines = []
    for i, s in enumerate(signals):
        bug_note = f" | {s['bug_mentions']} Bugs" if s.get('bug_mentions', 0) > 0 else ""
        sev_note = f" | Severity ø{s['avg_severity']}" if s.get('avg_severity', 0) > 0 else ""
        overview_lines.append(
            f"  #{i+1:>3} {s['feature']:<28} "
            f"{s['fr_mentions']:>4} FR{bug_note}{sev_note} "
            f"| {s['app_count']} App(s): {', '.join(s['affected_apps'][:3])}"
        )
    signal_overview = "\n".join(overview_lines)

    # ── Part B: Deep-dive with real reviews for top signals ───────────────
    deep_dive_parts = []
    for i, s in enumerate(signals):
        if not s.get("reviews") and not s.get("top_narrative"):
            continue
        # Only deep-dive the top 15 by mention count
        if i >= 15:
            break

        lines = [
            f"\n▶ SIGNAL #{i+1}: \"{s['feature']}\"",
            f"  {s['fr_mentions']} Feature-Wünsche · {s['total_mentions']} Erwähnungen · "
            f"{s['app_count']} App(s) · Severity ø{s.get('avg_severity', 0)}",
        ]
        if s.get("top_narrative"):
            lines.append(f"  KI-Zusammenfassung: \"{s['top_narrative'][:300]}\"")

        if s.get("reviews"):
            lines.append(f"  Echte Nutzerstimmen ({len(s['reviews'])} Reviews):")
            for r in s["reviews"]:
                stars = "⭐" * max(1, round(r["score"])) if r["score"] else "?"
                sev = f" [Severity {r['severity']}]" if r.get("severity") else ""
                app = f" [{r['app']}]" if r.get("app") else ""
                text_preview = r["content"][:280].replace("\n", " ").strip()
                lines.append(f"    {stars}{sev}{app}: \"{text_preview}\"")

        deep_dive_parts.append("\n".join(lines))

    signals_text = signal_overview + "\n\n━━━ DEEP-DIVE (Top-Signale mit echten Reviews) ━━━" + "\n".join(deep_dive_parts)

    # Signal graph block — hub vs edge node context for the LLM
    graph_block = ""
    if signal_graph and signal_graph.get("hub_signals"):
        hub_lines = []
        for h in signal_graph["hub_signals"][:4]:
            connected = ", ".join(h["connected_to"][:5])
            hub_lines.append(f"  ⚠ {h['feature']} (Hub-Score {h['score']:,}) → verbunden mit: {connected}")
        edge_signals = [
            s["feature"] for s in signals
            if s["feature"] not in signal_graph.get("hub_set", set())
        ][:8]
        edge_line = ", ".join(edge_signals) if edge_signals else "keine"
        graph_block = f"""

━━━ SIGNAL-GRAPH ANALYSE ━━━
HUB-SIGNALE — systemische OEM-Infrastrukturprobleme, keine direkten Produktchancen für Dritte:
{chr(10).join(hub_lines)}

EDGE-SIGNALE — eigenständige Produktchancen, kein OEM-Infrastrukturproblem:
  ✓ {edge_line}

STRATEGISCHE ANWEISUNG: Baue das Konzept primär auf EDGE-SIGNALEN auf. \
Hub-Signale sind strukturelle Probleme die Hersteller selbst lösen müssen — \
kein Drittanbieter kann sie systemisch adressieren. Die Edge-Signale sind deine Marktlücke."""

    # Top-3 dominant signals for anchoring the concept
    dominant = signals[:3]
    dominant_summary = ", ".join(
        f"\"{s['feature']}\" ({s['fr_mentions']:,} FR in {s['app_count']} Apps)"
        for s in dominant
    )

    # Constraint: previous concepts to avoid repetition
    previous_concepts_block = ""
    if previous_concepts:
        names = ", ".join(f'"{n}"' for n in previous_concepts)
        previous_concepts_block = f"""
⚠️ BEREITS GENERIERTE KONZEPTE — entwickle etwas GRUNDLEGEND ANDERES:
{names}
Diese Konzepte sind bereits bekannt. Wähle einen anderen strategischen Winkel, andere Zielgruppe, \
anderen Kern-Use-Case oder fokussiere auf andere Signale aus der Liste."""

    # Optional focus signal
    focus_block = ""
    if focus_signal:
        focus_block = f"""
🎯 FOKUS-VORGABE: Baue das Konzept primär um das Signal "{focus_signal}" herum. \
Die anderen Signale dienen als ergänzender Kontext."""

    if user_hypothesis:
        mode_instruction = f"""Du bist ein Senior-Produktstratege. Der Gründer hat folgende Idee:

HYPOTHESE: "{user_hypothesis}"

Deine Aufgabe in zwei Schritten:
1. VALIDIERUNG: Prüfe diese Hypothese gegen die Nutzerdaten. Wo hat der Gründer recht? Wo liegen blinde Flecken? Welche Signale widersprechen der Idee?
2. KONZEPT: Entwickle daraus ein konkretes Produkt — behalte was die Daten bestätigen, korrigiere was sie widerlegen, ergänze was der Gründer übersehen hat.

Modus: {"Konkurrenzprodukt — greife die spezifischen Schwächen der analysierten Apps an" if mode == "competitor" else "Innovationsprodukt — besetze die Marktlücke die kein bestehender Anbieter füllt"}{previous_concepts_block}{focus_block}"""
        hypothesis_fields = (
            '"hypothesis_check": "Konkrete Einschätzung in 3-4 Sätzen: Welche Teile der Hypothese sind durch Daten stark belegt (mit Zahlen), '
            'welche sind schwach belegt, was hat der Gründer übersehen? Sei direkt und ehrlich.",\n'
            '  "hypothesis_alignment": "stark" | "mittel" | "schwach",'
        )
    else:
        if mode == "competitor":
            mode_instruction = f"""Du bist ein Senior-Produktstratege mit 15 Jahren Erfahrung in Competitive Intelligence.

Analysiere diese {apps_analyzed} Apps mit {total_reviews:,} Reviews aus {scope_desc}. \
Die dominanten ungelösten Probleme sind: {dominant_summary}.

Entwickle ein Konkurrenzprodukt das diese Apps vom Markt verdrängt — \
nicht durch marginale Verbesserungen, sondern durch einen fundamentalen Ansatz der die Kernprobleme strukturell löst.{previous_concepts_block}{focus_block}"""
        else:
            mode_instruction = f"""Du bist ein Senior-Innovationsstratege der unbesetzte Marktlücken identifiziert.

Analysiere diese {apps_analyzed} Apps mit {total_reviews:,} Reviews aus {scope_desc}. \
Die stärksten unerfüllten Wünsche sind: {dominant_summary}.

Identifiziere was KEIN bestehender Anbieter löst und entwickle ein Produkt \
das eine neue Kategorie schafft — nicht eine bessere Version des Bestehenden.{previous_concepts_block}{focus_block}"""
        hypothesis_fields = ""

    # Instructions before the schema (not inside field values — avoids model copying them back)
    field_instructions = f"""
AUSFÜLLANWEISUNG für das JSON-Objekt unten:
• product_name  → Echter Produktname, 2-4 Wörter, kein Generikum. Beispiel: "ConnectDrive Pro", "UpdateSync"
• tagline       → 1 Satz: "Fahrer können endlich X — ohne Y". X und Y aus den Daten ableiten.
• core_problem  → Konkretes Problem mit Zahlen und Nutzerzitat. Beispiel: "Updates sind das meistgenannte Problem mit 56 FR-Wünschen — Nutzer schreiben wörtlich: ..."
• market_gap    → Warum lösen die analysierten Apps das Problem NICHT? Konkrete Schwäche benennen.
• features      → Je Feature einen ausformulierten Namen (nicht rohe Labels wie "Updates"). Beispiel: "OTA-Software-Updates ohne Werkstatt". Zahlen EXAKT aus den Signalen übernehmen.
• target_audience → Wer sind die Nutzer konkret? Fahrzeughalter, pendelnde Berufstätige, Flottenbetreiber etc.
• differentiation → Konkret vergleichen: "Während [App X] nur Y tut, löst dieses Produkt Z durch [Ansatz]."
• risk          → 1 konkretes Risiko, kein Generikum wie "Akzeptanz".
• risk_level    → Exakt einer dieser Werte: hoch | mittel | niedrig"""

    hypothesis_field_str = (f"\n  {hypothesis_fields}" if hypothesis_fields else "")

    json_schema = f"""{{
  "product_name": "HIER_ECHTER_PRODUKTNAME",
  "tagline": "HIER_EINE_ZEILE_TAGLINE",
  "core_problem": "HIER_KERNPROBLEM_MIT_ZAHLEN_UND_ZITAT",
  "market_gap": "HIER_STRUKTURELLE_LUECKE_DER_ANALYSIERTEN_APPS",
  "features": [
    {{"name": "AUSFORMULIERTER_FEATURE_NAME_AUS_SIGNAL_1", "mentions": {signals[0]['fr_mentions'] if signals else 0}, "priority": "hoch"}},
    {{"name": "AUSFORMULIERTER_FEATURE_NAME_AUS_SIGNAL_2", "mentions": {signals[1]['fr_mentions'] if len(signals) > 1 else 0}, "priority": "hoch"}},
    {{"name": "AUSFORMULIERTER_FEATURE_NAME_AUS_SIGNAL_3", "mentions": {signals[2]['fr_mentions'] if len(signals) > 2 else 0}, "priority": "mittel"}},
    {{"name": "AUSFORMULIERTER_FEATURE_NAME_AUS_SIGNAL_4", "mentions": {signals[3]['fr_mentions'] if len(signals) > 3 else 0}, "priority": "mittel"}},
    {{"name": "AUSFORMULIERTER_FEATURE_NAME_AUS_SIGNAL_5", "mentions": {signals[4]['fr_mentions'] if len(signals) > 4 else 0}, "priority": "niedrig"}}
  ],
  "target_audience": "HIER_ZIELGRUPPE_KONKRET",
  "differentiation": "HIER_USP_KONKRET_VERGLICHEN_MIT_DEN_APPS",
  "risk": "HIER_KONKRETES_HAUPTRISIKO",
  "risk_level": "HIER_RISIKOLEVEL"{hypothesis_field_str}
}}"""

    retrieval_header = ""
    if retrieval_mode == "hypothesis" and retrieval_note:
        retrieval_header = f"\n📍 RETRIEVAL-MODUS: {retrieval_note}\n"

    return f"""{mode_instruction}

━━━ ECHTE NUTZERSIGNALE ({apps_analyzed} Apps · {total_reviews:,} Reviews analysiert) ━━━{retrieval_header}

{signals_text}{graph_block}

━━━ AUSFÜLLANWEISUNG ━━━
{field_instructions}

Ersetze ALLE Platzhalter (HIER_...) durch echte Inhalte. Antworte NUR als valides JSON — kein Text davor oder danach, keine Erklärungen:
{json_schema}"""


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate_limit" in s or "rate limit" in s or "overloaded" in s


# ---------------------------------------------------------------------------
# Claude — primary provider
# ---------------------------------------------------------------------------

def _call_claude_json(prompt: str) -> dict:
    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=2500,
        temperature=0.6,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _call_claude_text(prompt: str, system: Optional[str] = None, messages: Optional[list] = None) -> str:
    client = anthropic_sdk.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    kwargs: dict = dict(model=settings.ANTHROPIC_MODEL, max_tokens=3000, temperature=0.4)
    if system:
        kwargs["system"] = system
    kwargs["messages"] = messages if messages else [{"role": "user", "content": prompt}]
    msg = client.messages.create(**kwargs)
    return msg.content[0].text.strip()


# ---------------------------------------------------------------------------
# Groq — fallback provider
# ---------------------------------------------------------------------------

_GROQ_JSON_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "gemma2-9b-it"]
_GROQ_TEXT_MODELS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]


def _groq_json_fallback(prompt: str) -> dict:
    keys = [k for k in [settings.GROQ_API_KEY, settings.GROQ_API_KEY_2] if k]
    last_exc: Optional[Exception] = None
    for model in _GROQ_JSON_MODELS:
        for key in keys:
            try:
                resp = Groq(api_key=key).chat.completions.create(
                    model=model, messages=[{"role": "user", "content": prompt}],
                    temperature=0.35, max_tokens=2500,
                )
                raw = resp.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                return json.loads(raw.strip())
            except Exception as exc:
                if _is_rate_limit(exc):
                    last_exc = exc
                    continue
                raise
    raise HTTPException(status_code=429, detail="Alle KI-Anbieter haben das Limit erreicht. Bitte später erneut versuchen.") from last_exc


def _groq_text_fallback(messages: list, temperature: float, max_tokens: int) -> str:
    keys = [k for k in [settings.GROQ_API_KEY, settings.GROQ_API_KEY_2] if k]
    last_exc: Optional[Exception] = None
    for model in _GROQ_TEXT_MODELS:
        for key in keys:
            try:
                resp = Groq(api_key=key).chat.completions.create(
                    model=model, messages=messages, temperature=temperature, max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as exc:
                if _is_rate_limit(exc):
                    last_exc = exc
                    continue
                raise
    raise HTTPException(status_code=429, detail="Alle KI-Anbieter haben das Limit erreicht. Bitte später erneut versuchen.") from last_exc


# ---------------------------------------------------------------------------
# Public API — Claude primary, Groq fallback
# ---------------------------------------------------------------------------

def _call_groq(prompt: str) -> dict:
    if settings.ANTHROPIC_API_KEY:
        try:
            return _call_claude_json(prompt)
        except Exception as exc:
            log.warning("claude_json_fallback_to_groq", error=str(exc)[:150])
    return _groq_json_fallback(prompt)


def _call_groq_text(prompt: str) -> str:
    if settings.ANTHROPIC_API_KEY:
        try:
            return _call_claude_text(prompt)
        except Exception as exc:
            log.warning("claude_text_fallback_to_groq", error=str(exc)[:150])
    return _groq_text_fallback([{"role": "user", "content": prompt}], 0.4, 2000)


def _groq_call_robust(messages: list, temperature: float, max_tokens: int, prefer_fast_model: bool = False) -> str:
    """Chat endpoint: Claude primary, Groq fallback."""
    if settings.ANTHROPIC_API_KEY:
        try:
            system = next((m["content"] for m in messages if m["role"] == "system"), None)
            user_msgs = [m for m in messages if m["role"] != "system"]
            return _call_claude_text("", system=system, messages=user_msgs)
        except Exception as exc:
            log.warning("claude_chat_fallback_to_groq", error=str(exc)[:150])
    return _groq_text_fallback(messages, temperature, max_tokens)


def _build_concept_prompt(result: "InnovationBrief", signals: list, meta: dict) -> str:
    features_text = "\n".join(
        f"  {i+1}. {f.name} — {f.mentions:,} Erwähnungen (Priorität: {f.priority.upper()})"
        for i, f in enumerate(result.features)
    )
    signals_text = "\n".join(
        f"  [{i+1}] \"{s['feature']}\": {s['fr_mentions']} FR-Wünsche · {s['total_mentions']} Erwähnungen · {s['app_count']} Apps"
        + (f"\n       Nutzerzitat: \"{s['top_narrative'][:300]}\"" if s.get('top_narrative') else "")
        for i, s in enumerate(signals[:15])
    )

    return f"""Du bist ein erfahrener Unternehmensberater und Produktstratege. \
Du hast soeben folgendes Produktkonzept auf Basis realer Nutzerdaten entwickelt:

PRODUKT: {result.product_name}
TAGLINE: {result.tagline}
KERNPROBLEM: {result.core_problem}
MARKTLÜCKE: {result.market_gap}
ZIELGRUPPE: {result.target_audience}
USP: {result.differentiation}
RISIKO: {result.risk} (Level: {result.risk_level})

KERN-FEATURES (datenbasiert):
{features_text}

DATENBASIS — Echte Review-Signale ({meta['apps_analyzed']} Apps · {meta['total_reviews']:,} Reviews):
{signals_text}

━━━ DEINE AUFGABE ━━━

Schreibe jetzt eine vollständige, professionelle und ausführliche Konzeptbeschreibung für dieses Produkt. \
Das Dokument richtet sich an Investoren, Co-Founder und erste Entwicklungspartner. \
Es muss auf ECHTEN DATEN basieren — zitiere Zahlen und Nutzerfeedback konkret.

Struktur des Dokuments (verwende diese genauen deutschen Überschriften):

## Executive Summary
Zwei bis drei Absätze. Beschreibe das Produkt, das Problem, die Chance und warum jetzt. \
Nenne konkrete Zahlen aus der Datenbasis.

## Markt- und Wettbewerbsanalyse
Drei bis vier Absätze. Analysiere den Markt anhand der {meta['apps_analyzed']} analysierten Apps. \
Welche Schwächen haben sie? Wo ist die strukturelle Lücke? Belege mit konkreten Signalzahlen.

## Produktvision und Alleinstellungsmerkmal
Zwei bis drei Absätze. Was ist das Produkt in 5 Jahren? \
Was macht es fundamental anders als alles was existiert? Konkret, nicht generisch.

## Feature-Konzept im Detail
Für jedes der {len(result.features)} Kern-Features einen eigenständigen Unterabschnitt (### Feature-Name). \
Je Feature: Warum existiert dieses Feature (Datenbelegung), wie funktioniert es aus Nutzersicht, \
welchen konkreten Nutzen schafft es?

## Zielgruppe und Nutzerszenarien
Zwei bis drei Absätze. Wen sprechen wir genau an? Beschreibe 2-3 konkrete Nutzungsszenarien \
mit echten Situationen aus dem Leben der Zielgruppe.

## Geschäftsmodell und Monetarisierung
Zwei bis drei Absätze. Wie verdient das Produkt Geld? \
Welches Preismodell macht Sinn (Freemium, SaaS, Marktplatz)? Welche Metriken sind entscheidend?

## Go-to-Market Strategie
Zwei bis drei Absätze. Wie erreicht das Produkt die ersten 1.000 Nutzer? \
Welche Kanäle, welche Botschaft, welche Kooperationen? Erste 90 Tage konkret.

## Risiken und Mitigationsstrategien
Zwei bis drei Absätze. Die {len(result.features)} größten Risiken (das Hauptrisiko ist: "{result.risk}"). \
Für jedes Risiko eine konkrete Mitigation.

## Nächste Schritte
Eine priorisierte Liste von 5-7 konkreten nächsten Aktionen — was macht das Team in den ersten 30 Tagen?

WICHTIG: Schreibe fließenden Prosatext, keine kurzen Stichpunkte. \
Jeder Absatz muss substanziell sein (mindestens 3-4 Sätze). \
Nutze keine Floskeln wie "ist wichtig" oder "spielt eine Rolle" — sei konkret und präzise. \
Insgesamt mindestens 1.200 Wörter. Schreibe auf Deutsch."""


class SavedBriefMeta(BaseModel):
    id: str
    created_at: str
    mode: str
    scope: str
    product_name: str
    tagline: Optional[str]
    risk_level: Optional[str]
    total_demand: Optional[int]
    apps_analyzed: Optional[int]
    user_hypothesis: Optional[str]
    industry: Optional[str]


class SavedBriefFull(InnovationBrief):
    id: str
    created_at: str
    mode: str
    scope: str
    industry: Optional[str] = None
    user_hypothesis: Optional[str] = None
    concept_description: Optional[str] = None


async def _save_brief(
    db: AsyncSession,
    user_id: str,
    body: InnovationRequest,
    result: InnovationBrief,
) -> str:
    sql = text("""
        INSERT INTO innovation_briefs (
            user_id, mode, scope, industry, market, user_hypothesis,
            product_name, tagline, core_problem, market_gap,
            features, target_audience, differentiation,
            risk, risk_level, hypothesis_check, hypothesis_alignment,
            total_demand, apps_analyzed, sources, concept_description
        ) VALUES (
            :user_id, :mode, :scope, :industry, :market, :user_hypothesis,
            :product_name, :tagline, :core_problem, :market_gap,
            :features, :target_audience, :differentiation,
            :risk, :risk_level, :hypothesis_check, :hypothesis_alignment,
            :total_demand, :apps_analyzed, :sources, :concept_description
        ) RETURNING id
    """)
    row = (await db.execute(sql, {
        "user_id": user_id,
        "mode": body.mode,
        "scope": body.scope,
        "industry": body.industry,
        "market": body.market,
        "user_hypothesis": body.user_hypothesis,
        "product_name": result.product_name,
        "tagline": result.tagline,
        "core_problem": result.core_problem,
        "market_gap": result.market_gap,
        "features": json.dumps([f.dict() for f in result.features]),
        "target_audience": result.target_audience,
        "differentiation": result.differentiation,
        "risk": result.risk,
        "risk_level": result.risk_level,
        "hypothesis_check": result.hypothesis_check,
        "hypothesis_alignment": result.hypothesis_alignment,
        "total_demand": result.total_demand,
        "apps_analyzed": result.apps_analyzed,
        "sources": json.dumps([s.dict() for s in result.sources]),
        "concept_description": result.concept_description,
    })).fetchone()
    await db.commit()
    return str(row.id)


@router.get("/briefs", response_model=List[SavedBriefMeta])
async def list_briefs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(text("""
        SELECT id, created_at, mode, scope, industry, user_hypothesis,
               product_name, tagline, risk_level, total_demand, apps_analyzed
        FROM innovation_briefs
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 50
    """), {"uid": current_user.id})).fetchall()
    return [
        SavedBriefMeta(
            id=str(r.id),
            created_at=r.created_at.isoformat(),
            mode=r.mode,
            scope=r.scope,
            product_name=r.product_name,
            tagline=r.tagline,
            risk_level=r.risk_level,
            total_demand=r.total_demand,
            apps_analyzed=r.apps_analyzed,
            user_hypothesis=r.user_hypothesis,
            industry=r.industry,
        )
        for r in rows
    ]


@router.get("/briefs/{brief_id}", response_model=SavedBriefFull)
async def get_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (await db.execute(text("""
        SELECT * FROM innovation_briefs WHERE id = :id AND user_id = :uid
    """), {"id": brief_id, "uid": current_user.id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brief nicht gefunden.")
    return SavedBriefFull(
        id=str(row.id),
        created_at=row.created_at.isoformat(),
        mode=row.mode,
        scope=row.scope,
        industry=row.industry,
        user_hypothesis=row.user_hypothesis,
        product_name=row.product_name,
        tagline=row.tagline or "",
        core_problem=row.core_problem or "",
        market_gap=row.market_gap or "",
        features=[ProductFeature(**f) for f in (row.features or [])],
        target_audience=row.target_audience or "",
        differentiation=row.differentiation or "",
        risk=row.risk or "",
        risk_level=row.risk_level or "mittel",
        hypothesis_check=row.hypothesis_check,
        hypothesis_alignment=row.hypothesis_alignment,
        total_demand=row.total_demand or 0,
        apps_analyzed=row.apps_analyzed or 0,
        sources=[FeatureSignal(**s) for s in (row.sources or [])],
        concept_description=row.concept_description,
    )


@router.delete("/briefs/{brief_id}", status_code=204)
async def delete_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.execute(text("""
        DELETE FROM innovation_briefs WHERE id = :id AND user_id = :uid
    """), {"id": brief_id, "uid": current_user.id})
    await db.commit()


class ConceptResponse(BaseModel):
    concept_description: str


@router.post("/briefs/{brief_id}/generate-concept", response_model=ConceptResponse)
async def generate_concept_for_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (await db.execute(text("""
        SELECT * FROM innovation_briefs WHERE id = :id AND user_id = :uid
    """), {"id": brief_id, "uid": current_user.id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brief nicht gefunden.")

    # Reconstruct InnovationBrief from stored data to pass to prompt builder
    result = InnovationBrief(
        product_name=row.product_name,
        tagline=row.tagline or "",
        core_problem=row.core_problem or "",
        market_gap=row.market_gap or "",
        features=[ProductFeature(**f) for f in (row.features or [])],
        target_audience=row.target_audience or "",
        differentiation=row.differentiation or "",
        risk=row.risk or "",
        risk_level=row.risk_level or "mittel",
        total_demand=row.total_demand or 0,
        apps_analyzed=row.apps_analyzed or 0,
        sources=[FeatureSignal(**s) for s in (row.sources or [])],
    )
    meta = {
        "apps_analyzed": row.apps_analyzed or 0,
        "total_reviews": 0,
        "scope_desc": "dem analysierten Markt",
    }
    signals = [s for s in (row.sources or [])]

    concept_prompt = _build_concept_prompt(result, signals, meta)
    concept_description = _call_groq_text(concept_prompt)

    await db.execute(text("""
        UPDATE innovation_briefs SET concept_description = :cd WHERE id = :id AND user_id = :uid
    """), {"cd": concept_description, "id": brief_id, "uid": current_user.id})
    await db.commit()

    return ConceptResponse(concept_description=concept_description)


@router.post("/signals", response_model=List[SignalInfo])
async def get_available_signals(
    body: InnovationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all available signal clusters for the given filter — used by the frontend signal selector."""
    where, params = _build_where(
        body.scope, body.industry, body.datasource_ids, body.market, current_user.id
    )
    sql = text(f"""
        SELECT
            rs.feature,
            COUNT(*) AS total_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') AS fr_mentions,
            COUNT(*) FILTER (WHERE rs.signal_type = 'bug') AS bug_mentions,
            COUNT(DISTINCT rs.datasource_id) AS app_count,
            AVG(rs.severity) AS avg_severity
        FROM review_signals rs
        JOIN datasources ds ON rs.datasource_id = ds.id
        WHERE {where}
          AND rs.feature IS NOT NULL
          AND rs.signal_type IN ('feature_request', 'bug', 'ux', 'performance')
        GROUP BY rs.feature
        HAVING COUNT(*) >= 2
        ORDER BY
            COUNT(DISTINCT rs.datasource_id) DESC,
            COUNT(*) FILTER (WHERE rs.signal_type = 'feature_request') DESC,
            COUNT(*) DESC
    """)
    rows = (await db.execute(sql, params)).fetchall()
    return [
        SignalInfo(
            feature=r.feature,
            total_mentions=r.total_mentions,
            fr_mentions=r.fr_mentions,
            bug_mentions=r.bug_mentions,
            app_count=r.app_count,
            avg_severity=round(float(r.avg_severity or 0), 1),
        )
        for r in rows
    ]


@router.post("/generate", response_model=SavedBriefFull)
async def generate_innovation_brief(
    body: InnovationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    where, params = _build_where(
        body.scope, body.industry, body.datasource_ids, body.market, current_user.id
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

    # Step 1: signal exclusion — manual UI selection takes precedence, history-based as fallback
    if body.excluded_signals is not None:
        excluded_signals: List[str] = body.excluded_signals
        log.info("signal_exclusion_manual", excluded=excluded_signals)
    else:
        excluded_signals = await _get_excluded_signals(db, current_user.id)
        log.info("signal_exclusion_auto", excluded=excluded_signals)

    # Step 2: hypothesis-guided retrieval or standard frequency aggregation
    if hypothesis:
        hyp_embedding = _embed_text(hypothesis)
        if hyp_embedding:
            signals = await _aggregate_signals_hypothesis(
                db, where, params, hyp_embedding, exclude_features=excluded_signals or None
            )
            meta["retrieval_mode"] = "hypothesis"
            meta["retrieval_note"] = (
                f"Signale wurden durch semantische Suche aus {meta['total_reviews']:,} Reviews "
                f"anhand der Hypothese gefiltert — nicht nach allgemeiner Häufigkeit."
            )
            log.info("hypothesis_retrieval_active", signals_found=len(signals))
        else:
            signals = await _aggregate_signals(db, where, params, exclude_features=excluded_signals or None)
            log.warning("hypothesis_embed_unavailable_fallback_standard")
    else:
        signals = await _aggregate_signals(db, where, params, exclude_features=excluded_signals or None)
    _ = excluded_signals  # consumed above

    if not signals:
        raise HTTPException(
            status_code=422,
            detail="Nicht genug Daten für diese Filtereinstellung. Bitte mehr Apps hinzufügen oder den Scope erweitern."
        )

    # Step 3: compute signal graph — identify hubs vs edge nodes
    signal_graph = await _compute_signal_graph(db, signals, where, params)
    log.info("signal_graph", hubs=[h["feature"] for h in signal_graph.get("hub_signals", [])])

    # Step 4: fetch previous product names for concept differentiation
    prev_sql = text("""
        SELECT product_name FROM innovation_briefs
        WHERE user_id = :uid
        ORDER BY created_at DESC
        LIMIT 5
    """)
    prev_rows = (await db.execute(prev_sql, {"uid": current_user.id})).fetchall()
    previous_concepts = [r.product_name for r in prev_rows if r.product_name]

    prompt = _build_prompt(
        body.mode, signals, meta, hypothesis,
        previous_concepts=previous_concepts or None,
        signal_graph=signal_graph,
    )

    try:
        brief = _call_groq(prompt)
    except json.JSONDecodeError as exc:
        log.error("groq_json_parse_error", error=str(exc))
        raise HTTPException(status_code=500, detail="KI-Antwort konnte nicht verarbeitet werden. Bitte erneut versuchen.")
    except Exception as exc:
        log.error("groq_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Groq-Fehler: {str(exc)[:200]}")

    total_demand = sum(s["fr_mentions"] for s in signals[:10])

    result = InnovationBrief(
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
            for s in signals  # all signals, no cutoff
        ],
    )

    # Second Groq call: comprehensive long-form concept description
    try:
        concept_prompt = _build_concept_prompt(result, signals, meta)
        concept_description = _call_groq_text(concept_prompt)
    except Exception as exc:
        log.warning("concept_description_failed", error=str(exc))
        concept_description = None

    result.concept_description = concept_description

    saved_id = await _save_brief(db, current_user.id, body, result)

    return SavedBriefFull(
        id=saved_id,
        created_at="",
        mode=body.mode,
        scope=body.scope,
        industry=body.industry,
        user_hypothesis=body.user_hypothesis,
        **result.dict(),
    )


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    reply: str


def _build_system_prompt(row) -> str:
    features_text = "\n".join(
        f"  {i+1}. {f['name']} — {f.get('mentions', 0):,} Erwähnungen, Priorität: {f.get('priority', '?').upper()}"
        for i, f in enumerate(row.features or [])
    )
    sources_text = "\n".join(
        f"  [{i+1}] \"{s['feature']}\"\n"
        f"      {s['fr_mentions']} Feature-Wünsche · {s['total_mentions']} Gesamterwähnungen · {s['app_count']} App(s): {', '.join((s.get('affected_apps') or [])[:3])}\n"
        + (f"      Was Nutzer wörtlich sagen: \"{s['top_narrative'][:300]}\"\n" if s.get('top_narrative') else "")
        for i, s in enumerate(row.sources or [])
    )
    hypothesis_ctx = (
        f"\nNUTZER-HYPOTHESE DIE ZU DIESEM BRIEF GEFÜHRT HAT:\n\"{row.user_hypothesis}\"\n"
        if row.user_hypothesis else ""
    )
    return f"""Du bist ein erfahrener Produktstratege und Datenanaly bei MA Analytics. \
Du hast dieses Produktkonzept selbst generiert und kennst jeden Datenpunkt dahinter auswendig. \
Jetzt diskutierst du es gemeinsam mit dem Gründer weiter.

━━━ DAS PRODUKTKONZEPT ━━━
Name: {row.product_name}
Tagline: {row.tagline or '—'}
Modus: {'Konkurrenzprodukt (Schwächen der Konkurrenz angreifen)' if row.mode == 'competitor' else 'Innovationsprodukt (Marktlücke besetzen)'}
Kernproblem: {row.core_problem or '—'}
Marktlücke: {row.market_gap or '—'}
Zielgruppe: {row.target_audience or '—'}
USP: {row.differentiation or '—'}
Hauptrisiko ({(row.risk_level or 'mittel').upper()}): {row.risk or '—'}
{hypothesis_ctx}
━━━ KERN-FEATURES (aus echten Nutzerdaten destilliert) ━━━
{features_text}

━━━ VOLLSTÄNDIGE DATENGRUNDLAGE (echte Review-Signale) ━━━
{sources_text}
━━━ DEIN VERHALTEN ━━━

PFLICHT bei jeder Antwort:
→ Wenn du ein Feature oder Konzept erklärst: Zitiere IMMER die konkreten Zahlen aus den Signalen oben \
(z.B. "Das basiert auf [X] Feature-Wünschen in [Y] Apps — Nutzer sagten wörtlich: '...'").
→ Wenn du eine Empfehlung gibst: Begründe sie mit den Signalen, nicht mit allgemeinem Wissen.
→ Wenn der Nutzer etwas vorschlägt das den Daten widerspricht: Sag es direkt und zeige welche Zahl dagegen spricht.
→ Wenn der Nutzer nach "mehr Detail" fragt: Gib alle relevanten Signale aus der Liste oben aus.

VERBOTEN:
✗ Generische Antworten ohne Datenbezug ("Das könnte bedeuten...", "Typischerweise...")
✗ Erfundene Nutzerzitate oder Zahlen die nicht in den Signalen stehen
✗ Zustimmen wenn die Daten anderes sagen

FORMAT:
- Antworte auf Deutsch
- Keine Bullet-Listen außer der Nutzer fragt explizit danach
- Kurz wenn die Frage einfach ist, ausführlich wenn die Frage komplex ist
- Stell am Ende eine weiterführende Frage wenn es strategisch sinnvoll ist"""


@router.post("/briefs/{brief_id}/chat", response_model=ChatResponse)
async def chat_with_brief(
    brief_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (await db.execute(text("""
        SELECT * FROM innovation_briefs WHERE id = :id AND user_id = :uid
    """), {"id": brief_id, "uid": current_user.id})).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Brief nicht gefunden.")

    system_prompt = _build_system_prompt(row)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in (body.history or [])[-10:]:   # max 10 turns context
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": body.message})

    try:
        reply = _groq_call_robust(messages=messages, temperature=0.4, max_tokens=1200)
    except HTTPException:
        raise
    except Exception as exc:
        log.error("groq_chat_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"Groq-Fehler: {str(exc)[:200]}")

    return ChatResponse(reply=reply)
