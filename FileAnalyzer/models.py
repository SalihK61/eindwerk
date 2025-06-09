from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    sub      = db.Column(db.String(64), unique=True, nullable=False)  # Auth0 user_id
    name     = db.Column(db.String(128), nullable=False)
    email    = db.Column(db.String(128), unique=True, nullable=False)
    picture  = db.Column(db.String(256), nullable=True)

class CSVFile(db.Model):
    __tablename__ = 'csv_files'
    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(64), db.ForeignKey('users.sub'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    uploaded_at = db.Column(db.DateTime, server_default=db.func.now())

class PDFReport(db.Model):
    __tablename__ = 'pdf_reports'
    id = db.Column(db.Integer, primary_key=True)
    user_sub = db.Column(db.String(64), db.ForeignKey('users.sub'), nullable=False)
    filename = db.Column(db.String(256), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    generated_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self):
        return f"<User {self.email}>"
