from flask import Blueprint, jsonify, request
from src.acl_db import ACLTuple, ACLDB

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


# POST /acl endpoint
@api_bp.route('/acl', methods=['POST'])
def add_acl():
    data = request.get_json()
    required = {'object', 'relation', 'user'}
    if not data or not required.issubset(data):
        return jsonify({'error': 'Missing required fields'}), 400
    try:
        acl_tuple = ACLTuple(data['object'], data['relation'], data['user'])
        db = ACLDB()
        db.add_acl(acl_tuple)
        db.close()
        return jsonify({'message': 'ACL added', 'acl': acl_tuple.to_string()}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
