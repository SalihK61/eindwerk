import os
from flask import Flask, session, redirect, url_for
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from config import Config
from models import db, User
from routes import main
from flask_login import current_user
from flask import current_app
from flask import send_from_directory

load_dotenv()


def create_app():
    app = Flask(__name__, static_folder='static')
    app.config.from_object(Config)

    # Optional: force new secret key on restart in dev (logs out all users)
    # app.secret_key = os.urandom(24)

    # Initialize database
    db.init_app(app)

    # Auth0 setup
    oauth = OAuth(app)
    auth0 = oauth.register(
        'auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        client_kwargs={'scope': 'openid profile email'},
        server_metadata_url=f"https://{app.config['AUTH0_DOMAIN']}/.well-known/openid-configuration"
    )
    app.auth0 = auth0

    # Register routes
    app.register_blueprint(main)

    # Create database tables (and upload/report folders)
    with app.app_context():
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        os.makedirs(app.config.get('REPORT_FOLDER', 'reports'), exist_ok=True)

    return app

app = create_app()

if app.config['ENV'] != 'development':
    with app.app_context():
        from models import db
        db.create_all()


with app.app_context():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

@app.context_processor
def inject_user():
    # Pull the Auth0 profile you stored in session['user']
    return {"user": session.get("user")}

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    from config import UPLOAD_FOLDER
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- ADDED: Ensure user still exists in DB for every request ---
@app.before_request
def ensure_user_still_exists():
    user = session.get("user")
    if user:
        # Check if user is still in your DB (by email)
        user_in_db = db.session.execute(
            db.select(User).filter_by(email=user.get("email"))
        ).scalar_one_or_none()
        if not user_in_db:
            session.clear()
            return redirect(url_for("main.login"))  # Update if your login route differs

# --- ADDED: Example logout route ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("main.login"))  # Update if your login route differs

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=4000,
        debug=(app.config.get('FLASK_ENV') == 'development')
    )
