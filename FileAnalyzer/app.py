from flask import Flask
from authlib.integrations.flask_client import OAuth
from config import Config
from models import db
from routes import main

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize DB
    db.init_app(app)

    # OAuth / Auth0
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

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=(app.config['FLASK_ENV']=='development'))
