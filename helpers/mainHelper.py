import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop, ConversationHandler

from helpers.userHelper import (
    add_user,
    get_all_user_ids,
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load whitelisted telegram ids
admin_telegram_id = int(os.getenv('TELEGRAM_ADMIN_ID'))
whitelisted_telegram_id = get_all_user_ids()

# Define shared states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

## Main Helper Functions

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

## Handler functions ## 

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