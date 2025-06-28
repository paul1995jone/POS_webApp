from app import db, create_default_admin, app

with app.app_context():
    db.create_all()
    create_default_admin()
    print("✅ Database tables created and default admin initialized.")
