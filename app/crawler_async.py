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
    try:
        start = time.time()
        async with session.get(url, timeout=10) as response:
            await response.text()  # on lit pour valider
            duration = time.time() - start
            return url, response.status, duration
    except Exception:
        return url, None, None

async def crawl_site(start_url, max_pages=300):
    visited = set()
    to_visit = [start_url]

    async with aiohttp.ClientSession() as session:
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            fetched_url, status, duration = await fetch(session, url)

            # Enregistrer dans la DB avec status_code + response_time
            url_entry = Url(
                url=fetched_url,
                status_code=status,
                response_time=duration,
                last_seen=datetime.utcnow(),
                is_active=(status == 200),
                crawled=True
            )
            db.session.merge(url_entry)
            db.session.commit()

            # Extraire les liens si status OK
            if status == 200:
                try:
                    async with session.get(url) as resp:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        for link in soup.find_all("a", href=True):
                            abs_url = urljoin(url, link["href"])
                            if urlparse(abs_url).netloc == urlparse(start_url).netloc:
                                if abs_url not in visited:
                                    to_visit.append(abs_url)
                except:
                    continue
