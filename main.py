"""
main.py — Orchestrateur du Job Hunter Bot
Lance le bot et fait tourner les cycles de recherche
"""

import json
import logging
import time
import os
import webbrowser
import pathlib
from datetime import datetime, timedelta

import schedule

from config import CHECK_INTERVAL, SEEN_JOBS_FILE, MIN_SCORE, PROFILE, SEARCH_KEYWORDS, SEARCH_LOCATIONS
from scrapers import fetch_all_jobs
from analyzer import analyze_job
from notifier import send_to_discord, send_summary
from dashboard import save_to_history, generate_dashboard

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("job_hunter.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ── Gestion des offres déjà vues ──────────────────────────────────────────────
_seen_dates: dict = {}

def load_seen() -> set:
    global _seen_dates
    if not os.path.exists(SEEN_JOBS_FILE):
        return set()
    with open(SEEN_JOBS_FILE, "r") as f:
        data = json.load(f)

    # Migration ancien format (liste) → nouveau format (dict avec dates)
    if isinstance(data, list):
        _seen_dates = {job_id: "2000-01-01" for job_id in data}
    else:
        _seen_dates = data

    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    valid   = {k: v for k, v in _seen_dates.items() if v >= cutoff}
    removed = len(_seen_dates) - len(valid)
    _seen_dates = valid

    if removed > 0:
        logger.info(f"[Mémoire] {removed} offres expirées supprimées (> 30 jours)")
    logger.debug(f"[Mémoire] {len(_seen_dates)} offres déjà vues chargées")
    return set(_seen_dates.keys())


def save_seen(seen: set):
    global _seen_dates
    today = datetime.now().strftime("%Y-%m-%d")
    for job_id in seen:
        if job_id not in _seen_dates:
            _seen_dates[job_id] = today
    _seen_dates = {k: v for k, v in _seen_dates.items() if k in seen}
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(_seen_dates, f, indent=2)
    logger.debug(f"[Mémoire] {len(_seen_dates)} offres sauvegardées dans {SEEN_JOBS_FILE}")


ANNONCES_FILE = "annonces.md"

def save_annonces(new_jobs: list):
    """Ajoute toutes les nouvelles offres dans annonces.md, peu importe le score."""
    if not new_jobs:
        return

    # Crée le fichier avec un header s'il n'existe pas encore
    if not os.path.exists(ANNONCES_FILE):
        with open(ANNONCES_FILE, "w", encoding="utf-8") as f:
            f.write("# 📋 Toutes les annonces trouvées\n\n")

    with open(ANNONCES_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## 🔍 Cycle du {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n\n")
        for job in new_jobs:
            f.write(f"- **{job['title']}** — {job['company']} ({job['location']})\n")
            f.write(f"  {job['url']}\n\n")

    logger.info(f"📄 {len(new_jobs)} annonces sauvegardées dans {ANNONCES_FILE}")


# ── Cycle principal ───────────────────────────────────────────────────────────
def run_cycle():
    start_time = time.time()

    logger.info("=" * 60)
    logger.info(f"🔍 NOUVEAU CYCLE — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 60)

    # ── Scraping ────────────────────────────────────────────
    logger.info("📡 Lancement du scraping sur tous les sites...")
    seen     = load_seen()
    all_jobs = fetch_all_jobs()

    new_jobs  = [j for j in all_jobs if j["id"] not in seen]
    skip_jobs = len(all_jobs) - len(new_jobs)

    logger.info(f"📊 Résultats scraping :")
    logger.info(f"   • Total trouvé   : {len(all_jobs)}")
    logger.info(f"   • Déjà vus       : {skip_jobs} (ignorés)")
    logger.info(f"   • Nouvelles      : {len(new_jobs)} à analyser")

    # ── Détail par source ───────────────────────────────────
    sources = {}
    for j in all_jobs:
        sources[j["source"]] = sources.get(j["source"], 0) + 1
    for src, count in sources.items():
        logger.info(f"   └─ {src:<15} : {count} offre(s)")

    if not new_jobs:
        elapsed = round(time.time() - start_time, 1)
        logger.info(f"💤 Aucune nouvelle offre — prochain cycle dans {CHECK_INTERVAL} min (durée : {elapsed}s)\n")
        return

    # ── Analyse ─────────────────────────────────────────────
    logger.info(f"\n🤖 Analyse des {len(new_jobs)} nouvelles offres...")
    logger.info("-" * 60)

    total_sent = 0
    sent_jobs  = []

    try:
        for i, job in enumerate(new_jobs, 1):
            seen.add(job["id"])

            logger.info(f"[{i}/{len(new_jobs)}] {job['source']:<15} | {job['title'][:50]}")
            logger.info(f"         Entreprise : {job['company']} | Lieu : {job['location']}")

            analysis = analyze_job(job)

            if analysis:
                score   = analysis["score"]
                verdict = analysis.get("verdict", "")
                pos     = ", ".join(analysis.get("points_positifs", []))
                neg     = ", ".join(analysis.get("points_negatifs", [])) or "aucun"

                logger.info(f"         ✅ Score : {score}/10 — {verdict}")
                logger.info(f"         👍 Positifs : {pos}")
                logger.info(f"         ⚠️  Négatifs : {neg}")

                sent = send_to_discord(job, analysis)
                if sent:
                    total_sent += 1
                    sent_jobs.append({**job, "analysis": analysis})
                    logger.info(f"         📨 Envoyé sur Discord ✓")
            else:
                logger.info(f"         ⛔ Score < {MIN_SCORE}/10 — ignoré")

            logger.info("")
    finally:
        save_seen(seen)

    # ── Bilan ────────────────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)
    save_annonces(new_jobs)

    all_entries = []
    for job in new_jobs:
        entry = {**job}
        matched = next((j for j in sent_jobs if j["id"] == job["id"]), None)
        if matched:
            entry["analysis"] = matched["analysis"]
        all_entries.append(entry)

    save_to_history(all_entries)
    generate_dashboard()
    logger.info("📊 Dashboard mis à jour → dashboard.html")

    logger.info("=" * 60)
    logger.info(f"✅ CYCLE TERMINÉ en {elapsed}s")
    logger.info(f"   • Analysées : {len(new_jobs)}")
    logger.info(f"   • Envoyées  : {total_sent}")
    logger.info(f"   • Ignorées  : {len(new_jobs) - total_sent} (score trop bas)")
    logger.info(f"   • Prochain cycle dans {CHECK_INTERVAL} min")
    logger.info("=" * 60 + "\n")

    send_summary(total_checked=len(new_jobs), total_sent=total_sent, sent_jobs=sent_jobs)



# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 JOB HUNTER BOT DÉMARRÉ")
    logger.info("=" * 60)
    logger.info(f"👤 Profil    : {PROFILE['title']}")
    logger.info(f"📍 Lieu      : {SEARCH_LOCATIONS}")
    logger.info(f"🔑 Mots-clés : {', '.join(SEARCH_KEYWORDS)}")
    logger.info(f"⭐ Score min : {MIN_SCORE}/10")
    logger.info("=" * 60 + "\n")

    run_cycle()

    dashboard_path = pathlib.Path("dashboard.html").resolve()
    webbrowser.open(dashboard_path.as_uri())
    logger.info("🌐 Dashboard ouvert dans le navigateur")

    logger.info("✅ Cycle terminé — arrêt du script.")
