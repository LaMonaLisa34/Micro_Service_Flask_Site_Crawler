from . import db
from datetime import datetime

class Url(db.Model):
    __tablename__ = "urls"
    url = db.Column(db.String, primary_key=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    crawled = db.Column(db.Boolean, default=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)
    
    