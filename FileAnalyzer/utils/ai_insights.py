import warnings
import os
import openai

# Configure OpenAI once for all insight calls
openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o"
MAX_RETRIES = 3


def build_insight_prompt(df):
    """
    Construct the prompt for AI-based dataset analysis.
    """
    stats = df.describe(include='all').to_string()
    columns = ', '.join(df.columns)
    sample_rows = df.head(5).to_string(index=False)

    corr_section = ''
    if df.select_dtypes(include='number').shape[1] >= 2:
        corr_section = df.corr(numeric_only=True).to_string()

    top_cats = ''
    for col in df.select_dtypes(include='object').columns:
        top = df[col].value_counts().head(3)
        top_cats += (
            f"\nTop values in '{col}':\n"
            f"{top.to_string()}\n"
        )
    #we need to use a very general question becauese of the veriaty of the files that can be uploaded
    return (
        f"Here is a dataset with columns: {columns}\n\n"
        f"Summary statistics:\n{stats}\n\n"
        f"The first 5 rows of the data:\n{sample_rows}\n{top_cats}"
        f"Correlation between numeric columns:\n{corr_section}\n\n"
        "Provide a detailed analysis of this dataset for a professional report. "
        "Discuss notable figures, trends, correlations, outliers, and potential relationships. "
        "Offer hypotheses for why these patterns exist, give concrete examples, and draw multiple conclusions. "
        "Conclude with recommendations or suggestions for further investigation. "
        "Use only standard ASCII characters, without bullet points, emojis, or special punctuation."
    )


def generate_ai_insight(df):
    """
    Generate a detailed AI-powered data analysis report with retries.
    """
    prompt = build_insight_prompt(df)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = openai.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )
            return resp.choices[0].message.content
        except openai.error.OpenAIError as e:
            warnings.warn(f"OpenAI API error on attempt {attempt}: {e}")
            if attempt == MAX_RETRIES:
                return "AI insights currently unavailable due to an error."
            continue
