from flask import Flask
from flask_mail import Mail, Message

app = Flask(__name__)

# Gmail SMTP settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'keerthikachar11@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'  # <- Use app password, not Gmail password
app.config['MAIL_DEFAULT_SENDER'] = 'keerthikachar11@gmail.com'

mail = Mail(app)

@app.route("/send-mail")
def send_mail():
    try:
        msg = Message("Test Mail from Flask",
                      recipients=["receiver_email@gmail.com"])
        msg.body = "Hello! This is a test mail from Flask-Mail."
        mail.send(msg)
        return "Mail sent successfully!"
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    app.run(debug=True)
