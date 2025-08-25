# app/routes.py
from flask import request, jsonify
from datetime import datetime
import time, requests
from . import db
from .models import Url
from flask import current_app as app
import asyncio
from .crawler_async import crawl_site 
from flask import request, jsonify, Response
from prometheus_client import generate_latest, Gauge, CollectorRegistry


@app.route("/urls", methods=["GET"])
def list_urls():
    urls = Url.query.all()
    return jsonify([{
        "url": u.url,
        "status_code": u.status_code,
        "response_time": u.response_time,
        "last_seen": u.last_seen.isoformat(),
        "is_active": u.is_active
    } for u in urls])


@app.route("/crawl_site", methods=["POST", "GET"])
def crawl_entire_site():
    start_url = request.args.get("url")
    if not start_url:
        return {"error": "Missing ?url= param"}, 400

    # Lancer l’asynchrone
    asyncio.run(crawl_site(start_url, max_pages=5000))

    return {"message": f"Crawl terminé pour {start_url}"}

@app.route("/report", methods=["GET"])
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

@app.route("/metrics")
def metrics():
    urls = Url.query.all()
    total = len(urls)
    active = sum(1 for u in urls if u.is_active)
    inactive = total - active
    avg_time = sum((u.response_time or 0) for u in urls) / total if total else 0
    error_rate = inactive / total if total else 0

    registry = CollectorRegistry()

    g_total = Gauge("crawler_total_urls", "Total URLs found", registry=registry)
    g_active = Gauge("crawler_active_urls", "Active URLs (status=200)", registry=registry)
    g_inactive = Gauge("crawler_inactive_urls", "Inactive URLs", registry=registry)
    g_avg_time = Gauge("crawler_avg_response_time_seconds", "Average response time", registry=registry)
    g_error_rate = Gauge("crawler_error_rate", "Error rate (0-1)", registry=registry)

    g_total.set(total)
    g_active.set(active)
    g_inactive.set(inactive)
    g_avg_time.set(avg_time)
    g_error_rate.set(error_rate)

    return Response(generate_latest(registry), mimetype="text/plain")