from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from models import db, User, Patient, Vital, Alert
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS
from datetime import timedelta

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

        if not username or not email or not password:
            return jsonify({"message": "All fields are required", "success": False}), 400

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"message": "Email already registered", "success": False}), 400

        # Create user
        user = User(username=username, email=email)
        user.set_password(password)  # uses method in User model
        db.session.add(user)
        db.session.commit()

        return jsonify({"message": "User registered successfully", "success": True}), 201

    # ---------- Login ----------
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
        token = create_access_token(identity=str(user.id), expires_delta=timedelta(hours=1))

        return jsonify({
            "message": "Login successful",
            "success": True,
            "token": token
        }), 200

    # ---------- Save Vitals ----------
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

        return jsonify({"success": True, "message": "Vitals saved successfully"}), 201

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
