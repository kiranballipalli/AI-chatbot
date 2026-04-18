from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_bcrypt import Bcrypt
from services.ollama_service import chat_with_ai, stream_chat_with_ai, get_available_models
from utils import helpers
from utils.auth import login_manager, bcrypt, create_user, verify_user, User
import os
import json

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Session settings
app.config.update(
    SESSION_COOKIE_SECURE=False,  # True if using HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400
)

# Initialize extensions
login_manager.init_app(app)
bcrypt.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = None

# ==================== AUTH ROUTES ====================
@app.route('/login', methods=['GET'])
def login_page():
    if current_user.is_authenticated:
        return redirect('/')
    return render_template('login.html')

@app.route('/register', methods=['GET'])
def register_page():
    if current_user.is_authenticated:
        return redirect('/')
    return render_template('register.html')

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    user_id = create_user(username, password)
    if user_id:
        return jsonify({'success': True})
    return jsonify({'error': 'Username already taken'}), 400

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = verify_user(username, password)
    if user:
        login_user(user, remember=True)
        return jsonify({'success': True, 'redirect': '/'})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'success': True})

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    if current_user.is_authenticated:
        return jsonify({'authenticated': True, 'username': current_user.username})
    return jsonify({'authenticated': False})

# ==================== MAIN UI ====================
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# ==================== MODELS ====================
@app.route('/api/models', methods=['GET'])
@login_required
def list_models():
    return jsonify(get_available_models())

# ==================== CONVERSATIONS ====================
@app.route('/api/conversations', methods=['GET'])
@login_required
def list_conversations():
    convs = helpers.get_all_conversations_for_user(current_user.id)
    return jsonify(convs)

@app.route('/api/conversations', methods=['POST'])
@login_required
def new_conversation():
    conv_id = helpers.create_conversation_for_user(current_user.id)
    return jsonify({'id': conv_id, 'title': 'New Chat'})

@app.route('/api/conversations/<int:conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    conv = helpers.get_conversation(conv_id)
    if not conv or conv['user_id'] != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    messages = helpers.get_conversation_messages(conv_id)
    return jsonify({'messages': messages})

@app.route('/api/conversations/<int:conv_id>', methods=['DELETE'])
@login_required
def delete_conversation(conv_id):
    conv = helpers.get_conversation(conv_id)
    if not conv or conv['user_id'] != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    helpers.delete_conversation(conv_id)
    return jsonify({'success': True})

# ==================== EXPORT ====================
@app.route('/api/conversations/<int:conv_id>/export', methods=['GET'])
@login_required
def export_conversation(conv_id):
    conv = helpers.get_conversation(conv_id)
    if not conv or conv['user_id'] != current_user.id:
        return jsonify({'error': 'Not found'}), 404
    messages = helpers.get_conversation_messages(conv_id)
    md_lines = [f"# {conv['title']}\n"]
    for msg in messages:
        role = "**User**" if msg['role'] == 'user' else "**Assistant**"
        md_lines.append(f"### {role}\n{msg['content']}\n")
    md_content = "\n".join(md_lines)
    return Response(md_content, mimetype='text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="conversation_{conv_id}.md"'})

# ==================== CHAT (NORMAL & STREAMING) ====================
@app.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    user_message = data.get('message', '').strip()
    conv_id = data.get('conversation_id')
    model = data.get('model', 'llama3')

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Create/verify conversation
    if not conv_id:
        conv_id = helpers.create_conversation_for_user(current_user.id)
    else:
        conv = helpers.get_conversation(conv_id)
        if not conv or conv['user_id'] != current_user.id:
            conv_id = helpers.create_conversation_for_user(current_user.id)

    # Save user message
    helpers.save_message(conv_id, 'user', user_message)

    # Auto-title if first message
    messages = helpers.get_conversation_messages(conv_id)
    if len(messages) == 1:
        title = user_message[:30] + ('...' if len(user_message) > 30 else '')
        helpers.update_conversation_title(conv_id, title)

    try:
        result = chat_with_ai(user_message, model=model)
        if 'error' in result:
            return jsonify(result), 500
        ai_response = result.get('response', '')
        if not ai_response:
            ai_response = "I couldn't generate a response."
        helpers.save_message(conv_id, 'assistant', ai_response)
        return jsonify({'response': ai_response, 'conversation_id': conv_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chat/stream', methods=['POST'])
@login_required
def chat_stream():
    data = request.json
    user_message = data.get('message', '').strip()
    conv_id = data.get('conversation_id')
    model = data.get('model', 'llama3')

    if not user_message:
        return Response("data: {\"error\":\"No message\"}\n\n", mimetype='text/event-stream')

    # Create/verify conversation
    if not conv_id:
        conv_id = helpers.create_conversation_for_user(current_user.id)
    else:
        conv = helpers.get_conversation(conv_id)
        if not conv or conv['user_id'] != current_user.id:
            conv_id = helpers.create_conversation_for_user(current_user.id)

    # Save user message
    helpers.save_message(conv_id, 'user', user_message)

    # Auto-title if first message
    messages = helpers.get_conversation_messages(conv_id)
    if len(messages) == 1:
        title = user_message[:30] + ('...' if len(user_message) > 30 else '')
        helpers.update_conversation_title(conv_id, title)

    def generate():
        full_response = ""
        try:
            for token in stream_chat_with_ai(user_message, model=model):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
            # Save full response
            helpers.save_message(conv_id, 'assistant', full_response)
            yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)