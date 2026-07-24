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
) -> list[list[dict]]:
    """Run pyABSA on full review texts.

    Returns a list (one per review) of lists of aspect dicts:
      [{"aspect_term": str, "sentiment": str, "confidence": float, "span_text": str}]

    Falls back to keyword-based feature detection when ABSA finds no aspects.
    """
    extractor = _get_absa_extractor()
    texts = [r.content[:512] if r.content else "" for r in reviews]
    raw_results: list = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            results = extractor.predict(batch, print_result=False)
            if isinstance(results, dict):
                results = [results]
            raw_results.extend(results)
        except Exception as exc:
            log.warning("absa_batch_error", start=i, error=str(exc)[:200])
            raw_results.extend([None] * len(batch))

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


def synthesize_feature_narrative(
    feature: str,
    signal_rows: list[dict],
    groq_api_key: str,
    model: str = "llama-3.3-70b-versatile",
) -> Optional[str]:
    """Generate a concise narrative for one feature based on its aspects/signals."""
    if not signal_rows or not groq_api_key:
        return None

    bugs = [r for r in signal_rows if r["signal_type"] == "bug"]
    resolved = [r for r in signal_rows if r.get("is_resolved")]
    requests = [r for r in signal_rows if r["signal_type"] == "feature_request"]

    def fmt(rows, limit=8):
        return "\n".join(
            f'- [{r.get("version") or "?"}] {r["text"][:200]}'
            for r in rows[:limit]
        )

    section = f"Feature: {feature}\nTotal mentions: {len(signal_rows)}\n"
    if bugs:
        section += f"\nBug reports ({len(bugs)}):\n{fmt(bugs)}"
    if resolved:
        section += f"\nResolutions ({len(resolved)}):\n{fmt(resolved)}"
    if requests:
        section += f"\nFeature requests ({len(requests)}):\n{fmt(requests)}"

    prompt = (
        f"You analyze app review intelligence for the feature '{feature}'.\n\n"
        f"{section}\n\n"
        "Write a concise 2–3 sentence narrative covering:\n"
        "1. What users most commonly report about this feature\n"
        "2. Whether problems were fixed in later versions (cite versions if clear)\n"
        "3. Any open issues or requests\n\n"
        "Respond in German. Be specific and factual."
    )

    try:
        def _call(key):
            from groq import Groq
            return Groq(api_key=key).chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
        response = _rate_limited_call(_call, groq_api_key)
        return response.choices[0].message.content.strip()
    except Exception as exc:
        log.warning("feature_narrative_failed", feature=feature, error=str(exc)[:200])
        return None
