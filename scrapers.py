"""
scrapers.py — France Travail + LinkedIn uniquement
"""

import requests
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from config import SEARCH_KEYWORDS, SEARCH_LOCATIONS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _log_request(source, url, status, cards, keyword="", location=""):
    kw_str  = f" | mot-clé : '{keyword}'"   if keyword  else ""
    loc_str = f" | lieu : '{location}'"      if location else ""
    if status == 200 and cards > 0:
        logger.info(f"   [{source}] ✅ HTTP {status} — {cards} cards trouvées{kw_str}{loc_str}")
    elif status == 200 and cards == 0:
        logger.warning(f"   [{source}] ⚠️  HTTP {status} — 0 cards trouvées{kw_str}{loc_str}")
    elif status in (403, 429):
        logger.warning(f"   [{source}] 🚫 HTTP {status} — Accès bloqué{kw_str}{loc_str}")
    else:
        logger.warning(f"   [{source}] ❌ HTTP {status}{kw_str}{loc_str}")


def make_job(source, job_id, title, company, location, contract,
             description, url, salary="Non précisé", published=""):
    return {
        "id":          f"{source}_{job_id}",
        "source":      source,
        "title":       title,
        "company":     company,
        "location":    location,
        "contract":    contract,
        "salary":      salary,
        "description": description[:3000],
        "url":         url,
        "published":   published or datetime.now().strftime("%d/%m/%Y"),
    }


def fetch_france_travail():
    jobs = []
    try:
        for location in SEARCH_LOCATIONS:
            for keyword in SEARCH_KEYWORDS[:2]:
                url = "https://candidat.francetravail.fr/offres/recherche"
                params = {"motsCles": keyword, "ville": location, "rayonRecherche": 50}
                r = requests.get(url, params=params, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.find_all("li", class_="result")
                _log_request("FranceTravail", r.url, r.status_code, len(cards), keyword, location)
                for card in cards:
                    try:
                        title_el   = card.find("h2") or card.find("h3")
                        title      = title_el.get_text(strip=True) if title_el else ""
                        company_el = card.find(class_="subTitle") or card.find(class_="entreprise")
                        company    = company_el.get_text(strip=True) if company_el else "?"
                        loc_el     = card.find(class_="location") or card.find(attrs={"data-original-title": True})
                        job_loc    = loc_el.get_text(strip=True) if loc_el else location
                        link_el    = card.find("a", href=True)
                        href       = link_el["href"] if link_el else ""
                        job_id     = href.split("/")[-1].split("?")[0]
                        job_url    = f"https://candidat.francetravail.fr{href}" if href.startswith("/") else href
                        if title:
                            jobs.append(make_job("FranceTravail", job_id, title, company,
                                                 job_loc, "", title, job_url))
                    except Exception:
                        continue
                time.sleep(2)
    except Exception as e:
        logger.error(f"[FranceTravail] Erreur : {e}")
    logger.info(f"[FranceTravail] {len(jobs)} offres trouvées")
    return jobs


def fetch_linkedin():
    jobs = []
    try:
        for location in SEARCH_LOCATIONS:
            for keyword in SEARCH_KEYWORDS[:1]:
                url = "https://www.linkedin.com/jobs/search/"
                params = {"keywords": keyword, "location": location, "sortBy": "DD", "f_TPR": "r604800"}
                r = requests.get(url, params=params, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                cards = soup.find_all("div", class_="base-card")
                _log_request("LinkedIn", r.url, r.status_code, len(cards), keyword, location)
                for card in cards:
                    try:
                        title_el = card.find("h3", class_="base-search-card__title")
                        title    = title_el.get_text(strip=True) if title_el else ""
                        co_el    = card.find("h4", class_="base-search-card__subtitle")
                        company  = co_el.get_text(strip=True) if co_el else "?"
                        loc_el   = card.find("span", class_="job-search-card__location")
                        job_loc  = loc_el.get_text(strip=True) if loc_el else location
                        link_el  = card.find("a", href=True)
                        job_url  = link_el["href"].split("?")[0] if link_el else ""
                        job_id   = job_url.split("-")[-1] if job_url else ""
                        if title:
                            jobs.append(make_job("LinkedIn", job_id, title, company,
                                                 job_loc, "", title, job_url))
                    except Exception:
                        continue
                time.sleep(3)
    except Exception as e:
        logger.warning(f"[LinkedIn] {e}")
    logger.info(f"[LinkedIn] {len(jobs)} offres trouvées")
    return jobs


def fetch_all_jobs():
    all_jobs = []
    for name, fn in [("FranceTravail", fetch_france_travail), ("LinkedIn", fetch_linkedin)]:
        try:
            all_jobs.extend(fn())
        except Exception as e:
            logger.error(f"[{name}] Échec total : {e}")
        time.sleep(1)

    seen, unique = set(), []
    for j in all_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    logger.info(f"Total : {len(unique)} offres uniques")
    return unique