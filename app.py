from flask import Flask, jsonify, render_template, redirect, session
from config import Config
from database import get_db_connection

from routes.auth_routes import auth_bp, bcrypt
from routes.project_routes import project_bp
from routes.sustainability_routes import sustainability_bp
from routes.restoration_routes import restoration_bp
from routes.carbon_routes import carbon_bp
from routes.carbon_credit_routes import carbon_credit_bp
from routes.biodiversity_routes import biodiversity_bp
from routes.report_routes import report_bp
from routes.audit_routes import audit_bp
app = Flask(__name__)

app.config.from_object(Config)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

bcrypt.init_app(app)

# Register API blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(project_bp, url_prefix='/api/projects')
app.register_blueprint(sustainability_bp, url_prefix='/api/sustainability')
app.register_blueprint(restoration_bp, url_prefix='/api/restoration')
app.register_blueprint(carbon_bp, url_prefix='/api/carbon')
app.register_blueprint(carbon_credit_bp, url_prefix='/api/carbon-credits')
app.register_blueprint(biodiversity_bp, url_prefix='/api/biodiversity')
app.register_blueprint(report_bp, url_prefix='/api/reports')
app.register_blueprint(audit_bp, url_prefix='/api/audit')

def is_logged_in():
    return 'user_id' in session


def is_admin():
    return (
        is_logged_in()
        and session.get('user_role') == 'admin'
    )


@app.route('/')
def home():
    return redirect('/login')


@app.route('/login')
def login_page():
    if is_logged_in():
        return redirect('/dashboard')
    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if not is_logged_in():
        return redirect('/login')

    return render_template(
        'dashboard.html',
        user_name=session.get('user_name'),
        user_role=session.get('user_role')
    )


@app.route('/projects')
def projects_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('projects.html')


@app.route('/sustainability')
def sustainability_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('sustainability.html')


@app.route('/restoration')
def restoration_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('restoration.html')


@app.route('/carbon')
def carbon_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('carbon.html')


@app.route('/carbon-credits')
def carbon_credits_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('carbon_credits.html')


@app.route('/biodiversity')
def biodiversity_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('biodiversity.html')


@app.route('/reports')
def reports_page():
    if not is_logged_in():
        return redirect('/login')
    return render_template('reports.html')
# Audit History page
@app.route('/audit')
def audit_page():

    if 'user_id' not in session:
        return redirect('/login')

    if session.get('user_role') not in ('admin', 'viewer'):
        return redirect('/dashboard')

    return render_template('audit.html')


@app.route('/users')
def users_page():
    if not is_logged_in():
        return redirect('/login')

    if not is_admin():
        return redirect('/dashboard')

    return render_template('users.html')


@app.route('/test-db')
def test_db():
    db = get_db_connection()

    if db:
        db.close()
        return jsonify({
            'message': 'EcoTrack Database Connected Successfully!',
            'status': 'success'
        })

    return jsonify({
        'message': 'Database Connection Failed!',
        'status': 'error'
    }), 500


@app.route('/api/auth/check-session')
def check_session():
    if is_logged_in():
        return jsonify({
            'logged_in': True,
            'user_id': session.get('user_id'),
            'user_name': session.get('user_name'),
            'user_role': session.get('user_role')
        })

    return jsonify({'logged_in': False}), 401


@app.route('/api/health')
def health():
    return jsonify({
        'application': 'EcoTrack',
        'status': 'running'
    })


if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=5001,
        debug=True
    )