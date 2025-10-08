from flask import Flask
from src.api.routes import api_bp


if __name__ == '__main__':
    app = Flask(__name__)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.run(host='0.0.0.0', port=5000, debug=True)
