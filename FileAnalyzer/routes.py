from flask import Blueprint, render_template, request, redirect, url_for

# 1) create a Blueprint
main = Blueprint('main', __name__)

@main.route('/')
def home():
    return render_template('base.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        # TODO: handle login logic
        pass
    return render_template('login.html')

@main.route('/register', methods=['POST'])
def register():
    # TODO: handle registration logic
    return redirect(url_for('main.login'))

@main.route('/upload')
def upload():
    return "<h1>Upload Page Placeholder</h1>"
