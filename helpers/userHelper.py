import sqlite3
import logging
import os
from dotenv import load_dotenv

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROMPT_DIR = os.getenv('PROMPT_DIR')
PROMPT_FILE = 'system_prompt.txt'
PROMPT_PATH = os.path.join(PROMPT_DIR, PROMPT_FILE)

os.makedirs(PROMPT_DIR, exist_ok=True)

DEFAULT_STARTING_MESSAGE = open(PROMPT_PATH, 'r').read()

load_dotenv()

DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'user_preferences.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

conn_users = sqlite3.connect(DB_PATH)
c = conn_users.cursor()

def on_start() -> None:
    whitelisted_telegram_id = [int(id) for id in os.getenv('TELEGRAM_WHITELISTED_IDS').split(',')]
    for id in whitelisted_telegram_id:
        add_user(id)

def get_all_user_ids() -> list:
    c.execute("SELECT user_id FROM user_preferences")
    row = c.fetchall()
    user_ids = [user_id[0] for user_id in row]
    return user_ids

def add_user(user_id: int) -> None:
    # insert user only if they don't exist
    c.execute("SELECT user_id FROM user_preferences WHERE user_id=?", (user_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO user_preferences (user_id, start_prompt) VALUES (?, ?)", (user_id, DEFAULT_STARTING_MESSAGE))
    conn_users.commit()

def kill_connection() -> None:
    conn_users.close()
    print("User DB Connection in user.py Closed")

on_start()