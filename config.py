# ============================================================
#  CONFIG — Adapte cette section à ton profil
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()  # charge automatiquement le fichier .env

# --- Ton profil développeur ---
PROFILE = {
    "title": "Développeur Full Stack React.js / Node.js",
    "skills": [
        "React.js", "Node.js", "JavaScript", "TypeScript",
        "Express.js", "REST API", "MongoDB", "PostgreSQL",
        "Git", "HTML", "CSS", "Docker"
    ],
    "experience_years": 3,
    "contract_types": ["CDI", "CDD", "Freelance", "Alternance"],
    "locations": [
        "Amiens", "Hauts-de-France", "Télétravail",
        "Remote", "Paris", "Lille"
    ],
    "min_salary": 35000,
    "remote_ok": True,
    "excluded_keywords": [
        "15 ans d'expérience", "10 ans minimum", "Architecte senior"
    ],
}

# --- Mots-clés de recherche pour chaque site ---
SEARCH_KEYWORDS = [
    "développeur fullstack react node",
    "full stack javascript",
    "react node.js développeur",
]
SEARCH_LOCATION = "Ile de France"

# ============================================================
#  CLÉS & TOKENS — définies dans le fichier .env
# ============================================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

if not DISCORD_WEBHOOK_URL:
    raise ValueError("❌ DISCORD_WEBHOOK_URL manquant — crée un fichier .env (voir .env.example)")

# ============================================================
#  PARAMÈTRES DU BOT
# ============================================================

MIN_SCORE      = 6
CHECK_INTERVAL = 120
SEEN_JOBS_FILE = "seen_jobs.json"