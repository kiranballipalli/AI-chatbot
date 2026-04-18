import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bcrypt for password hashing (will be initialised in main app, but we use it here)
bcrypt = Bcrypt()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'dbname': os.getenv('DB_NAME', 'ai_chat_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', '')
}

def get_db_connection():
    """Create and return a PostgreSQL connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def init_db():
    """Create all necessary tables if they don't exist."""
    logger.info("Initializing database tables...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("✅ users table checked/created.")

        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        logger.info("✅ conversations table checked/created.")

        # Add user_id column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        except Exception as e:
            logger.warning(f"Could not add user_id column (might already exist): {e}")

        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role VARCHAR(10) CHECK (role IN ('user', 'assistant')) NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("✅ messages table checked/created.")

        # Trigger function for updated_at
        cursor.execute('''
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql'
        ''')
        logger.info("✅ trigger function checked/created.")

        # Drop trigger if exists and recreate
        cursor.execute('''
            DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations
        ''')
        cursor.execute('''
            CREATE TRIGGER update_conversations_updated_at
            BEFORE UPDATE ON conversations
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column()
        ''')
        logger.info("✅ trigger on conversations checked/created.")

        conn.commit()
        cursor.close()
        conn.close()
        logger.info("🎉 Database initialization complete.")
        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        if conn:
            conn.rollback()
            cursor.close()
            conn.close()
        return False

# Initialize DB on import
_init_success = init_db()
if not _init_success:
    logger.warning("Database initialization failed. Tables may not exist.")

# ==================== USER MANAGEMENT ====================

def create_user(username: str, password: str) -> int:
    """Create a new user. Returns user ID or None if username exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    hashed = bcrypt.generate_password_hash(password).decode('utf-8')
    try:
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id',
            (username, hashed)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        return user_id
    except psycopg2.IntegrityError:
        conn.rollback()
        cursor.close()
        conn.close()
        return None

def verify_user(username: str, password: str) -> dict:
    """Verify user credentials. Returns user dict (id, username) or None."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT id, username, password_hash FROM users WHERE username = %s',
        (username,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row and bcrypt.check_password_hash(row['password_hash'], password):
        return {'id': row['id'], 'username': row['username']}
    return None

def get_user_by_id(user_id: int) -> dict:
    """Get user by ID."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT id, username FROM users WHERE id = %s', (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

# ==================== CONVERSATION MANAGEMENT (USER-SCOPED) ====================

def create_conversation_for_user(user_id: int, title: str = None) -> int:
    """Create a new conversation for a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if title:
        cursor.execute(
            'INSERT INTO conversations (title, user_id) VALUES (%s, %s) RETURNING id',
            (title, user_id)
        )
    else:
        cursor.execute(
            'INSERT INTO conversations (user_id) VALUES (%s) RETURNING id',
            (user_id,)
        )
    conv_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return conv_id

def get_all_conversations_for_user(user_id: int):
    """Get all conversations belonging to a specific user."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT id, title, created_at, updated_at,
               (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
        FROM conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_conversation(conv_id: int):
    """Get a conversation by ID (includes user_id)."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('SELECT * FROM conversations WHERE id = %s', (conv_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

def delete_conversation(conv_id: int):
    """Delete a conversation and all its messages."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE id = %s', (conv_id,))
    conn.commit()
    cursor.close()
    conn.close()

def update_conversation_title(conv_id: int, title: str):
    """Update conversation title."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE conversations SET title = %s WHERE id = %s', (title, conv_id))
    conn.commit()
    cursor.close()
    conn.close()

# ==================== MESSAGES ====================

def save_message(conv_id: int, role: str, content: str) -> int:
    """Save a message to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO messages (conversation_id, role, content) VALUES (%s, %s, %s) RETURNING id',
        (conv_id, role, content)
    )
    msg_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return msg_id

def get_conversation_messages(conv_id: int):
    """Get all messages for a conversation, ordered chronologically."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        'SELECT id, role, content, timestamp FROM messages WHERE conversation_id = %s ORDER BY timestamp ASC',
        (conv_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def get_last_user_message(conv_id: int):
    """Get the most recent user message from a conversation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT content FROM messages WHERE conversation_id = %s AND role = %s ORDER BY timestamp DESC LIMIT 1',
        (conv_id, 'user')
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None

# ==================== BACKWARD COMPATIBILITY (for old code) ====================

def create_conversation(title: str = None) -> int:
    """
    ⚠️ Deprecated: Use create_conversation_for_user instead.
    Creates a conversation without user association (for backward compatibility).
    """
    logger.warning("create_conversation() called without user_id. This will break multi-user support.")
    conn = get_db_connection()
    cursor = conn.cursor()
    if title:
        cursor.execute('INSERT INTO conversations (title) VALUES (%s) RETURNING id', (title,))
    else:
        cursor.execute('INSERT INTO conversations DEFAULT VALUES RETURNING id')
    conv_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return conv_id

def get_all_conversations():
    """
    ⚠️ Deprecated: Use get_all_conversations_for_user instead.
    Returns all conversations regardless of user.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute('''
        SELECT id, title, created_at, updated_at,
               (SELECT COUNT(*) FROM messages WHERE conversation_id = conversations.id) as message_count
        FROM conversations
        ORDER BY updated_at DESC
    ''')
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows