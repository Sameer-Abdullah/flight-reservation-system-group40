from datetime import datetime
from . import db

class Flight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    origin = db.Column(db.String(3), nullable=False)
    destination = db.Column(db.String(3), nullable=False)
    depart_time = db.Column(db.DateTime, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
