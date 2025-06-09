import os
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

        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        user_sub = session['user']['sub']
        csv_file = CSVFile(
            user_sub=user_sub,
            filename=filename,
            filepath=os.path.join('uploads', filename)
        )
        db.session.add(csv_file)
        db.session.commit()

        try:
            df = pd.read_csv(file_path)
            print("DF HEAD:", df.head())
        except Exception as e:
            flash(f'Error reading CSV: {e}', 'danger')
            return redirect(request.url)

        if df.empty:
            flash('Uploaded CSV is empty.', 'danger')
            return redirect(request.url)

        # Automatic datatype detection
        dtypes = df.dtypes.astype(str).to_dict()

        # Basic statistics
        basic_stats = []
        for col in df.columns:
            col_data = df[col]
            basic_stats.append({
                'column': col,
                'mean': float(col_data.mean()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'median': float(col_data.median()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'missing': int(col_data.isna().sum())
            })

        # Correlation matrix
        corr_df = df.select_dtypes(include=[np.number]).corr()
        corr_html = corr_df.to_html(classes='table table-bordered', border=0) if not corr_df.empty else ''

        # Identify categorical and datetime columns
        categorical_cols = df.select_dtypes(include=['object', 'category', 'bool']).columns.tolist()
        datetime_cols = []

        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',           # 2023-01-01
            '%m/%d/%Y',           # 01/01/2023
            '%d-%m-%Y',           # 01-01-2023
            '%Y/%m/%d',           # 2023/01/01
            '%d/%m/%Y',           # 01/01/2023
            '%Y-%m-%d %H:%M:%S',  # 2023-01-01 12:00:00
            '%m/%d/%Y %H:%M:%S',  # 01/01/2023 12:00:00
        ]

        # Pre-filter columns likely to contain dates
        potential_date_cols = [
            col for col in df.columns
            if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]) or
               col.lower() in ['date', 'time', 'datetime', 'created_at', 'updated_at']
        ]

        for col in potential_date_cols:
            for fmt in date_formats:
                try:
                    parsed = pd.to_datetime(df[col], format=fmt, errors='coerce')
                    if parsed.notna().sum() > len(df) / 2:  # More than half the values are valid dates
                        df[col] = parsed
                        datetime_cols.append(col)
                        print(f"Parsed column '{col}' as datetime with format '{fmt}'")
                        break  # Stop trying formats once one works
                except Exception as e:
                    continue
            else:
                # If no format worked, try with dateutil as a fallback but suppress the warning
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        parsed = pd.to_datetime(df[col], errors='coerce')
                        if parsed.notna().sum() > len(df) / 2:
                            df[col] = parsed
                            datetime_cols.append(col)
                            print(f"Parsed column '{col}' as datetime with dateutil fallback")
                except Exception:
                    continue

        # Prepare data for charts
        cat_data = {col: df[col].fillna('NaN').value_counts().to_dict() for col in categorical_cols}
        pie_data = cat_data.copy()

        time_data = {}
        for col in datetime_cols:
            counts = df.groupby(df[col].dt.date).size()
            time_data[col] = {
                'dates': [str(d) for d in counts.index],
                'values': counts.tolist()
            }

        # Static histograms
        analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(csv_file.id))
        os.makedirs(analysis_dir, exist_ok=True)
        hist_paths = []
        for col in df.select_dtypes(include=[np.number]).columns:
            plt.figure()
            df[col].dropna().hist()
            plt.title(f'Distribution of {col}')
            img_name = f"{col}.png"
            plt.savefig(os.path.join(analysis_dir, img_name), bbox_inches='tight')
            plt.close()
            hist_paths.append(
                url_for('static', filename=f'analysis/{csv_file.id}/{img_name}')
            )

        return render_template(
            'analysis.html',
            filename=filename,
            dtypes=dtypes,
            basic_stats=basic_stats,
            corr=corr_html,
            categorical_cols=categorical_cols,
            datetime_cols=datetime_cols,
            cat_data=cat_data,
            time_data=time_data,
            pie_data=pie_data,
            hist_paths=hist_paths
        )

    return render_template('upload.html')

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