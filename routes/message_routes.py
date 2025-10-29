from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Message, Room, RoomMember, MessageReaction, User
from config import Config
from datetime import datetime

message_bp = Blueprint('message', __name__)

@message_bp.route('/rooms/<room_id>/messages', methods=['GET'])
@jwt_required()
def get_messages(room_id):
    try:
        current_user = get_jwt_identity()
        
        # Check if user is room member
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 403
        
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        # Get messages with authors and reactions
        messages = Message.query.filter_by(room_id=room_id)\
            .order_by(Message.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Format response
        messages_data = []
        for message in messages.items:
            message_data = message.to_dict()
            
            # Get reactions for this message
            reactions = MessageReaction.query.filter_by(message_id=message.id).all()
            message_data['reactions'] = {}
            
            for reaction in reactions:
                if reaction.emoji not in message_data['reactions']:
                    message_data['reactions'][reaction.emoji] = []
                message_data['reactions'][reaction.emoji].append(reaction.user.to_dict())
            
            messages_data.append(message_data)
        
        return jsonify({
            "messages": messages_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": messages.total,
                "pages": messages.pages
            }
        })
        
    except Exception as e:
        return jsonify({"error": "Server error"}), 500

@message_bp.route('/rooms/<room_id>/messages', methods=['POST'])
@jwt_required()
def send_message(room_id):
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Check if user is room member
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 403
        
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to = data.get('reply_to')
        file_url = data.get('file_url', '').strip()
        
        if not content and not file_url:
            return jsonify({"error": "Message content or file is required"}), 400
        
        # Validate reply_to
        if reply_to:
            parent_message = Message.query.get(reply_to)
            if not parent_message or parent_message.room_id != room_id:
                return jsonify({"error": "Invalid reply message"}), 400
        
        # Create message
        message = Message(
            room_id=room_id,
            user_id=current_user.id,
            content=content,
            message_type=message_type,
            file_url=file_url,
            reply_to=reply_to
        )
        
        db.session.add(message)
        db.session.commit()
        
        return jsonify({
            "message": "Message sent successfully",
            "message_data": message.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during message sending"}), 500

@message_bp.route('/messages/<message_id>', methods=['PUT'])
@jwt_required()
def edit_message(message_id):
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({"error": "Message not found"}), 404
        
        # Check if user owns the message
        if message.user_id != current_user.id:
            return jsonify({"error": "Can only edit your own messages"}), 403
        
        new_content = data.get('content', '').strip()
        if not new_content:
            return jsonify({"error": "Message content is required"}), 400
        
        message.content = new_content
        message.is_edited = True
        
        db.session.commit()
        
        return jsonify({
            "message": "Message updated successfully",
            "message_data": message.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during message edit"}), 500

@message_bp.route('/messages/<message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    try:
        current_user = get_jwt_identity()
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({"error": "Message not found"}), 404
        
        # Check if user owns the message or is room admin
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=message.room_id
        ).first()
        
        can_delete = (message.user_id == current_user.id) or (membership and membership.role in ['admin', 'owner'])
        
        if not can_delete:
            return jsonify({"error": "Insufficient permissions to delete message"}), 403
        
        # Delete reactions first
        MessageReaction.query.filter_by(message_id=message_id).delete()
        
        # Delete message
        db.session.delete(message)
        db.session.commit()
        
        return jsonify({"message": "Message deleted successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during message deletion"}), 500

@message_bp.route('/messages/<message_id>/reactions', methods=['POST'])
@jwt_required()
def add_reaction(message_id):
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        emoji = data.get('emoji', '').strip()
        if not emoji:
            return jsonify({"error": "Emoji is required"}), 400
        
        message = Message.query.get(message_id)
        if not message:
            return jsonify({"error": "Message not found"}), 404
        
        # Check if user is room member
        membership = RoomMember.query.filter_by(
            user_id=current_user.id, 
            room_id=message.room_id
        ).first()
        
        if not membership:
            return jsonify({"error": "Not a member of this room"}), 403
        
        # Check if reaction already exists
        existing_reaction = MessageReaction.query.filter_by(
            message_id=message_id,
            user_id=current_user.id,
            emoji=emoji
        ).first()
        
        if existing_reaction:
            return jsonify({"error": "Reaction already exists"}), 409
        
        # Add reaction
        reaction = MessageReaction(
            message_id=message_id,
            user_id=current_user.id,
            emoji=emoji
        )
        
        db.session.add(reaction)
        db.session.commit()
        
        return jsonify({
            "message": "Reaction added successfully",
            "reaction": {
                'id': reaction.id,
                'emoji': reaction.emoji,
                'user': current_user.to_dict()
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during reaction addition"}), 500

@message_bp.route('/messages/<message_id>/reactions', methods=['DELETE'])
@jwt_required()
def remove_reaction(message_id):
    try:
        current_user = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        emoji = data.get('emoji', '').strip()
        if not emoji:
            return jsonify({"error": "Emoji is required"}), 400
        
        # Find and delete reaction
        reaction = MessageReaction.query.filter_by(
            message_id=message_id,
            user_id=current_user.id,
            emoji=emoji
        ).first()
        
        if not reaction:
            return jsonify({"error": "Reaction not found"}), 404
        
        db.session.delete(reaction)
        db.session.commit()
        
        return jsonify({"message": "Reaction removed successfully"})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Server error during reaction removal"}), 500
