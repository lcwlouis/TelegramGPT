import logging
import sqlite3
import base64
from typing import Final
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from backend import build_message_list, chat_with_gpt, chat_with_claude
from settingsMenu import get_current_settings

# Define conversation states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING = range(3)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect('chats.db')

c = conn_chats.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS chats
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
     user_id INTEGER NOT NULL,
     chat_title TEXT)
''')
conn_chats.commit()
# Create chat history table
c.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        chat_id INTEGER,
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'text',
        message TEXT,
        role TEXT,
        FOREIGN KEY (chat_id) REFERENCES chats(id)
    )
''')
conn_chats.commit()

# Chats Menu 
def start_keyboard():
    keyboard = [
        [InlineKeyboardButton("Show Chats", callback_data="show_chats")],
        [InlineKeyboardButton("Settings", callback_data="settings")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    c.execute("SELECT id, chat_title FROM chats WHERE user_id = ?", (user_id,))
    chats = c.fetchall()

    keyboard = []
    for chat_id, chat_title in chats:
        keyboard.append([InlineKeyboardButton(chat_title, callback_data=f"open_chat_{chat_id}")])
    
    keyboard.append([InlineKeyboardButton("Create New Chat", callback_data="create_new_chat")])
    keyboard.append([InlineKeyboardButton("Back to Main Menu", callback_data="back_to_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "Select a chat or create a new one:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=message_text, reply_markup=reply_markup)
    
    return SELECTING_CHAT

async def create_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text="Please enter the name of the new chat:",
    )
    return CREATE_NEW_CHAT

async def save_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_title = update.message.text
    
    c.execute("INSERT INTO chats (user_id, chat_title) VALUES (?, ?)", (user_id, chat_title))
    conn_chats.commit()
    
    await update.message.reply_text(f"New chat '{chat_title}' created successfully!")
    return await show_chats(update, context)

async def open_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split('_')[-1])
    
    c.execute("SELECT chat_title FROM chats WHERE id = ?", (chat_id,))
    chat_title = c.fetchone()[0]
    
    context.user_data['current_chat_id'] = chat_id
    context.user_data['current_chat_title'] = chat_title
    
    await query.answer()
    await query.edit_message_text(f"You are now chatting in: {chat_title}\nType your message or /end to finish the chat.")
    
    # Print the chat history if there is any
    c.execute("SELECT message, role FROM chat_history WHERE chat_id = ?", (chat_id,))
    chat_history = c.fetchall()
    if chat_history:
        for message, role in chat_history:
            print(f"{role}: {message}")
            if role == 'user':
                await query.message.reply_text(f"<b>You</b>: \n{message}", parse_mode="HTML")
            elif role == 'assistant':
                await query.message.reply_text(f"<b>Academic Weapon</b>: \n{message}", parse_mode="HTML")
            else:
                pass
    else:
        pass
    return CHATTING

def check_if_chat_history_exists(chat_id: int, SYSTEM_PROMPT: str) -> None:
    c.execute("SELECT COUNT(*) FROM chat_history WHERE chat_id = ?", (chat_id,))
    count = c.fetchone()[0]
    if count == 0:
        # If chat history is empty add system prompt to chat history
        c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
                  (chat_id, SYSTEM_PROMPT, 'system'))
        conn_chats.commit()
        print(f"Chat history for chat {chat_id} created")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = context.user_data.get('current_chat_id')
    user_id = update.effective_user.id
    # Get current settings
    _, provider, model, temperature, max_tokens, n, start_prompt = get_current_settings(user_id)
    # Check if chat history is empty for the current chat
    check_if_chat_history_exists(chat_id, start_prompt)
    
    # Save user message to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
              (chat_id, user_message, 'user'))
    conn_chats.commit()
    
    # Retrieve chat history
    c.execute("SELECT type, message, role FROM chat_history WHERE chat_id = ? ORDER BY rowid", (chat_id,))
    chat_history = c.fetchall()
    
    # Format chat history for AI model
    messages = []
    for type, message, role in chat_history:
        messages = build_message_list(type, message, role, messages)

    # Generate AI response
    if provider == 'openai':
        bot_message = await update.message.reply_text("working hard...")
        input_tokens, output_tokens, role, message = chat_with_gpt(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n)
    elif provider == 'claude':
        # Remove system prompt from messages
        messages = messages[1:]
        response = await chat_with_claude(messages, model=model, temperature=temperature, max_tokens=max_tokens, sys=start_prompt)
    else:
        response = "Error: Invalid AI provider"
    
    # Save AI response to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
              (chat_id, message, role))
    conn_chats.commit()

    reply = f"<b>Academic Weapon</b>: \n{message} \n\n <i>Used {input_tokens} input tokens and {output_tokens} output tokens</i>"
    
    await bot_message.edit_text(reply, parse_mode="HTML")
    return CHATTING

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del context.user_data['current_chat_id']
    del context.user_data['current_chat_title']
    await update.message.reply_text("Chat ended. Returning to chat selection.")
    return await show_chats(update, context)

async def del_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.user_data.get('current_chat_id')
    
    c.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn_chats.commit()
    
    print(f"Chat {chat_id} deleted successfully!")

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(f"Chat \"{context.user_data.get('current_chat_title')}\" deleted successfully!")
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
        return await show_chats(update, context)
    else:
        await update.message.reply_text(f"Chat \"{context.user_data.get('current_chat_title')}\" deleted successfully!")
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
        return await show_chats(update, context)




def get_chat_handlers():
    return {
        SELECTING_CHAT: [
            CallbackQueryHandler(create_new_chat, pattern="^create_new_chat$"),
            CallbackQueryHandler(open_chat, pattern="^open_chat_"),
        ],
        CREATE_NEW_CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_chat),
        ],
        CHATTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CommandHandler("end", end_chat),
            CommandHandler("delete", del_chat),
        ],
    }

def kill_connection():
    conn_chats.close()
    print("Chat DB Connection Closed")