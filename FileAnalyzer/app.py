import os
from flask import Flask, session
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from config import Config
from models import db
from routes import main
from flask_login import current_user
from flask import current_app

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)


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
        db.create_all()
        os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
        os.makedirs(app.config.get('REPORT_FOLDER', 'reports'), exist_ok=True)

    return app

app = create_app()


# Make sure the uploads directory is at the project root
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'  # Or your PostgreSQL URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Ensure upload folder and database exist
with app.app_context():
    db.create_all()
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])


@app.context_processor
def inject_user():
    # Pull the Auth0 profile you stored in session['user']
    return {"user": session.get("user")}


if __name__ == '__main__':
    # Listen on port 4000 per your Docker setup
    app.run(
        host='0.0.0.0',
        port=4000,
        debug=(app.config.get('FLASK_ENV') == 'development')
    )
