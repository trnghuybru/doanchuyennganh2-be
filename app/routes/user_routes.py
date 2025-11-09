from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models import db

api_bp = Blueprint('api', __name__)

@api_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    data = request.get_json()
    new_name = data.get('name')
    new_email = data.get('email')

    if new_email and new_email != user.email:
        if User.query.filter_by(email=new_email).first():
            return jsonify({'message': 'Email already in use'}), 400
        user.email = new_email

    if new_name:
        user.name = new_name

    db.session.commit()

    return jsonify({'message': 'Profile upadted successfully', 'user':{'id':user.user_id, 'name': user.name, 'email': user.email}}), 200