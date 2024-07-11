import logging
import time
import os
import traceback, html, json
from typing import Final
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    TypeHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PicklePersistence,
)
from settings.chatCompletionHandler import (
    settings, 
    settings_menu_handler,
    kill_connection as settings_kill_connection
    )
from settings.imageGenHandler import (
    kill_connection as imageGen_kill_connection
)
from chat.chatMenu import (
    start,
    show_chats,
    create_new_chat,
    open_chat,
    show_help,
    prev_page,
    next_page,
    end_chat,
    del_chat,
    no_page,
    kill_connection as chatMenu_kill_connection
)
from chat.chatHandler import (
    get_chat_handlers,
    kill_connection as chatHandler_kill_connection
)
from helpers.userHelper import (
    kill_connection as user_kill_connection
)
from helpers.mainHelper import (
    exit_menu,
    callback,
    admin_add_user,
    admin_reset_user_settings,
)
from flask import Flask, request

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(override=True)

# Telegram bot token
TOKEN: Final = os.getenv(f'TELEGRAM_BOT_TOKEN_{os.getenv("ENVIRONMENT")}')

# Load error chat id
ERROR_CHAT_ID = int(os.getenv('TELEGRAM_ERROR_CHAT_ID'))

# load directory
DB_DIR = os.getenv('DB_DIR')
PICKLE_DIR = 'user_data.pickle'
PICKLE_PATH = os.path.join(DB_DIR, PICKLE_DIR)

os.makedirs(DB_DIR, exist_ok=True)

# Error handler taken from python telegram bot examples
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)[:5]
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "<b>An exception was raised while handling an update at time {time} </b>\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    )
    message_traceback = (
        f"<b>Traceback (most recent call last):</b>\n"
        f"<pre>{html.escape(tb_string)}</pre>"
        f"<b>-----------End of traceback-----------</b>"
    )

    # Split the message if it's too long
    from helpers.chatHelper import smart_split
    parts = smart_split(message, 4096)
    for part in parts:
        # Finally, send the message
        try:
            await context.bot.send_message(
                chat_id=ERROR_CHAT_ID, text=part, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            if 'Message is not modified' in str(e):
                # If the message is not modified don't send anything
                pass
            else:
                # undo html escape
                part = html.unescape(part)
                await context.bot.send_message(
                    chat_id=ERROR_CHAT_ID, text=part
                )

    parts = smart_split(message_traceback, 4096)
    for part in parts:
        # Finally, send the message
        try:
            await context.bot.send_message(
                chat_id=ERROR_CHAT_ID, text=part, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            if 'Message is not modified' in str(e):
                # If the message is not modified don't send anything
                pass
            else:
                # undo html escape
                part = html.unescape(part)
                await context.bot.send_message(
                    chat_id=ERROR_CHAT_ID, text=part
                )

# Main
def create_application() -> None:
    persistence = PicklePersistence(filepath=PICKLE_PATH)
    application = ApplicationBuilder().token(TOKEN).persistence(persistence).build()
    # application = ApplicationBuilder().token(TOKEN).build()
    callback_handler = TypeHandler(Update, callback)

    # Chats menu
    chat_menu_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start), 
            CommandHandler("help", show_help),
            CommandHandler("end", end_chat),
            CommandHandler("delete", del_chat),
            CallbackQueryHandler(show_chats, pattern="^show_chats$"), 
            CallbackQueryHandler(create_new_chat, pattern="^create_new_chat$"),
            CallbackQueryHandler(open_chat, pattern="^open_chat_"),
            CallbackQueryHandler(show_help, pattern="^help$"),
            CallbackQueryHandler(exit_menu, pattern="^exit_menu$"),
            CallbackQueryHandler(prev_page, pattern="^prev_page$"),
            CallbackQueryHandler(next_page, pattern="^next_page$"),
            CallbackQueryHandler(no_page, pattern="^no_page$"),
            ],
        states=get_chat_handlers(),
        fallbacks=[CallbackQueryHandler(start, pattern="^start$")],
        name="chat_menu",
        allow_reentry=True,
        per_message=False,
        block=True,
        persistent=True
    )
    
    # Settings menu handler
    settings_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(settings, pattern="^settings$")],
        states=settings_menu_handler(),
        fallbacks=[CallbackQueryHandler(settings, pattern="^settings$")],
        name="settings",
        per_message=False,
        allow_reentry=True,
        block=True,
        persistent=True
    )
    
    # Handle adding users by admin
    admin_add_cmd_handler = CommandHandler("admin_add", admin_add_user)
    admin_reset_cmd_handler = CommandHandler("admin_reset", admin_reset_user_settings)

    # Handle unsupported commands and messages
    # unsupported_cmd_handler = MessageHandler(filters.COMMAND, handle_unsupported_command)
    # unsupported_msg_handler = MessageHandler(~filters.COMMAND, handle_unsupported_message)

    # Add handlers
    # application.add_handler(unsupported_cmd_handler, 1)
    # application.add_handler(unsupported_msg_handler, 1)
    application.add_handler(callback_handler, -1)
    application.add_handler(chat_menu_handler)
    application.add_handler(settings_handler)
    application.add_handler(admin_add_cmd_handler)
    application.add_handler(admin_reset_cmd_handler)

    # Add error handler
    application.add_error_handler(error_handler)
    
    return application

app = Flask(__name__)

import http
@app.route('/')
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.process_update(update)
    return "", http.HTTPStatus.NO_CONTENT



def main() -> None:
    global application
    application = create_application()

    # if os.getenv('ENVIRONMENT') == 'PROD':
    # Cloud Run environment
    port = int(os.getenv('PORT', 8080))
    # Set the webhook
    application.bot.set_webhook(f'https://{os.getenv("CLOUD_RUN_URL")}/{TOKEN}')
    # Start Flask server
    app.run(host='0.0.0.0', port=port)
    # else:
    #     # Local development environment
    #     print("Bot polling, will exit on Ctrl+C and continue posting updates if there are warnings or errors")
    #     application.run_polling(allowed_updates=Update.ALL_TYPES)

    # On Ctrl+C exit
    chatHandler_kill_connection()
    chatMenu_kill_connection()
    settings_kill_connection()
    imageGen_kill_connection()
    user_kill_connection()
    print("Bot polling closed. Exiting...")

if __name__ == '__main__':
    main()