"""ABSA-First Intelligence Pipeline.

Full review text → pyABSA (multilingual aspect extraction + sentiment)
→ feature normalization → rule-based signal classification
→ LLM narrative synthesis (Groq, ~20 calls total).

Eliminates context loss from sentence-level LLM extraction.
"""
from __future__ import annotations
import re
import time
import threading
import uuid
import structlog
from typing import Optional

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# pyABSA extractor — loaded once, ~25s warmup
# ---------------------------------------------------------------------------

_absa_extractor = None
_absa_lock = threading.Lock()


def _get_absa_extractor():
    global _absa_extractor
    if _absa_extractor is not None:
        return _absa_extractor
    with _absa_lock:
        if _absa_extractor is not None:
            return _absa_extractor
        import warnings
        warnings.filterwarnings("ignore")
        from pyabsa import AspectTermExtraction as ATEPC
        log.info("absa_model_loading", model="multilingual")
        _absa_extractor = ATEPC.AspectExtractor(
            "multilingual", auto_device=False, cal_perplexity=False
        )
        log.info("absa_model_ready")
        return _absa_extractor


# ---------------------------------------------------------------------------
# Feature taxonomy — aspect term → canonical feature
# ---------------------------------------------------------------------------

_FEATURE_KEYWORDS: dict[str, list[str]] = {
    "Bluetooth":       ["bluetooth", " bt ", "ble", "koppeln", "pairing", "kopplung"],
    "Navigation":      ["navigation", "navi", "karten", "karte", "maps", "route", "gps", "routing", "routenführung",
                        "standort", "ortung", "positionierung", "position"],
    "CarPlay":         ["carplay", "car play", "apple carplay"],
    "AndroidAuto":     ["android auto"],
    "Login":           ["login", "anmelden", "einloggen", "anmeldung", "passwort", "password", "pin",
                        "registrierung", "bmw id", "bmw-id"],
    "Updates":         ["update", "aktualisierung", "upgrade", "patch", "software"],
    "Performance":     ["absturz", "crash", "stürzt", "abstürzen", "einfriert", "eingefroren",
                        "friert", "hängt sich", "reagiert nicht"],
    "UI":              ["oberfläche", "benutzeroberfläche", "interface", "design", "layout", "optik",
                        "bedienung", "bedienen", "handhabung", "übersicht", "überblick",
                        "widgets", "widget", "darstellung", "menü"],
    "Connectivity":    ["internet", "wlan", "wifi", "mobilfunk", "mobile daten", "verbindung",
                        "alexa", "sprachsteuerung", "voice"],
    "Battery":         ["akku", "batterie", "ladezustand", "energieverbrauch", "stromverbrauch"],
    "Notifications":   ["benachrichtigung", "push", "notification", "mitteilung", "meldung"],
    "Music":           ["musik", "spotify", "radio", "audio", "sound", "lautsprecher", "media"],
    "Phone":           ["telefon", "anruf", "freisprechen", "telefonieren", "anrufen", "kontakte"],
    "Remote":          ["fernsteuerung", "remote", "klimaanlage", "vorklimatisierung", "vorheizen", "fernstart",
                        "standheizung", "klimatisierung", "lüftung", "fenster", "alarmanlage",
                        "verriegeln", "entriegeln", "türen öffnen", "türen schließen"],
    "Charging":        ["laden", "ladestation", "wallbox", "ladepunkt", "ladevorgang", "charge",
                        "ladehistorie", "ladeleistung", "ladesäule", "ladeverlauf"],
    "Settings":        ["einstellungen", "konfiguration", "einrichten", "konfigurieren"],
    "Account":         ["konto", "profil", "fahrzeug hinzufügen", "fahrzeug verbinden", "fahrzeug",
                        "registrieren"],
    "Vehicle Status":  ["tankinhalt", "tankfüllstand", "verbrauch", "reichweite", "reifendruck",
                        "kilometerstand", "tankuhr", "kraftstoff", "tank", "ölstand",
                        "reifenluftdruck", "ladehistorie der batterie"],
    "Digital Key":     ["digital key", "digitalkey", "schlüssel", "nfc-schlüssel", "car access"],
    "Support":         ["service", "support", "entwickler", "kundenservice", "kundendienst",
                        "hotline", "bmw support", "bmw service"],
}


def normalize_feature(aspect_term: str) -> str:
    """Map a raw ABSA aspect term to a canonical feature name."""
    term = aspect_term.lower()
    for feature, keywords in _FEATURE_KEYWORDS.items():
        if any(kw in term for kw in keywords):
            return feature
    # Direct match against feature names
    for feature in _FEATURE_KEYWORDS:
        if feature.lower() in term:
            return feature
    return "General"


def _keyword_features_from_text(text: str) -> list[str]:
    """Fallback: find feature names via keyword scan on full review text."""
    text_lower = text.lower()
    found = []
    for feature, keywords in _FEATURE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(feature)
    return found or ["General"]


# ---------------------------------------------------------------------------
# Signal classification — rule-based, zero Groq calls for extraction
# ---------------------------------------------------------------------------

_BUG_RE = re.compile(
    r"absturz|crash|stürzt|abstürzt|einfriert|eingefroren|friert ein|"
    r"fehler|funktioniert nicht|geht nicht|verbindet nicht|öffnet nicht|"
    r"startet nicht|hängt sich auf|reagiert nicht|spinnt|kaputt|defekt",
    re.IGNORECASE,
)
_PERF_RE = re.compile(
    r"langsam|träge|hängt|lädt.*lang|läuft.*langsam|sekunden|minuten|verzöger|buffert",
    re.IGNORECASE,
)
_UX_RE = re.compile(
    r"bedienung|unübersichtlich|verwirrend|schlecht.*design|umständlich|"
    r"nicht intuitiv|schwer zu bedienen|kompliziert|schlechte ui|schlechte oberfläche",
    re.IGNORECASE,
)
_REQ_RE = re.compile(
    r"sollte|wäre toll|fehlt|wünsche|vermisse|bitte.*hinzufügen|"
    r"könnte man|wäre schön|feature.*fehlt|funktion.*fehlt|man könnte",
    re.IGNORECASE,
)
_RESOLVED_RE = re.compile(
    r"nach.*update|nach dem update|jetzt klappt|klappt wieder|"
    r"funktioniert wieder|wurde behoben|ist behoben|endlich.*klappt|fixed|behoben",
    re.IGNORECASE,
)
_VERSION_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)*)\b")


def classify_signal_type(sentiment: str, review_text: str) -> str:
    if sentiment.lower() == "positive":
        return "resolution" if _RESOLVED_RE.search(review_text) else "general"
    if _BUG_RE.search(review_text):
        return "bug"
    if _PERF_RE.search(review_text):
        return "performance"
    if _UX_RE.search(review_text):
        return "ux"
    if _REQ_RE.search(review_text):
        return "feature_request"
    return "bug" if sentiment.lower() == "negative" else "general"


def derive_severity(sentiment: str, signal_type: str, score: Optional[float], confidence: float) -> Optional[int]:
    if sentiment.lower() != "negative":
        return None
    if score is not None:
        if score <= 1:
            return 5
        elif score <= 2:
            return 4
        else:
            return 3
    return 3 if confidence >= 0.85 else 2


def extract_version_hint(text: str) -> Optional[str]:
    m = _VERSION_RE.search(text)
    return m.group(1)[:50] if m else None


# ---------------------------------------------------------------------------
# Core ABSA extraction
# ---------------------------------------------------------------------------

def extract_aspects_from_reviews(
    reviews: list,
    batch_size: int = 32,
    on_progress: "callable | None" = None,
) -> list[list[dict]]:
    """Run pyABSA on full review texts.

    Returns a list (one per review) of lists of aspect dicts:
      [{"aspect_term": str, "sentiment": str, "confidence": float, "span_text": str}]

    Falls back to keyword-based feature detection when ABSA finds no aspects.
    """
    extractor = _get_absa_extractor()
    texts = [r.content[:512] if r.content else "" for r in reviews]
    raw_results: list = []

    total = len(texts)
    for i in range(0, total, batch_size):
        batch = texts[i : i + batch_size]
        try:
            results = extractor.predict(batch, print_result=False)
            if isinstance(results, dict):
                results = [results]
            raw_results.extend(results)
        except Exception as exc:
            log.warning("absa_batch_error", start=i, error=str(exc)[:200])
            raw_results.extend([None] * len(batch))
        if on_progress and total > 0:
            on_progress(min(int(100 * (i + len(batch)) / total), 99))

    per_review: list[list[dict]] = []

    for review, raw in zip(reviews, raw_results):
        if raw is None or not isinstance(raw, dict):
            aspects = _fallback_aspects(review)
            per_review.append(aspects)
            continue

        aspects_found = raw.get("aspect") or []
        sentiments_found = raw.get("sentiment") or []
        confidences = raw.get("confidence") or []
        sentence_text = raw.get("sentence", review.content or "")

        if not aspects_found:
            aspects = _fallback_aspects(review)
            per_review.append(aspects)
            continue

        aspects = []
        for j, (asp, sent) in enumerate(zip(aspects_found, sentiments_found)):
            conf = confidences[j] if j < len(confidences) else 0.5
            aspects.append({
                "aspect_term": asp,
                "sentiment": sent,
                "confidence": float(conf),
                "span_text": sentence_text[:400],
                "absa_source": "pyabsa",
            })
        per_review.append(aspects)

    return per_review


def _fallback_aspects(review) -> list[dict]:
    """Keyword fallback when pyABSA finds no aspects."""
    features = _keyword_features_from_text(review.content or "")
    score = review.score
    if score is not None:
        sentiment = "Positive" if score >= 4 else ("Negative" if score <= 2 else "Neutral")
    else:
        sentiment = "Neutral"
    return [
        {
            "aspect_term": None,
            "sentiment": sentiment,
            "confidence": 0.5,
            "span_text": (review.content or "")[:400],
            "absa_source": "keyword_fallback",
            "feature_override": feat,
        }
        for feat in features
    ]


# ---------------------------------------------------------------------------
# Groq key rotation (for narrative synthesis — only ~20 calls total)
# ---------------------------------------------------------------------------

_GROQ_MIN_INTERVAL = 60.0 / 15
_groq_key_pool: list[dict] = []
_groq_pool_lock = threading.Lock()


def _get_key_pool(groq_api_key: str) -> list[dict]:
    global _groq_key_pool
    with _groq_pool_lock:
        if _groq_key_pool:
            return _groq_key_pool
        from app.core.config import settings
        keys = [groq_api_key]
        for attr in ["GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_4", "GROQ_API_KEY_5"]:
            extra = getattr(settings, attr, None)
            if extra and extra not in keys:
                keys.append(extra)
        _groq_key_pool = [{"key": k, "last_call": 0.0, "lock": threading.Lock()} for k in keys]
        log.info("groq_key_pool_init", n_keys=len(_groq_key_pool))
        return _groq_key_pool


def _rate_limited_call(fn, groq_api_key: str):
    pool = _get_key_pool(groq_api_key)
    with _groq_pool_lock:
        entry = min(pool, key=lambda e: e["last_call"])
    with entry["lock"]:
        wait = _GROQ_MIN_INTERVAL - (time.time() - entry["last_call"])
        if wait > 0:
            time.sleep(wait)
        entry["last_call"] = time.time()
    return fn(entry["key"])


def _semver_key(v: str) -> tuple:
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts[:4]) + (0,) * (4 - len(parts[:4]))


def synthesize_feature_narrative(
    feature: str,
    signal_rows: list[dict],
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile",
) -> Optional[str]:
    """Generate a version-anchored status narrative for one feature."""
    if not signal_rows or not groq_api_key:
        return None

    # --- Build version timeline ---
    from collections import defaultdict

    version_data: dict = defaultdict(lambda: {
        "bugs": 0, "resolutions": 0, "feature_requests": 0,
        "total": 0, "has_reply": False, "date": None,
    })

    for r in signal_rows:
        v = (r.get("version") or "").strip() or "unknown"
        sig = r.get("signal_type", "")
        version_data[v]["total"] += 1
        if sig in ("bug", "performance", "ux"):
            version_data[v]["bugs"] += 1
        elif sig == "resolution":
            version_data[v]["resolutions"] += 1
        elif sig == "feature_request":
            version_data[v]["feature_requests"] += 1
        if r.get("has_reply"):
            version_data[v]["has_reply"] = True
        date = r.get("reviewed_at")
        if date and not version_data[v]["date"]:
            version_data[v]["date"] = str(date)[:10]

    known_versions = sorted(
        [v for v in version_data if v != "unknown"],
        key=_semver_key,
    )

    latest_version = known_versions[-1] if known_versions else None
    bug_versions = [v for v in known_versions if version_data[v]["bugs"] > 0]
    first_bug_version = bug_versions[0] if bug_versions else None
    last_bug_version = bug_versions[-1] if bug_versions else None
    peak_bug_version = (
        max(bug_versions, key=lambda v: version_data[v]["bugs"]) if bug_versions else None
    )

    # Resolution evidence: drop in bugs or dev-reply after last bug version
    resolution_evidence: list[str] = []
    if last_bug_version and latest_version and last_bug_version != latest_version:
        last_idx = known_versions.index(last_bug_version)
        versions_after = known_versions[last_idx + 1:]
        if any(version_data[v]["resolutions"] > 0 for v in versions_after):
            resolution_evidence.append("Positive Nutzermeldungen nach letztem Bug")
        if any(version_data[v]["has_reply"] for v in versions_after):
            resolution_evidence.append("Entwickler-Reply nach letztem Bug vorhanden")
        gaps_without_bug = len(versions_after)
        if gaps_without_bug >= 2:
            resolution_evidence.append(
                f"Keine Bug-Meldungen in {gaps_without_bug} neueren Versionen"
            )

    # Timeline string — cap at 15 most relevant versions
    display_versions = known_versions[-15:] if len(known_versions) > 15 else known_versions
    timeline_lines = []
    for v in display_versions:
        d = version_data[v]
        parts = [f"v{v}"]
        if d["date"]:
            parts.append(f"({d['date'][:7]})")
        counts = []
        if d["bugs"]:
            counts.append(f"{d['bugs']} Bugs")
        if d["resolutions"]:
            counts.append(f"{d['resolutions']} Behebungen")
        if d["feature_requests"]:
            counts.append(f"{d['feature_requests']} Wünsche")
        if d["has_reply"]:
            counts.append("Dev-Reply ✓")
        if counts:
            parts.append(", ".join(counts))
        timeline_lines.append(" | ".join(parts))

    # Mixed examples: bugs + resolutions + feature requests for Gesamtbild context
    bug_rows = [r for r in signal_rows if r.get("signal_type") in ("bug", "performance", "ux")]
    res_rows = [r for r in signal_rows if r.get("signal_type") == "resolution"]
    req_rows = [r for r in signal_rows if r.get("signal_type") == "feature_request"]

    def _fmt_examples(rows, limit=3):
        return "\n".join(f'- {r["text"][:140]}' for r in rows[:limit])

    signal_summary = (
        f"Gesamt: {len(signal_rows)} Signale | "
        f"Bugs/Perf/UX: {len(bug_rows)} | "
        f"Behebungen: {len(res_rows)} | "
        f"Feature-Wünsche: {len(req_rows)}"
    )

    examples_block = ""
    if bug_rows:
        examples_block += f"Häufige Beschwerden:\n{_fmt_examples(bug_rows)}\n"
    if res_rows:
        examples_block += f"\nPositive Rückmeldungen:\n{_fmt_examples(res_rows)}\n"
    if req_rows:
        examples_block += f"\nFeature-Wünsche:\n{_fmt_examples(req_rows)}\n"

    context = f"""Feature: {feature}
{signal_summary}
Aktuellste Version im Datensatz: {latest_version or "unbekannt"}
Erste Bug-Meldung: {f"v{first_bug_version}" if first_bug_version else "keine"}
Letzte Bug-Meldung: {f"v{last_bug_version}" if last_bug_version else "keine"}
Peak der Bug-Meldungen: {f"v{peak_bug_version} ({version_data[peak_bug_version]['bugs']} Bugs)" if peak_bug_version else "—"}
Behebungshinweise: {"; ".join(resolution_evidence) if resolution_evidence else "keine"}

Versions-Timeline:
{chr(10).join(timeline_lines) if timeline_lines else "(keine Versionsdaten)"}

{examples_block.strip()}"""

    prompt = (
        f"Du analysierst das Feature '{feature}' einer mobilen App anhand von Nutzerbewertungen.\n\n"
        f"{context}\n\n"
        "Schreibe genau 3 Absätze — KEIN Titel, KEINE Nummerierung, nur Fließtext:\n\n"
        "Absatz 1 — Gesamtbild: Fasse zusammen was Nutzer über dieses Feature berichten. "
        "Was sind die häufigsten Beschwerden? Was funktioniert gut? Wie ist die allgemeine Stimmung? "
        "Keine Versionsnummern in diesem Absatz.\n\n"
        "Absatz 2 — Versionshistorie: In welchen Versionen trat das Problem auf? "
        "Wann zuletzt gemeldet ('zuletzt in vX.Y.Z', nicht 'noch immer in')? Behebungshinweise?\n\n"
        "Absatz 3 — Status: Genau ein Satz. Beginnt mit 'Status: Offen', 'Status: Wahrscheinlich behoben' "
        "oder 'Status: Keine ausreichenden Daten' — gefolgt von einer kurzen Begründung.\n\n"
        "Regeln: Nur Deutsch. Keine Markdown-Symbole. Versionsnummern nur in Absatz 2 und 3."
    )

    try:
        def _call(key):
            from groq import Groq
            return Groq(api_key=key).chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
            )
        response = _rate_limited_call(_call, groq_api_key)
        return response.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("feature_narrative_failed", feature=feature, error=str(exc)[:200])
        return None
