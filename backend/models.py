from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(50), default="patient") 
    
    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    age = db.Column(db.Integer, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Vital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    hr = db.Column(db.Float)         # heart rate
    spo2 = db.Column(db.Float)       # oxygen saturation
    temp = db.Column(db.Float)       # temperature Celsius
    rr = db.Column(db.Float)        # respiratory rate (optional)
    raw = db.Column(db.Text)        # store the raw json if needed

     # For debugging in console
    def __repr__(self):
        return f"<Vital id={self.id} patient_id={self.patient_id} hr={self.hr} spo2={self.spo2} temp={self.temp} rr={self.rr}>"

    # For converting to dictionary (useful for APIs)
    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "hr": self.hr,
            "spo2": self.spo2,
            "temp": self.temp,
            "rr": self.rr,
            "raw": self.raw
        }
class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    severity = db.Column(db.String(32))  # Normal / Alert / Warning / Emergency / Critical
    message = db.Column(db.String(500))
    sent_sms = db.Column(db.Boolean, default=False)
    sent_email = db.Column(db.Boolean, default=False)
