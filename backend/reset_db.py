from app import create_app, db

# create the app instance
app = create_app()

# reset database
with app.app_context():
    db.drop_all()
    db.create_all()
    print("Database reset successfully!")
