import os
from flask import (
    Blueprint, render_template, session,
    redirect, url_for, current_app, request, flash
)
from authlib.integrations.flask_client import OAuthError
from models import db, User,CSVFile
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
import pandas as pd

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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


@main.route('/upload', methods=['GET', 'POST'])
def upload():
    preview = None
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # FIX: Get user_sub correctly from session['user']
            user_sub = session.get('user', {}).get('sub')
            if not user_sub:
                flash('You must be logged in to upload.', 'danger')
                return redirect(url_for('main.login'))

            filename = secure_filename(file.filename)
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            relative_path = os.path.join('uploads', filename)
            absolute_path = os.path.join(upload_folder, filename)
            file.save(absolute_path)

            try:
                import pandas as pd  # Just in case!
                df = pd.read_csv(absolute_path)
                preview = df.head().to_html(classes='table table-striped', border=0)
                flash('File uploaded and processed!', 'success')
            except Exception as e:
                flash(f'Error processing file: {e}', 'danger')
                return render_template('upload.html', preview=None)

            # Save file to DB with user_sub
            csv_file = CSVFile(
                user_sub=user_sub,
                filename=filename,
                filepath=relative_path  # <-- relative path (for portability)
            )
            db.session.add(csv_file)
            db.session.commit()
        else:
            flash('Invalid file type.', 'danger')
    return render_template('upload.html', preview=preview)

