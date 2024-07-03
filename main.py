import logging
import os
import traceback, html, json
from typing import Final
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationHandlerStop,
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    TypeHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PicklePersistence
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
TOKEN: Final = os.getenv(f'TELEGRAM_BOT_TOKEN_{os.getenv("ENVIRONMENT")}')
# BOT_USERNAME: Final = os.getenv('TELEGRAM_BOT_USERNAME') # Not used

# Load whitelisted telegram ids
admin_telegram_id = int(os.getenv('TELEGRAM_ADMIN_ID'))
whitelisted_telegram_id = get_all_user_ids()

# Load error chat id
ERROR_CHAT_ID = int(os.getenv('TELEGRAM_ERROR_CHAT_ID'))

# Define shared states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

# load directory
DB_DIR = os.getenv('DB_DIR')
PICKLE_DIR = 'user_data.pickle'
PICKLE_PATH = os.path.join(DB_DIR, PICKLE_DIR)

os.makedirs(DB_DIR, exist_ok=True)


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
        message = await update.effective_message.reply_text(f"Hey! You are not allowed to use me! Ask the admin to add your user id: <code>{update.effective_user.id}</code>", parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        raise ApplicationHandlerStop

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Delete all messages before the next message
    if 'sent_messages' in context.user_data:
        min_id = min(context.user_data['sent_messages'])
        max_id = max(context.user_data['sent_messages']) + 1
        for message_id in range(min_id, max_id):
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
    # print(f"Sent message: {message.message_id}")
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    return ConversationHandler.END

async def admin_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id == admin_telegram_id:
        user_id = update.message.text.split(" ")[1].strip()
        print(f"User id: {user_id}")
        if user_id.isdigit() and int(user_id) not in whitelisted_telegram_id and not None:
            add_user(user_id)
            whitelisted_telegram_id.append(int(user_id))
            message = await update.effective_message.reply_text(f"User id <code>{user_id}</code> added successfully", parse_mode=ParseMode.HTML)
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
    else:
        message = await update.effective_message.reply_text("You are not allowed to use me!", parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)

# Error handler taken from python telegram bot examples
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=ERROR_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )

# Main
def main() -> None:
    persistence = PicklePersistence(filepath=PICKLE_PATH)
    application = ApplicationBuilder().token(TOKEN).persistence(persistence).build()
    # application = ApplicationBuilder().token(TOKEN).build()
    callback_handler = TypeHandler(Update, callback)

    # Chats menu
    chat_menu_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CommandHandler("help", show_help), CallbackQueryHandler(show_chats, pattern="^show_chats$")],
        states=get_chat_handlers(),
        fallbacks=[CallbackQueryHandler(start, pattern="^start$")],
        per_message=False,
    )
    
    # Settings menu handler
    settings_handler = ConversationHandler(
        entry_points=[CommandHandler("settings", settings), CallbackQueryHandler(settings, pattern="^settings$")],
        states=settings_menu_handler(),
        fallbacks=[CallbackQueryHandler(settings, pattern="^settings$")],
        per_message=False
    )
    
    # Handle adding users by admin
    admin_add_cmd_handler = CommandHandler("admin_add", admin_add_user)

    # Add handlers

    application.add_handler(callback_handler, -1)
    application.add_handler(chat_menu_handler)
    application.add_handler(settings_handler)
    application.add_handler(admin_add_cmd_handler)

    # Add error handler
    application.add_error_handler(error_handler)
    
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

