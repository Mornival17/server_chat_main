from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Room, RoomMember, User, Message
from auth import validate_username, validate_password

room_bp = Blueprint('room', __name__)

@room_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_rooms():
    try:
        current_user = get_jwt_identity()
        
        # Get public rooms and rooms user is member of
        public_rooms = Room.query.filter_by(is_private=False).all()
        user_memberships = RoomMember.query.filter_by(user_id=current_user.id).all()
        user_room_ids = [membership.room_id for membership in user_memberships]
        user_rooms = Room.query.filter(Room.id.in_(user_room_ids)).all()
        
        all_rooms = list(set(public_rooms + user_rooms))
        
        return jsonify({
            "rooms": [room.to_dict() for room in all_rooms]
        })
        
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@room_bp.route('/rooms', methods=['POST'])
@jwt_required()
def create_room():
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        is_private = data.get('is_private', False)
        password = data.get('password', '')
        
        if not name:
            return jsonify({"error": "Room name is required"}), 400
        
        # Check room limit
        user_room_count = Room.query.filter_by(created_by=current_user.id).count()
        if user_room_count >= 50:  # Config.MAX_ROOMS_PER_USER
            return jsonify({"error": "Room limit reached"}), 400
        
        # Create room
        room = Room(
            name=name,
            description=description,
            is_private=is_private,
            created_by=current_user.id
        )
        room.set_password(password)
        
        db.session.add(room)
        db.session.flush()  # Get room ID
        
        # Add creator as owner
        membership = RoomMember(
            user_id=current_user.id,
            room_id=room.id,
            role='owner'
        )
        db.session.add(membership)
        
        # Add system message
        system_message = Message(
            room_id=room.id,
            user_id=current_user.id,
            content=f"Room '{name}' was created by {current_user.display_name}",
            message_type='system'
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        return jsonify({
            "message": "Room created successfully",
            "room": room.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during room creation"}), 500

@room_bp.route('/rooms/<room_id>', methods=['GET'])
@jwt_required()
def get_room(room_id):
    try:
        current_user = get_jwt_identity()
        
        room = Room.query.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        
        # Check if user can access the room
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=room_id
        ).first()
        
        if room.is_private and not membership:
            return jsonify({"error": "Access denied"}), 403
        
        room_data = room.to_dict()
        
        # Get room members
        members = RoomMember.query.filter_by(room_id=room_id).all()
        room_data['members'] = [
            {
                'user': member.user.to_dict(),
                'role': member.role,
                'joined_at': member.joined_at.isoformat()
            }
            for member in members
        ]
        
        return jsonify({"room": room_data})
        
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@room_bp.route('/rooms/<room_id>/join', methods=['POST'])
@jwt_required()
def join_room(room_id):
    try:
        current_user = get_jwt_identity()
        data = request.get_json() or {}
        
        room = Room.query.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        
        # Check if already member
        existing_membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=room_id
        ).first()
        
        if existing_membership:
            return jsonify({"error": "Already a member of this room"}), 409
        
        # Check password for private rooms
        if room.is_private or room.password_hash:
            password = data.get('password', '')
            if not room.check_password(password):
                return jsonify({"error": "Invalid password"}), 401
        
        # Check member limit
        member_count = RoomMember.query.filter_by(room_id=room_id).count()
        if member_count >= room.max_members:
            return jsonify({"error": "Room is full"}), 400
        
        # Add user to room
        membership = RoomMember(
            user_id=current_user.id,
            room_id=room_id,
            role='member'
        )
        db.session.add(membership)
        
        # Add system message
        system_message = Message(
            room_id=room_id,
            user_id=current_user.id,
            content=f"{current_user.display_name} joined the room",
            message_type='system'
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        return jsonify({
            "message": "Joined room successfully",
            "room": room.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during room join"}), 500

@room_bp.route('/rooms/<room_id>/leave', methods=['POST'])
@jwt_required()
def leave_room(room_id):
    try:
        current_user = get_jwt_identity()
        
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 404
        
        # Add system message
        system_message = Message(
            room_id=room_id,
            user_id=current_user.id,
            content=f"{current_user.display_name} left the room",
            message_type='system'
        )
        db.session.add(system_message)
        
        # Remove membership
        db.session.delete(membership)
        db.session.commit()
        
        return jsonify({"message": "Left room successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during room leave"}), 500
