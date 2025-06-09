# app.py
import os
from flask import Flask
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from config import Config
from models import db
from routes import main

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize SQLAlchemy
    db.init_app(app)

    # Set up Auth0 via Authlib
    oauth = OAuth(app)
    auth0 = oauth.register(
        name='auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        client_kwargs={'scope': 'openid profile email'},
        server_metadata_url=f"https://{app.config['AUTH0_DOMAIN']}/.well-known/openid-configuration"
    )
    app.auth0 = auth0

    # Register your routes Blueprint
    app.register_blueprint(main)

    # Create database tables (moet hier gebeuren anders error ps. No idea whyyy??)
    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == '__main__':
    # bind to all interfaces, enable debug in development
    app.run(host='0.0.0.0',
            port=4000,
            debug=(app.config.get('FLASK_ENV') == 'development'))
