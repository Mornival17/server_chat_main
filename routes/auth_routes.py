from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from models import db, User, LoginAttempt
from auth import validate_email, validate_username, validate_password, check_login_attempts, record_login_attempt, get_client_ip

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip() or username
        
        # Validation
        if not validate_username(username):
            return jsonify({"error": "Username must be 3-20 characters and contain only letters, numbers, and underscores"}), 400
        
        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400
        
        if not validate_password(password):
            return jsonify({"error": "Password must be at least 6 characters long"}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already exists"}), 409
        
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already exists"}), 409
        
        # Create user
        user = User(
            username=username,
            email=email,
            display_name=display_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(identity=user)
        
        return jsonify({
            "message": "User created successfully",
            "user": user.to_dict(),
            "access_token": access_token
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during registration"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400
        
        ip_address = get_client_ip()
        
        # Check login attempts
        if not check_login_attempts(ip_address, username):
            return jsonify({
                "error": "Too many login attempts. Please try again in 15 minutes.",
                "blocked": True
            }), 429
        
        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and user.check_password(password):
            # Update user status
            user.is_online = True
            user.last_seen = db.func.now()
            db.session.commit()
            
            # Record successful attempt
            record_login_attempt(ip_address, username, True)
            
            # Create access token
            access_token = create_access_token(identity=user)
            
            return jsonify({
                "message": "Login successful",
                "user": user.to_dict(),
                "access_token": access_token
            })
        else:
            # Record failed attempt
            record_login_attempt(ip_address, username, False)
            return jsonify({"error": "Invalid username or password"}), 401
            
    except Exception as e:
        return jsonify({"error": "Server error during login"}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        current_user = get_jwt_identity()
        return jsonify({"user": current_user.to_dict()})
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        display_name = data.get('display_name', '').strip()
        avatar_url = data.get('avatar_url', '').strip()
        
        if display_name:
            current_user.display_name = display_name
        
        if avatar_url:
            current_user.avatar_url = avatar_url
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile updated successfully",
            "user": current_user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during profile update"}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        current_user = get_jwt_identity()
        current_user.is_online = False
        current_user.last_seen = db.func.now()
        db.session.commit()
        
        return jsonify({"message": "Logout successful"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during logout"}), 500
