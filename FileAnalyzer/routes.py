import os
import io
import warnings

from flask import (
    Blueprint, render_template, session, redirect, url_for,
    current_app, request, flash, send_file
)
from authlib.integrations.flask_client import OAuthError
from werkzeug.utils import secure_filename

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import openai
from fpdf import FPDF

from models import db, User, CSVFile, PDFReport

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Initialize Blueprint
main = Blueprint('main', __name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------
# Authentication Routes
# ----------------------
@main.route('/')
def home():
    """Render the home page."""
    return render_template('home.html', user=session.get('user'))

@main.route('/login')
def login():
    """Redirect to Auth0 for login."""
    return current_app.auth0.authorize_redirect(
        redirect_uri=current_app.config['AUTH0_CALLBACK_URL']
    )

@main.route('/register')
def register():
    """Redirect to Auth0 for signup."""
    return current_app.auth0.authorize_redirect(
        redirect_uri=current_app.config['AUTH0_CALLBACK_URL'],
        screen_hint='signup'
    )

@main.route('/callback')
def callback():
    """Handle Auth0 callback, create or update user."""
    try:
        token = current_app.auth0.authorize_access_token()
    except OAuthError:
        return redirect(url_for('main.home'))

    userinfo = current_app.auth0.get(
        f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo",
        token=token
    ).json()

    # Extract user details
    sub = userinfo['sub']
    name = userinfo.get('name')
    email = userinfo.get('email')
    picture = userinfo.get('picture')

    # Create or update user in database
    user = User.query.filter_by(sub=sub).first()
    if not user:
        user = User(sub=sub, name=name, email=email, picture=picture)
        db.session.add(user)
    else:
        user.name = name
        user.email = email
        user.picture = picture
    db.session.commit()

    # Store user in session
    session['user'] = {'sub': sub, 'name': name, 'email': email, 'picture': picture}
    session.permanent = True

    return redirect(url_for('main.dashboard'))

@main.route('/logout')
def logout():
    """Log out user and clear session."""
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
    """Render user dashboard or redirect to login."""
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return render_template('dashboard.html', user=session['user'])

@main.route('/reports')
def reports():
    """List all PDF reports for logged-in user."""
    if 'user' not in session:
        return redirect(url_for('main.login'))
    pdfs = PDFReport.query.filter_by(user_sub=session['user']['sub']).all()
    return render_template('reports.html', reports=pdfs)

# ----------------------
# CSV Upload & Analysis
# ----------------------
@main.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload CSV, perform initial analysis and show results."""
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

        # Save file
        filename = secure_filename(file.filename)
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Record file in DB
        csv_record = CSVFile(user_sub=session['user']['sub'], filename=filename, filepath=file_path)
        db.session.add(csv_record)
        db.session.commit()

        # Load data
        df = pd.read_csv(file_path)
        if df.empty:
            flash('Uploaded CSV is empty.', 'danger')
            return redirect(request.url)

        # Data type summary
        dtypes = df.dtypes.astype(str).to_dict()

        # Basic stats: mean, median, mode, missing count
        basic_stats = []
        for col in df.columns:
            col_data = df[col]
            # Mode calculation
            modes = col_data.mode()
            mode_val = (
                float(modes.iloc[0]) if pd.api.types.is_numeric_dtype(col_data) and not modes.empty
                else modes.iloc[0] if not modes.empty
                else 'N/A'
            )
            basic_stats.append({
                'column': col,
                'mean': float(col_data.mean()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'median': float(col_data.median()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
                'mode': mode_val,
                'missing': int(col_data.isna().sum())
            })

        # Correlation matrix for numeric columns
        corr_df = df.select_dtypes(include=[np.number]).corr()
        corr_html = corr_df.to_html(classes='table table-bordered text-black', border=0) if not corr_df.empty else ''

        # Duplicate removal
        total_rows = len(df)
        dup_count = df.duplicated().sum()
        cleaned_filename = f"cleaned_{filename}"
        df.drop_duplicates().to_csv(os.path.join(upload_folder, cleaned_filename), index=False)

        # Missing data
        missing_stats = df.isna().sum().to_dict()
        missing_rows = df[df.isna().any(axis=1)]
        missing_filename = f"missing_{filename}"
        missing_rows.to_csv(os.path.join(upload_folder, missing_filename), index=False)

        # Generate histograms
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(csv_record.id))
        os.makedirs(analysis_dir, exist_ok=True)
        hist_paths = []
        for col in numeric_cols:
            plt.figure()
            df[col].dropna().hist()
            plt.title(f'Distribution of {col}')
            img_name = f"{col}.png"
            plt.savefig(os.path.join(analysis_dir, img_name), bbox_inches='tight')
            plt.close()
            hist_paths.append(url_for('static', filename=f'analysis/{csv_record.id}/{img_name}'))

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
    """List all CSVs uploaded by the user."""
    if 'user' not in session:
        return redirect(url_for('main.login'))
    csvs = CSVFile.query.filter_by(user_sub=session['user']['sub']).all()
    return render_template('csvs.html', csvs=csvs)

@main.route('/analyse/<int:csv_id>')
def analyse_csv(csv_id):
    """Re-run analysis for an existing CSV record."""
    record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(record.filepath)

    # Repeat analysis steps
    dtypes = df.dtypes.astype(str).to_dict()
    basic_stats = []
    for col in df.columns:
        col_data = df[col]
        modes = col_data.mode()
        mode_val = (
            float(modes.iloc[0]) if pd.api.types.is_numeric_dtype(col_data) and not modes.empty
            else modes.iloc[0] if not modes.empty
            else 'N/A'
        )
        basic_stats.append({
            'column': col,
            'mean': float(col_data.mean()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
            'median': float(col_data.median()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
            'mode': mode_val,
            'missing': int(col_data.isna().sum())
        })

    corr_df = df.select_dtypes(include=[np.number]).corr()
    corr_html = corr_df.to_html(classes='table table-bordered text-black', border=0) if not corr_df.empty else ''

    total_rows = len(df)
    dup_count = df.duplicated().sum()
    cleaned_filename = f"cleaned_{record.filename}"
    df.drop_duplicates().to_csv(os.path.join(current_app.config['UPLOAD_FOLDER'], cleaned_filename), index=False)

    missing_stats = df.isna().sum().to_dict()
    missing_rows_count = int(df[df.isna().any(axis=1)].shape[0])
    missing_filename = f"missing_{record.filename}"
    df[df.isna().any(axis=1)].to_csv(os.path.join(current_app.config['UPLOAD_FOLDER'], missing_filename), index=False)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(record.id))
    os.makedirs(analysis_dir, exist_ok=True)
    hist_paths = []
    for col in numeric_cols:
        plt.figure()
        df[col].dropna().hist()
        plt.title(f'Distribution of {col}')
        img_name = f"{col}.png"
        plt.savefig(os.path.join(analysis_dir, img_name), bbox_inches='tight')
        plt.close()
        hist_paths.append(url_for('static', filename=f'analysis/{record.id}/{img_name}'))

    ai_insight = generate_ai_insight(df)
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
    """Serve a CSV or PDF file for download."""
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    mimetype = 'application/pdf' if filename.lower().endswith('.pdf') else 'text/csv'
    file_bytes = open(file_path, 'rb').read()
    return send_file(io.BytesIO(file_bytes), mimetype=mimetype, download_name=filename, as_attachment=True)

# ----------------------
# Utility Functions
# ----------------------
def clean_text(text):
    """
    Normalize text for PDF output by replacing special characters.
    """
    if not isinstance(text, str):
        text = str(text)
    text = (
        text.replace("•", "-")
            .replace("–", "-")
            .replace("—", "-")
            .replace("’", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("…", "...")
    )
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_ai_insight(df):
    """
    Generate a detailed AI-powered data analysis report.
    """
    stats = df.describe(include='all').to_string()
    columns = ', '.join(df.columns)
    sample_rows = df.head(5).to_string(index=False)

    correlations = ''
    if df.select_dtypes(include='number').shape[1] >= 2:
        correlations = df.corr(numeric_only=True).to_string()

    top_cats = ''
    for col in df.select_dtypes(include='object').columns:
        top = df[col].value_counts().head(3)
        top_cats += f"\nTop values in '{col}':\n{top.to_string()}\n"

    prompt = (
        f"Here is a dataset with columns: {columns}\n\n"
        f"Summary statistics:\n{stats}\n\n"
        f"The first 5 rows of the data:\n{sample_rows}\n{top_cats}"
        f"Correlation between numeric columns:\n{correlations}\n\n"
        "Provide a detailed analysis of this dataset for a professional report. "
        "Discuss notable figures, trends, correlations, outliers, and potential relationships. "
        "Offer hypotheses for why these patterns exist, give concrete examples, and draw multiple conclusions. "
        "Conclude with recommendations or suggestions for further investigation. "
        "Use only standard ASCII characters, without bullet points, emojis, or special punctuation. "
        "The topic of the data is unknown, so analyze without assuming prior knowledge."
    )
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    return response.choices[0].message.content

def create_numeric_plot(df):
    """
    Generate a histogram for the first numeric column.
    Returns buffer, filename, and explanation.
    """
    num_cols = df.select_dtypes(include='number').columns.tolist()
    if not num_cols:
        return None, None, None
    col = num_cols[0]
    buf = io.BytesIO()
    plt.figure(figsize=(6, 4))
    df[col].dropna().hist(bins=20)
    plt.title(f"Distribution of {col}")
    plt.xlabel(col)
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    explanation = f"This histogram shows the distribution of the numeric column '{col}'."
    filename = f"plot_numeric_{col}.png"
    return buf, filename, explanation

def create_category_plot(df):
    """
    Generate a bar chart for top 10 values of the first categorical column.
    Returns buffer, filename, and explanation.
    """
    cat_cols = df.select_dtypes(include='object').columns.tolist()
    if not cat_cols:
        return None, None, None
    col = cat_cols[0]
    buf = io.BytesIO()
    plt.figure(figsize=(6, 4))
    df[col].value_counts().head(10).plot(kind='bar')
    plt.title(f"Top 10 values in {col}")
    plt.xlabel(col)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    explanation = f"This bar chart shows the top 10 values in the categorical column '{col}'."
    filename = f"plot_categorical_{col}.png"
    return buf, filename, explanation

def create_correlation_heatmap(df):
    """
    Generate a heatmap of correlations for numeric columns.
    Returns buffer, filename, and explanation.
    """
    num_df = df.select_dtypes(include='number')
    if num_df.shape[1] < 2:
        return None, None, None
    buf = io.BytesIO()
    plt.figure(figsize=(6, 5))
    sns.heatmap(num_df.corr(), annot=True, fmt=".2f", cmap="coolwarm")
    plt.title("Correlation Matrix")
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    explanation = "This heatmap shows pairwise correlations of numeric columns."
    return buf, 'correlation_heatmap.png', explanation

@main.route('/generate_pdf/<int:csv_id>')
def generate_pdf(csv_id):
    """Create and return a PDF report for the CSV file."""
    csv_record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(csv_record.filepath)

    # AI-generated insights
    ai_insight = generate_ai_insight(df)

    # Generate plots
    plot_funcs = [create_numeric_plot, create_category_plot, create_correlation_heatmap]
    plot_infos = [(buf, fname, exp) for func in plot_funcs for buf, fname, exp in [func(df)] if buf]

    # Build PDF
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

    # Insert plots
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

    # Save PDF to disk
    pdf_filename = f"{os.path.splitext(csv_record.filename)[0]}_analysis_report.pdf"
    storage_path = os.path.join(current_app.config['UPLOAD_FOLDER'], pdf_filename)
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    with open(storage_path, 'wb') as f:
        f.write(pdf_bytes)

    # Store report in DB if new
    if not PDFReport.query.filter_by(filename=pdf_filename, user_sub=csv_record.user_sub).first():
        db.session.add(PDFReport(
            filename=pdf_filename,
            user_sub=csv_record.user_sub,
            filepath=storage_path))

        db.session.commit()

    # Send PDF to user
    return send_file(
        storage_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=pdf_filename
    )
