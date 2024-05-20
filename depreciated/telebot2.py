from typing import Final
import sqlite3
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, MessageHandler, filters, ContextTypes, Application, CommandHandler
from backendGPT import handle_input_text
from dotenv import load_dotenv
import os 
# Load environment variables from .env file
load_dotenv()

# Telegram bot token
TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_USERNAME: Final = os.getenv('TELEGRAM_BOT_USERNAME')

# Whitelisted
whitelisted_telegram_id = [int(id) for id in os.getenv('TELEGRAM_WHITELISTED_ID').split(',')]

# Initialize sqlite database to store the chat history
conn = sqlite3.connect('chat_history.db')
conn2 = sqlite3.connect('user_preferences.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS chat_history (user_id INTEGER PRIMARY KEY, chat_history TEXT)')
conn.commit()

# Store user preferences
# model, temperature, max_tokens, n, stop
c2 = conn2.cursor()
c2.execute('CREATE TABLE IF NOT EXISTS user_preferences (user_id INTEGER PRIMARY KEY, model TEXT, temperature FLOAT, max_tokens INTEGER, n INTEGER, stop TEXT)')
conn2.commit()
# One time setting for admin
c2.execute('REPLACE INTO user_preferences (user_id, model, temperature, max_tokens, n, stop) VALUES (?, ?, ?, ?, ?, ?)', (id, 'gpt-4o', 0.8, 1000, 1, None))
conn2.commit()
c2.execute('REPLACE INTO user_preferences (user_id, model, temperature, max_tokens, n, stop) VALUES (?, ?, ?, ?, ?, ?)', (id, 'gpt-4o', 0.8, 1000, 1, None))
conn2.commit()

# Start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    
    if user_id not in whitelisted_telegram_id:
        await update.message.reply_text(f'You are not whitelisted!, your id is {user_id}! Please contact the developer to be whitelisted.')
        return
    # retrieve chat history from database
    else:
        c.execute('SELECT * FROM chat_history WHERE user_id = ?', (user_id,))
        chat_history = c.fetchall()
        if len(chat_history) == 0:
            chat_history = [
                {"role": "system", "content": "You are a helpful assistant, be concise and logical, however if you are unsure of what the user is asking for, clarify with them."}
            ]
        print(f'User({user_id}) just started the bot!')
        await update.message.reply_text('Welcome! Start typing to chat with the bot. Type /exit to stop chatting or /reset to reset the chat history.')
    
# Handle message 
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    user_message = update.message.text
    
    if user_id not in whitelisted_telegram_id:
        await update.message.reply_text(f'You are not whitelisted!, your id is {user_id}! Please contact the developer to be whitelisted.')
        return

    # retrieve chat history from database
    chat_history = get_chat_history(user_id)
    append_chat_history(user_id, user_message, "user")
    print(f'User({user_id}) just sent a message: {user_message}')
    # Get user preferences
    c2.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    result = c2.fetchone()
    if result is None:
        model = 'gpt-3.5-turbo-0125'
        temperature = 0.8
        max_tokens = 100
        n = 1
        stop = None
    else:
        throwaway, model, temperature, max_tokens, n, stop = result

    await update.message.reply_text('Generating...')
    # Generate a response using GPT-4
    response = handle_input_text(user_message, model, temperature, max_tokens, n, stop, chat_history)
    # Save the chat history to the database
    append_chat_history(user_id, response, "assistant")
    print(f'Bot just sent a message: {response}')
    # Print current chat history in database
    chat_history = get_chat_history(user_id)
    print(f'Chat history: {chat_history}')
    await update.message.reply_text(response)

# Change settings command
# Change the preferences for the user via menu inside telegram
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    if user_id not in whitelisted_telegram_id:
        update.message.reply_text(f'You are not whitelisted! Please contact the developer to be whitelisted.')
        return
    # retrieve current settings and print as list to user
    c2.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    result = c2.fetchone()
    # Reply to user what are their current settings
    if result is None:
        await update.message.reply_text(f'You have not set any preferences yet, using default, \nmodel: gpt-3.5-turbo-0125\ntemperature: 0.8\nmax_tokens: 100\nn: 1\nstop: None')
    else:
        await update.message.reply_text(f'Your current preferences are: \nmodel: {result[1]}\ntemperature: {result[2]}\nmax_tokens: {result[3]}\nn: {result[4]}\nstop: {result[5]}')
    # Ask user to change preferences
    await update.message.reply_text('Reply to this message gpt-3.5-turbo-0125 0.8 100 1 None\nType No to keep the current settings')
    # Handle user reply
    user_input = await update.message.text
    if user_input.lower() == 'no':
        return
    user_input = user_input.split()
    if len(user_input) != 5:
        await update.message.reply_text('Invalid input! Please try again.')
        return
    model, temperature, max_tokens, n, stop = user_input
    # Save the user preferences to the database
    c2.execute('REPLACE INTO user_preferences (user_id, model, temperature, max_tokens, n, stop) VALUES (?, ?, ?, ?, ?, ?)', (user_id, model, temperature, max_tokens, n, stop))
    conn2.commit()
    print(f'User({user_id}) just changed their preferences to model: {model}, temperature: {temperature}, max_tokens: {max_tokens}, n: {n}, stop: {stop}')
    await update.message.reply_text(f'Settings changed to model: {model}, temperature: {temperature}, max_tokens: {max_tokens}, n: {n}, stop: {stop}!')

# Reset command
# Empties the chat history for user_id
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    if user_id not in whitelisted_telegram_id:
        update.message.reply_text(f'You are not whitelisted!')
        return
    print(f'User({user_id}) just reset the chat history!')
    c.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
    conn.commit()
    await update.message.reply_text('Chat history reset!')

# Exit command
async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    if user_id not in whitelisted_telegram_id:
        update.message.reply_text(f'You are not whitelisted!, your id is {user_id}! Please contact the developer to be whitelisted.')
        return
    print(f'User({user_id}) just exited the bot!')
    await update.message.reply_text('''Goodbye! This doesn't do anything''')
    
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'An error occurred: {context.error}')
    await update.message.reply_text('An error occurred!')
    
def get_chat_history(user_id: int) -> list:
    c.execute('SELECT * FROM chat_history WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is not None:
        return json.loads(result[1])
    else:
        return [{"role": "system", "content": "You are a helpful assistant, be concise and logical, however if you are unsure of what the user is asking for, clarify with them."}]

def append_chat_history(user_id: int, message: str, role: str):
    chat_history = get_chat_history(user_id)
    chat_history.insert(0, {"role": role, "content": message})
    # Save the chat history to the database
    c.execute('REPLACE INTO chat_history (user_id, chat_history) VALUES (?, ?)', (user_id, json.dumps(chat_history)))
    conn.commit()    
    
def main():
    print('Bot started')
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('settings', settings_command))
    app.add_handler(CommandHandler('reset', reset_command))
    app.add_handler(CommandHandler('exit', exit_command))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Error handler
    app.add_error_handler(error)
    
    # Start the bot
    print("Bot polling")
    app.run_polling()
    conn.close()
    conn2.close()
    print("Bot polling done")
    
    
if __name__ == '__main__':
    main()