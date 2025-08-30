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

    # Dernier crawl (timestamp Unix en secondes)
    last_crawl_ts = 0
    if urls:
        last_seen_values = [u.last_seen for u in urls if u.last_seen]
        if last_seen_values:
            last_crawl_ts = max(last_seen_values).timestamp()

    registry = CollectorRegistry()

    # --- Métriques globales ---
    Gauge("crawler_total_urls", "Total URLs found", registry=registry).set(total)
    Gauge("crawler_active_urls", "Active URLs (status=200)", registry=registry).set(active)
    Gauge("crawler_inactive_urls", "Inactive URLs", registry=registry).set(inactive)
    Gauge("crawler_avg_response_time_seconds", "Average response time", registry=registry).set(avg_time)
    Gauge("crawler_error_rate", "Error rate (0-1)", registry=registry).set(error_rate)
    Gauge("crawler_last_crawl_timestamp", "Unix timestamp of last crawl", registry=registry).set(last_crawl_ts)

    # --- Compteurs par code HTTP ---
    g_status_count = Gauge(
        "crawler_status_count",
        "Number of URLs per HTTP status",
        ["status"],
        registry=registry
    )

    # Initialiser quelques codes courants + 'error' pour les status absents
    for code in ["200", "301", "302", "404", "500", "error"]:
        g_status_count.labels(status=code).set(0)

    for u in urls:
        # Ne pas utiliser 'if u.status_code' (0/False) -> utiliser 'is not None'
        status_label = str(u.status_code) if (u.status_code is not None) else "error"
        g_status_count.labels(status=status_label).inc()

    # --- Métriques détaillées par URL ---
    g_url_status = Gauge(
        "crawler_url_status",
        "Status of each crawled URL",
        ["url", "status"],
        registry=registry
    )
    g_url_time = Gauge(
        "crawler_url_response_time_seconds",
        "Response time of each crawled URL",
        ["url"],
        registry=registry
    )

    for u in urls:
        # Harmoniser: pas de 'unknown', uniquement 'error' quand le status est absent
        status_label = str(u.status_code) if (u.status_code is not None) else "error"
        g_url_status.labels(url=u.url, status=status_label).set(1)
        if u.response_time is not None:
            g_url_time.labels(url=u.url).set(u.response_time)

    return Response(generate_latest(registry), mimetype="text/plain")
