import os
from flask import (
    Blueprint, render_template, session,
    redirect, url_for, current_app, request, flash
)
from authlib.integrations.flask_client import OAuthError
from models import db, User, CSVFile
from werkzeug.utils import secure_filename
from flask_login import current_user, login_required
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from flask import send_from_directory

main = Blueprint('main', __name__)

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main.route('/')
def home():
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

    userinfo_url = f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo"
    resp = current_app.auth0.get(userinfo_url, token=token)
    userinfo = resp.json()

    sub     = userinfo.get('sub')
    name    = userinfo.get('name')
    email   = userinfo.get('email')
    picture = userinfo.get('picture')

    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub, name=name, email=email, picture=picture)
        db.session.add(user)
    else:
        user.name    = name
        user.email   = email
        user.picture = picture
    db.session.commit()

    session['user'] = {'sub': sub, 'name': name, 'email': email, 'picture': picture}
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
    csvs = CSVFile.query.filter_by(user_sub=session['user']['sub']).all()
    reports = []
    return render_template('dashboard.html', user=session['user'], csvs=csvs, reports=reports)

@main.route('/reports')
def reports():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    reports = []
    return render_template('reports.html', reports=reports)

@main.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user' not in session:
        flash('Please log in to upload files.', 'danger')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        file = request.files['csv_file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Invalid file type.', 'danger')
            return redirect(request.url)

        # Save file
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Record metadata
        user_sub = session['user']['sub']
        csv_file = CSVFile(user_sub=user_sub, filename=filename, filepath=os.path.join('uploads', filename))
        db.session.add(csv_file)
        db.session.commit()

        # Data analysis
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            flash(f'Error reading CSV: {e}', 'danger')
            return redirect(request.url)

        # Summary statistics
        summary_html = df.describe(include='all').to_html(classes='table table-striped', border=0)
        # Correlation matrix for numeric columns
        corr_df = df.select_dtypes(include=[np.number]).corr()
        corr_html = corr_df.to_html(classes='table table-bordered', border=0)

        # Histograms
        analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(csv_file.id))
        os.makedirs(analysis_dir, exist_ok=True)
        hist_paths = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            plt.figure()
            df[col].dropna().hist()
            plt.title(f'Distribution of {col}')
            plt.xlabel(col)
            plt.ylabel('Frequency')
            img_name = f"{col}.png"
            img_full_path = os.path.join(analysis_dir, img_name)
            plt.savefig(img_full_path, bbox_inches='tight')
            plt.close()
            hist_paths.append(url_for('static', filename=f'analysis/{csv_file.id}/{img_name}'))

        # Render analysis
        return render_template(
            'analysis.html',
            filename=filename,
            summary=summary_html,
            corr=corr_html,
            hist_paths=hist_paths
        )

    return render_template('upload.html')

@main.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@main.route('/mycsvs')
def mycsvs():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user_sub = session['user']['sub']
    csvs = CSVFile.query.filter_by(user_sub=user_sub).all()
    return render_template('csvs.html', csvs=csvs)
