"""
main.py — Orchestrateur du Job Hunter Bot
Lance le bot et fait tourner les cycles de recherche
"""

import json
import logging
import time
import os
from datetime import datetime

import schedule

from config import CHECK_INTERVAL, SEEN_JOBS_FILE, MIN_SCORE, PROFILE, SEARCH_KEYWORDS, SEARCH_LOCATIONS
from scrapers import fetch_all_jobs
from analyzer import analyze_job
from notifier import send_to_discord, send_summary

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
def load_seen() -> set:
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            data = json.load(f)
            logger.debug(f"[Mémoire] {len(data)} offres déjà vues chargées")
            return set(data)
    logger.debug("[Mémoire] Aucun fichier seen_jobs.json, démarrage à zéro")
    return set()


def save_seen(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)
    logger.debug(f"[Mémoire] {len(seen)} offres sauvegardées dans {SEEN_JOBS_FILE}")


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
        time.sleep(1.5)

    # ── Bilan ────────────────────────────────────────────────
    elapsed = round(time.time() - start_time, 1)
    save_seen(seen)
    save_annonces(new_jobs)

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
    logger.info(f"⏱  Intervalle: toutes les {CHECK_INTERVAL} min")
    logger.info("=" * 60 + "\n")

    run_cycle()

    schedule.every(CHECK_INTERVAL).minutes.do(run_cycle)

    while True:
        schedule.run_pending()
        time.sleep(30)