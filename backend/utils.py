import os, json, requests
from datetime import datetime
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL")

# Simple threshold-based fallback analysis
def rule_based_analysis(vitals: dict):
    # vitals expected: {'hr':.., 'spo2':.., 'temp':.., 'rr':..}
    hr = vitals.get('hr')
    spo2 = vitals.get('spo2')
    temp = vitals.get('temp')
    rr = vitals.get('rr')

    # basic rules - tune these
    if spo2 is not None and spo2 < 90:
        return {"label": "Emergency", "score": 0.99, "reason": "Low SpO2"}
    if temp is not None and temp > 40:
        return {"label": "Emergency", "score": 0.95, "reason": "High fever"}
    if hr is not None and hr > 140:
        return {"label": "Emergency", "score": 0.9, "reason": "Very high HR"}
    if (spo2 is not None and spo2 < 92) or (hr is not None and hr > 120):
        return {"label": "Warning", "score": 0.8, "reason": "Low SpO2 or high HR"}
    # default
    return {"label": "Normal", "score": 0.2, "reason": "Within thresholds"}

def call_ml_service(vitals: dict):
    if not ML_SERVICE_URL:
        return None
    try:
        r = requests.post(ML_SERVICE_URL, json={"vitals": vitals}, timeout=5)
        if r.status_code == 200:
            return r.json()  # expected: {'label': 'Emergency', 'score':0.95, 'meta':...}
        else:
            return None
    except Exception as e:
        print("ML service call failed:", e)
        return None

# Twilio SMS
def send_sms_via_twilio(to_number: str, message: str):
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    if not sid or not token or not from_number:
        return False, "Twilio credentials not configured"
    try:
        client = Client(sid, token)
        msg = client.messages.create(body=message, from_=from_number, to=to_number)
        return True, msg.sid
    except Exception as e:
        return False, str(e)

# SMTP email
def send_email_via_smtp(to_email: str, subject: str, body: str):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    if not host or not user or not pwd:
        return False, "SMTP not configured"
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = user
        msg['To'] = to_email
        s = smtplib.SMTP(host, port)
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [to_email], msg.as_string())
        s.quit()
        return True, "sent"
    except Exception as e:
        return False, str(e)
