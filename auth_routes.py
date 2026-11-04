
from flask import Blueprint, request, jsonify, session
from flask_bcrypt import Bcrypt
from database import get_db_connection

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

# Only these three roles are allowed.
VALID_ROLES = ('admin', 'viewer', 'field_officer')


# Check whether the logged-in user is an Admin.
def admin_required():
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in first.'}), 401

    if session.get('user_role') != 'admin':
        return jsonify({
            'error': 'Access denied. Admin permission required.'
        }), 403

    return None


# --------------------------------------------------
# REGISTER
# Public registration creates Field Officer accounts only.
# --------------------------------------------------

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not name or not email or not password:
        return jsonify({
            'error': 'Name, email and password are required.'
        }), 400

    if len(password) < 8:
        return jsonify({
            'error': 'Password must contain at least 8 characters.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            return jsonify({
                'error': 'Email already registered.'
            }), 409

        hashed_password = bcrypt.generate_password_hash(
            password
        ).decode('utf-8')

        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, 'field_officer')
        """, (name, email, hashed_password))

        db.commit()

        return jsonify({
            'message': 'Field Officer account created successfully.',
            'role': 'field_officer'
        }), 201

    except Exception:
        db.rollback()
        return jsonify({
            'error': 'Unable to create account.'
        }), 500

    finally:
        cursor.close()
        db.close()


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({
            'error': 'Email and password are required.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, email, password, role
            FROM users
            WHERE email = %s
        """, (email,))

        user = cursor.fetchone()

        if not user or not bcrypt.check_password_hash(
            user['password'], password
        ):
            return jsonify({
                'error': 'Invalid email or password.'
            }), 401

        if user['role'] not in VALID_ROLES:
            return jsonify({
                'error': 'Your account has an invalid role. Contact Admin.'
            }), 403

        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_role'] = user['role']

        return jsonify({
            'message': 'Login successful.',
            'user': {
                'id': user['id'],
                'name': user['name'],
                'email': user['email'],
                'role': user['role']
            }
        }), 200

    except Exception:
        return jsonify({
            'error': 'Unable to log in. Please try again.'
        }), 500

    finally:
        cursor.close()
        db.close()


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()

    return jsonify({
        'message': 'Logged out successfully.'
    }), 200


# --------------------------------------------------
# CHECK CURRENT SESSION
# --------------------------------------------------

@auth_bp.route('/check-session', methods=['GET'])
def check_session():
    if 'user_id' not in session:
        return jsonify({'logged_in': False}), 401

    return jsonify({
        'logged_in': True,
        'user_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'user_role': session.get('user_role')
    }), 200


# --------------------------------------------------
# ADMIN: VIEW ALL USERS
# GET /api/auth/users
# --------------------------------------------------

@auth_bp.route('/users', methods=['GET'])
def get_users():
    access_error = admin_required()

    if access_error:
        return access_error

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id, name, email, role, created_at
            FROM users
            ORDER BY id DESC
        """)

        users = cursor.fetchall()

        return jsonify({'users': users}), 200

    except Exception:
        return jsonify({'error': 'Unable to retrieve users.'}), 500

    finally:
        cursor.close()
        db.close()


# --------------------------------------------------
# ADMIN: UPDATE A USER'S ROLE
# PUT /api/auth/users/<user_id>/role
# --------------------------------------------------

@auth_bp.route('/users/<int:user_id>/role', methods=['PUT'])
def update_user_role(user_id):
    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}
    new_role = (data.get('role') or '').strip().lower()

    if new_role not in VALID_ROLES:
        return jsonify({
            'error': 'Invalid role. Choose Admin, Viewer or Field Officer.'
        }), 400

    # Prevent the logged-in Admin from accidentally removing
    # their own Admin access.
    if user_id == session.get('user_id') and new_role != 'admin':
        return jsonify({
            'error': 'You cannot remove your own Admin role.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = db.cursor()

    try:
        cursor.execute(
            "SELECT id FROM users WHERE id = %s",
            (user_id,)
        )

        if not cursor.fetchone():
            return jsonify({'error': 'User not found.'}), 404

        cursor.execute("""
            UPDATE users
            SET role = %s
            WHERE id = %s
        """, (new_role, user_id))

        db.commit()

        return jsonify({
            'message': 'User role updated successfully.',
            'user_id': user_id,
            'role': new_role
        }), 200

    except Exception:
        db.rollback()
        return jsonify({
            'error': 'Unable to update user role.'
        }), 500

    finally:
        cursor.close()
        db.close()
