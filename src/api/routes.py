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


def validate_acl_params(object_id, relation, user):
    object_re = r'^[a-zA-Z0-9:_\-]{3,64}$'
    relation_re = r'^[a-zA-Z0-9_]{3,32}$'
    user_re = r'^[a-zA-Z0-9:_\-]{3,64}$'

    if not re.match(object_re, object_id):
        return jsonify({'error': 'Invalid object format'}), 400
    if not re.match(relation_re, relation):
        return jsonify({'error': 'Invalid relation format'}), 400
    if not re.match(user_re, user):
        return jsonify({'error': 'Invalid user format'}), 400

    return None, None

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
            'GET /acl/check',
            'POST /namespace',
            'GET /namespace/<namespace>',
        ]
    })


# POST /acl endpoint with JWT auth and role check
@api_bp.route('/acl', methods=['POST'])
def add_acl():
    # Debug logging
    logger.info(
        f"POST /acl - Content-Type: {request.headers.get('Content-Type')}")
    logger.info(f"POST /acl - Raw data: {request.data}")

    payload, error_response, status_code = verify_token()
    if error_response:
        return error_response, status_code

    username = payload['username']
    role = payload['role']

    data = request.get_json()
    logger.info(f"POST /acl - Parsed JSON: {data}")

    required = {'object', 'relation', 'user'}
    if not data or not required.issubset(data):
        logger.error(
            f"POST /acl - Missing fields. Data: {data}, Required: {required}")
        return jsonify({'error': 'Missing required fields'}), 400

    # Input validation
    error_response, status_code = validate_acl_params(
        data['object'], data['relation'], data['user'])
    if error_response:
        return error_response, status_code

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


# GET /acl/check endpoint - Check ACL authorization
@api_bp.route('/acl/check', methods=['GET'])
def check_acl():
    payload, error_response, status_code = verify_token()
    if error_response:
        return error_response, status_code

    object_id = request.args.get('object')
    relation = request.args.get('relation')
    user = request.args.get('user')

    if not object_id or not relation or not user:
        return jsonify({'error': 'Missing required parameters: object, relation, user'}), 400

    # Input validation
    error_response, status_code = validate_acl_params(
        object_id, relation, user)
    if error_response:
        return error_response, status_code

    try:
        # Extract namespace from object (e.g., "doc:readme" -> "doc")
        namespace = object_id.split(':')[0] if ':' in object_id else object_id

        # Get namespace configuration
        namespace_config = consul_store.get_namespace(namespace)

        # Determine which relations to check (including inherited ones)
        relations_to_check = [relation]
        if namespace_config and namespace_config.has_relation(relation):
            relations_to_check = namespace_config.compute_inherited_relations(
                relation)

        # Check ACL for the requested relation and all inherited relations
        db = ACLDB()
        authorized = False

        for rel in relations_to_check:
            acl_tuple = ACLTuple(object_id, rel, user)
            if db.check_acl(acl_tuple):
                authorized = True
                logger.info(
                    f"ACL check: {user} authorized for {object_id}#{relation} (via {rel})")
                break

        db.close()

        if not authorized:
            logger.info(
                f"ACL check: {user} NOT authorized for {object_id}#{relation}")

        return jsonify({'authorized': authorized}), 200

    except Exception as e:
        logger.error(f"Error checking ACL: {str(e)}")
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
        logger.warning(f"Validation error while creating namespace: {str(e)}")
        return jsonify({'error': 'Validation error'}), 400
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
