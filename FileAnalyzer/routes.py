import os
from flask import Blueprint, render_template, session, redirect, url_for, current_app
from authlib.integrations.flask_client import OAuthError
from models import db, User

main = Blueprint('main', __name__)

@main.before_app_first_request
def create_tables():
    db.create_all()

@main.route('/')
def home():
    user = session.get('user')
    return render_template('base.html', user=user)

@main.route('/login')
def login():
    return current_app.auth0.authorize_redirect(redirect_uri=current_app.config['AUTH0_CALLBACK_URL'])

@main.route('/register')
def register():
    return current_app.auth0.authorize_redirect(
        redirect_uri=current_app.config['AUTH0_CALLBACK_URL'],
        screen_hint='signup'
    )

@main.route('/callback')
def callback():
    try:
        token = current_app.auth0.authorize_access_token()
    except OAuthError:
        return redirect(url_for('main.home'))

    userinfo = current_app.auth0.parse_id_token(token)
    sub, name, email, picture = (
        userinfo['sub'],
        userinfo.get('name'),
        userinfo.get('email'),
        userinfo.get('picture')
    )

    # Upsert user into local DB
    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub, name=name, email=email, picture=picture)
        db.session.add(user)
    else:
        user.name = name
        user.email = email
        user.picture = picture
    db.session.commit()

    # Store minimal info in session
    session['user'] = {'sub': sub, 'name': name, 'email': email, 'picture': picture}
    return redirect(url_for('main.home'))

@main.route('/logout')
def logout():
    session.clear()
    return redirect(
        f"https://{current_app.config['AUTH0_DOMAIN']}/v2/logout"
        f"?returnTo={url_for('main.home', _external=True)}"
        f"&client_id={current_app.config['AUTH0_CLIENT_ID']}"
    )

@main.route('/upload')
def upload():
    return "<h1>Upload Page Placeholder</h1>"
