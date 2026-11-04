
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from audit_logger import log_audit
from datetime import date

sustainability_bp = Blueprint('sustainability', __name__)

VALID_ROLES = ('admin', 'viewer', 'field_officer')

VALID_ACTIVITIES = (
    'Tree Plantation',
    'Water Conservation',
    'Energy Conservation',
    'Waste Management',
    'Sustainable Agriculture'
)


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
        return jsonify({'error': 'Please login first.'}), 401

    if session.get('user_role') != 'admin':
        return jsonify({
            'error': 'Only Admin can perform this operation.'
        }), 403

    return None


def edit_required():
    if not logged_in():
        return jsonify({'error': 'Please login first.'}), 401

    if session.get('user_role') not in ('admin', 'field_officer'):
        return jsonify({
            'error': 'Viewer accounts have read-only access.'
        }), 403

    return None


# --------------------------------------------------
# VALIDATION
# --------------------------------------------------

def validate_record(data, existing=None):
    existing = existing or {}

    project_id = data.get(
        'project_id', existing.get('project_id')
    )

    activity_type = data.get(
        'activity_type', existing.get('activity_type')
    )

    target_value = data.get(
        'target_value', existing.get('target_value')
    )

    achieved_value = data.get(
        'achieved_value', existing.get('achieved_value')
    )

    unit = data.get('unit', existing.get('unit'))

    activity_date = data.get(
        'activity_date', existing.get('activity_date')
    )

    if not project_id:
        return None, 'Project is required.'

    if activity_type not in VALID_ACTIVITIES:
        return None, 'Select a valid activity type.'

    try:
        project_id = int(project_id)
        target_value = float(target_value)
        achieved_value = float(achieved_value)

        if project_id <= 0:
            return None, 'Invalid project.'

        if target_value <= 0:
            return None, 'Target value must be greater than zero.'

        if achieved_value < 0:
            return None, 'Achieved value cannot be negative.'

        if achieved_value > target_value:
            return None, 'Achieved value cannot exceed target value.'

    except (ValueError, TypeError):
        return None, 'Enter valid numeric values.'

    if not unit or not str(unit).strip():
        return None, 'Unit is required.'

    if not activity_date:
        return None, 'Activity date is required.'

    try:
        if isinstance(activity_date, date):
            activity_date = activity_date
        else:
            activity_date = date.fromisoformat(str(activity_date))
    except (ValueError, TypeError):
        return None, 'Enter a valid activity date.'

    return {
        'project_id': project_id,
        'activity_type': activity_type,
        'target_value': target_value,
        'achieved_value': achieved_value,
        'unit': str(unit).strip(),
        'activity_date': activity_date
    }, None


def project_exists(cursor, project_id):
    cursor.execute(
        'SELECT id FROM projects WHERE id = %s',
        (project_id,)
    )
    return cursor.fetchone() is not None


# --------------------------------------------------
# VIEW ALL RECORDS
# GET /api/sustainability/
# --------------------------------------------------

@sustainability_bp.route('/', methods=['GET'])
def get_sustainability():

    if not logged_in():
        return jsonify({'error': 'Please login first.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT s.*, p.project_name
            FROM sustainability s
            LEFT JOIN projects p ON s.project_id = p.id
            ORDER BY s.id DESC
        """)

        records = cursor.fetchall()

        for record in records:
            target = float(record['target_value'] or 0)
            achieved = float(record['achieved_value'] or 0)

            record['progress'] = round(
                (achieved / target) * 100, 2
            ) if target > 0 else 0

        return jsonify({
            'total_records': len(records),
            'records': records,
            'activities': records
        }), 200

    except Exception as e:
        print('Sustainability retrieval error:', e)

        return jsonify({
            'error': 'Unable to retrieve sustainability records.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# ADD RECORD - ADMIN ONLY
# POST /api/sustainability/add
# --------------------------------------------------

@sustainability_bp.route('/add', methods=['POST'])
def add_sustainability():

    access_error = admin_required()
    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    record, error = validate_record(data)

    if error:
        return jsonify({'error': error}), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        if not project_exists(cursor, record['project_id']):
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            INSERT INTO sustainability
            (project_id, activity_type, target_value,
             achieved_value, unit, activity_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            record['project_id'],
            record['activity_type'],
            record['target_value'],
            record['achieved_value'],
            record['unit'],
            record['activity_date']
        ))

        record_id = cursor.lastrowid
        db.commit()

        # AUDIT LOG: CREATE
        log_audit(
            'CREATE',
            'Sustainability',
            record_id,
            f"Added {record['activity_type']} activity "
            f"for project ID {record['project_id']}"
        )

        return jsonify({
            'message': 'Sustainability record added successfully.',
            'record_id': record_id
        }), 201

    except Exception as e:
        db.rollback()
        print('Add sustainability error:', e)

        return jsonify({
            'error': 'Unable to add sustainability record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# UPDATE RECORD - ADMIN AND FIELD OFFICER
# PUT /api/sustainability/update/<record_id>
# --------------------------------------------------

@sustainability_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_sustainability(record_id):

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
            FROM sustainability
            WHERE id = %s
        """, (record_id,))

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Sustainability record not found.'
            }), 404

        record, error = validate_record(data, existing)

        if error:
            return jsonify({'error': error}), 400

        if not project_exists(cursor, record['project_id']):
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            UPDATE sustainability
            SET project_id = %s,
                activity_type = %s,
                target_value = %s,
                achieved_value = %s,
                unit = %s,
                activity_date = %s
            WHERE id = %s
        """, (
            record['project_id'],
            record['activity_type'],
            record['target_value'],
            record['achieved_value'],
            record['unit'],
            record['activity_date'],
            record_id
        ))

        db.commit()

        # AUDIT LOG: UPDATE
        log_audit(
            'UPDATE',
            'Sustainability',
            record_id,
            f"Updated {record['activity_type']} activity "
            f"for project ID {record['project_id']}"
        )

        return jsonify({
            'message': 'Sustainability record updated successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Update sustainability error:', e)

        return jsonify({
            'error': 'Unable to update sustainability record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# DELETE RECORD - ADMIN ONLY
# DELETE /api/sustainability/delete/<record_id>
# --------------------------------------------------

@sustainability_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_sustainability(record_id):

    access_error = admin_required()
    if access_error:
        return access_error

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        # Fetch details before deleting the record
        cursor.execute("""
            SELECT project_id, activity_type
            FROM sustainability
            WHERE id = %s
        """, (record_id,))

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Sustainability record not found.'
            }), 404

        cursor.execute("""
            DELETE FROM sustainability
            WHERE id = %s
        """, (record_id,))

        db.commit()

        # AUDIT LOG: DELETE
        log_audit(
            'DELETE',
            'Sustainability',
            record_id,
            f"Deleted {existing['activity_type']} activity "
            f"from project ID {existing['project_id']}"
        )

        return jsonify({
            'message': 'Sustainability record deleted successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Delete sustainability error:', e)

        return jsonify({
            'error': 'Unable to delete sustainability record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()

