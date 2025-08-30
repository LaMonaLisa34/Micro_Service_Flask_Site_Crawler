# app/crawler_async.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import time
from . import db
from .models import Url


async def fetch(session, url, retries=3, backoff=1):
    """
    Télécharge une page avec retries.
    Retourne (url, status, duration, html).
    - retries : nombre de tentatives max
    - backoff : temps d’attente entre tentatives (exponentiel)
    """
    for attempt in range(1, retries + 1):
        try:
            start = time.time()
            async with session.get(url, timeout=10) as response:
                html = await response.text()
                duration = time.time() - start
                return url, response.status, duration, html
        except Exception as e:
            if attempt < retries:
                await asyncio.sleep(backoff * attempt)  # backoff exponentiel
                continue
            return url, None, None, None


async def crawl_site(start_url, max_pages=300, commit_batch=20, inject_tests=True, max_requeue=2):
    """
    Crawler async qui explore un site et stocke les infos en DB.
    - inject_tests: laissé tel quel (True par défaut) pour ne pas changer ton comportement actuel.
    - max_requeue: nb max de ré-enfilages pour 5xx/échecs réseau.
    """
    visited = set()
    attempts = {}
    to_visit = [start_url]
    buffer = []

    if inject_tests:
        domain = urlparse(start_url).scheme + "://" + urlparse(start_url).netloc
        to_visit.extend([
            domain + "/page-introuvable-test-404",
            domain + "/page-erreur-test-500",
            domain + "/admin"
        ])

    async with aiohttp.ClientSession() as session:
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue

            fetched_url, status, duration, html = await fetch(session, url)

            # Upsert (url est PK -> merge met à jour)
            entry = Url(
                url=fetched_url,
                status_code=status,
                response_time=duration,
                last_seen=datetime.utcnow(),
                is_active=(status is not None and 200 <= status < 300),
                crawled=True
            )
            db.session.merge(entry)
            buffer.append(entry)

            # Politique de ré-enfilage pour 5xx/échecs réseau
            if status is None or (status >= 500):
                attempts[url] = attempts.get(url, 0) + 1
                if attempts[url] <= max_requeue:
                    # On retentera plus tard dans CE run (ne pas marquer visited)
                    to_visit.append(url)
                else:
                    # On abandonne après N essais -> on marque visité
                    visited.add(url)
            else:
                # Cas "terminé" (2xx/3xx/4xx) -> on marque visité
                visited.add(url)

                # Exploration uniquement si 2xx + HTML
                if 200 <= status < 300 and html:
                    try:
                        soup = BeautifulSoup(html, "html.parser")
                        for link in soup.find_all("a", href=True):
                            abs_url = urljoin(url, link["href"])
                            if urlparse(abs_url).netloc == urlparse(start_url).netloc:
                                if abs_url not in visited:
                                    to_visit.append(abs_url)
                    except Exception:
                        pass

            # Commit par batch
            if len(buffer) >= commit_batch:
                db.session.commit()
                buffer.clear()

    if buffer:
        db.session.commit()

    print(f"[Crawler] Terminé : {len(visited)} pages visitées.")


if __name__ == "__main__":
    # Test direct
    start = "https://example.com"
    asyncio.run(crawl_site(start, max_pages=50))
