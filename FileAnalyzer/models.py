from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id       = db.Column(db.Integer, primary_key=True)
    sub      = db.Column(db.String(64), unique=True, nullable=False)  # Auth0 user_id
    name     = db.Column(db.String(128), nullable=False)
    email    = db.Column(db.String(128), unique=True, nullable=False)
    picture  = db.Column(db.String(256), nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"
