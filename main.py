import logging
import os
from typing import Final
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationHandlerStop,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    TypeHandler,
    CallbackQueryHandler,
    ConversationHandler
)
from settingsMenu import (
    settings, 
    settings_menu_handler,
    kill_connection as settings_kill_connection
    )
from chattingMenu import (
    start,
    show_chats,
    show_help,
    get_chat_handlers,
    kill_connection as chat_kill_connection
)
from user import (
    add_user,
    get_all_user_ids,
    kill_connection as user_kill_connection
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Telegram bot token
TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN_DEV')
# BOT_USERNAME: Final = os.getenv('TELEGRAM_BOT_USERNAME') # Not used

# Load whitelisted telegram ids
admin_telegram_id = int(os.getenv('TELEGRAM_ADMIN_ID'))
whitelisted_telegram_id = get_all_user_ids()

# Define shared states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Asynchronous function that checks if the user ID is whitelisted on Telegram. If not, it replies with a message indicating the user is not allowed to use the bot and raises an ApplicationHandlerStop exception.

    Parameters:
    - update: Update object containing information about the user update
    - context: ContextTypes.DEFAULT_TYPE object providing the context for the update

    Returns:
    - None
    """
    if update.effective_user.id in whitelisted_telegram_id:
        pass
    else:
        await update.effective_message.reply_text(f"Hey! You are not allowed to use me! Ask the admin to add ur user id: <code>{update.effective_user.id}</code>", parse_mode="HTML")
        raise ApplicationHandlerStop

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Delete all messages before the next message
    if 'sent_messages' in context.user_data:
        for message_id in context.user_data['sent_messages']:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            except Exception as e:
                logger.warning(f"Failed to delete message {message_id}: {e}")
        context.user_data['sent_messages'] = []

async def exit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cleanup(update, context)
    # Clear all user data
    context.user_data.clear()
    # Send a new message telling the user to /start
    message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Type /start to start again")
    print(f"Sent message: {message.message_id}")
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    return ConversationHandler.END

# Main
def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    callback_handler = TypeHandler(Update, callback)

    # Chats menu
    chat_menu_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("help", show_help), CallbackQueryHandler(show_chats, pattern="^show_chats$")],
        states=get_chat_handlers(),
        fallbacks=[CallbackQueryHandler(show_chats, pattern="^show_chats$")],
        per_message=False
    )
    
    # Settings menu handler
    settings_handler = ConversationHandler(
        entry_points=[CommandHandler("settings", settings), CallbackQueryHandler(settings, pattern="^settings$")],
        states=settings_menu_handler(),
        fallbacks=[CallbackQueryHandler(settings, pattern="^settings$")],
        per_message=False
    )

    # Add handlers
    application.add_handler(callback_handler, -1)
    application.add_handler(chat_menu_handler)
    application.add_handler(settings_handler)
    
    # Start the bot
    print("Bot polling, will exit on Ctrl+C and continue posting updates if there are warnings or errors")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    # On Ctrl+C exit
    chat_kill_connection()
    settings_kill_connection()
    user_kill_connection()
    print("Bot polling closed. Exiting...")


if __name__ == '__main__':
    main()
