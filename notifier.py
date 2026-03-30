"""
notifier.py — Envoie les offres sélectionnées sur Discord via un webhook
"""

import logging
import requests
from datetime import datetime
from config import DISCORD_WEBHOOK_URL, MIN_SCORE

logger = logging.getLogger(__name__)

# Couleurs des embeds Discord selon le score
def _color(score: int) -> int:
    if score >= 9: return 0x00FF7F   # vert flashy
    if score >= 7: return 0x3498DB   # bleu
    return 0xF39C12                  # orange

# Emojis selon la source
SOURCE_EMOJI = {
    "FranceTravail": "🇫🇷",
    "Indeed":        "🔵",
    "WTTJ":          "🌴",
    "HelloWork":     "🟠",
    "LinkedIn":      "💼",
}

# Emoji verdict
VERDICT_EMOJI = {
    "Excellent match": "🏆",
    "Bon match":       "✅",
    "Match partiel":   "⚠️",
    "Faible match":    "❌",
}


def send_to_discord(job: dict, analysis: dict) -> bool:
    """Envoie une offre enrichie vers Discord."""
    score   = analysis["score"]
    verdict = analysis.get("verdict", "")
    source_emoji = SOURCE_EMOJI.get(job["source"], "📌")
    verdict_emoji = VERDICT_EMOJI.get(verdict, "")

    positifs = "\n".join(f"✅ {p}" for p in analysis.get("points_positifs", []))
    negatifs = "\n".join(f"⚠️ {n}" for n in analysis.get("points_negatifs", []))

    embed = {
        "title":       f"{source_emoji} {job['title']}",
        "description": (
            f"{verdict_emoji} **{verdict}** — Score : **{score}/10**\n\n"
            f"_{analysis.get('resume', '')}_\n\n"
            f"🔗 **[Voir l'annonce]({job['url']})**\n`{job['url']}`"
        ),
        "color":       _color(score),
        "url":         job["url"],
        "fields": [
            {"name": "🏢 Entreprise",  "value": job["company"],  "inline": True},
            {"name": "📍 Lieu",        "value": job["location"],  "inline": True},
            {"name": "📄 Contrat",     "value": job["contract"] or "Non précisé", "inline": True},
            {"name": "💰 Salaire",     "value": job["salary"],    "inline": True},
            {"name": "📅 Publié le",   "value": job["published"], "inline": True},
            {"name": "🌐 Source",      "value": job["source"],    "inline": True},
        ],
        "footer": {"text": f"Job Hunter Bot • {datetime.now().strftime('%d/%m/%Y %H:%M')}"},
    }

    if positifs:
        embed["fields"].append({"name": "👍 Points positifs", "value": positifs, "inline": False})
    if negatifs:
        embed["fields"].append({"name": "👎 Points à noter", "value": negatifs, "inline": False})

    payload = {
        "username":   "🤖 Job Hunter",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/2920/2920349.png",
        "embeds":     [embed],
    }

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        logger.info(f"[Discord] Envoyé : {job['title']} ({score}/10)")
        return True
    except Exception as e:
        logger.error(f"[Discord] Erreur : {e}")
        return False


def send_summary(total_checked: int, total_sent: int, sent_jobs: list = None):
    """Message récapitulatif après chaque cycle avec la liste des offres trouvées."""

    if not sent_jobs:
        content = (
            f"📭 **Aucune nouvelle offre** — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"• Offres analysées : **{total_checked}** — aucune ne dépasse le score de {MIN_SCORE}/10\n"
            f"• Prochain cycle dans 2h"
        )
    else:
        lines = [
            f"📋 **{total_sent} offre(s) trouvée(s)** — {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        ]
        for job in sent_jobs:
            score   = job["analysis"]["score"]
            verdict = job["analysis"].get("verdict", "")
            lines.append(
                f"**{job['title']}** — {job['company']} ({job['location']})\n"
                f"Score : {score}/10 — {verdict}\n"
                f"🔗 {job['url']}\n"
            )
        content = "\n".join(lines)

    # Discord limite les messages à 2000 caractères
    if len(content) > 2000:
        content = content[:1950] + "\n_... (tronqué)_"

    payload = {"username": "🤖 Job Hunter", "content": content}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"[Discord] Erreur résumé : {e}")