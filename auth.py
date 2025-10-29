from flask import request, jsonify
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from models import db, User, LoginAttempt
from config import Config
from datetime import datetime, timedelta
import re

jwt = JWTManager()

def init_auth(app):
    jwt.init_app(app)

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user.id

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.get(identity)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username):
    pattern = r'^[a-zA-Z0-9_]{3,20}$'
    return re.match(pattern, username) is not None

def validate_password(password):
    return len(password) >= 6

def check_login_attempts(ip_address, username):
    # Check attempts in last 15 minutes
    time_threshold = datetime.utcnow() - timedelta(seconds=Config.LOGIN_BLOCK_TIME)
    recent_attempts = LoginAttempt.query.filter(
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.username == username,
        LoginAttempt.attempted_at >= time_threshold,
        LoginAttempt.successful == False
    ).count()
    
    return recent_attempts < Config.MAX_LOGIN_ATTEMPTS

def record_login_attempt(ip_address, username, successful):
    attempt = LoginAttempt(
        ip_address=ip_address,
        username=username,
        successful=successful
    )
    db.session.add(attempt)
    db.session.commit()

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr
