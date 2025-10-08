from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


@api_bp.route('/', methods=['GET'])
def root():
    """Root endpoint showing available endpoints."""
    return jsonify({
        'message': 'Mini Zanzibar API',
        'version': '0.1.0',
        'endpoints': [
            '/hello',
            '/health'
        ]
    })


@api_bp.route('/hello', methods=['GET'])
def hello_world():
    """Simple hello world endpoint."""
    return jsonify({'message': 'Hello, Bojan!'})


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'mini-zanzibar'
    })
