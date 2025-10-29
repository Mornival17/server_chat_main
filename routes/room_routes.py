from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Room, RoomMember, User, Message

room_bp = Blueprint('room', __name__)

@room_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_rooms():
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
        
        # Get public rooms and rooms user is member of
        public_rooms = Room.query.filter_by(is_private=False).all()
        user_memberships = RoomMember.query.filter_by(user_id=current_user_id).all()
        user_room_ids = [membership.room_id for membership in user_memberships]
        user_rooms = Room.query.filter(Room.id.in_(user_room_ids)).all()
        
        all_rooms = list(set(public_rooms + user_rooms))
        
        return jsonify({
            "rooms": [room.to_dict() for room in all_rooms]
        })
        
    except Exception as e:
        print(f"❌ Error in /rooms GET: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@room_bp.route('/rooms', methods=['POST'])
@jwt_required()
def create_room():
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
            
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
        user_room_count = Room.query.filter_by(created_by=current_user_id).count()
        if user_room_count >= 50:
            return jsonify({"error": "Room limit reached"}), 400
        
        # Create room
        room = Room(
            name=name,
            description=description,
            is_private=is_private,
            created_by=current_user_id
        )
        room.set_password(password)
        
        db.session.add(room)
        db.session.flush()  # Get room ID without committing
        
        # Add creator as owner
        membership = RoomMember(
            user_id=current_user_id,
            room_id=room.id,
            role='owner'
        )
        db.session.add(membership)
        
        # Add system message
        system_message = Message(
            room_id=room.id,
            user_id=current_user_id,
            content=f"Room '{name}' was created by {current_user.display_name}",
            message_type='system'
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        print(f"✅ Room created: {name} (ID: {room.id}) by {current_user.username}")
        
        return jsonify({
            "message": "Room created successfully",
            "room": room.to_dict(),
            "auto_joined": True  # Сообщаем что пользователь автоматически присоединился
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in /rooms POST: {str(e)}")
        return jsonify({"error": f"Server error during room creation: {str(e)}"}), 500

@room_bp.route('/rooms/<room_id>', methods=['GET'])
@jwt_required()
def get_room(room_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
            
        room = Room.query.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        
        # Check if user can access the room
        membership = RoomMember.query.filter_by(
            user_id=current_user_id, 
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
        
        # Добавляем информацию о том, является ли пользователь участником
        room_data['is_member'] = membership is not None
        
        return jsonify({"room": room_data})
        
    except Exception as e:
        print(f"❌ Error in /rooms/<room_id> GET: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@room_bp.route('/rooms/<room_id>/join', methods=['POST'])
@jwt_required()
def join_room(room_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
            
        data = request.get_json() or {}
        
        room = Room.query.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        
        # Check if already member
        existing_membership = RoomMember.query.filter_by(
            user_id=current_user_id, 
            room_id=room_id
        ).first()
        
        if existing_membership:
            # Если уже участник, просто возвращаем успех и переходим в чат
            return jsonify({
                "message": "Already a member",
                "room": room.to_dict(),
                "already_member": True
            })
        
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
            user_id=current_user_id,
            room_id=room_id,
            role='member'
        )
        db.session.add(membership)
        
        # Add system message только если пользователь действительно впервые входит
        system_message = Message(
            room_id=room_id,
            user_id=current_user_id,
            content=f"{current_user.display_name} joined the room",
            message_type='system'
        )
        db.session.add(system_message)
        
        db.session.commit()
        
        print(f"✅ User {current_user.username} joined room {room_id}")
        
        return jsonify({
            "message": "Joined room successfully",
            "room": room.to_dict(),
            "new_member": True
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in /rooms/<room_id>/join: {str(e)}")
        return jsonify({"error": "Server error during room join"}), 500

@room_bp.route('/rooms/<room_id>/enter', methods=['POST'])
@jwt_required()
def enter_room(room_id):
    """Альтернативный endpoint для входа в комнату - всегда разрешает вход участникам"""
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
            
        room = Room.query.get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404
        
        # Check if user is member
        membership = RoomMember.query.filter_by(
            user_id=current_user_id, 
            room_id=room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 403
        
        # Если пользователь участник - разрешаем вход
        print(f"✅ User {current_user.username} entered room {room_id}")
        
        return jsonify({
            "message": "Entered room successfully",
            "room": room.to_dict(),
            "is_member": True
        })
        
    except Exception as e:
        print(f"❌ Error in /rooms/<room_id>/enter: {str(e)}")
        return jsonify({"error": "Server error during room enter"}), 500

@room_bp.route('/rooms/<room_id>/leave', methods=['POST'])
@jwt_required()
def leave_room(room_id):
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        if not current_user:
            return jsonify({"error": "User not found"}), 404
            
        membership = RoomMember.query.filter_by(
            user_id=current_user_id, 
            room_id=room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 404
        
        # Если пользователь владелец комнаты, проверяем есть ли другие участники
        if membership.role == 'owner':
            other_members = RoomMember.query.filter(
                RoomMember.room_id == room_id,
                RoomMember.user_id != current_user_id
            ).count()
            
            if other_members > 0:
                # Назначаем нового владельца (первого попавшегося участника)
                new_owner = RoomMember.query.filter(
                    RoomMember.room_id == room_id,
                    RoomMember.user_id != current_user_id
                ).first()
                
                if new_owner:
                    new_owner.role = 'owner'
                    # Добавляем системное сообщение о смене владельца
                    system_message = Message(
                        room_id=room_id,
                        user_id=current_user_id,
                        content=f"{new_owner.user.display_name} is now the room owner",
                        message_type='system'
                    )
                    db.session.add(system_message)
        
        # Add system message about leaving
        system_message = Message(
            room_id=room_id,
            user_id=current_user_id,
            content=f"{current_user.display_name} left the room",
            message_type='system'
        )
        db.session.add(system_message)
        
        # Remove membership
        db.session.delete(membership)
        db.session.commit()
        
        print(f"✅ User {current_user.username} left room {room_id}")
        
        return jsonify({"message": "Left room successfully"})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error in /rooms/<room_id>/leave: {str(e)}")
        return jsonify({"error": "Server error during room leave"}), 500

@room_bp.route('/rooms/<room_id>/membership', methods=['GET'])
@jwt_required()
def check_membership(room_id):
    """Проверка является ли пользователь участником комнаты"""
    try:
        current_user_id = get_jwt_identity()
        
        membership = RoomMember.query.filter_by(
            user_id=current_user_id, 
            room_id=room_id
        ).first()
        
        return jsonify({
            "is_member": membership is not None,
            "role": membership.role if membership else None
        })
        
    except Exception as e:
        print(f"❌ Error in /rooms/<room_id>/membership: {str(e)}")
        return jsonify({"error": "Server error"}), 500
