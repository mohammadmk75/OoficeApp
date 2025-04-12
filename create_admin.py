from app import create_app, db
from app.models import Users
from werkzeug.security import generate_password_hash

def create_admin():
    app = create_app()
    with app.app_context():
        # Check if the admin already exists
        admin = Users.query.filter_by(email='keshavarzi96@gmail.com').first()
        if admin:
            print("Admin user already exists!")
            return

        # Create the admin user
        admin = Users(
            first_name='Mohammad',
            last_name='Keshavarzi',
            email='Keshavarzi96@gmail.com',
            phone_number='09198012887',
            password=generate_password_hash('22317677@Mk'),  # Set a secure password
            group='Admin',
            is_superuser=True
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")

if __name__ == '__main__':
    create_admin()
