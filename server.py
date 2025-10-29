from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db, User, Room, RoomMember, Message, MessageReaction, LoginAttempt, UserSession
from auth import init_auth
from routes import register_routes
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Database configuration
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///chat.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    CORS(app)
    init_auth(app)
    
    # Register routes
    register_routes(app)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy", "message": "Chat server is running"})
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    print("🚀 Starting Secure Chat Server...")
    print("📊 Database:", app.config['SQLALCHEMY_DATABASE_URI'])
    print("🔐 Authentication: Enabled")
    print("🌐 CORS: Enabled")
    print("📡 Available Endpoints:")
    print("   POST /api/auth/register - Register new user")
    print("   POST /api/auth/login - Login user")
    print("   GET  /api/auth/profile - Get user profile")
    print("   PUT  /api/auth/profile - Update user profile")
    print("   POST /api/auth/logout - Logout user")
    print("   GET  /api/rooms - Get available rooms")
    print("   POST /api/rooms - Create new room")
    print("   GET  /api/rooms/<room_id> - Get room details")
    print("   POST /api/rooms/<room_id>/join - Join room")
    print("   POST /api/rooms/<room_id>/leave - Leave room")
    print("   GET  /api/rooms/<room_id>/messages - Get room messages")
    print("   POST /api/rooms/<room_id>/messages - Send message")
    print("   PUT  /api/messages/<message_id> - Edit message")
    print("   DELETE /api/messages/<message_id> - Delete message")
    print("   POST /api/messages/<message_id>/reactions - Add reaction")
    print("   DELETE /api/messages/<message_id>/reactions - Remove reaction")
    print("   GET  /health - Health check")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
