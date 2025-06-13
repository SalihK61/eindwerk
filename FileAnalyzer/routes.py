import os
import io
from flask import Blueprint, render_template, session, redirect, url_for,current_app, request, flash, send_file
from authlib.integrations.flask_client import OAuthError
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
from fpdf import FPDF
from models import db, User, CSVFile, PDFReport
from utils.text import allowed_file, clean_text
from utils.stats import compute_basic_stats, make_corr_html
from utils.plotting import save_histograms, create_numeric_plot, create_category_plot, create_correlation_heatmap
from utils.ai_insights import generate_ai_insight

# Initialize Blueprint
main = Blueprint('main', __name__)

# ----------------------
# Authentication Routes
# ----------------------
@main.route('/')
def home():
    return render_template('home.html', user=session.get('user'))

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

    userinfo = current_app.auth0.get(
        f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo",
        token=token
    ).json()

    sub = userinfo['sub']
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

# ----------------------
# Dashboard & Reports
# ----------------------
@main.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return render_template('dashboard.html', user=session['user'])

@main.route('/reports')
def reports():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    pdfs = PDFReport.query.filter_by(user_sub=session['user']['sub']).all()
    return render_template('reports.html', reports=pdfs)

# ----------------------
# CSV Upload & Analysis
# ----------------------
@main.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user' not in session:
        flash('Please log in to upload files.', 'danger')
        return redirect(url_for('main.login'))

    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file or file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash('Invalid file type.', 'danger')
            return redirect(request.url)

        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        csv_record = CSVFile(user_sub=session['user']['sub'], filename=filename, filepath=file_path)
        db.session.add(csv_record)
        db.session.commit()

        df = pd.read_csv(file_path)
        if df.empty:
            flash('Uploaded CSV is empty.', 'danger')
            return redirect(request.url)

        dtypes = df.dtypes.astype(str).to_dict()
        basic_stats = compute_basic_stats(df)
        corr_html = make_corr_html(df)
        total_rows, dup_count = len(df), df.duplicated().sum()

        cleaned_filename = f"cleaned_{filename}"
        df.drop_duplicates().to_csv(os.path.join(upload_folder, cleaned_filename), index=False)

        missing_stats = df.isna().sum().to_dict()
        missing_rows = df[df.isna().any(axis=1)]
        missing_filename = f"missing_{filename}"
        missing_rows.to_csv(os.path.join(upload_folder, missing_filename), index=False)

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        hist_paths = save_histograms(df, csv_record.id, numeric_cols)

        return render_template(
            'analysis.html', filename=filename, dtypes=dtypes,
            basic_stats=basic_stats, corr=corr_html,
            total_rows=total_rows, dup_count=dup_count,
            cleaned_filename=cleaned_filename, missing_stats=missing_stats,
            missing_rows_count=len(missing_rows), missing_filename=missing_filename,
            numeric_cols=numeric_cols, hist_paths=hist_paths, csv_file=csv_record
        )

    return render_template('upload.html')

@main.route('/mycsvs')
def mycsvs():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    csvs = CSVFile.query.filter_by(user_sub=session['user']['sub']).all()
    return render_template('csvs.html', csvs=csvs)

@main.route('/analyse/<int:csv_id>')
def analyse_csv(csv_id):
    record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(record.filepath)

    dtypes = df.dtypes.astype(str).to_dict()
    basic_stats = compute_basic_stats(df)
    corr_html = make_corr_html(df)

    total_rows, dup_count = len(df), df.duplicated().sum()
    cleaned_filename = f"cleaned_{record.filename}"
    df.drop_duplicates().to_csv(os.path.join(current_app.config['UPLOAD_FOLDER'], cleaned_filename), index=False)

    missing_stats = df.isna().sum().to_dict()
    missing_rows_count = int(df[df.isna().any(axis=1)].shape[0])
    missing_filename = f"missing_{record.filename}"
    df[df.isna().any(axis=1)].to_csv(os.path.join(current_app.config['UPLOAD_FOLDER'], missing_filename), index=False)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    hist_paths = save_histograms(df, record.id, numeric_cols)


    return render_template(
        'analysis.html', filename=record.filename, dtypes=dtypes,
        basic_stats=basic_stats, corr=corr_html,
        total_rows=total_rows, dup_count=dup_count,
        cleaned_filename=cleaned_filename, missing_stats=missing_stats,
        missing_rows_count=missing_rows_count, missing_filename=missing_filename,
        numeric_cols=numeric_cols, hist_paths=hist_paths, csv_file=record
    )

@main.route('/download/<path:filename>')
def download_file(filename):
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    mimetype = 'application/pdf' if filename.lower().endswith('.pdf') else 'text/csv'
    file_bytes = open(file_path, 'rb').read()
    return send_file(io.BytesIO(file_bytes), mimetype=mimetype, download_name=filename, as_attachment=True)

@main.route('/generate_pdf/<int:csv_id>')
def generate_pdf(csv_id):
    csv_record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(csv_record.filepath)

    # get optional prompt if it is given by the uaser
    user_prompt = request.args.get("prompt", "").strip()
    ai_insight = generate_ai_insight(df, user_prompt)

    plot_funcs = [create_numeric_plot, create_category_plot, create_correlation_heatmap]
    plot_infos = [(buf, fname, exp) for func in plot_funcs for buf, fname, exp in [func(df)] if buf]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, clean_text(f"CSV Analysis Report for {csv_record.filename}"), ln=True)
    pdf.set_font("Arial", "B", 12)
    pdf.ln(5)
    pdf.cell(0, 10, clean_text("AI Analysis:"), ln=True)
    pdf.set_font("Arial", size=10)
    for line in ai_insight.split("\n"):
        pdf.multi_cell(0, 7, clean_text(line))
    pdf.ln(5)

    for i, (buf, fname, explanation) in enumerate(plot_infos):
        path = os.path.join(current_app.config['UPLOAD_FOLDER'], fname)
        with open(path, 'wb') as f:
            f.write(buf.getbuffer())
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, clean_text(f"Figure {i+1}"), ln=True)
        pdf.set_font("Arial", size=10)
        if explanation:
            pdf.multi_cell(0, 7, clean_text(explanation))
            pdf.ln(3)
        pdf.image(path, x=10, w=pdf.w - 20)
        os.remove(path)

    pdf_filename = f"{os.path.splitext(csv_record.filename)[0]}_analysis_report.pdf"
    storage_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    with open(storage_path, 'wb') as f:
        f.write(pdf_bytes)

    if not PDFReport.query.filter_by(filename=pdf_filename, user_sub=csv_record.user_sub).first():
        db.session.add(PDFReport(
            filename=pdf_filename,
            user_sub=csv_record.user_sub,
            filepath=storage_path))
        db.session.commit()

    return send_file(
        storage_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=pdf_filename
    )
