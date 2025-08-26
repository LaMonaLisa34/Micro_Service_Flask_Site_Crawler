# app/crawler_async.py
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import time
from . import db
from .models import Url


async def fetch(session, url):
    """
    Télécharge une page et renvoie (url, status, duration, html).
    """
    try:
        start = time.time()
        async with session.get(url, timeout=10) as response:
            html = await response.text()
            duration = time.time() - start
            return url, response.status, duration, html
    except Exception:
        return url, None, None, None


async def crawl_site(start_url, max_pages=300, commit_batch=20, inject_tests=True):
    """
    Crawler async qui explore un site et stocke les infos en DB.
    - start_url : URL de départ
    - max_pages : limite du nombre de pages à visiter
    - commit_batch : taille des batchs avant commit DB
    - inject_tests : si True, on ajoute quelques URLs volontairement invalides
    """
    visited = set()
    to_visit = [start_url]
    buffer = []  # URLs en attente de commit DB

    # Ajout d'URLs de test (404, 500, admin) pour toujours avoir des stats en cas de site "parfait"
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
            visited.add(url)

            fetched_url, status, duration, html = await fetch(session, url)

            # Sauvegarde dans le buffer
            url_entry = Url(
                url=fetched_url,
                status_code=status,
                response_time=duration,
                last_seen=datetime.utcnow(),
                is_active=(status == 200),
                crawled=True
            )
            buffer.append(url_entry)

            # Commit par batch
            if len(buffer) >= commit_batch:
                for entry in buffer:
                    db.session.merge(entry)
                db.session.commit()
                buffer.clear()

            # Exploration uniquement si page valide
            if status == 200 and html:
                try:
                    soup = BeautifulSoup(html, "html.parser")
                    for link in soup.find_all("a", href=True):
                        abs_url = urljoin(url, link["href"])
                        # On reste dans le même domaine
                        if urlparse(abs_url).netloc == urlparse(start_url).netloc:
                            if abs_url not in visited:
                                to_visit.append(abs_url)
                except Exception:
                    continue

    # Commit final
    if buffer:
        for entry in buffer:
            db.session.merge(entry)
        db.session.commit()

    print(f"[Crawler] Terminé : {len(visited)} pages visitées.")


if __name__ == "__main__":
    # Test direct
    start = "https://example.com"
    asyncio.run(crawl_site(start, max_pages=50))
