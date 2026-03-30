# ============================================================
#  Copie ce fichier en config.py et adapte à ton profil
#  cp config.example.py config.py
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# --- Ton profil développeur ---
PROFILE = {
    "title": "Développeur Full Stack React.js / Node.js",
    "skills": [
        "React.js", "Node.js", "JavaScript", "TypeScript",
        "Express.js", "REST API", "MongoDB", "PostgreSQL",
        "Git", "HTML", "CSS", "Docker"
    ],
    "experience_years": 0,          # ← tes années d'expérience
    "contract_types": ["CDI", "CDD", "Freelance", "Alternance"],
    "locations": [
        "Ta ville", "Télétravail", "Remote"
    ],
    "min_salary": 0,                # ← 0 pour ignorer
    "remote_ok": True,
    "excluded_keywords": [          # ← annonces à ignorer
        "15 ans d'expérience", "10 ans minimum"
    ],
}

# --- Mots-clés de recherche ---
SEARCH_KEYWORDS = [
    "développeur fullstack react node",
    "full stack javascript",
]
SEARCH_LOCATIONS = [               # ← une ou plusieurs villes
    "Ta ville",
    "Paris",
    "Télétravail",
]       # ← ta ville / région

# ============================================================
#  CLÉS & TOKENS — définies dans le fichier .env
# ============================================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

if not DISCORD_WEBHOOK_URL:
    raise ValueError("❌ DISCORD_WEBHOOK_URL manquant — crée un fichier .env (voir .env.example)")

# ============================================================
#  PARAMÈTRES DU BOT
# ============================================================

MIN_SCORE      = 6      # Score minimum sur 10 pour notifier
CHECK_INTERVAL = 120    # Minutes entre chaque cycle
SEEN_JOBS_FILE = "seen_jobs.json"