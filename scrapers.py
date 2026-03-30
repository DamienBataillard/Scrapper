"""
scrapers.py — Récupère les offres d'emploi depuis plusieurs sources
"""

import requests
import time
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from config import SEARCH_KEYWORDS, SEARCH_LOCATION

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


# ─────────────────────────────────────────────
# Modèle d'une offre (dict normalisé)
# ─────────────────────────────────────────────
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
        "description": description[:3000],   # limite pour Claude
        "url":         url,
        "published":   published or datetime.now().strftime("%d/%m/%Y"),
    }


# ─────────────────────────────────────────────
# 1. FRANCE TRAVAIL (scraping)
# ─────────────────────────────────────────────
def fetch_france_travail():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://candidat.francetravail.fr/offres/recherche"
            params = {
                "motsCles":  keyword,
                "ville":     SEARCH_LOCATION,
                "rayonRecherche": 50,
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.find_all("li", class_="result")
            for card in cards:
                try:
                    title_el   = card.find("h2") or card.find("h3")
                    title      = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find(class_="subTitle") or card.find(class_="entreprise")
                    company    = company_el.get_text(strip=True) if company_el else "?"
                    loc_el     = card.find(class_="location") or card.find(attrs={"data-original-title": True})
                    location   = loc_el.get_text(strip=True) if loc_el else SEARCH_LOCATION
                    link_el    = card.find("a", href=True)
                    href       = link_el["href"] if link_el else ""
                    job_id     = href.split("/")[-1].split("?")[0]
                    job_url    = f"https://candidat.francetravail.fr{href}" if href.startswith("/") else href

                    if title:
                        jobs.append(make_job(
                            source="FranceTravail", job_id=job_id, title=title,
                            company=company, location=location, contract="",
                            description=title, url=job_url,
                        ))
                except Exception:
                    continue
            time.sleep(2)

    except Exception as e:
        logger.error(f"[FranceTravail] Erreur : {e}")

    logger.info(f"[FranceTravail] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 2. INDEED (scraping)
# ─────────────────────────────────────────────
def fetch_indeed():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://fr.indeed.com/jobs"
            params = {
                "q": keyword,
                "l": SEARCH_LOCATION,
                "sort": "date",
                "fromage": "7",     # offres des 7 derniers jours
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.find_all("div", class_="job_seen_beacon")
            for card in cards:
                try:
                    title_el  = card.find("h2", class_="jobTitle")
                    title     = title_el.get_text(strip=True) if title_el else ""
                    company_el = card.find("span", {"data-testid": "company-name"})
                    company   = company_el.get_text(strip=True) if company_el else "?"
                    loc_el    = card.find("div", {"data-testid": "text-location"})
                    location  = loc_el.get_text(strip=True) if loc_el else ""
                    salary_el = card.find("div", {"data-testid": "attribute_snippet_testid"})
                    salary    = salary_el.get_text(strip=True) if salary_el else "Non précisé"
                    link_el   = card.find("a", href=True)
                    job_id    = link_el["href"].split("jk=")[-1][:16] if link_el else ""
                    job_url   = f"https://fr.indeed.com{link_el['href']}" if link_el else ""

                    # Description courte visible dans la card
                    desc_el   = card.find("div", class_="job-snippet")
                    desc      = desc_el.get_text(strip=True) if desc_el else title

                    if title and job_id:
                        jobs.append(make_job(
                            source="Indeed", job_id=job_id, title=title,
                            company=company, location=location,
                            contract="", salary=salary,
                            description=desc, url=job_url,
                        ))
                except Exception:
                    continue

            time.sleep(2)

    except Exception as e:
        logger.error(f"[Indeed] Erreur : {e}")

    logger.info(f"[Indeed] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 3. WELCOME TO THE JUNGLE (API publique)
# ─────────────────────────────────────────────
def fetch_wttj():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://api.welcometothejungle.com/api/v1/jobs"
            params = {
                "query":    keyword,
                "page":     1,
                "per_page": 15,
                "aroundQuery": SEARCH_LOCATION,
                "aroundRadius": 100,
            }
            headers = {**HEADERS, "X-Api-Key": "anonymous"}
            r = requests.get(url, params=params, headers=headers, timeout=15)

            if r.status_code != 200:
                # Fallback scraping page web
                _wttj_scrape(keyword, jobs)
                continue

            for o in r.json().get("jobs", []):
                contract = ", ".join(
                    [c.get("name", "") for c in o.get("contract_types", [])]
                )
                jobs.append(make_job(
                    source      = "WTTJ",
                    job_id      = str(o["id"]),
                    title       = o.get("name", ""),
                    company     = o.get("organization", {}).get("name", "?"),
                    location    = o.get("office", {}).get("city", ""),
                    contract    = contract,
                    description = o.get("description", ""),
                    url         = f"https://www.welcometothejungle.com/fr/jobs/{o.get('slug', '')}",
                    published   = o.get("published_at", "")[:10],
                ))
            time.sleep(1.5)

    except Exception as e:
        logger.error(f"[WTTJ] Erreur : {e}")

    logger.info(f"[WTTJ] {len(jobs)} offres trouvées")
    return jobs


def _wttj_scrape(keyword, jobs):
    """Fallback scraping WTTJ si l'API ne répond pas."""
    try:
        url = f"https://www.welcometothejungle.com/fr/jobs?query={keyword}&aroundQuery={SEARCH_LOCATION}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("li", attrs={"data-testid": "search-results-list-item-wrapper"})
        for card in cards:
            title_el = card.find("h3")
            link_el  = card.find("a", href=True)
            if title_el and link_el:
                job_id = link_el["href"].split("/")[-1]
                jobs.append(make_job(
                    source="WTTJ", job_id=job_id,
                    title=title_el.get_text(strip=True), company="?",
                    location=SEARCH_LOCATION, contract="",
                    description=title_el.get_text(strip=True),
                    url=f"https://www.welcometothejungle.com{link_el['href']}",
                ))
    except Exception:
        pass


# ─────────────────────────────────────────────
# 4. HELLOWORK (scraping)
# ─────────────────────────────────────────────
def fetch_hellowork():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            slug_kw  = keyword.replace(" ", "-").lower()
            slug_loc = SEARCH_LOCATION.lower()
            url = f"https://www.hellowork.com/fr-fr/emploi/recherche.html?k={requests.utils.quote(keyword)}&l={SEARCH_LOCATION}&d=100km"

            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.find_all("article", attrs={"data-id": True})
            for card in cards:
                try:
                    job_id  = card.get("data-id", "")
                    title_el = card.find("h3") or card.find("h2")
                    title   = title_el.get_text(strip=True) if title_el else ""
                    co_el   = card.find(attrs={"data-cy": "company-name"})
                    company = co_el.get_text(strip=True) if co_el else "?"
                    loc_el  = card.find(attrs={"data-cy": "location"})
                    location = loc_el.get_text(strip=True) if loc_el else ""
                    link_el = card.find("a", href=True)
                    job_url = "https://www.hellowork.com" + link_el["href"] if link_el else ""

                    if title:
                        jobs.append(make_job(
                            source="HelloWork", job_id=job_id, title=title,
                            company=company, location=location, contract="",
                            description=title, url=job_url,
                        ))
                except Exception:
                    continue
            time.sleep(2)

    except Exception as e:
        logger.error(f"[HelloWork] Erreur : {e}")

    logger.info(f"[HelloWork] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 5. LINKEDIN — Note importante
# ─────────────────────────────────────────────
def fetch_linkedin():
    """
    LinkedIn bloque très agressivement le scraping.
    Cette fonction utilise une approche basique ; si elle échoue,
    utilise les alertes email LinkedIn classiques.
    """
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:1]:
            url = "https://www.linkedin.com/jobs/search/"
            params = {
                "keywords":  keyword,
                "location":  SEARCH_LOCATION,
                "sortBy":    "DD",    # Plus récent
                "f_TPR":     "r604800",  # 7 derniers jours
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            cards = soup.find_all("div", class_="base-card")
            for card in cards:
                try:
                    title_el = card.find("h3", class_="base-search-card__title")
                    title    = title_el.get_text(strip=True) if title_el else ""
                    co_el    = card.find("h4", class_="base-search-card__subtitle")
                    company  = co_el.get_text(strip=True) if co_el else "?"
                    loc_el   = card.find("span", class_="job-search-card__location")
                    location = loc_el.get_text(strip=True) if loc_el else ""
                    link_el  = card.find("a", href=True)
                    job_url  = link_el["href"].split("?")[0] if link_el else ""
                    job_id   = job_url.split("-")[-1] if job_url else ""

                    if title:
                        jobs.append(make_job(
                            source="LinkedIn", job_id=job_id, title=title,
                            company=company, location=location, contract="",
                            description=title, url=job_url,
                        ))
                except Exception:
                    continue
            time.sleep(3)

    except Exception as e:
        logger.warning(f"[LinkedIn] Scraping limité : {e}. "
                       "Utilise les alertes email LinkedIn en parallèle.")

    logger.info(f"[LinkedIn] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# Point d'entrée unique
# ─────────────────────────────────────────────
def fetch_all_jobs():
    """Lance tous les scrapers et retourne une liste unifiée."""
    all_jobs = []
    scrapers = [
        ("France Travail", fetch_france_travail),
        ("Indeed",         fetch_indeed),
        ("WTTJ",           fetch_wttj),
        ("HelloWork",      fetch_hellowork),
        ("LinkedIn",       fetch_linkedin),
    ]
    for name, fn in scrapers:
        try:
            results = fn()
            all_jobs.extend(results)
        except Exception as e:
            logger.error(f"[{name}] Échec total : {e}")
        time.sleep(1)

    # Dédoublonnage par ID
    seen = set()
    unique = []
    for j in all_jobs:
        if j["id"] not in seen:
            seen.add(j["id"])
            unique.append(j)

    logger.info(f"Total : {len(unique)} offres uniques")
    return unique