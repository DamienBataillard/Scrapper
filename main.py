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

from config import CHECK_INTERVAL, SEEN_JOBS_FILE, MIN_SCORE
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
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)


# ── Cycle principal ───────────────────────────────────────────────────────────
def run_cycle():
    logger.info("=" * 60)
    logger.info(f"🔍 Nouveau cycle — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    logger.info("=" * 60)

    seen       = load_seen()
    all_jobs   = fetch_all_jobs()
    new_jobs   = [j for j in all_jobs if j["id"] not in seen]

    logger.info(f"📬 {len(new_jobs)} nouvelles offres à analyser")

    total_sent = 0

    for job in new_jobs:
        seen.add(job["id"])   # marquer comme vu même si score faible

        logger.info(f"🤖 Analyse : {job['title']} [{job['source']}]")
        analysis = analyze_job(job)

        if analysis:
            logger.info(
                f"   ➜ Score {analysis['score']}/10 — {analysis.get('verdict')} — envoi Discord"
            )
            sent = send_to_discord(job, analysis)
            if sent:
                total_sent += 1
        else:
            logger.info(f"   ➜ Score < {MIN_SCORE}/10, ignoré")

        time.sleep(1.5)   # pause pour ne pas spammer l'API Claude

    save_seen(seen)
    send_summary(total_checked=len(new_jobs), total_sent=total_sent)
    logger.info(f"✅ Cycle terminé — {total_sent} offres envoyées sur Discord\n")


# ── Lancement ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("🚀 Job Hunter Bot démarré !")
    logger.info(f"⏱  Intervalle : toutes les {CHECK_INTERVAL} minutes")

    # Premier cycle immédiat
    run_cycle()

    # Puis cycles périodiques
    schedule.every(CHECK_INTERVAL).minutes.do(run_cycle)

    while True:
        schedule.run_pending()
        time.sleep(30)