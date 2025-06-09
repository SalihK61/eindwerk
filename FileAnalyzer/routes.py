import os
from flask import (
    Blueprint, render_template, session,
    redirect, url_for, current_app
)
from authlib.integrations.flask_client import OAuthError
from models import db, User

main = Blueprint('main', __name__)

@main.route('/')
def home():
    # Grab any existing user from the session
    user = session.get('user')
    return render_template('home.html', user=user)

@main.route('/login')
def login():
    return current_app.auth0.authorize_redirect(
        redirect_uri=current_app.config['AUTH0_CALLBACK_URL']
    )

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

    # Full UserInfo endpoint
    userinfo_url = f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo"
    resp = current_app.auth0.get(userinfo_url, token=token)
    userinfo = resp.json()

    sub     = userinfo.get('sub')
    name    = userinfo.get('name')
    email   = userinfo.get('email')
    picture = userinfo.get('picture')

    # Upsert user into Postgres
    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub, name=name, email=email, picture=picture)
        db.session.add(user)
    else:
        user.name    = name
        user.email   = email
        user.picture = picture
    db.session.commit()

    # Persist to session and make it permanent
    session['user'] = {
        'sub': sub,
        'name': name,
        'email': email,
        'picture': picture
    }
    session.permanent = True

    return redirect(url_for('main.dashboard'))

@main.route('/logout')
def logout():
    session.clear()
    return redirect(
        f"https://{current_app.config['AUTH0_DOMAIN']}/v2/logout"
        f"?returnTo={url_for('main.home', _external=True)}"
        f"&client_id={current_app.config['AUTH0_CLIENT_ID']}"
    )

@main.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    # TODO: load user’s CSVs & reports
    csvs    = []
    reports = []
    return render_template(
        'dashboard.html',
        user=session['user'],
        csvs=csvs,
        reports=reports
    )

@main.route('/mycsvs')
def mycsvs():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    csvs = []
    return render_template('csvs.html', csvs=csvs)

@main.route('/reports')
def reports():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    reports = []
    return render_template('reports.html', reports=reports)

@main.route('/upload')
def upload():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return "<h1>Upload Page Placeholder</h1>"
