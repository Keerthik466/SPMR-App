from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from models import db, User, Patient, Vital, Alert
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity,get_jwt
from flask_cors import CORS
from datetime import timedelta
from auth_utils import role_required
from flask_mail import Mail, Message


load_dotenv()  # load environment variables


def create_app():
    app = Flask(__name__)

    # ---------- Configs ----------
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///spmr.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # optional configs
    app.config['TARGET_PHONE'] = os.getenv('TARGET_PHONE')
    app.config['ALERT_EMAIL_TO'] = os.getenv('ALERT_EMAIL_TO')
    app.config['CHATBOT_URL'] = os.getenv('CHATBOT_URL')

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = "your_email@gmail.com"   # replace
    app.config['MAIL_PASSWORD'] = "your_app_password"      # replace
    app.config['MAIL_DEFAULT_SENDER'] = "your_email@gmail.com"
    
    mail = Mail(app)
    # ---------- Init Extensions ----------
    db.init_app(app)
    JWTManager(app)
    CORS(app)

    # ---------- Create Tables ----------
    with app.app_context():
        db.create_all()

    # ---------- Routes ----------
    @app.route("/")
    def home():
        return {"message": "Flask backend is running 🚀"}

    # ---------- Register ----------
    @app.route("/register", methods=["POST"])
    def register():
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "user")

        if not username or not email or not password:
            return jsonify({"message": "All fields are required", "success": False}), 400

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"message": "Email already registered", "success": False}), 400

        # Create user
        user = User(username=username, email=email, role=role)
        user.set_password(password)  # uses method in User model
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "User registered successfully", "success": True}), 201

    # ---------- Login ----------
    @app.route("/patient/dashboard", methods=["GET"])
    @jwt_required()
    @role_required(["patient","doctor", "admin"])   # only patient can access
    def patient_dashboard():
       return jsonify({"msg": "Welcome Patient!"})


    @app.route("/doctor/dashboard", methods=["GET"])
    @jwt_required()
    @role_required(["doctor", "admin"])  # doctor and admin can access
    def doctor_dashboard():
       return jsonify({"msg": "Welcome Doctor!"})


    @app.route("/admin/dashboard", methods=["GET"])
    @jwt_required()
    @role_required(["admin"])  # only admin
    def admin_dashboard():
        return jsonify({"msg": "Welcome Admin!"})

    @app.route("/login", methods=["POST"])
    def login():
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"message": "Email and password required", "success": False}), 400

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({"message": "Invalid credentials", "success": False}), 401

        # Create JWT token
        token = create_access_token(
        identity=str(user.id),  
        additional_claims={"role": user.role},
        expires_delta=timedelta(hours=1)
      )

        return jsonify({
            "message": "Login successful",
            "success": True,
            "token": token
        }), 200
    
    
    @app.route("/adminonly", methods=["GET"])
    @jwt_required()
    def admin_only():
        claims = get_jwt()
        if claims.get("role") != "admin":
           return jsonify({"msg": "Admins only!"}), 403
        return jsonify({"msg": "Welcome, Admin!"})


    # ---------- Vitals ----------
   
    @app.route("/vitals/<int:patient_id>", methods=["GET"])
    @jwt_required()
    def get_vitals(patient_id):
        vitals = Vital.query.filter_by(patient_id=patient_id).all()
        return jsonify([v.to_dict() for v in vitals])

    @app.route("/saveVitals", methods=["POST"])
    @jwt_required()
    def save_vitals():
        current_user_id = get_jwt_identity()
        data = request.get_json()
        patient_id = data.get("patient_id")
        hr = data.get("hr")
        spo2 = data.get("spo2")
        temp = data.get("temp")
        rr = data.get("rr", None)

    # Save the vital
        vital = Vital(
           patient_id=patient_id,
           hr=hr,
           spo2=spo2,
           temp=temp,
            rr=rr,
            raw=str(data)
          )
        db.session.add(vital)
        db.session.commit()

    # --------- Automatic alert check ---------
        alert_triggered = False
        alert_message = ""

        if hr and hr > 120:
            alert_triggered = True
            alert_message += f"Heart rate too high ({hr})! "

        if spo2 and spo2 < 90:
            alert_triggered = True
            alert_message += f"SpO2 too low ({spo2})! "

        if alert_triggered:
            alert = Alert(
                patient_id=patient_id,
                severity="Critical",
                message=alert_message
           )
            db.session.add(alert)
            db.session.commit()

        return jsonify({
        "success": True,
        "message": "Vitals saved successfully",
        "alert_triggered": alert_triggered,
        "alert_message": alert_message if alert_triggered else None
        }), 201


    # ---------- Patients ----------
    @app.route("/patients", methods=["POST"])
    @jwt_required()
    def add_patient():
        current_user_id = get_jwt_identity()
        data = request.get_json()
        name = data.get("name")
        age = data.get("age")

        if not name:
            return jsonify({"success": False, "message": "Name is required"}), 400

        patient = Patient(name=name, age=age, owner_id=current_user_id)
        db.session.add(patient)
        db.session.commit()

        return jsonify({"success": True, "patient_id": patient.id, "name": patient.name}), 201

    @app.route("/patients", methods=["GET"])
    @jwt_required()
    def get_patients():
        current_user_id = get_jwt_identity()
        patients = Patient.query.filter_by(owner_id=current_user_id).all()
        return jsonify([
            {"id": p.id, "name": p.name, "age": p.age} for p in patients
        ]), 200

    # ---------- Alerts ----------
    @app.route("/alerts/<int:patient_id>", methods=["GET"])
    @jwt_required()
    def get_alerts(patient_id):
        alerts = Alert.query.filter_by(patient_id=patient_id).all()
        return jsonify([
            {
                "id": a.id,
                "severity": a.severity,
                "message": a.message,
                "timestamp": a.timestamp
            } for a in alerts
        ]), 200

    @app.route("/alerts", methods=["POST"])
    @jwt_required()
    def add_alert():
        data = request.get_json()
        patient_id = data.get("patient_id")
        severity = data.get("severity", "Alert")
        message = data.get("message", "No message provided")

        if not patient_id:
            return jsonify({"success": False, "message": "Patient ID required"}), 400

        alert = Alert(patient_id=patient_id, severity=severity, message=message)
        db.session.add(alert)
        db.session.commit()

        return jsonify({"success": True, "alert_id": alert.id}), 201
    
    @app.route("/send_email", methods=["POST"])
    @jwt_required()
    def send_email():
        claims = get_jwt()
        role = claims.get("role")

    # only doctor and admin can send mails
        if role not in ["doctor", "admin"]:
           return jsonify({"msg": "Not authorized"}), 403

        data = request.get_json()
        recipient = data.get("recipient")
        subject = data.get("subject")
        body = data.get("body")

        if not recipient or not subject or not body:
            return jsonify({"msg": "Missing fields"}), 400

        try:
            msg = Message(subject, recipients=[recipient])
            msg.body = body
            mail.send(msg)
            return jsonify({"msg": "Email sent successfully"})
        except Exception as e:
             return jsonify({"msg": str(e)}), 500
 
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
