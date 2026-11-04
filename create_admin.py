from database import get_db_connection
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

name = "EcoTrack Admin"
email = "admin@ecotrack.com"
password = "Admin@123"

hashed_password = bcrypt.generate_password_hash(
    password
).decode('utf-8')

db = get_db_connection()

if db:
    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:
            print("Admin account already exists.")

        else:
            cursor.execute(
                """
                INSERT INTO users (name, email, password, role)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email, hashed_password, 'admin')
            )

            db.commit()
            print("Admin account created successfully!")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        db.close()

else:
    print("Database connection failed.")