from database import get_db_connection

db = get_db_connection()

if db:
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT id, name, email, role FROM users WHERE email = %s",
        ("officer@ecotrack.com",)
    )

    result = cursor.fetchall()

    print("\nFIELD OFFICER ACCOUNT DETAILS:")
    print(result)

    cursor.close()
    db.close()

else:
    print("Database connection failed!")