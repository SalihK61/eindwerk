from flask import Flask
from routes import main  # import your Blueprint

def create_app():
    app = Flask(__name__)
    # 2) register the Blueprint
    app.register_blueprint(main)
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
