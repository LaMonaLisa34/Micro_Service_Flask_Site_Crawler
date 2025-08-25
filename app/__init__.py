# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import asyncio


db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:postgres@postgres-crawler:5432/crawlerdb"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        from . import routes, models
        db.create_all()

    # --- Scheduler ---
    scheduler = BackgroundScheduler()

    def scheduled_crawl():
        with app.app_context():
            print("Scheduled crawl lancé...")
            asyncio.run(crawl_site("https://chevauxdumonde.com", max_pages=5000))

    # Job toutes les 10 minutes
    scheduler.add_job(scheduled_crawl, "interval", minutes=2)
    scheduler.start()

    # Arrêt propre du scheduler
    atexit.register(lambda: scheduler.shutdown())

    return app

