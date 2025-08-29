from flask import Blueprint, request, jsonify, current_app
from models import db, User, Patient, Vital, Alert
from werkzeug.security import generate_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import datetime
import json
from utils import call_ml_service, rule_based_analysis, send_sms_via_twilio, send_email_via_smtp

bp = Blueprint('api', __name__)

# Helper: create test user (for quick start)
@bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"msg":"username & password required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"msg":"user exists"}), 400
    u = User(username=username)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return jsonify({"msg":"registered"}), 201

@bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    u = User.query.filter_by(username=username).first()
    if not u or not u.check_password(password):
        return jsonify({"msg":"Bad credentials"}), 401
    token = create_access_token(identity=u.id)
    return jsonify({"access_token": token})

# Save vitals and analyse
@bp.route('/saveVitals', methods=['POST'])
@jwt_required()
def save_vitals():
    payload = request.json or {}
    patient_id = payload.get('patient_id')
    vitals = payload.get('vitals')
    ts = payload.get('timestamp')
    if not patient_id or not vitals:
        return jsonify({"msg":"patient_id and vitals required"}), 400
    try:
        timestamp = datetime.fromisoformat(ts) if ts else datetime.utcnow()
    except:
        timestamp = datetime.utcnow()
    # persist
    v = Vital(patient_id=patient_id,
              timestamp=timestamp,
              hr=vitals.get('hr'),
              spo2=vitals.get('spo2'),
              temp=vitals.get('temp'),
              rr=vitals.get('rr'),
              raw=json.dumps(vitals))
    db.session.add(v)
    db.session.commit()

    # Analysis (ML service or fallback)
    ml_result = call_ml_service(vitals)
    if not ml_result:
        ml_result = rule_based_analysis(vitals)

    label = ml_result.get('label', 'Normal')
    score = ml_result.get('score', 0.0)
    reason = ml_result.get('reason', "")

    response = {"label": label, "score": score, "reason": reason, "timestamp": timestamp.isoformat()}

    # create alert if critical
    if label in ("Emergency", "Critical"):
        msg = f"ALERT: Patient {patient_id} -> {label}. Reason: {reason}"
        a = Alert(patient_id=patient_id, severity=label, message=msg)
        db.session.add(a)
        db.session.commit()

        # Send notifications (Twilio SMS then email fallback)
        # NOTE: set TARGET_PHONE and ALERT_EMAIL_TO in env or send to patient owner
        target_phone = current_app.config.get('TARGET_PHONE')
        if target_phone:
            ok, info = send_sms_via_twilio(target_phone, msg)
            a.sent_sms = ok
        alert_email = current_app.config.get('ALERT_EMAIL_TO')
        if alert_email:
            ok_e, info_e = send_email_via_smtp(alert_email, f"SPMR Alert: {label}", msg)
            a.sent_email = ok_e
        db.session.commit()

    return jsonify({"status":"ok", "analysis": response})

# Get latest analysis / quick analysis by calling ML
@bp.route('/getAnalysis/<int:patient_id>', methods=['GET'])
@jwt_required()
def get_analysis(patient_id):
    # fetch latest vitals
    v = Vital.query.filter_by(patient_id=patient_id).order_by(Vital.timestamp.desc()).first()
    if not v:
        return jsonify({"msg":"no vitals found"}), 404
    vitals = {"hr": v.hr, "spo2": v.spo2, "temp": v.temp, "rr": v.rr}
    ml_result = call_ml_service(vitals)
    if not ml_result:
        ml_result = rule_based_analysis(vitals)
    return jsonify({"patient_id": patient_id, "vitals": vitals, "analysis": ml_result})

# Simple chatbot endpoint (rule-based, and can proxy to external)
@bp.route('/chatbot', methods=['POST'])
@jwt_required()
def chatbot():
    payload = request.json or {}
    message = (payload.get('message') or "").lower()
    # very simple rules
    if "fever" in message:
        return jsonify({"reply": "If you have fever, measure temperature and rest. If temp > 40C, seek emergency care."})
    if "headache" in message:
        return jsonify({"reply": "Headache can be due to stress or dehydration. Drink water, rest, if severe seek care."})
    # else call external chatbot if configured
    chatbot_url = current_app.config.get('CHATBOT_URL')
    if chatbot_url:
        try:
            r = requests.post(chatbot_url, json={"message": message}, timeout=5)
            if r.ok:
                return jsonify({"reply": r.json().get("reply")})
        except Exception as e:
            current_app.logger.error("Chatbot proxy failed: %s", e)
    return jsonify({"reply":"I am not sure — please provide more symptoms or contact your clinician."})
