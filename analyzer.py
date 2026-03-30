"""
analyzer.py — Envoie chaque offre à Claude pour obtenir un score et une analyse
"""

import json
import logging
import requests
from config import ANTHROPIC_API_KEY, PROFILE, MIN_SCORE

logger = logging.getLogger(__name__)

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
HEADERS = {
    "x-api-key":         ANTHROPIC_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type":      "application/json",
}

SYSTEM_PROMPT = """Tu es un assistant RH expert qui analyse la compatibilité
entre un profil développeur et une offre d'emploi.
Tu réponds UNIQUEMENT en JSON valide, sans texte avant ou après.
Format attendu :
{
  "score": <entier 0 à 10>,
  "verdict": "<Excellent match | Bon match | Match partiel | Faible match>",
  "points_positifs": ["...", "..."],
  "points_negatifs": ["...", "..."],
  "resume": "<1 phrase de synthèse>"
}"""


def _build_prompt(job: dict) -> str:
    profile_str = json.dumps(PROFILE, ensure_ascii=False, indent=2)
    return f"""
PROFIL DU CANDIDAT :
{profile_str}

OFFRE D'EMPLOI :
- Titre       : {job['title']}
- Entreprise  : {job['company']}
- Lieu        : {job['location']}
- Contrat     : {job['contract']}
- Salaire     : {job['salary']}
- Source      : {job['source']}
- Description : {job['description']}

Analyse la compatibilité et retourne le JSON demandé.
"""


def analyze_job(job: dict) -> dict | None:
    """
    Envoie l'offre à Claude et retourne le résultat d'analyse.
    Retourne None si le score est < MIN_SCORE ou si erreur.
    """
    try:
        payload = {
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 512,
            "system":     SYSTEM_PROMPT,
            "messages":   [{"role": "user", "content": _build_prompt(job)}],
        }
        r = requests.post(CLAUDE_URL, headers=HEADERS, json=payload, timeout=30)
        r.raise_for_status()

        raw = r.json()["content"][0]["text"].strip()

        # Nettoyage au cas où Claude ajoute des backticks
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        analysis = json.loads(raw)
        score = int(analysis.get("score", 0))

        if score < MIN_SCORE:
            logger.debug(f"Score trop bas ({score}/10) : {job['title']}")
            return None

        return {**analysis, "score": score}

    except json.JSONDecodeError as e:
        logger.error(f"[Claude] JSON invalide pour '{job['title']}' : {e}")
        return None
    except Exception as e:
        logger.error(f"[Claude] Erreur API pour '{job['title']}' : {e}")
        return None