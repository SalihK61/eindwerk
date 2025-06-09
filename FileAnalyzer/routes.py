import os
import warnings
from flask import (
    Blueprint, render_template, session,
    redirect, url_for, current_app, request, flash
)
from authlib.integrations.flask_client import OAuthError
from models import db, User, CSVFile
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from flask import send_from_directory, url_for

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

    sub = userinfo.get('sub')
    name = userinfo.get('name')
    email = userinfo.get('email')
    picture = userinfo.get('picture')

    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub, name=name, email=email, picture=picture)
        db.session.add(user)
    else:
        user.name = name
        user.email = email
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
    reports = CSVFile.query.filter_by(user_sub=session['user']['sub']).all()
    return render_template('reports.html', reports=reports)

@main.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user' not in session:
        flash('Please log in to upload files.', 'danger')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        # file upload logic unchanged...
        filename = secure_filename(request.files['csv_file'].filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        request.files['csv_file'].save(file_path)

        # Save record
        user_sub = session['user']['sub']
        csv_file = CSVFile(user_sub=user_sub, filename=filename, filepath=file_path)
        db.session.add(csv_file)
        db.session.commit()

        # Read dataframe
        df = pd.read_csv(file_path)
        if df.empty:
            flash('Uploaded CSV is empty.', 'danger')
            return redirect(request.url)

        # 1. Analyse CSV Documents
        dtypes = df.dtypes.astype(str).to_dict()
        basic_stats = []
        for col in df.columns:
            col_data = df[col]
            basic_stats.append({
                'column': col,
                'mean': float(col_data.mean()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'median': float(col_data.median()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'missing': int(col_data.isna().sum())
            })
        corr_df = df.select_dtypes(include=[np.number]).corr()
        corr_html = corr_df.to_html(classes='table table-bordered text-black', border=0) if not corr_df.empty else ''

        # 2. Remove Duplicates
        total_rows = len(df)
        dup_count = df.duplicated().sum()
        cleaned_df = df.drop_duplicates()
        cleaned_path = os.path.join(upload_folder, f"cleaned_{filename}")
        cleaned_df.to_csv(cleaned_path, index=False)

        # 3. Detect Missing Data
        missing_stats = df.isna().sum().to_dict()
        missing_rows = df[df.isna().any(axis=1)]
        missing_rows_path = os.path.join(upload_folder, f"missing_{filename}")
        missing_rows.to_csv(missing_rows_path, index=False)

        # 4. Static histograms (unchanged)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(csv_file.id))
        os.makedirs(analysis_dir, exist_ok=True)
        hist_paths = []
        for col in numeric_cols:
            plt.figure()
            df[col].dropna().hist()
            plt.title(f'Distribution of {col}')
            img_name = f"{col}.png"
            plt.savefig(os.path.join(analysis_dir, img_name), bbox_inches='tight')
            plt.close()
            hist_paths.append(url_for('static', filename=f'analysis/{csv_file.id}/{img_name}'))

        return render_template(
            'analysis.html',
            filename=filename,
            dtypes=dtypes,
            basic_stats=basic_stats,
            corr=corr_html,
            total_rows=total_rows,
            dup_count=dup_count,
            cleaned_filename=f"cleaned_{filename}",
            missing_stats=missing_stats,
            missing_rows_count=len(missing_rows),
            missing_filename=f"missing_{filename}",
            numeric_cols=numeric_cols,
            hist_paths=hist_paths,
            csv_file=csv_file
        )
    return render_template('upload.html')

@main.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@main.route('/generate_pdf/<int:csv_id>')
def generate_pdf(csv_id):
    # For simplicity, render the same analysis template and convert to PDF
    from weasyprint import HTML
    record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(record.filepath)
    # re-run or cache analysis here...
    html = render_template('analysis_pdf.html', filename=record.filename, dtypes=dtypes,
                           basic_stats=basic_stats, corr=corr_html,
                           total_rows=total_rows, dup_count=dup_count,
                           cleaned_filename=f"cleaned_{record.filename}",
                           missing_stats=missing_stats,
                           missing_rows_count=len(missing_rows),
                           missing_filename=f"missing_{record.filename}")
    pdf = HTML(string=html).write_pdf()
    return send_file(io.BytesIO(pdf), mimetype='application/pdf',
                     download_name=f"report_{record.filename}.pdf", as_attachment=True)

@main.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True
    )

@main.route('/mycsvs')
def mycsvs():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    user_sub = session['user']['sub']
    csvs = CSVFile.query.filter_by(user_sub=user_sub).all()
    return render_template('csvs.html', csvs=csvs)