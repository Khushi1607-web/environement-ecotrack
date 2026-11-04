
from flask import Blueprint, request, jsonify, session
from database import get_db_connection
from datetime import date
from audit_logger import log_audit

project_bp = Blueprint('projects', __name__)


# --------------------------------------------------
# ROLE CHECKS
# --------------------------------------------------

def logged_in():
    return 'user_id' in session


def admin_required():
    if not logged_in():
        return jsonify({'error': 'Please login first'}), 401

    if session.get('user_role') != 'admin':
        return jsonify({
            'error': 'Permission denied. Only Admin can manage projects.'
        }), 403

    return None


# --------------------------------------------------
# AUTOMATIC PROJECT STATUS UPDATE
# --------------------------------------------------

def sync_expired_projects():
    """Automatically complete active projects after their end date."""

    db = get_db_connection()

    if not db:
        return False

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute("""
            UPDATE projects
            SET status = 'Completed'
            WHERE status = 'Active'
            AND end_date IS NOT NULL
            AND end_date < CURDATE()
        """)

        updated_count = cursor.rowcount
        db.commit()

        return True

    except Exception as e:
        db.rollback()
        print("Automatic project status update error:", e)
        return False

    finally:
        if cursor:
            cursor.close()

        db.close()


# --------------------------------------------------
# DATE VALIDATION
# --------------------------------------------------

def validate_dates(start_date, end_date):

    try:
        if start_date:
            start_date = date.fromisoformat(str(start_date))

        if end_date:
            end_date = date.fromisoformat(str(end_date))

        if start_date and end_date and end_date < start_date:
            return False

        return True

    except (ValueError, TypeError):
        return False


# --------------------------------------------------
# ADD PROJECT - ADMIN ONLY
# POST /api/projects/add
# --------------------------------------------------

@project_bp.route('/add', methods=['POST'])
def add_project():

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    name = data.get('project_name')
    category = data.get('category')
    location = data.get('location')
    description = data.get('description')
    start_date = data.get('start_date') or None
    end_date = data.get('end_date') or None
    status = data.get('status', 'Active')

    if not name or not str(name).strip():
        return jsonify({'error': 'Project name is required'}), 400

    if status not in ['Active', 'Completed', 'On Hold']:
        return jsonify({'error': 'Invalid project status'}), 400

    if not validate_dates(start_date, end_date):
        return jsonify({
            'error': 'Invalid dates. End date cannot be before start date.'
        }), 400

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO projects
            (project_name, category, location, description,
             start_date, end_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name.strip(),
            category,
            location,
            description,
            start_date,
            end_date,
            status
        ))

        project_id = cursor.lastrowid
        db.commit()

        # Record project creation in audit history
        log_audit(
            action='CREATE',
            module='Projects',
            record_id=project_id,
            details=f"Created project: {name.strip()}"
        )

        return jsonify({
            'message': 'Project added successfully',
            'project_id': project_id
        }), 201

    except Exception as e:
        db.rollback()
        print("Add project error:", e)
        return jsonify({'error': 'Unable to add project'}), 500

    finally:
        if cursor:
            cursor.close()

        db.close()


# --------------------------------------------------
# VIEW ALL PROJECTS - ALL THREE ROLES
# GET /api/projects/
# --------------------------------------------------

@project_bp.route('/', methods=['GET'])
def get_projects():

    if not logged_in():
        return jsonify({'error': 'Please login first'}), 401

    sync_expired_projects()

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM projects
            ORDER BY id DESC
        """)

        projects = cursor.fetchall()

        return jsonify({
            'total_projects': len(projects),
            'projects': projects
        }), 200

    except Exception as e:
        print("Get projects error:", e)
        return jsonify({'error': 'Unable to retrieve projects'}), 500

    finally:
        if cursor:
            cursor.close()

        db.close()


# --------------------------------------------------
# VIEW SINGLE PROJECT - ALL THREE ROLES
# GET /api/projects/<project_id>
# --------------------------------------------------

@project_bp.route('/<int:project_id>', methods=['GET'])
def get_project(project_id):

    if not logged_in():
        return jsonify({'error': 'Please login first'}), 401

    sync_expired_projects()

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM projects
            WHERE id = %s
        """, (project_id,))

        project = cursor.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        return jsonify(project), 200

    except Exception as e:
        print("Get project error:", e)
        return jsonify({'error': 'Unable to retrieve project'}), 500

    finally:
        if cursor:
            cursor.close()

        db.close()


# --------------------------------------------------
# UPDATE PROJECT - ADMIN ONLY
# PUT /api/projects/update/<project_id>
# --------------------------------------------------

@project_bp.route('/update/<int:project_id>', methods=['PUT'])
def update_project(project_id):

    access_error = admin_required()

    if access_error:
        return access_error

    data = request.get_json(silent=True) or {}

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM projects
            WHERE id = %s
        """, (project_id,))

        project = cursor.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        name = data.get('project_name', project['project_name'])
        category = data.get('category', project['category'])
        location = data.get('location', project['location'])
        description = data.get('description', project['description'])
        start_date = data.get('start_date', project['start_date'])
        end_date = data.get('end_date', project['end_date'])
        status = data.get('status', project['status'])

        if not name or not str(name).strip():
            return jsonify({'error': 'Project name is required'}), 400

        if status not in ['Active', 'Completed', 'On Hold']:
            return jsonify({'error': 'Invalid project status'}), 400

        if not validate_dates(start_date, end_date):
            return jsonify({
                'error': 'Invalid dates. End date cannot be before start date.'
            }), 400

        cursor.execute("""
            UPDATE projects
            SET project_name = %s,
                category = %s,
                location = %s,
                description = %s,
                start_date = %s,
                end_date = %s,
                status = %s
            WHERE id = %s
        """, (
            str(name).strip(),
            category,
            location,
            description,
            start_date,
            end_date,
            status,
            project_id
        ))

        db.commit()

        # Record project update in audit history
        log_audit(
            action='UPDATE',
            module='Projects',
            record_id=project_id,
            details=f"Updated project: {str(name).strip()}"
        )

        return jsonify({
            'message': 'Project updated successfully'
        }), 200

    except Exception as e:
        db.rollback()
        print("Update project error:", e)
        return jsonify({'error': 'Unable to update project'}), 500

    finally:
        if cursor:
            cursor.close()

        db.close()


# --------------------------------------------------
# DELETE PROJECT - ADMIN ONLY
# DELETE /api/projects/delete/<project_id>
# --------------------------------------------------

@project_bp.route('/delete/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):

    access_error = admin_required()

    if access_error:
        return access_error

    db = get_db_connection()

    if not db:
        return jsonify({'error': 'Database connection failed'}), 500

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        # Get project name before deleting it
        cursor.execute("""
            SELECT project_name
            FROM projects
            WHERE id = %s
        """, (project_id,))

        project = cursor.fetchone()

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        project_name = project['project_name']

        cursor.execute("""
            DELETE FROM projects
            WHERE id = %s
        """, (project_id,))

        db.commit()

        # Record project deletion in audit history
        log_audit(
            action='DELETE',
            module='Projects',
            record_id=project_id,
            details=f"Deleted project: {project_name}"
        )

        return jsonify({
            'message': 'Project deleted successfully'
        }), 200

    except Exception as e:
        db.rollback()
        print("Delete project error:", e)
        return jsonify({
            'error': 'Unable to delete project. Check whether environmental records are linked to it.'
        }), 500

    finally:
        if cursor:
            cursor.close()

        db.close()
