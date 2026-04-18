from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from utils.helpers import get_db_connection, verify_user as db_verify_user, create_user as db_create_user, get_user_by_id as db_get_user_by_id
import psycopg2
from psycopg2.extras import RealDictCursor

login_manager = LoginManager()
bcrypt = Bcrypt()

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    row = db_get_user_by_id(int(user_id))
    if row:
        return User(row['id'], row['username'])
    return None

def create_user(username, password):
    """Create a new user. Returns user ID or None if username exists."""
    return db_create_user(username, password)

def verify_user(username, password):
    """Verify credentials. Returns User object if valid, else None."""
    user_data = db_verify_user(username, password)
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None