from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.user import User
from app.models import db
from flask_jwt_extended import create_access_token
import uuid

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not all(key in data for key in ['email', 'password', 'name']):
            return jsonify({'message': 'Missing required fields'}), 400
            
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        
        # Validate email format
        if '@' not in email:
            return jsonify({'message': 'Invalid email format'}), 400
            
        # Validate password length
        if len(password) < 6:
            return jsonify({'message': 'Password must be at least 6 characters'}), 400
            
        # Check existing user
        if User.query.filter_by(email=email).first():
            return jsonify({'message': 'Email already registered'}), 400
        
        # Create user
        user = User(
            user_id=f"u_{email.split('@')[0]}_{str(uuid.uuid4())[:8]}", # Make ID more unique
            name=name,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User registered successfully',
            'user': {
                'id': user.user_id,
                'name': user.name,
                'email': user.email
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not all(key in data for key in ['email', 'password']):
            return jsonify({'message': 'Missing email or password'}), 400
            
        email = data.get('email')
        password = data.get('password')

        # Find user and verify password
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            return jsonify({'message': 'Invalid email or password'}), 401
        
        # Generate token with expiration
        token = create_access_token(
            identity=user.user_id,
            expires_delta=False  # No expiration
        )

        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user.user_id,
                'name': user.name,
                'email': user.email
            }
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Login failed: {str(e)}'}), 500
