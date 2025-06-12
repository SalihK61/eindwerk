import pandas as pd
import numpy as np


def compute_basic_stats(df):
    """
    Compute mean, median, mode, and missing count for each column.
    """
    stats = []
    for col in df.columns:
        col_data = df[col]
        modes = col_data.mode()
        mode_val = (
            float(modes.iloc[0]) if pd.api.types.is_numeric_dtype(col_data) and not modes.empty
            else modes.iloc[0] if not modes.empty
            else 'N/A'
        )
        stats.append({
            'column': col,
            'mean': float(col_data.mean()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
            'median': float(col_data.median()) if pd.api.types.is_numeric_dtype(col_data) else 'N/A',
            'mode': mode_val,
            'missing': int(col_data.isna().sum())
        })
    return stats


def make_corr_html(df):
    """
    Generate HTML table for correlation matrix of numeric columns.
    """
    corr = df.select_dtypes(include=[np.number]).corr()
    return corr.to_html(classes='table table-bordered text-black', border=0) if not corr.empty else ''
