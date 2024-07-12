import logging
import os
import telegramify_markdown as tm
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop, ConversationHandler

from helpers.userHelper import (
    add_user,
    get_all_user_ids,
)

from settings.chatCompletionHandler import reset_user_settings
from settings.imageGenHandler import reset_user_image_settings
# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load whitelisted telegram ids
admin_telegram_id = int(os.getenv('TELEGRAM_ADMIN_ID'))
whitelisted_telegram_id = get_all_user_ids()
BOT_NAME = os.getenv('BOT_NAME')

# Define shared states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

## Main Helper Functions

async def admin_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id == admin_telegram_id:
        # Ensure that there is a user ID in the message
        if len(update.message.text.split(" ")) < 2:
            message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Admin \nPlease provide a *user ID*",
                                                                            max_line_length=None, 
                                                                            normalize_whitespace=False
                                                                            ), 
                                                                            parse_mode=ParseMode.MARKDOWN_V2)
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return
        user_id = update.message.text.split(" ")[1].strip()
        print(f"User id: {user_id}")
        if user_id.isdigit() and int(user_id) not in whitelisted_telegram_id and not None:
            add_user(user_id)
            whitelisted_telegram_id.append(int(user_id))
            message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Admin \nUser id `{user_id}` added successfully",
                                                                            max_line_length=None,
                                                                            normalize_whitespace=False
                                                                            ), 
                                                                            parse_mode=ParseMode.MARKDOWN_V2)
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
    else:
        message = await update.effective_message.reply_text("You are not allowed to use me!")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)

async def admin_reset_user_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id == admin_telegram_id:
        # Ensure that there is a user ID in the message
        if len(update.message.text.split(" ")) < 2:
            message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Admin\nPlease provide a user ID",
                                                                            max_line_length=None,
                                                                            normalize_whitespace=False
                                                                            ), 
                                                                            parse_mode=ParseMode.MARKDOWN_V2)
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return
        user_id = update.message.text.split(" ")[1].strip()
        print(f"User id: {user_id}")
        if user_id.isdigit() and int(user_id) in whitelisted_telegram_id:
            success_reset_settings = reset_user_settings(user_id)
            success_reset_image_settings = reset_user_image_settings(user_id)
            if success_reset_settings and success_reset_image_settings:
                message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Admin \nUser id `{user_id}` settings reset successfully", 
                                                                                max_line_length=None, 
                                                                                normalize_whitespace=False
                                                                                ), 
                                                                                parse_mode=ParseMode.MARKDOWN_V2)
                context.user_data.setdefault('sent_messages', []).append(message.message_id)
            else:
                message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Admin \nUser id `{user_id}` settings reset failed",
                                                                                max_line_length=None,
                                                                                normalize_whitespace=False
                                                                                ), 
                                                                                parse_mode=ParseMode.MARKDOWN_V2)
                context.user_data.setdefault('sent_messages', []).append(message.message_id)

    else:
        message = await update.effective_message.reply_text(tm.markdownify(f"__{BOT_NAME}__ | Error \nYou are not allowed to use me!",
                                                                        max_line_length=None,
                                                                        normalize_whitespace=False
                                                                        ), 
                                                                        parse_mode=ParseMode.MARKDOWN_V2)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)

async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Delete all messages before the next message
    if context.user_data.get('sent_messages'):
        min_id = min(context.user_data['sent_messages'])
        max_id = max(context.user_data['sent_messages']) + 1
        to_delete_list = [message_id for message_id in range(min_id, max_id)]
        for i in range(0, len(to_delete_list), 100):
            chunk = to_delete_list[i:i+100]
            await context.bot.delete_messages(chat_id=update.effective_chat.id, message_ids=chunk)
        context.user_data['sent_messages'] = []

async def exit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Send a new message telling the user to /start
    message = await context.bot.send_message(chat_id=update.effective_chat.id, text="Type /start to start again")
    to_delete_start_cmd_list = context.user_data.get('start_cmd_ids', [])
    # insert into context sent message list
    context.user_data.setdefault('sent_messages', []).extend(to_delete_start_cmd_list)
    await cleanup(update, context)

    # Clear all user data
    context.user_data.clear()
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
        message = await update.effective_message.reply_text(
            tm.markdownify(f"__{BOT_NAME}__ | Error\nHey! You are not allowed to use me! Ask the admin to add your user id: `{update.effective_user.id}`", max_line_length=None, normalize_whitespace=False), 
            parse_mode=ParseMode.MARKDOWN_V2)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        raise ApplicationHandlerStop

async def handle_unsupported_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await update.effective_message.reply_text(
        tm.markdownify((
            f"__{BOT_NAME}__ | Error\n"
            f"{update.effective_message.text} command is not available in this menu."),
            max_line_length=None,
            normalize_whitespace=False
        ), 
        parse_mode=ParseMode.MARKDOWN_V2)
    context.user_data.setdefault('sent_messages', []).append(message.message_id)

async def handle_unsupported_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await update.effective_message.reply_text(
        tm.markdownify((
            f"__{BOT_NAME}__ | Error\n"
            f"Sending messages is not available here!"),
            max_line_length=None,
            normalize_whitespace=False
        ), 
        parse_mode=ParseMode.MARKDOWN_V2)
    context.user_data.setdefault('sent_messages', []).append(message.message_id)