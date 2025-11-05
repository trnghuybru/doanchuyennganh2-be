from flask import Blueprint, jsonify

main = Blueprint('main', __name__)

@main.route('/api/hello')
def hello_world():
    return jsonify({'message': 'Hello, World!'})
