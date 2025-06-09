import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth0
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
    AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
    AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
    AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL")

    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    REPORT_FOLDER = os.getenv('REPORT_FOLDER', 'reports')