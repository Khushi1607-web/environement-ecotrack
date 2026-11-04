import mysql.connector
from config import Config

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            connection_timeout=30,
            **(
                {
                    "ssl_ca": Config.DB_SSL_CA,
                    "ssl_verify_cert": True
                }
                if Config.DB_SSL_CA else {}
            )
        )

        return connection

    except mysql.connector.Error as e:
        print("Database Error:", e)
        return None