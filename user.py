import sqlite3

conn_users = sqlite3.connect('user_preferences.db')
c = conn_users.cursor()

def get_all_user_ids() -> list:
    c.execute("SELECT user_id FROM user_preferences")
    row = c.fetchall()
    user_ids = [user_id[0] for user_id in row]
    return user_ids

def add_user(user_id: int) -> None:
    # insert user only if they don't exist
    c.execute("SELECT user_id FROM user_preferences WHERE user_id=?", (user_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO user_preferences (user_id) VALUES (?)", (user_id,))
    conn_users.commit()

def kill_connection() -> None:
    conn_users.close()
    print("User DB Connection in user.py Closed")
