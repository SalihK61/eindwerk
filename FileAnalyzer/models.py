from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    sub      = db.Column(db.String(64), unique=True, nullable=False)  # Auth0 user_id
    name     = db.Column(db.String(128), nullable=False)
    email    = db.Column(db.String(128), unique=True)
    picture  = db.Column(db.String(256), nullable=True)

    csv_files = db.relationship('CSVFile', back_populates='user')

class CSVFile(db.Model):
    __tablename__ = 'csv_files'
    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(64), db.ForeignKey('users.sub'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    upload_time = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', back_populates='csv_files')

class PDFReport(db.Model):
    __tablename__ = 'pdf_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(64), db.ForeignKey('users.sub'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    filepath = db.Column(db.String(512), nullable=False)
    generated_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"<User {self.email}>"
