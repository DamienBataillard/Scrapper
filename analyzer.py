"""
analyzer.py — Analyse des offres par filtrage mots-clés (sans API IA)
"""

import logging
from config import PROFILE, MIN_SCORE

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# Mots-clés positifs — présence = points bonus
# ─────────────────────────────────────────────────────────────
KEYWORDS_POSITIVE = {
    # Stack principale (poids fort)
    "react":        3,
    "javascript":   2,
    "typescript":   2,
    "mysql":        3,
    "git":          2,
    # Stack secondaire
    "express":      2,
    "next.js":      2,
    "mongodb":      1,
    "postgresql":   1,
    "rest api":     1,
    "api rest":     1,
    "docker":       1,
    # Type de poste
    "full stack":   3,
    "frontend":     3,
    "backend":      3,
    "développeur":  3,
    "developpeur":  3,
    "engineer":     3,
    # Remote / conditions
    "télétravail":  1,
    "remote":       1,
    "hybride":      1,
}

KEYWORDS_NEGATIVE = {
    "10 ans":           4,
    "15 ans":           5,
    "php":              2,
    ".net":             2,
    "c#":               2,
    "ruby":             2,
    "lead technique":   2,
    "architecte":       2,
    "devops":           1,
}

# Variantes groupées — un seul point accordé par groupe
KEYWORD_GROUPS = [
    (["react", "react.js", "reactjs"], 3),
    (["node", "node.js", "nodejs"], 3),
    (["fullstack", "full stack", "full-stack"], 3),
    (["teletravail", "télétravail"], 1),
]

# Mots-clés négatifs avec regex pour éviter les faux positifs
import re
KEYWORDS_NEGATIVE_REGEX = {
    r"\bjava\b":    2,
    r"\bstage\b(?!.*étape)":   3,
}


def analyze_job(job: dict) -> dict | None:
    text = (
        job.get("title", "") + " " +
        job.get("description", "") + " " +
        job.get("company", "")
    ).lower()

        # Rejet immédiat si un mot-clé exclu est présent
    for excl in PROFILE.get("excluded_keywords", []):
        if excl.lower() in text:
            logger.debug(f"Offre rejetée (mot-clé exclu : '{excl}') : {job['title']}")
            return None

    raw_score    = 0
    max_possible = sum(v for v in KEYWORDS_POSITIVE.values() if v >= 2)
    # Ajouter les groupes au max_possible
    max_possible += sum(w for _, w in KEYWORD_GROUPS if w >= 2)

    points_positifs = []
    points_negatifs = []

    # Mots-clés simples
    for kw, weight in KEYWORDS_POSITIVE.items():
        if kw in text:
            raw_score += weight
            if weight >= 2:
                points_positifs.append(f"{kw.capitalize()} mentionné")

    # Groupes de variantes — un seul point par groupe
    for variants, weight in KEYWORD_GROUPS:
        if any(v in text for v in variants):
            raw_score += weight
            if weight >= 2:
                points_positifs.append(f"{variants[0].capitalize()} mentionné")

    # Mots-clés négatifs simples
    for kw, penalty in KEYWORDS_NEGATIVE.items():
        if kw in text:
            raw_score -= penalty
            points_negatifs.append(f"{kw.strip().capitalize()} détecté")

    # Mots-clés négatifs regex
    for pattern, penalty in KEYWORDS_NEGATIVE_REGEX.items():
        if re.search(pattern, text):
            raw_score -= penalty
            points_negatifs.append(f"{pattern.strip('\\b').capitalize()} détecté")

    # Bonus contrat / lieu
    location_text = job.get("location", "").lower()
    for loc in PROFILE.get("locations", []):
        if loc.lower() in location_text:
            raw_score += 1
            break

    contract = job.get("contract", "").upper()
    for ct in PROFILE.get("contract_types", []):
        if ct.upper() in contract:
            raw_score += 1
            break

    # Normalisation sur 10
    score = round(max(0, min(10, (raw_score / max(max_possible, 1)) * 10)))

    if score < MIN_SCORE:
        logger.debug(f"Score trop bas ({score}/10) : {job['title']}")
        return None

    if score >= 9:   verdict = "Excellent match"
    elif score >= 7: verdict = "Bon match"
    elif score >= 5: verdict = "Match partiel"
    else:            verdict = "Faible match"

    resume = (
        f"Score calculé sur {len(points_positifs)} technologie(s) clé(s) détectée(s)"
        + (f", {len(points_negatifs)} point(s) négatif(s)" if points_negatifs else "")
        + "."
    )

    logger.info(f"   ➜ Score {score}/10 — {verdict}")
    return {
        "score":           score,
        "verdict":         verdict,
        "points_positifs": points_positifs or ["Profil potentiellement compatible"],
        "points_negatifs": points_negatifs,
        "resume":          resume,
    }
