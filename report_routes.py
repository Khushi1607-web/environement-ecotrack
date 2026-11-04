from flask import Blueprint, jsonify, session
from database import get_db_connection
from decimal import Decimal
import traceback

report_bp = Blueprint('reports', __name__)

VALID_ROLES = ('admin', 'viewer', 'field_officer')


def logged_in():
    return (
        'user_id' in session
        and session.get('user_role') in VALID_ROLES
    )


def clean_numbers(data):
    if not data:
        return {}

    result = {}

    integer_fields = {
        'total_projects',
        'active_projects',
        'completed_projects',
        'on_hold_projects',
        'total_activities',
        'restoration_records',
        'biodiversity_records',
        'unique_species',
        'total_records'
    }

    for key, value in data.items():

        if value is None:
            result[key] = 0

        elif isinstance(value, bool):
            result[key] = value

        elif key in integer_fields:
            result[key] = int(value)

        elif isinstance(value, (Decimal, int, float)):
            result[key] = float(value)

        else:
            result[key] = value

    return result


@report_bp.route('/', methods=['GET'])
def get_reports():

    if not logged_in():
        return jsonify({'error': 'Please log in.'}), 401

    db = None
    cursor = None

    try:
        db = get_db_connection()

        if db is None:
            return jsonify({
                'error': 'Database connection failed.'
            }), 500

        cursor = db.cursor(dictionary=True)

        # PROJECT SUMMARY
        cursor.execute("""
            SELECT
                COUNT(*) AS total_projects,
                COALESCE(SUM(status = 'Active'), 0) AS active_projects,
                COALESCE(SUM(status = 'Completed'), 0) AS completed_projects,
                COALESCE(SUM(status = 'On Hold'), 0) AS on_hold_projects
            FROM projects
        """)
        project_summary = clean_numbers(cursor.fetchone())

        # SUSTAINABILITY SUMMARY
        cursor.execute("""
            SELECT
                COUNT(*) AS total_activities,
                COALESCE(SUM(target_value), 0) AS total_target,
                COALESCE(SUM(achieved_value), 0) AS total_achieved
            FROM sustainability
        """)
        sustainability_summary = clean_numbers(cursor.fetchone())

        # TREE PLANTATION
        cursor.execute("""
            SELECT
                COALESCE(SUM(target_value), 0) AS total_tree_target,
                COALESCE(SUM(achieved_value), 0) AS total_trees
            FROM sustainability
            WHERE activity_type = 'Tree Plantation'
        """)
        tree_summary = clean_numbers(cursor.fetchone())

        # RESTORATION
        cursor.execute("""
            SELECT
                COUNT(*) AS restoration_records,
                COALESCE(SUM(target_area), 0) AS total_target_area,
                COALESCE(SUM(restored_area), 0) AS total_restored_area
            FROM restoration
        """)
        restoration_summary = clean_numbers(cursor.fetchone())

        # CARBON MANAGEMENT
        cursor.execute("""
            SELECT
                COALESCE(SUM(emission_value), 0) AS total_emissions,
                COALESCE(SUM(reduction_value), 0) AS total_reductions,
                COALESCE(SUM(sequestration_value), 0) AS total_sequestration
            FROM carbon_management
        """)
        carbon_summary = clean_numbers(cursor.fetchone())

        # CARBON CREDITS
        cursor.execute("""
            SELECT
                COALESCE(SUM(estimated_credits), 0) AS estimated_credits,
                COALESCE(SUM(verified_credits), 0) AS verified_credits,
                COALESCE(SUM(issued_credits), 0) AS issued_credits
            FROM carbon_credits
        """)
        credit_summary = clean_numbers(cursor.fetchone())

        # BIODIVERSITY
        cursor.execute("""
            SELECT
                COUNT(*) AS biodiversity_records,
                COUNT(DISTINCT species_name) AS unique_species
            FROM biodiversity
        """)
        biodiversity_summary = clean_numbers(cursor.fetchone())

        # ACTIVITY DISTRIBUTION
        cursor.execute("""
            SELECT
                activity_type,
                COUNT(*) AS total_records,
                COALESCE(SUM(target_value), 0) AS total_target,
                COALESCE(SUM(achieved_value), 0) AS total_achieved
            FROM sustainability
            GROUP BY activity_type
            ORDER BY activity_type
        """)

        activity_summary = [
            clean_numbers(item)
            for item in cursor.fetchall()
        ]

        report_data = {
            **project_summary,
            **sustainability_summary,
            **tree_summary,
            **restoration_summary,
            **carbon_summary,
            **credit_summary,
            **biodiversity_summary,
            'activity_summary': activity_summary
        }

        return jsonify(report_data), 200

    except Exception as e:
        print("\n========== ECOTRACK REPORT ERROR ==========")
        print(str(e))
        traceback.print_exc()
        print("===========================================\n")

        return jsonify({
            'error': 'Unable to generate reports.',
            'details': str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()

        if db:
            db.close()