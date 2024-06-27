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
    start_keyboard,
    show_chats,
    get_chat_handlers,
    kill_connection as chat_kill_connection
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
TOKEN: Final = os.getenv('TELEGRAM_BOT_TOKEN')
# BOT_USERNAME: Final = os.getenv('TELEGRAM_BOT_USERNAME') # Not used

# Load whitelisted telegram ids
whitelisted_telegram_id = [int(id) for id in os.getenv('TELEGRAM_WHITELISTED_IDS').split(',')]

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id in whitelisted_telegram_id:
        pass
    else:
        await update.effective_message.reply_text(f"Hey! You are not allowed to use me! Ask the admin to add ur user id: <code>{update.effective_user.id}</code>", parse_mode="HTML")
        raise ApplicationHandlerStop

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"<b><u>Hello {update.effective_user.first_name}</u></b>! Welcome to the Academic Weapon, I am here to answer your questions about anything. \n\n<u>Select the following options to get started</u>:",
        reply_markup=start_keyboard(),
        parse_mode="HTML"
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        InlineKeyboardButton("Start", callback_data="back_to_main")
    ]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="""
        <b><u>Help</u></b> 
        Here are the available commands: 
        /start - Brings you to starting menu
        /help - Brings you here. 
        /settings - Enter Settings Menu 
        /image [prompt] - Generates an image (Only use in a Conversation)
        /end - Ends the current conversation (Only use in a Conversation)
        /delete - Deletes the current conversation (Only use in a Conversation)
        """,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([keyboard])
    )

# Main
def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    callback_handler = TypeHandler(Update, callback)
    
    # Settings menu handler
    settings_handler = ConversationHandler(
        entry_points=[CommandHandler("settings", settings), CallbackQueryHandler(settings, pattern="^settings$")],
        states=settings_menu_handler(),
        fallbacks=[CommandHandler("cancel", start)],
        per_message=False
    )

    # Chats menu
    chat_menu_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_chats, pattern="^show_chats$")],
        states=get_chat_handlers(),
        fallbacks=[CallbackQueryHandler(start, pattern="^back_to_main$")],
        per_message=False
    )

    # Start menu items
    select_chat = CallbackQueryHandler(show_chats, pattern="^show_chats$")
    select_help = CallbackQueryHandler(help, pattern="^help$")
    
    start_cmd_handler = CommandHandler('start', start)
    help_cmd_handler = CommandHandler('help', help)
    application.add_handler(callback_handler, -1)
    application.add_handler(start_cmd_handler)
    application.add_handler(help_cmd_handler)
    application.add_handler(settings_handler)
    application.add_handler(select_help)
    application.add_handler(chat_menu_handler)
    application.add_handler(select_chat)
    
    # Start the bot
    print("Bot polling, will exit on Ctrl+C and continue posting updates if there are warnings or errors")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

    # On Ctrl+C exit
    chat_kill_connection()
    settings_kill_connection()
    print("Bot polling closed. Exiting...")


if __name__ == '__main__':
    main()
