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

    # Actif = toute 2xx
    active = sum(1 for u in urls if (u.status_code is not None and 200 <= u.status_code < 300))
    inactive = total - active
    avg_time = sum((u.response_time or 0) for u in urls) / total if total else 0
    # Taux d'erreur = non-2xx / total
    error_rate = (sum(1 for u in urls if (u.status_code is None or not (200 <= u.status_code < 300))) / total) if total else 0

    # Dernier crawl (timestamp Unix en secondes)
    last_crawl_ts = 0
    if urls:
        last_seen_values = [u.last_seen for u in urls if u.last_seen]
        if last_seen_values:
            last_crawl_ts = max(last_seen_values).timestamp()

    registry = CollectorRegistry()

    # --- Métriques globales ---
    Gauge("crawler_total_urls", "Total URLs found", registry=registry).set(total)
    Gauge("crawler_active_urls", "Active URLs (status 2xx)", registry=registry).set(active)
    Gauge("crawler_inactive_urls", "Inactive URLs (non-2xx)", registry=registry).set(inactive)
    Gauge("crawler_avg_response_time_seconds", "Average response time", registry=registry).set(avg_time)
    Gauge("crawler_error_rate", "Error rate (0-1)", registry=registry).set(error_rate)
    Gauge("crawler_last_crawl_timestamp", "Unix timestamp of last crawl", registry=registry).set(last_crawl_ts)

    # --- Compteurs par code HTTP (optionnel, agrégé) ---
    g_status_count = Gauge(
        "crawler_status_count",
        "Number of URLs per HTTP status",
        ["status"],
        registry=registry
    )
    # Compte dynamique par code (None -> 'error')
    counts = {}
    for u in urls:
        key = str(u.status_code) if (u.status_code is not None) else "error"
        counts[key] = counts.get(key, 0) + 1
    for code, cnt in counts.items():
        g_status_count.labels(status=code).set(cnt)

    # --- Métriques détaillées par URL (une seule série par URL) ---
    g_url_time = Gauge(
        "crawler_url_response_time_seconds",
        "Response time of each crawled URL",
        ["url"],
        registry=registry
    )
    g_url_status_code = Gauge(
        "crawler_url_status_code",
        "HTTP status code for each URL (-1 if unknown)",
        ["url"],
        registry=registry
    )
    g_url_is_error = Gauge(
        "crawler_url_is_error",
        "1 if URL is not 2xx (or unknown), else 0",
        ["url"],
        registry=registry
    )

    for u in urls:
        status_num = int(u.status_code) if (u.status_code is not None) else -1
        g_url_status_code.labels(url=u.url).set(status_num)
        is_err = 0 if (200 <= status_num < 300) else 1
        g_url_is_error.labels(url=u.url).set(is_err)
        if u.response_time is not None:
            g_url_time.labels(url=u.url).set(u.response_time)

    return Response(generate_latest(registry), mimetype="text/plain")
