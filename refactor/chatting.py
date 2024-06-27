import sqlite3
import base64
from typing import Final
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# Initialize sqlite database to store and retrieve the chat history
conn_settings = sqlite3.connect('chat_history.db')

c = conn_settings.cursor()
c.execute('CREATE TABLE IF NOT EXISTS chat_history (user_id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, chat_title TEXT, chat_history TEXT)')
conn_settings.commit()

# Define conversation states

# Chats Menu 
def start_keyboard():
    keyboard = [
        [InlineKeyboardButton("Show Chats", callback_data="show_chats")],
        [InlineKeyboardButton("Settings", callback_data="settings")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def kill_connection():
    conn_settings.close()
    print("Chat DB Connection Closed")