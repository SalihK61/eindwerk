import pandas as pd
import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose
import io
from matplotlib import pyplot as plt


def run_economic_analysis(filepath):
    # 1) Read all sheets
    xl = pd.ExcelFile(filepath)
    results = {}
    figures = {}

    for sheet in xl.sheet_names:
        df = xl.parse(sheet)

        # Example: assume a “Date” column + numeric “Value” columns
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.set_index('Date').sort_index()

        # 2) Descriptive stats
        desc = df.describe().to_dict()

        # 3) Year-over-Year growth
        yoy = df.pct_change(periods=12).dropna()
        desc['yoy_mean'] = yoy.mean().to_dict()

        # 4) Seasonal decomposition on the first numeric column
        col = df.select_dtypes(float).columns[0]
        decomposition = seasonal_decompose(df[col], period=12, model='additive')

        # 5) Plot the decomposition
        buf = io.BytesIO()
        decomposition.plot()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        figures[sheet] = buf  # you’ll pass this buffer to your template or PDF builder

        # Consolidate insights
        results[sheet] = {
            'descriptive_stats': desc,
            'seasonal_trend_insights': (
                f"Peak seasonal effects around month {decomposition.seasonal.idxmax()}. "
                f"Overall trend slope: {np.polyfit(range(len(df[col])), df[col], 1)[0]:.4f}"
            )
        }

    return results, figures
