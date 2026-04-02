"""
scrapers.py — France Travail + LinkedIn uniquement
"""

import requests
import time
import logging
import re
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

WTTJ_APP_ID  = "CSEKHVMS53"
WTTJ_API_KEY = "4bd8f6215d0cc52b26430765769e65a0"
WTTJ_INDEX   = "wttj_jobs_production_fr"

_coords_cache: dict = {}

def get_coords(city: str):
    if city in _coords_cache:
        return _coords_cache[city]
    try:
        r = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={"q": city, "type": "municipality", "limit": 1},
            timeout=10,
        )
        features = r.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"]
            _coords_cache[city] = (lat, lon)
            return lat, lon
    except Exception:
        pass
    _coords_cache[city] = None
    return None


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


def fetch_job_description(url: str) -> str:
    """Récupère la description complète d'une offre France Travail."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        # Le contenu de l'offre est dans une div avec cette classe
        desc_el = (
            soup.find("div", class_="description-offre")
            or soup.find("div", {"data-id": "description"})
            or soup.find("div", class_="modal-body")
        )
        return desc_el.get_text(separator=" ", strip=True)[:3000] if desc_el else ""
    except Exception:
        return ""

def fetch_linkedin_description(url: str) -> str:
    """Récupère la description complète d'une offre LinkedIn."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        desc_el = (
            soup.find("div", class_="description__text")
            or soup.find("div", class_="show-more-less-html__markup")
            or soup.find("section", class_="description")
        )
        return desc_el.get_text(separator=" ", strip=True)[:3000] if desc_el else ""
    except Exception:
        return ""


def fetch_france_travail():
    jobs = []
    try:
        for location in SEARCH_LOCATIONS:
            for keyword in SEARCH_KEYWORDS:
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

                        if not title:
                            continue

                        # ← Nouveau : récupération de la description complète
                        description = fetch_job_description(job_url) if job_url else ""

                        jobs.append(make_job("FranceTravail", job_id, title, company,
                                             job_loc, "", description, job_url))
                        time.sleep(1)  # ← pause entre chaque page d'offre
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
                            # après
                            description = fetch_linkedin_description(job_url) if job_url else ""
                            jobs.append(make_job("LinkedIn", job_id, title, company,
                                                job_loc, "", description, job_url))
                            time.sleep(1)
                    except Exception:
                        continue
                time.sleep(3)
    except Exception as e:
        logger.warning(f"[LinkedIn] {e}")
    logger.info(f"[LinkedIn] {len(jobs)} offres trouvées")
    return jobs

def fetch_wttj():
    jobs = []
    try:
        url = f"https://{WTTJ_APP_ID}-dsn.algolia.net/1/indexes/{WTTJ_INDEX}/query"
        headers = {
            "X-Algolia-Application-Id": WTTJ_APP_ID,
            "X-Algolia-API-Key":        WTTJ_API_KEY,
            "Content-Type":             "application/json",
            "Referer":                  "https://www.welcometothejungle.com/",
            "Origin":                   "https://www.welcometothejungle.com",
        }

        for location in SEARCH_LOCATIONS:
            coords = get_coords(location)

            for keyword in SEARCH_KEYWORDS:
                payload = {
                    "query":       keyword,
                    "hitsPerPage": 50,
                    "filters":     '("offices.country_code":"FR")',
                    "attributesToRetrieve": [
                        "name", "organization", "office", "offices",
                        "contract_type", "salary", "description",
                        "slug", "published_at", "remote",
                    ],
                }

                if coords:
                    payload["aroundLatLng"]    = f"{coords[0]},{coords[1]}"
                    payload["aroundRadius"]    = 50000   # 50 km
                    payload["aroundPrecision"] = 10000

                r = requests.post(url, headers=headers, json=payload, timeout=15)
                hits = r.json().get("hits", [])
                _log_request("WTTJ", url, r.status_code, len(hits), keyword, location)

                for hit in hits:
                    try:
                        offices     = hit.get("offices") or [hit.get("office") or {}]
                        office      = offices[0] if offices else {}
                        org         = hit.get("organization") or {}
                        slug        = hit.get("slug", "")
                        job_url     = f"https://www.welcometothejungle.com/fr/companies/{org.get('slug', '')}/jobs/{slug}" if slug else ""
                        job_loc     = office.get("city") or office.get("name") or location
                        salary_data = hit.get("salary") or {}
                        salary      = (
                            f"{salary_data.get('min', '')}–{salary_data.get('max', '')} €"
                            if salary_data.get("min") else "Non précisé"
                        )
                        description = hit.get("description") or hit.get("name", "")

                        jobs.append(make_job(
                            source      = "WTTJ",
                            job_id      = slug,
                            title       = hit.get("name", ""),
                            company     = org.get("name", "?"),
                            location    = job_loc,
                            contract    = hit.get("contract_type", ""),
                            description = description,
                            url         = job_url,
                            salary      = salary,
                            published   = (hit.get("published_at") or "")[:10],
                        ))
                    except Exception:
                        continue
                time.sleep(1)

    except Exception as e:
        logger.error(f"[WTTJ] Erreur : {e}")

    logger.info(f"[WTTJ] {len(jobs)} offres trouvées")
    return jobs

def _normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s.lower().strip())

def fetch_all_jobs():
    all_jobs = []
    for name, fn in [
        ("FranceTravail", fetch_france_travail),
        ("LinkedIn",      fetch_linkedin),
        ("WTTJ",          fetch_wttj),
    ]:
        try:
            all_jobs.extend(fn())
        except Exception as e:
            logger.error(f"[{name}] Échec total : {e}")
        time.sleep(1)

    seen_ids, seen_titles, unique = set(), set(), []
    for j in all_jobs:
        if j["id"] not in seen_ids:
            title_key = f"{_normalize(j['title'])}_{_normalize(j['company'])}"
            if title_key not in seen_titles:
                seen_ids.add(j["id"])
                seen_titles.add(title_key)
                unique.append(j)

    logger.info(f"Total : {len(unique)} offres uniques")
    return unique



