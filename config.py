import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=30)
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:///chat.db'
    
    # Security
    MAX_MESSAGES_PER_ROOM = 1000
    MAX_ROOMS_PER_USER = 50
    MAX_USERS_PER_ROOM = 100
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_BLOCK_TIME = 900  # 15 minutes
    
    # File upload
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'mp4'}
