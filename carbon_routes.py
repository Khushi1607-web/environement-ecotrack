
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from decimal import Decimal, InvalidOperation

carbon_bp = Blueprint('carbon', __name__)

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
# VIEW ALL CARBON RECORDS
# ALL THREE ROLES
# GET /api/carbon/
# --------------------------------------------------

@carbon_bp.route('/', methods=['GET'])
def get_carbon():

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
            FROM carbon_management c
            LEFT JOIN projects p ON c.project_id = p.id
            ORDER BY c.id DESC
        """)

        records = cursor.fetchall()

        for record in records:
            record['emission_value'] = float(
                record['emission_value'] or 0
            )
            record['reduction_value'] = float(
                record['reduction_value'] or 0
            )
            record['sequestration_value'] = float(
                record['sequestration_value'] or 0
            )

            emission = record['emission_value']
            reduction = record['reduction_value']

            record['reduction_percentage'] = round(
                (reduction / emission) * 100, 2
            ) if emission > 0 else 0

        return jsonify({
            'total_records': len(records),
            'records': records
        }), 200

    except Exception as e:
        print('Carbon retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve carbon records.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# VIEW SINGLE CARBON RECORD
# ALL THREE ROLES
# GET /api/carbon/<record_id>
# --------------------------------------------------

@carbon_bp.route('/<int:record_id>', methods=['GET'])
def get_carbon_record(record_id):

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
            FROM carbon_management c
            LEFT JOIN projects p ON c.project_id = p.id
            WHERE c.id = %s
        """, (record_id,))

        record = cursor.fetchone()

        if not record:
            return jsonify({'error': 'Carbon record not found.'}), 404

        for field in (
            'emission_value',
            'reduction_value',
            'sequestration_value'
        ):
            record[field] = float(record[field] or 0)

        return jsonify(record), 200

    except Exception as e:
        print('Carbon record retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve carbon record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# ADD CARBON RECORD
# ADMIN ONLY
# POST /api/carbon/add
# --------------------------------------------------

@carbon_bp.route('/add', methods=['POST'])
def add_carbon():

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    project_id = data.get('project_id')
    unit = (data.get('unit') or '').strip()
    record_date = data.get('record_date')

    if not project_id or not unit or not record_date:
        return jsonify({
            'error': 'Project, unit and record date are required.'
        }), 400

    try:
        project_id = int(project_id)

        if project_id <= 0:
            raise ValueError

        emission = valid_number(
            data.get('emission_value'), 'Emission value'
        )

        reduction = valid_number(
            data.get('reduction_value', 0), 'Reduction value'
        )

        sequestration = valid_number(
            data.get('sequestration_value', 0),
            'Sequestration value'
        )

        if reduction > emission:
            return jsonify({
                'error': 'Reduction cannot exceed emissions.'
            }), 400

        from datetime import date
        record_date = date.fromisoformat(str(record_date))

    except (ValueError, TypeError):
        return jsonify({
            'error': 'Enter valid project, carbon values and date.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM projects WHERE id = %s",
            (project_id,)
        )

        if not cursor.fetchone():
            return jsonify({
                'error': 'Selected project does not exist.'
            }), 404

        cursor.execute("""
            INSERT INTO carbon_management
            (project_id, emission_value, reduction_value,
             sequestration_value, unit, record_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            project_id,
            emission,
            reduction,
            sequestration,
            unit,
            record_date
        ))

        db.commit()

        return jsonify({
            'message': 'Carbon record added successfully.',
            'record_id': cursor.lastrowid
        }), 201

    except Exception as e:
        db.rollback()
        print('Add carbon error:', e)
        return jsonify({
            'error': 'Unable to add carbon record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# UPDATE CARBON RECORD
# ADMIN AND FIELD OFFICER
# PUT /api/carbon/update/<record_id>
# --------------------------------------------------

@carbon_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_carbon(record_id):

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
            FROM carbon_management
            WHERE id = %s
        """, (record_id,))

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Carbon record not found.'
            }), 404

        project_id = data.get(
            'project_id', existing['project_id']
        )

        emission = data.get(
            'emission_value', existing['emission_value']
        )

        reduction = data.get(
            'reduction_value', existing['reduction_value']
        )

        sequestration = data.get(
            'sequestration_value',
            existing['sequestration_value']
        )

        unit = data.get('unit', existing['unit'])
        record_date = data.get(
            'record_date', existing['record_date']
        )

        try:
            project_id = int(project_id)

            if project_id <= 0:
                raise ValueError

            emission = valid_number(emission, 'Emission value')
            reduction = valid_number(reduction, 'Reduction value')
            sequestration = valid_number(
                sequestration, 'Sequestration value'
            )

            if reduction > emission:
                return jsonify({
                    'error': 'Reduction cannot exceed emissions.'
                }), 400

            from datetime import date
            record_date = date.fromisoformat(str(record_date))

        except (ValueError, TypeError):
            return jsonify({
                'error': 'Enter valid project, carbon values and date.'
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
            UPDATE carbon_management
            SET project_id = %s,
                emission_value = %s,
                reduction_value = %s,
                sequestration_value = %s,
                unit = %s,
                record_date = %s
            WHERE id = %s
        """, (
            project_id,
            emission,
            reduction,
            sequestration,
            str(unit).strip(),
            record_date,
            record_id
        ))

        db.commit()

        return jsonify({
            'message': 'Carbon record updated successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Update carbon error:', e)
        return jsonify({
            'error': 'Unable to update carbon record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# DELETE CARBON RECORD
# ADMIN ONLY
# DELETE /api/carbon/delete/<record_id>
# --------------------------------------------------

@carbon_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_carbon(record_id):

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
            DELETE FROM carbon_management
            WHERE id = %s
        """, (record_id,))

        if cursor.rowcount == 0:
            return jsonify({
                'error': 'Carbon record not found.'
            }), 404

        db.commit()

        return jsonify({
            'message': 'Carbon record deleted successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Delete carbon error:', e)
        return jsonify({
            'error': 'Unable to delete carbon record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()
