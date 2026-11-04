
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from datetime import date

biodiversity_bp = Blueprint('biodiversity', __name__)

VALID_ROLES = ('admin', 'viewer', 'field_officer')

VALID_CONSERVATION_STATUSES = (
    'Least Concern',
    'Near Threatened',
    'Vulnerable',
    'Endangered',
    'Critically Endangered',
    'Extinct in the Wild',
    'Not Evaluated',
    'Data Deficient'
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
# VALIDATE BIODIVERSITY DATA
# --------------------------------------------------

def validate_biodiversity_data(data, existing=None):

    existing = existing or {}

    project_id = data.get(
        'project_id', existing.get('project_id')
    )

    species_name = data.get(
        'species_name', existing.get('species_name')
    )

    species_type = data.get(
        'species_type', existing.get('species_type')
    )

    conservation_status = data.get(
        'conservation_status',
        existing.get('conservation_status', 'Not Evaluated')
    )

    observation_date = data.get(
        'observation_date', existing.get('observation_date')
    )

    description = data.get(
        'description', existing.get('description')
    )

    try:
        project_id = int(project_id)

        if project_id <= 0:
            raise ValueError

    except (ValueError, TypeError):
        raise ValueError('Enter a valid project ID.')

    if not species_name or not str(species_name).strip():
        raise ValueError('Species name is required.')

    if not species_type or not str(species_type).strip():
        raise ValueError('Species type is required.')

    if conservation_status not in VALID_CONSERVATION_STATUSES:
        raise ValueError('Select a valid conservation status.')

    if not observation_date:
        raise ValueError('Observation date is required.')

    try:
        observation_date = date.fromisoformat(
            str(observation_date)
        )
    except (ValueError, TypeError):
        raise ValueError('Enter a valid observation date.')

    return {
        'project_id': project_id,
        'species_name': str(species_name).strip(),
        'species_type': str(species_type).strip(),
        'conservation_status': conservation_status,
        'observation_date': observation_date,
        'description': (
            str(description).strip() if description else None
        )
    }


# --------------------------------------------------
# VIEW ALL BIODIVERSITY RECORDS
# ALL THREE ROLES
# GET /api/biodiversity/
# --------------------------------------------------

@biodiversity_bp.route('/', methods=['GET'])
def get_biodiversity():

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT b.*, p.project_name
            FROM biodiversity b
            LEFT JOIN projects p ON b.project_id = p.id
            ORDER BY b.id DESC
        """)

        records = cursor.fetchall()

        return jsonify({
            'total_records': len(records),
            'records': records
        }), 200

    except Exception as e:
        print('Biodiversity retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve biodiversity records.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# VIEW SINGLE BIODIVERSITY RECORD
# ALL THREE ROLES
# GET /api/biodiversity/<record_id>
# --------------------------------------------------

@biodiversity_bp.route('/<int:record_id>', methods=['GET'])
def get_biodiversity_record(record_id):

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed.'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT b.*, p.project_name
            FROM biodiversity b
            LEFT JOIN projects p ON b.project_id = p.id
            WHERE b.id = %s
        """, (record_id,))

        record = cursor.fetchone()

        if not record:
            return jsonify({
                'error': 'Biodiversity record not found.'
            }), 404

        return jsonify(record), 200

    except Exception as e:
        print('Biodiversity record retrieval error:', e)
        return jsonify({
            'error': 'Unable to retrieve biodiversity record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# ADD BIODIVERSITY RECORD
# ADMIN ONLY
# POST /api/biodiversity/add
# --------------------------------------------------

@biodiversity_bp.route('/add', methods=['POST'])
def add_biodiversity():

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    try:
        record = validate_biodiversity_data(data)
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
            INSERT INTO biodiversity
            (project_id, species_name, species_type,
             conservation_status, observation_date, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            record['project_id'],
            record['species_name'],
            record['species_type'],
            record['conservation_status'],
            record['observation_date'],
            record['description']
        ))

        db.commit()

        return jsonify({
            'message': 'Biodiversity record added successfully.',
            'record_id': cursor.lastrowid
        }), 201

    except Exception as e:
        db.rollback()
        print('Add biodiversity error:', e)
        return jsonify({
            'error': 'Unable to add biodiversity record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# UPDATE BIODIVERSITY RECORD
# ADMIN AND FIELD OFFICER
# PUT /api/biodiversity/update/<record_id>
# --------------------------------------------------

@biodiversity_bp.route('/update/<int:record_id>', methods=['PUT'])
def update_biodiversity(record_id):

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
            FROM biodiversity
            WHERE id = %s
        """, (record_id,))

        existing = cursor.fetchone()

        if not existing:
            return jsonify({
                'error': 'Biodiversity record not found.'
            }), 404

        try:
            record = validate_biodiversity_data(data, existing)
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
            UPDATE biodiversity
            SET project_id = %s,
                species_name = %s,
                species_type = %s,
                conservation_status = %s,
                observation_date = %s,
                description = %s
            WHERE id = %s
        """, (
            record['project_id'],
            record['species_name'],
            record['species_type'],
            record['conservation_status'],
            record['observation_date'],
            record['description'],
            record_id
        ))

        db.commit()

        return jsonify({
            'message': 'Biodiversity record updated successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Update biodiversity error:', e)
        return jsonify({
            'error': 'Unable to update biodiversity record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()


# --------------------------------------------------
# DELETE BIODIVERSITY RECORD
# ADMIN ONLY
# DELETE /api/biodiversity/delete/<record_id>
# --------------------------------------------------

@biodiversity_bp.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_biodiversity(record_id):

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
            DELETE FROM biodiversity
            WHERE id = %s
        """, (record_id,))

        if cursor.rowcount == 0:
            return jsonify({
                'error': 'Biodiversity record not found.'
            }), 404

        db.commit()

        return jsonify({
            'message': 'Biodiversity record deleted successfully.'
        }), 200

    except Exception as e:
        db.rollback()
        print('Delete biodiversity error:', e)
        return jsonify({
            'error': 'Unable to delete biodiversity record.'
        }), 500

    finally:
        if cursor:
            cursor.close()
        db.close()
