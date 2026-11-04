from database import get_db_connection
from flask import session


def log_audit(action, module, record_id=None, details=None):

    db = None
    cursor = None

    try:
        if 'user_id' not in session:
            return False

        db = get_db_connection()

        if not db:
            return False

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO audit_logs
            (user_id, user_name, user_role, action,
             module, record_id, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            session.get('user_id'),
            session.get('user_name'),
            session.get('user_role'),
            action,
            module,
            record_id,
            details
        ))

        db.commit()
        return True

    except Exception as e:
        if db:
            db.rollback()

        print("Audit logging error:", e)
        return False

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()