
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from decimal import Decimal, InvalidOperation

restoration_bp = Blueprint('restoration', __name__)

VALID_ROLES = ('admin', 'viewer', 'field_officer')


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
# GET: VIEW ALL RESTORATION RECORDS
# ALL THREE ROLES
# --------------------------------------------------

@restoration_bp.route('/', methods=['GET'])
def get_restoration():

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.*, p.project_name
            FROM restoration r
            JOIN projects p ON r.project_id = p.id
            ORDER BY r.id DESC
        """)

        records = cursor.fetchall()

        for record in records:
            target = float(record['target_area'] or 0)
            restored = float(record['restored_area'] or 0)

            record['target_area'] = target
            record['restored_area'] = restored

            record['progress'] = round(
                (restored / target) * 100, 2
            ) if target > 0 else 0

        return jsonify({
            'total_records': len(records),
            'restoration': records
        }), 200

    except Exception as e:
        print('Restoration retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve restoration records.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# POST: ADD RESTORATION RECORD
# ADMIN ONLY
# --------------------------------------------------

@restoration_bp.route('/add', methods=['POST'])
def add_restoration():

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    project_id = data.get('project_id')
    restoration_type = (data.get('restoration_type') or '').strip()
    unit = (data.get('unit') or 'Acres').strip()
    description = (data.get('description') or '').strip()

    if not project_id or not restoration_type:
        return jsonify({
            'error': 'Project and restoration type are required.'
        }), 400

    try:
        project_id = int(project_id)

        target_area = valid_number(
            data.get('target_area'), 'Target area'
        )

        restored_area = valid_number(
            data.get('restored_area', 0), 'Restored area'
        )

        if project_id <= 0:
            return jsonify({'error': 'Invalid project ID.'}), 400

        if target_area <= 0:
            return jsonify({
                'error': 'Target area must be greater than zero.'
            }), 400

        if restored_area > target_area:
            return jsonify({
                'error': 'Restored area cannot exceed target area.'
            }), 400

    except (ValueError, TypeError):
        return jsonify({
            'error': 'Invalid project ID or area value.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM projects WHERE id = %s",
            (project_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            INSERT INTO restoration
            (project_id, restoration_type, target_area,
             restored_area, unit, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            project_id,
            restoration_type,
            target_area,
            restored_area,
            unit,
            description
        ))

        db.commit()

        progress = round(
            float(restored_area / target_area * 100), 2
        )

        return jsonify({
            'message': 'Restoration record added successfully.',
            'id': cursor.lastrowid,
            'progress': progress
        }), 201

    except Exception as e:
        db.rollback()
        print('Add restoration error:', e)
        return jsonify({
            'error': 'Unable to add restoration record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# PUT: UPDATE RESTORATION RECORD
# ADMIN AND FIELD OFFICER
# --------------------------------------------------

@restoration_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_restoration(record_id):

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

        cursor.execute(
            "SELECT * FROM restoration WHERE id = %s",
            (record_id,)
        )

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Restoration record not found.'
            }), 404

        project_id = data.get(
            'project_id', existing['project_id']
        )

        restoration_type = data.get(
            'restoration_type', existing['restoration_type']
        )

        target_area = data.get(
            'target_area', existing['target_area']
        )

        restored_area = data.get(
            'restored_area', existing['restored_area']
        )

        unit = data.get('unit', existing['unit'])
        description = data.get(
            'description', existing['description']
        )

        try:
            project_id = int(project_id)

            target_area = valid_number(
                target_area, 'Target area'
            )

            restored_area = valid_number(
                restored_area, 'Restored area'
            )

            if project_id <= 0:
                return jsonify({
                    'error': 'Invalid project ID.'
                }), 400

            if target_area <= 0:
                return jsonify({
                    'error': 'Target area must be greater than zero.'
                }), 400

            if restored_area > target_area:
                return jsonify({
                    'error': 'Restored area cannot exceed target area.'
                }), 400

        except (ValueError, TypeError):
            return jsonify({
                'error': 'Invalid project ID or area value.'
            }), 400

        if not str(restoration_type or '').strip():
            return jsonify({
                'error': 'Restoration type is required.'
            }), 400

        if not str(unit or '').strip():
            return jsonify({'error': 'Unit is required.'}), 400

        cursor.execute(
            "SELECT id FROM projects WHERE id = %s",
            (project_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            UPDATE restoration
            SET project_id = %s,
                restoration_type = %s,
                target_area = %s,
                restored_area = %s,
                unit = %s,
                description = %s
            WHERE id = %s
        """, (
            project_id,
            str(restoration_type).strip(),
            target_area,
            restored_area,
            str(unit).strip(),
            description,
            record_id
        ))

        db.commit()

        progress = round(
            float(restored_area / target_area * 100), 2
        )

        return jsonify({
            'message': 'Restoration record updated successfully.',
            'progress': progress
        }), 200

    except Exception as e:
        db.rollback()
        print('Update restoration error:', e)
        return jsonify({
            'error': 'Unable to update restoration record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# DELETE: ADMIN ONLY
# --------------------------------------------------

@restoration_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_restoration(record_id):

    access_error = admin_required()

    if access_error:
        return access_error

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute(
            "DELETE FROM restoration WHERE id = %s",
            (record_id,)
        )

        if cursor.rowcount == 0:
            return jsonify({
                'error': 'Restoration record not found.'
            }), 404

        db.commit()

        return jsonify({
            'message': 'Restoration record deleted successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Delete restoration error:', e)
        return jsonify({
            'error': 'Unable to delete restoration record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()

