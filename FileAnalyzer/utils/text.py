def allowed_file(filename):
    """
    Check if the file has an allowed extension (csv).
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'csv'


def clean_text(text):
    """
    Normalize text for PDF output by replacing special characters.
    """
    if not isinstance(text, str):
        text = str(text)
    replacements = {
        "•": "-", "–": "-", "—": "-",
        "’": "'", "“": '"', "”": '"', "…": '...',
        "#": "",
        "*": ""
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode('latin-1', 'replace').decode('latin-1')