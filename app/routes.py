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

    registry = CollectorRegistry()

    Gauge("crawler_total_urls", "Total URLs found", registry=registry).set(total)
    Gauge("crawler_active_urls", "Active URLs (status=200)", registry=registry).set(active)
    Gauge("crawler_inactive_urls", "Inactive URLs", registry=registry).set(inactive)
    Gauge("crawler_avg_response_time_seconds", "Average response time", registry=registry).set(avg_time)
    Gauge("crawler_error_rate", "Error rate (0-1)", registry=registry).set(error_rate)

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
        status_label = str(u.status_code) if u.status_code else "unknown"
        g_url_status.labels(url=u.url, status=status_label).set(1)
        if u.response_time is not None:
            g_url_time.labels(url=u.url).set(u.response_time)

    return Response(generate_latest(registry), mimetype="text/plain")
