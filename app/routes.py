#routes.py
from flask import Blueprint, request, jsonify, Response
from datetime import datetime
import asyncio
from prometheus_client import generate_latest, Gauge, CollectorRegistry
from . import db
from .models import Url
from .crawler_async import crawl_site

bp = Blueprint("routes", __name__)

@bp.route("/urls", methods=["GET"])
def list_urls():
    urls = Url.query.all()
    return jsonify([{
        "url": u.url,
        "status_code": u.status_code,
        "response_time": u.response_time,
        "last_seen": u.last_seen.isoformat(),
        "is_active": u.is_active
    } for u in urls])


@bp.route("/crawl_site", methods=["POST", "GET"])
def crawl_entire_site():
    start_url = request.args.get("url")
    if not start_url:
        return {"error": "Missing ?url= param"}, 400
    asyncio.run(crawl_site(start_url, max_pages=5000))
    return {"message": f"Crawl terminé pour {start_url}"}


@bp.route("/report", methods=["GET"])
def report():
    urls = Url.query.all()
    total = len(urls)
    active = sum(1 for u in urls if u.is_active)
    inactive = total - active
    avg_time = sum((u.response_time or 0) for u in urls) / total if total else 0
    error_rate = inactive / total if total else 0

    return jsonify({
        "total_urls": total,
        "active_urls": active,
        "inactive_urls": inactive,
        "avg_response_time": round(avg_time, 3),
        "error_rate": f"{round(error_rate * 100, 2)}%"
    })
    
@bp.route("/metrics")
def metrics():
    urls = Url.query.all()

    total = len(urls)
    active = sum(1 for u in urls if u.is_active)
    inactive = total - active
    avg_time = sum((u.response_time or 0) for u in urls) / total if total else 0
    error_rate = inactive / total if total else 0

    # last crawl (unix seconds)
    last_crawl_ts = 0
    last_seen_values = [u.last_seen for u in urls if u.last_seen]
    if last_seen_values:
        last_crawl_ts = max(last_seen_values).timestamp()

    reg = CollectorRegistry()

    # Globales (une seule série chacune)
    Gauge("crawler_total_urls", "Total URLs found", registry=reg).set(total)
    Gauge("crawler_active_urls", "Active URLs (status=200)", registry=reg).set(active)
    Gauge("crawler_inactive_urls", "Inactive URLs", registry=reg).set(inactive)
    Gauge("crawler_avg_response_time_seconds", "Average response time", registry=reg).set(avg_time)
    Gauge("crawler_error_rate", "Error rate (0-1)", registry=reg).set(error_rate)
    Gauge("crawler_last_crawl_timestamp", "Unix timestamp of last crawl", registry=reg).set(last_crawl_ts)

    # Compteurs agrégés par code (une série par "status" — SANS 'url')
    g_status_count = Gauge(
        "crawler_status_count",
        "Number of URLs per HTTP status (aggregated)",
        ["status"],
        registry=reg,
    )
    # initialise proprement (évite 'unknown' résiduels)
    for code in ["200", "301", "302", "404", "500", "error"]:
        g_status_count.labels(status=code).set(0)

    # Métriques PAR URL (⚠️ contiennent le label 'url' et UNE SEULE série par URL)
    g_status_code = Gauge(
        "crawler_url_status_code",
        "HTTP status code for each URL",
        ["url"],
        registry=reg,
    )
    g_is_error = Gauge(
        "crawler_url_is_error",
        "1 if URL is considered error, else 0",
        ["url"],
        registry=reg,
    )
    g_resp_time = Gauge(
        "crawler_url_response_time_seconds",
        "Response time per URL",
        ["url"],
        registry=reg,
    )

    # Remplissage (et agrégats)
    per_code = {}
    for u in urls:
        # statut numérique ou None
        status_val = int(u.status_code) if (u.status_code is not None) else None

        # --- séries par URL ---
        # on émet TOUJOURS 'crawler_url_status_code{url="..."}' (pas de série fantôme)
        g_status_code.labels(url=u.url).set(status_val if status_val is not None else -1)  # -1 = inconnu
        g_is_error.labels(url=u.url).set(1 if (status_val not in (200, 301, 302) or status_val is None) else 0)
        if u.response_time is not None:
            g_resp_time.labels(url=u.url).set(u.response_time)

        # --- agrégat par code ---
        key = str(status_val) if status_val is not None else "error"
        per_code[key] = per_code.get(key, 0) + 1

    for code, count in per_code.items():
        g_status_count.labels(status=code).set(count)

    return Response(generate_latest(reg), mimetype="text/plain")