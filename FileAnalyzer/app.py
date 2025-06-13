import os
from flask import Flask, session, redirect, url_for, send_from_directory
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

from config import Config
from models import db, User
from routes import main

# Load environment variables from .env file for configuration values
load_dotenv()

def create_app():
    """
    Application factory: creates and configures the Flask app.
    """
    # Instantiate Flask application, serving static files from 'static'
    app = Flask(__name__, static_folder='static')
    # Load configuration settings from Config class
    app.config.from_object(Config)

    # Initialize SQLAlchemy with the app
    db.init_app(app)

    # Set up Auth0 OAuth client
    oauth = OAuth(app)
    auth0 = oauth.register(
        'auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        client_kwargs={'scope': 'openid profile email'},
        server_metadata_url=f"https://{app.config['AUTH0_DOMAIN']}/.well-known/openid-configuration"
    )
    # Attach auth0 client to app for use in routes
    app.auth0 = auth0

    # Register blueprint(s) for main application routes
    app.register_blueprint(main)

    # Within application context, ensure database tables and folders exist
    with app.app_context():
        # Create any missing database tables
        db.create_all()
        # Ensure upload and report directories exist
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        os.makedirs(app.config.get('REPORT_FOLDER', 'reports'), exist_ok=True)

    return app

# Create and configure the Flask app instance
app = create_app()

# Additional configuration overrides (database URI, disable event system overhead)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'  # Or set your PostgreSQL URI here
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# After overrides, ensure tables and upload folder exist
with app.app_context():
    db.create_all()
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

@app.context_processor
def inject_user():
    """
    Make the authenticated user profile available in all Jinja2 templates
    via the variable 'user'.
    """
    return {"user": session.get("user")}

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """
    Serve files from the upload directory.
    """
    folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    return send_from_directory(folder, filename)

@app.before_request
def ensure_user_still_exists():
    """
    Before every request, confirm the user in session still exists in the DB.
    If the user record was removed, clear session and redirect to login.
    """
    user_info = session.get("user")
    if user_info:
        user_in_db = db.session.execute(
            db.select(User).filter_by(email=user_info.get("email"))
        ).scalar_one_or_none()
        if not user_in_db:
            session.clear()
            return redirect(url_for("main.login"))

@app.route('/logout')
def logout():
    """
    Clear the user session and redirect to the login page.
    """
    session.clear()
    return redirect(url_for("main.login"))

if __name__ == '__main__':
    # Run the Flask development server on port 4000
    app.run(
        host='0.0.0.0',
        port=4000,
        debug=(app.config.get('FLASK_ENV') == 'development')
    )
