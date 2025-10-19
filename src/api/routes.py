from flask import Blueprint, jsonify, request, current_app
import re
import logging
import bcrypt
import jwt
import datetime
from src.acl_db import ACLTuple, ACLDB
from src.users import USERS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

api_bp = Blueprint('api', __name__)

# Rate limiting for login: 5 requests per minute per IP
limiter = Limiter(get_remote_address, default_limits=["100 per minute"])

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
            '/login',
            '/acl'
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
        logging.info(f"ACL changed by {username} ({role}): {acl_tuple.to_string()}")
        return jsonify({'message': 'ACL added', 'acl': acl_tuple.to_string()}), 201
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500
