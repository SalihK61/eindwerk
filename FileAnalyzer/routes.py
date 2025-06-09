import os
import warnings
from flask import (
    Blueprint, render_template, session,
    redirect, url_for, current_app, request, flash, send_file
)
from authlib.integrations.flask_client import OAuthError
from models import db, User, CSVFile, PDFReport
from werkzeug.utils import secure_filename
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import openai
from fpdf import FPDF

openai.api_key = os.getenv("OPENAI_API_KEY")

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
    userinfo = current_app.auth0.get(
        f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo", token=token
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

@main.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return render_template('dashboard.html', user=session['user'])

@main.route('/reports')
def reports():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    pdfs = []  # placeholder for generated reports
    return render_template('reports.html', reports=pdfs)

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

        csv_record = CSVFile(
            user_sub=session['user']['sub'],
            filename=filename,
            filepath=file_path
        )
        db.session.add(csv_record)
        db.session.commit()

        df = pd.read_csv(file_path)
        if df.empty:
            flash('Uploaded CSV is empty.', 'danger')
            return redirect(request.url)

        # 1. Analyse CSV
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

        # 2. Remove duplicates
        total_rows = len(df)
        dup_count = df.duplicated().sum()
        cleaned_filename = f"cleaned_{filename}"
        cleaned_path = os.path.join(upload_folder, cleaned_filename)
        df.drop_duplicates().to_csv(cleaned_path, index=False)

        # 3. Detect missing data
        missing_stats = df.isna().sum().to_dict()
        missing_rows = df[df.isna().any(axis=1)]
        missing_filename = f"missing_{filename}"
        missing_rows.to_csv(os.path.join(upload_folder, missing_filename), index=False)

        # 4. Static histograms
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
            'analysis.html',
            filename=filename,
            dtypes=dtypes,
            basic_stats=basic_stats,
            corr=corr_html,
            total_rows=total_rows,
            dup_count=dup_count,
            cleaned_filename=cleaned_filename,
            missing_stats=missing_stats,
            missing_rows_count=len(missing_rows),
            missing_filename=missing_filename,
            numeric_cols=numeric_cols,
            hist_paths=hist_paths,
            csv_file=csv_record
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

    # 1. Analyse CSV
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

    # 2. Remove duplicates
    total_rows = len(df)
    dup_count = df.duplicated().sum()
    cleaned_filename = f"cleaned_{record.filename}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    df.drop_duplicates().to_csv(os.path.join(upload_folder, cleaned_filename), index=False)

    # 3. Detect missing data
    missing_stats = df.isna().sum().to_dict()
    missing_rows_count = int(df[df.isna().any(axis=1)].shape[0])
    missing_filename = f"missing_{record.filename}"
    df[df.isna().any(axis=1)].to_csv(os.path.join(upload_folder, missing_filename), index=False)

    # 4. Static histograms
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

    #ai insights
    ai_insight = generate_ai_insight(df)

    return render_template(
        'analysis.html',
        filename=record.filename,
        dtypes=dtypes,
        basic_stats=basic_stats,
        corr=corr_html,
        total_rows=total_rows,
        dup_count=dup_count,
        cleaned_filename=cleaned_filename,
        missing_stats=missing_stats,
        missing_rows_count=missing_rows_count,
        missing_filename=missing_filename,
        numeric_cols=numeric_cols,
        hist_paths=hist_paths,
        csv_file=record
    )

@main.route('/download/<path:filename>')
def download_file(filename):
    return send_file(
        io.BytesIO(open(os.path.join(current_app.config['UPLOAD_FOLDER'], filename), 'rb').read()),
        mimetype='text/csv',
        download_name=filename,
        as_attachment=True
    )


@main.route('/generate_pdf/<int:csv_id>')
def generate_pdf(csv_id):
    import io
    import os
    from flask import send_file, current_app
    from fpdf import FPDF
    from models import CSVFile, PDFReport, db

    # 1. Find the uploaded file and load dataframe
    csv_record = CSVFile.query.get_or_404(csv_id)
    df = pd.read_csv(csv_record.filepath)

    # 2. AI Analysis
    ai_insight = generate_ai_insight(df)

    # 3. Generic plot
    plot_buf = create_generic_plot(df)

    # 4. PDF creation
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"CSV Analyse Rapport voor {csv_record.filename}", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.ln(5)
    pdf.cell(0, 10, "Samenvattende statistieken:", ln=True)
    pdf.set_font("Arial", size=9)
    stats = df.describe(include='all').to_string()
    for line in stats.split('\n'):
        pdf.cell(0, 7, line, ln=True)
    pdf.ln(3)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "AI-Analyse:", ln=True)
    pdf.set_font("Arial", size=10)
    for line in ai_insight.split('\n'):
        pdf.multi_cell(0, 7, line)
    pdf.ln(5)

    # Save plot to a temporary file
    plot_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"plot_{csv_id}.png")
    with open(plot_path, "wb") as f:
        f.write(plot_buf.getbuffer())
    pdf.image(plot_path, x=10, w=pdf.w - 20)
    os.remove(plot_path)

    # Save to in-memory buffer for download
    output = io.BytesIO()
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    output.write(pdf_bytes)
    output.seek(0)

    # Save to PDFReport database table (optional, remove if not needed)
    pdf_filename = f"{os.path.splitext(csv_record.filename)[0]}_analysis_report.pdf"
    # Only add if not already in the DB, else you get duplicates:
    existing = PDFReport.query.filter_by(filename=pdf_filename, user_id=csv_record.user.id).first()
    if not existing:
        pdf_report = PDFReport(filename=pdf_filename, user_id=csv_record.user.id)
        db.session.add(pdf_report)
        db.session.commit()

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_filename
    )



def generate_ai_insight(df):
    stats = df.describe(include='all').to_string()
    columns = ', '.join(df.columns)
    sample_rows = df.head(5).to_string(index=False)
    prompt = (
        f"Hier is een dataset met kolommen: {columns}\n\n"
        f"Samenvattende statistieken:\n{stats}\n\n"
        f"De eerste 5 rijen van de data:\n{sample_rows}\n\n"
        "Geef een gedetailleerde, begrijpelijke analyse en interessante inzichten voor een rapport. "
        "Beschrijf opvallende cijfers, trends, mogelijke verbanden, of bijzonderheden. "
        "De data kan over eender welk onderwerp gaan, dus geef de analyse zonder specifieke voorkennis."
    )
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=350,
    )
    return response.choices[0].message.content


def create_generic_plot(df):
    num_cols = df.select_dtypes(include='number').columns.tolist()
    cat_cols = df.select_dtypes(include='object').columns.tolist()
    buf = io.BytesIO()
    plt.figure(figsize=(6, 4))

    if num_cols:
        col = num_cols[0]
        df[col].dropna().hist(bins=10)
        plt.title(f"Verdeling van {col}")
        plt.xlabel(col)
        plt.ylabel("Frequentie")
    elif cat_cols:
        col = cat_cols[0]
        df[col].value_counts().head(10).plot(kind="bar")
        plt.title(f"Top 10 meest voorkomende waarden in {col}")
        plt.xlabel(col)
        plt.ylabel("Frequentie")
    else:
        plt.text(0.5, 0.5, "Geen geschikte kolom voor grafiek", ha='center')
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close()
    buf.seek(0)
    return buf



