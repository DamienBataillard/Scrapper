"""
scrapers.py — Récupère les offres d'emploi depuis plusieurs sources
"""

import requests
import time
import logging
import os
from datetime import datetime
from bs4 import BeautifulSoup
from config import SEARCH_KEYWORDS, SEARCH_LOCATION

logger = logging.getLogger(__name__)

# Active le mode debug : sauvegarde le HTML brut dans /debug_html/
DEBUG_HTML = os.environ.get("DEBUG_HTML", "false").lower() == "true"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _log_request(source: str, url: str, status: int, cards: int, keyword: str = ""):
    kw_str = f" | mot-clé : '{keyword}'" if keyword else ""
    if status == 200 and cards > 0:
        logger.info(f"   [{source}] ✅ HTTP {status} — {cards} cards trouvées{kw_str}")
    elif status == 200 and cards == 0:
        logger.warning(f"   [{source}] ⚠️  HTTP {status} — 0 cards trouvées{kw_str} "
                       f"→ sélecteur CSS peut-être obsolète ou page vide")
    elif status in (403, 429):
        logger.warning(f"   [{source}] 🚫 HTTP {status} — Accès bloqué / rate limit{kw_str}")
    elif status in (301, 302):
        logger.warning(f"   [{source}] 🔀 HTTP {status} — Redirection{kw_str}")
    else:
        logger.warning(f"   [{source}] ❌ HTTP {status}{kw_str}")
    logger.debug(f"   [{source}] URL : {url}")


def _save_debug_html(source: str, keyword: str, html: str):
    """Sauvegarde le HTML brut pour inspection des sélecteurs."""
    if not DEBUG_HTML:
        return
    os.makedirs("debug_html", exist_ok=True)
    slug = keyword.replace(" ", "_")[:30]
    path = f"debug_html/{source}_{slug}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"   [{source}] 💾 HTML sauvegardé → {path}")


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


# ─────────────────────────────────────────────
# 1. FRANCE TRAVAIL (scraping) ✅ fonctionnel
# ─────────────────────────────────────────────
def fetch_france_travail():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://candidat.francetravail.fr/offres/recherche"
            params = {
                "motsCles":       keyword,
                "ville":          SEARCH_LOCATION,
                "rayonRecherche": 50,
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("li", class_="result")
            _log_request("FranceTravail", r.url, r.status_code, len(cards), keyword)
            _save_debug_html("FranceTravail", keyword, r.text)

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
# 2. INDEED ❌ retiré (403 systématique en France)
# → Utilise les alertes email Indeed en parallèle :
#    indeed.fr > ta recherche > "Recevoir les nouvelles offres par email"
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# 3. WELCOME TO THE JUNGLE ⚠️  à calibrer
# ─────────────────────────────────────────────
def fetch_wttj():
    """
    WTTJ charge ses offres dynamiquement en JS.
    On scrape la version serveur de leur page de recherche.
    Si 0 résultats : active DEBUG_HTML=true et inspecte debug_html/WTTJ_*.html
    """
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://www.welcometothejungle.com/fr/jobs"
            params = {
                "query":       keyword,
                "aroundQuery": SEARCH_LOCATION,
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            _save_debug_html("WTTJ", keyword, r.text)

            # Sélecteurs connus — peut nécessiter une mise à jour
            cards = (
                soup.find_all("li", attrs={"data-testid": "search-results-list-item-wrapper"}) or
                soup.select("ul[data-testid='search-results-list'] li") or
                soup.select("[data-testid*='job']") or
                soup.find_all("article")
            )
            _log_request("WTTJ", r.url, r.status_code, len(cards), keyword)

            for card in cards:
                try:
                    title_el = card.find("h3") or card.find("h2")
                    link_el  = card.find("a", href=True)
                    if not title_el or not link_el:
                        continue
                    job_id  = link_el["href"].split("/")[-1].split("?")[0]
                    job_url = f"https://www.welcometothejungle.com{link_el['href']}"
                    co_el   = card.find("span", class_=lambda c: c and "company" in c.lower())
                    company = co_el.get_text(strip=True) if co_el else "?"
                    jobs.append(make_job(
                        source="WTTJ", job_id=job_id,
                        title=title_el.get_text(strip=True),
                        company=company, location=SEARCH_LOCATION,
                        contract="", description=title_el.get_text(strip=True),
                        url=job_url,
                    ))
                except Exception:
                    continue
            time.sleep(2)
    except Exception as e:
        logger.error(f"[WTTJ] Erreur : {e}")

    if not jobs:
        logger.warning("[WTTJ] 0 offres — relance avec DEBUG_HTML=true pour inspecter le HTML")
    logger.info(f"[WTTJ] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 4. HELLOWORK ⚠️  à calibrer
# ─────────────────────────────────────────────
def fetch_hellowork():
    """
    Si 0 résultats : active DEBUG_HTML=true et inspecte debug_html/HelloWork_*.html
    """
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = (f"https://www.hellowork.com/fr-fr/emploi/recherche.html"
                   f"?k={requests.utils.quote(keyword)}&l={SEARCH_LOCATION}&d=100km")

            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            _save_debug_html("HelloWork", keyword, r.text)

            cards = (
                soup.find_all("li", attrs={"data-id": True}) or
                soup.find_all("article", attrs={"data-id": True}) or
                soup.select("ul[data-cy='job-list'] > li") or
                soup.select("[data-testid='job-item']") or
                soup.select("li[data-cy]")
            )
            _log_request("HelloWork", r.url, r.status_code, len(cards), keyword)

            for card in cards:
                try:
                    job_id   = card.get("data-id", "")
                    title_el = card.find("h3") or card.find("h2") or card.find("a")
                    title    = title_el.get_text(strip=True) if title_el else ""
                    co_el    = card.find(attrs={"data-cy": "company-name"})
                    company  = co_el.get_text(strip=True) if co_el else "?"
                    loc_el   = card.find(attrs={"data-cy": "location"})
                    location = loc_el.get_text(strip=True) if loc_el else SEARCH_LOCATION
                    link_el  = card.find("a", href=True)
                    job_url  = "https://www.hellowork.com" + link_el["href"] if link_el else ""
                    if title:
                        jobs.append(make_job(
                            source="HelloWork", job_id=job_id or title[:20],
                            title=title, company=company, location=location,
                            contract="", description=title, url=job_url,
                        ))
                except Exception:
                    continue
            time.sleep(2)
    except Exception as e:
        logger.error(f"[HelloWork] Erreur : {e}")

    if not jobs:
        logger.warning("[HelloWork] 0 offres — relance avec DEBUG_HTML=true pour inspecter le HTML")
    logger.info(f"[HelloWork] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 5. LINKEDIN ⚠️  résultats limités
# ─────────────────────────────────────────────
def fetch_linkedin():
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:1]:
            url = "https://www.linkedin.com/jobs/search/"
            params = {
                "keywords": keyword,
                "location": SEARCH_LOCATION,
                "sortBy":   "DD",
                "f_TPR":    "r604800",
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="base-card")
            _log_request("LinkedIn", r.url, r.status_code, len(cards), keyword)
            _save_debug_html("LinkedIn", keyword, r.text)

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
        logger.warning(f"[LinkedIn] {e}")

    logger.info(f"[LinkedIn] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# Point d'entrée unique
# ─────────────────────────────────────────────
def fetch_all_jobs():
    all_jobs = []
    scrapers = [
        ("FranceTravail", fetch_france_travail),
        ("WTTJ",          fetch_wttj),
        ("LinkedIn",      fetch_linkedin),
    ]
    for name, fn in scrapers:
        try:
            results = fn()
            all_jobs.extend(results)
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



def _log_request(source: str, url: str, status: int, cards: int, keyword: str = ""):
    """Log standardisé pour chaque requête de scraping."""
    kw_str = f" | mot-clé : '{keyword}'" if keyword else ""
    if status == 200 and cards > 0:
        logger.info(f"   [{source}] ✅ HTTP {status} — {cards} cards trouvées{kw_str}")
    elif status == 200 and cards == 0:
        logger.warning(f"   [{source}] ⚠️  HTTP {status} — 0 cards trouvées{kw_str} "
                       f"→ sélecteur CSS peut-être obsolète ou page vide")
    elif status in (403, 429):
        logger.warning(f"   [{source}] 🚫 HTTP {status} — Accès bloqué / rate limit{kw_str} "
                       f"→ le site a détecté le bot")
    elif status in (301, 302):
        logger.warning(f"   [{source}] 🔀 HTTP {status} — Redirection{kw_str} "
                       f"→ l'URL a peut-être changé")
    else:
        logger.warning(f"   [{source}] ❌ HTTP {status}{kw_str} → réponse inattendue")
    logger.debug(f"   [{source}] URL : {url}")


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
            _log_request("FranceTravail", r.url, r.status_code, len(cards), keyword)
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
# 2. INDEED (flux RSS — contourne le 403)
# ─────────────────────────────────────────────
def fetch_indeed():
    """
    Indeed bloque le scraping HTML (403), mais leur flux RSS
    est public et non protégé. On parse du XML, plus fiable.
    """
    import xml.etree.ElementTree as ET
    jobs = []
    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            url = "https://fr.indeed.com/rss"
            params = {
                "q":      keyword,
                "l":      SEARCH_LOCATION,
                "sort":   "date",
                "fromage": "7",
            }
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            _log_request("Indeed", r.url, r.status_code,
                         r.text.count("<item>"), keyword)

            if r.status_code != 200:
                continue

            root = ET.fromstring(r.text)
            items = root.findall(".//item")

            for item in items:
                try:
                    title   = item.findtext("title", "").strip()
                    job_url = item.findtext("link", "").strip()
                    company = item.findtext("source", "?").strip()
                    loc_raw = item.findtext("{https://www.indeed.com/about/}jobLocation", "")
                    location = loc_raw or SEARCH_LOCATION
                    desc    = item.findtext("description", title).strip()
                    pub     = item.findtext("pubDate", "")[:16]
                    job_id  = job_url.split("jk=")[-1][:16] if "jk=" in job_url else job_url[-16:]

                    if title:
                        jobs.append(make_job(
                            source="Indeed", job_id=job_id, title=title,
                            company=company, location=location, contract="",
                            description=desc, url=job_url, published=pub,
                        ))
                except Exception:
                    continue
            time.sleep(2)

    except Exception as e:
        logger.error(f"[Indeed] Erreur : {e}")

    logger.info(f"[Indeed] {len(jobs)} offres trouvées")
    return jobs


# ─────────────────────────────────────────────
# 3. WELCOME TO THE JUNGLE (Algolia)
# ─────────────────────────────────────────────
def fetch_wttj():
    """
    WTTJ utilise Algolia comme moteur de recherche interne.
    L'API Algolia est publique et accessible sans auth.
    """
    jobs = []
    ALGOLIA_APP  = "RQFKUXNY9B"
    ALGOLIA_KEY  = "63e8de1d00c7cc2e7e309f5abebb2a44"
    ALGOLIA_URL  = f"https://{ALGOLIA_APP}-dsn.algolia.net/1/indexes/wttj_jobs_production_fr/query"

    algolia_headers = {
        **HEADERS,
        "X-Algolia-Application-Id": ALGOLIA_APP,
        "X-Algolia-API-Key":        ALGOLIA_KEY,
    }

    try:
        for keyword in SEARCH_KEYWORDS[:2]:
            payload = {
                "query":         keyword,
                "hitsPerPage":   20,
                "aroundLatLngViaIP": False,
                "filters":       "",
            }
            r = requests.post(ALGOLIA_URL, headers=algolia_headers,
                              json=payload, timeout=15)
            hits = r.json().get("hits", []) if r.status_code == 200 else []
            _log_request("WTTJ", ALGOLIA_URL, r.status_code, len(hits), keyword)

            if r.status_code != 200:
                logger.warning(f"   [WTTJ] Algolia HTTP {r.status_code} → fallback scraping")
                _wttj_scrape(keyword, jobs)
                continue

            for o in hits:
                contract = o.get("contract_type", {}).get("en", "")
                city     = o.get("office", {}).get("city", "") or SEARCH_LOCATION
                slug     = o.get("slug", "")
                jobs.append(make_job(
                    source      = "WTTJ",
                    job_id      = str(o.get("objectID", slug)),
                    title       = o.get("name", ""),
                    company     = o.get("organization", {}).get("name", "?"),
                    location    = city,
                    contract    = contract,
                    description = o.get("description", ""),
                    url         = f"https://www.welcometothejungle.com/fr/companies/{o.get('organization', {}).get('slug', '')}/jobs/{slug}",
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
        _log_request("WTTJ-fallback", r.url, r.status_code, len(cards))
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
            url = (f"https://www.hellowork.com/fr-fr/emploi/recherche.html"
                   f"?k={requests.utils.quote(keyword)}&l={SEARCH_LOCATION}&d=100km")

            r = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")

            # Essai de plusieurs sélecteurs connus
            cards = (
                soup.find_all("li", attrs={"data-id": True}) or
                soup.find_all("article", attrs={"data-id": True}) or
                soup.find_all("div", attrs={"data-id": True}) or
                soup.select("ul[data-cy='job-list'] > li") or
                soup.select("[data-testid='job-item']")
            )
            _log_request("HelloWork", r.url, r.status_code, len(cards), keyword)

            for card in cards:
                try:
                    job_id   = card.get("data-id", "")
                    title_el = card.find("h3") or card.find("h2") or card.find("a")
                    title    = title_el.get_text(strip=True) if title_el else ""
                    co_el    = (card.find(attrs={"data-cy": "company-name"}) or
                                card.find(class_=lambda c: c and "company" in c.lower()))
                    company  = co_el.get_text(strip=True) if co_el else "?"
                    loc_el   = (card.find(attrs={"data-cy": "location"}) or
                                card.find(class_=lambda c: c and "location" in c.lower()))
                    location = loc_el.get_text(strip=True) if loc_el else SEARCH_LOCATION
                    link_el  = card.find("a", href=True)
                    job_url  = "https://www.hellowork.com" + link_el["href"] if link_el else ""

                    if title:
                        jobs.append(make_job(
                            source="HelloWork", job_id=job_id or title[:20],
                            title=title, company=company, location=location,
                            contract="", description=title, url=job_url,
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
            _log_request("LinkedIn", r.url, r.status_code, len(cards), keyword)
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