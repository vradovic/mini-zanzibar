from flask import Blueprint, jsonify, request, current_app
import re
import logging
import bcrypt
import jwt
import datetime
from src.acl_db import ACLTuple, ACLDB
from src.users import USERS
from src.namespace_config import NamespaceConfig
from src.consul_db import ConsulNamespaceStore
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

api_bp = Blueprint('api', __name__)

# Rate limiting for login: 5 requests per minute per IP
limiter = Limiter(get_remote_address, default_limits=["100 per minute"])

consul_store = ConsulNamespaceStore(host='consuldb', port=8500)

logger = logging.getLogger(__name__)


def verify_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, jsonify({'error': 'Missing or invalid token'}), 401

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, 'super-secret-key', algorithms=['HS256'])
        return payload, None, None
    except jwt.ExpiredSignatureError:
        return None, jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return None, jsonify({'error': 'Invalid token'}), 401

# POST /login endpoint


@api_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Missing username or password'}), 400
    username = data['username']
    password = data['password']
    user = USERS.get(username)
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    # bcrypt proverava lozinku
    if not bcrypt.checkpw(password.encode(), user['password'].encode()):
        return jsonify({'error': 'Invalid credentials'}), 401
    # Generate JWT token
    payload = {
        'username': username,
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, 'super-secret-key', algorithm='HS256')
    return jsonify({'token': token, 'role': user['role']}), 200


@api_bp.route('/', methods=['GET'])
def root():
    """Root endpoint showing available endpoints."""
    return jsonify({
        'message': 'Mini Zanzibar API',
        'version': '0.1.0',
        'endpoints': [
            'POST /login',
            'POST /acl',
            'POST /namespace',
            'GET /namespace/<namespace>',
        ]
    })


# POST /acl endpoint with JWT auth and role check
@api_bp.route('/acl', methods=['POST'])
def add_acl():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid token'}), 401
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, 'super-secret-key', algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'error': 'Invalid token'}), 401

    username = payload['username']
    role = payload['role']

    data = request.get_json()
    required = {'object', 'relation', 'user'}
    if not data or not required.issubset(data):
        return jsonify({'error': 'Missing required fields'}), 400

    # Input validation
    object_re = r'^[a-zA-Z0-9:_\-]{3,64}$'
    relation_re = r'^[a-zA-Z0-9_]{3,32}$'
    user_re = r'^[a-zA-Z0-9:_\-]{3,64}$'
    if not re.match(object_re, data['object']):
        return jsonify({'error': 'Invalid object format'}), 400
    if not re.match(relation_re, data['relation']):
        return jsonify({'error': 'Invalid relation format'}), 400
    if not re.match(user_re, data['user']):
        return jsonify({'error': 'Invalid user format'}), 400

    # Role-based access control example
    # Samo admin može menjati ACL za owner relaciju
    if data['relation'] == 'owner' and role != 'admin':
        return jsonify({'error': 'Only admin can modify owner ACL'}), 403

    try:
        acl_tuple = ACLTuple(data['object'], data['relation'], data['user'])
        db = ACLDB()
        db.add_acl(acl_tuple)
        db.close()
        # Audit log
        logging.basicConfig(level=logging.INFO)
        logging.info(
            f"ACL changed by {username} ({role}): {acl_tuple.to_string()}")
        return jsonify({'message': 'ACL added', 'acl': acl_tuple.to_string()}), 201
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/namespace', methods=['POST'])
def create_namespace():
    payload, error_response, status_code = verify_token()
    if error_response:
        return error_response, status_code

    if payload.get('role') != 'admin':
        return jsonify({'error': 'Only admin can create or update namespaces'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    if 'namespace' not in data or 'relations' not in data:
        return jsonify({'error': 'Missing required fields: namespace, relations'}), 400

    try:
        config = NamespaceConfig(
            namespace=data['namespace'],
            relations=data['relations']
        )

        consul_store.save_namespace(config)

        logger.info(
            f"Namespace '{config.namespace}' created/updated by {payload['username']}"
        )

        return jsonify({
            'message': 'Namespace configuration saved',
            'namespace': config.namespace,
            'relations': list(config.relations.keys())
        }), 201

    except ValueError as e:
        return jsonify({'error': f'Validation error: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error creating namespace: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@api_bp.route('/namespace/<namespace>', methods=['GET'])
def get_namespace(namespace):
    _, error_response, status_code = verify_token()
    if error_response:
        return error_response, status_code

    try:
        config = consul_store.get_namespace(namespace)

        if config is None:
            return jsonify({'error': f'Namespace "{namespace}" not found'}), 404

        return jsonify({
            'namespace': config.namespace,
            'relations': config.relations
        }), 200

    except Exception as e:
        logger.error(f"Error getting namespace {namespace}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
