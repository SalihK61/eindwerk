import os
import io
import matplotlib.pyplot as plt
import seaborn as sns
from flask import url_for, current_app


def save_histograms(df, record_id, numeric_cols):
    """
    Save histograms for each numeric column to static/analysis and return their URLs.
    """
    analysis_dir = os.path.join(current_app.static_folder, 'analysis', str(record_id))
    os.makedirs(analysis_dir, exist_ok=True)
    paths = []
    for col in numeric_cols:
        plt.figure()
        df[col].dropna().hist()
        plt.title(f'Distribution of {col}')
        img_name = f"{col}.png"
        plt.savefig(os.path.join(analysis_dir, img_name), bbox_inches='tight')
        plt.close()
        paths.append(url_for('static', filename=f'analysis/{record_id}/{img_name}'))
    return paths


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