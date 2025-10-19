
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.api.routes import api_bp


def create_app():
    app = Flask(__name__)
    # Rate limiting: 10 POSTs per minute per IP
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["100 per minute"]
    )
    app.register_blueprint(api_bp, url_prefix='/api')
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000)
