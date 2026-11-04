from database import get_db_connection
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

name = "Field Officer"
email = "officer@ecotrack.com"
password = "Officer@123"
role = "field_officer"

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
            print("Field Officer account already exists!")

        else:
            hashed_password = bcrypt.generate_password_hash(
                password
            ).decode("utf-8")

            cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (%s, %s, %s, %s)
            """, (name, email, hashed_password, role))

            db.commit()

            print("Field Officer account created successfully!")

    except Exception as e:
        db.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        db.close()

else:
    print("Database connection failed!")