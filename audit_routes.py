from flask import Blueprint, jsonify, session, request
from database import get_db_connection

audit_bp = Blueprint('audit', __name__)

ALLOWED_ROLES = ('admin', 'viewer')


def audit_access_required():
    if 'user_id' not in session:
        return jsonify({
            'error': 'Please log in first.'
        }), 401

    if session.get('user_role') not in ALLOWED_ROLES:
        return jsonify({
            'error': 'Access denied. Admin or Viewer permission required.'
        }), 403

    return None


# GET /api/audit/
# Admin and Viewer can view audit history.

@audit_bp.route('/', methods=['GET'])
def get_audit_logs():

    access_error = audit_access_required()

    if access_error:
        return access_error

    db = None
    cursor = None

    try:
        db = get_db_connection()

        if db is None:
            return jsonify({
                'error': 'Database connection failed.'
            }), 500

        cursor = db.cursor(dictionary=True)

        action = request.args.get('action', '').strip()
        module = request.args.get('module', '').strip()

        query = """
            SELECT
                id,
                user_id,
                user_name,
                user_role,
                action,
                module,
                record_id,
                details,
                created_at
            FROM audit_logs
            WHERE 1=1
        """

        params = []

        if action:
            query += " AND action = %s"
            params.append(action)

        if module:
            query += " AND module = %s"
            params.append(module)

        query += " ORDER BY created_at DESC LIMIT 500"

        cursor.execute(query, tuple(params))

        logs = cursor.fetchall()

        for log in logs:
            if log.get('created_at'):
                log['created_at'] = log['created_at'].strftime(
                    '%Y-%m-%d %H:%M:%S'
                )

        return jsonify({
            'total': len(logs),
            'logs': logs
        }), 200

    except Exception as e:
        print('Audit history error:', e)

        return jsonify({
            'error': 'Unable to retrieve audit history.'
        }), 500

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()