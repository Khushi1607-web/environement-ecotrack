
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from decimal import Decimal, InvalidOperation
from datetime import date

carbon_credit_bp = Blueprint('carbon_credits', __name__)

VALID_ROLES = ('admin', 'viewer', 'field_officer')
VALID_STATUSES = ('Pending', 'Under Review', 'Verified', 'Rejected')


# --------------------------------------------------
# ROLE CHECKS
# --------------------------------------------------

def logged_in():
    return (
        'user_id' in session
        and session.get('user_role') in VALID_ROLES
    )


def admin_required():
    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    if session.get('user_role') != 'admin':
        return jsonify({
            'error': 'Only Admin can perform this operation.'
        }), 403

    return None


def edit_required():
    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    if session.get('user_role') not in ('admin', 'field_officer'):
        return jsonify({
            'error': 'Viewer accounts have read-only access.'
        }), 403

    return None


# --------------------------------------------------
# NUMBER VALIDATION
# --------------------------------------------------

def valid_number(value, field_name):
    try:
        number = Decimal(str(value))

        if not number.is_finite() or number < 0:
            raise ValueError

        return number

    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(
            f'{field_name} must be a valid non-negative number.'
        )


# --------------------------------------------------
# RECORD VALIDATION
# --------------------------------------------------

def validate_credit_data(data, existing=None):

    existing = existing or {}

    project_id = data.get('project_id', existing.get('project_id'))

    estimated = data.get(
        'estimated_credits', existing.get('estimated_credits')
    )

    verified = data.get(
        'verified_credits', existing.get('verified_credits')
    )

    issued = data.get(
        'issued_credits', existing.get('issued_credits')
    )

    status = data.get(
        'verification_status',
        existing.get('verification_status', 'Pending')
    )

    standard = data.get(
        'standard_name', existing.get('standard_name')
    )

    verification_date = data.get(
        'verification_date', existing.get('verification_date')
    )

    try:
        project_id = int(project_id)

        if project_id <= 0:
            raise ValueError

        estimated = valid_number(
            estimated, 'Estimated credits'
        )

        verified = valid_number(
            verified, 'Verified credits'
        )

        issued = valid_number(
            issued, 'Issued credits'
        )

    except (ValueError, TypeError):
        raise ValueError('Enter valid project and credit values.')

    if not (issued <= verified <= estimated):
        raise ValueError(
            'Issued credits cannot exceed verified credits, '
            'and verified credits cannot exceed estimated credits.'
        )

    if status not in VALID_STATUSES:
        raise ValueError('Invalid verification status.')

    if status == 'Verified' and verified <= 0:
        raise ValueError(
            'Verified credits must be greater than zero '
            'for Verified status.'
        )

    if issued > 0 and status != 'Verified':
        raise ValueError(
            'Credits can only be issued when status is Verified.'
        )

    if verification_date:
        try:
            verification_date = date.fromisoformat(
                str(verification_date)
            )
        except (ValueError, TypeError):
            raise ValueError('Enter a valid verification date.')

    return {
        'project_id': project_id,
        'estimated_credits': estimated,
        'verified_credits': verified,
        'issued_credits': issued,
        'verification_status': status,
        'standard_name': standard,
        'verification_date': verification_date
    }


# --------------------------------------------------
# VIEW ALL CARBON CREDIT RECORDS
# ALL THREE ROLES
# GET /api/carbon-credits/
# --------------------------------------------------

@carbon_credit_bp.route('/', methods=['GET'])
def get_carbon_credits():

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.*, p.project_name
            FROM carbon_credits c
            LEFT JOIN projects p ON c.project_id = p.id
            ORDER BY c.id DESC
        """)

        records = cursor.fetchall()

        for record in records:
            for field in (
                'estimated_credits',
                'verified_credits',
                'issued_credits'
            ):
                record[field] = float(record[field] or 0)

        return jsonify({
            'total_records': len(records),
            'records': records
        }), 200

    except Exception as e:
        print('Carbon credit retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve carbon credit records.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# VIEW SINGLE CARBON CREDIT RECORD
# ALL THREE ROLES
# GET /api/carbon-credits/<record_id>
# --------------------------------------------------

@carbon_credit_bp.route('/<int:record_id>', methods=['GET'])
def get_carbon_credit(record_id):

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT c.*, p.project_name
            FROM carbon_credits c
            LEFT JOIN projects p ON c.project_id = p.id
            WHERE c.id = %s
        """, (record_id,))

        record = cursor.fetchone()

        if not record:
            return jsonify({
                'error': 'Carbon credit record not found.'
            }), 404

        for field in (
            'estimated_credits',
            'verified_credits',
            'issued_credits'
        ):
            record[field] = float(record[field] or 0)

        return jsonify(record), 200

    except Exception as e:
        print('Carbon credit retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve carbon credit record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# ADD CARBON CREDIT RECORD
# ADMIN ONLY
# POST /api/carbon-credits/add
# --------------------------------------------------

@carbon_credit_bp.route('/add', methods=['POST'])
def add_carbon_credit():

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    try:
        record = validate_credit_data(data)

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM projects WHERE id = %s",
            (record['project_id'],)
        )

        if not cursor.fetchone():
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            INSERT INTO carbon_credits
            (project_id, estimated_credits, verified_credits,
             issued_credits, verification_status,
             standard_name, verification_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            record['project_id'],
            record['estimated_credits'],
            record['verified_credits'],
            record['issued_credits'],
            record['verification_status'],
            record['standard_name'],
            record['verification_date']
        ))

        db.commit()

        return jsonify({
            'message': 'Carbon credit record added successfully.',
            'record_id': cursor.lastrowid
        }), 201

    except Exception as e:
        db.rollback()
        print('Add carbon credit error:', e)
        return jsonify({
            'error': 'Unable to add carbon credit record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# UPDATE CARBON CREDIT RECORD
# ADMIN AND FIELD OFFICER
# PUT /api/carbon-credits/update/<record_id>
# --------------------------------------------------

@carbon_credit_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_carbon_credit(record_id):

    access_error = edit_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM carbon_credits
            WHERE id = %s
        """, (record_id,))

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Carbon credit record not found.'
            }), 404

        try:
            record = validate_credit_data(data, existing)
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        cursor.execute(
            "SELECT id FROM projects WHERE id = %s",
            (record['project_id'],)
        )

        if not cursor.fetchone():
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            UPDATE carbon_credits
            SET project_id = %s,
                estimated_credits = %s,
                verified_credits = %s,
                issued_credits = %s,
                verification_status = %s,
                standard_name = %s,
                verification_date = %s
            WHERE id = %s
        """, (
            record['project_id'],
            record['estimated_credits'],
            record['verified_credits'],
            record['issued_credits'],
            record['verification_status'],
            record['standard_name'],
            record['verification_date'],
            record_id
        ))

        db.commit()

        return jsonify({
            'message': 'Carbon credit record updated successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Update carbon credit error:', e)
        return jsonify({
            'error': 'Unable to update carbon credit record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# DELETE CARBON CREDIT RECORD
# ADMIN ONLY
# DELETE /api/carbon-credits/delete/<record_id>
# --------------------------------------------------

@carbon_credit_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_carbon_credit(record_id):

    access_error = admin_required()

    if access_error:
        return access_error

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute("""
            DELETE FROM carbon_credits
            WHERE id = %s
        """, (record_id,))

        if cursor.rowcount == 0:
            return jsonify({
                'error': 'Carbon credit record not found.'
            }), 404

        db.commit()

        return jsonify({
            'message': 'Carbon credit record deleted successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Delete carbon credit error:', e)
        return jsonify({
            'error': 'Unable to delete carbon credit record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()
