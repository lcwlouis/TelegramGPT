from typing import Final
from telegram import Update
from telegram.ext import Updater, MessageHandler, filters, ContextTypes, Application, CommandHandler
from backendGPT import handle_input_text

# Telegram bot token
TOKEN: Final = 'BOTKEY'
BOT_USERNAME: Final = '@BOTUSERNAME'

# On start bot, the bot will verify the telegram id with the whitelisted telegram id in the database
# Admin will in future be able to add and remove telegram id from the whitelist from the bot itself
whitelisted_telegram_id = []

# Function to handle starting of bot and verifying the telegram id
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id: int = update.message.from_user.id
    user_name: str = update.message.from_user.username

    if user_id in whitelisted_telegram_id:
        print(f'User({user_id}, {user_name}) just started the bot!')
        await update.message.reply_text(f'Welcome {user_name}, you are whitelisted!')
    else:
        await update.message.reply_text(f'You are not whitelisted!')
        
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Help command called by user({update.message.chat.id})!')
    await update.message.reply_text('Help command TO BE IMPLEMENTED')
    
async def startChat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Chat started with user({update.message.chat.id})!')
    await update.message.reply_text('Start typing to chat with the bot. Type /exit to stop chatting or /reset to reset the chat history.')
    handle_response(update, 'start')
    
async def resetChat_command(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_history):
    # Clear the chat history on telegram
    chat_history = []
    print(f'Chat history reset for user({update.message.chat.id})!')
    await update.message.reply_text('Chat history reset!')

async def exit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Goodbye!')
    print('Bot stopped')
    exit()
        
# Function to handle messages from the user and generate a response while passing in the chat history
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle if chat history is empty
    chat_history = []
    if len(chat_history) == 0:
        chat_history = [
            {"role": "system", "content": "You are a personal assistant. Particularly helping students in University with their questions regard their majors and their events. Answer as logically as possible to help them."}
        ]
        
    # Get the user's message
    user_message = update.message.text
    print(f'User({update.message.chat.id}) message: {user_message}')

    # Generate a response using GPT-4
    response = handle_input_text(user_message, model='gpt-4', temperature=0.7, max_tokens=100, n=1, stop=None, chat_history=chat_history)
    
    # add message into chat history
    chat_history.append({"role": "user", "content": user_message})
    # add response into chat history
    chat_history.append({"role": "system", "content": response})

    # reply to the user
    print(f'Bot response: {response}')
    await update.message.reply_text(response)
    
    


async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'An error occurred: {context.error}')
    await update.message.reply_text('An error occurred!')

def run_bot():
    print('Starting bot')
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('startChat', startChat_command))
    app.add_handler(CommandHandler('resetChat', resetChat_command))
    app.add_handler(CommandHandler('exit', exit_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Error
    app.add_error_handler(error)

    # Polls the bot
    print('Bot polling...')
    app.run_polling(poll_interval=3)
    
if __name__ == '__main__':
    run_bot()