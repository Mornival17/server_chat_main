from .auth_routes import auth_bp
from .room_routes import room_bp
from .message_routes import message_bp

def register_routes(app):
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(room_bp, url_prefix='/api')
    app.register_blueprint(message_bp, url_prefix='/api')
