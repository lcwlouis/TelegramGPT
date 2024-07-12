import sqlite3
import os
import logging
import telegramify_markdown as tm
from typing import Final
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

import settings.settingMenu as settingMenu
from settings.imageGenHandler import (
    image_size_selected,
    image_option_selected,
    image_model_selected,
    back_to_image_settings
)

# Initialize logging
logger = logging.getLogger(__name__)

# Define conversation states
SELECTING_OPTION, SELECTING_MODEL, ENTERING_TEMPERATURE, ENTERING_MAX_TOKENS, ENTERING_N, ENTERING_START_PROMPT, SELECT_RESET, SELECTING_PROVIDER, SELECTING_IMAGE_SETTINGS, SELECTING_IMAGE_MODEL, SELECTING_IMAGE_SIZE = range(4, 15)

BOT_NAME = os.getenv('BOT_NAME')

# Initialise path to db
DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'user_preferences.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# Initialise path to system prompt
PROMPT_DIR = os.getenv('PROMPT_DIR')
PROMPT_FILE = 'system_prompt.txt'
PROMPT_PATH = os.path.join(PROMPT_DIR, PROMPT_FILE)

os.makedirs(PROMPT_DIR, exist_ok=True)

# start sqlite3
conn_settinngs = sqlite3.connect(DB_PATH)

COLUMNS: Final = 2

# Default starting message from file system_prompt.txt
DEFAULT_STARTING_MESSAGE = open(PROMPT_PATH, 'r').read()
DEFAULT_MAX_TOKENS = 512

# Store user preferences in database
c = conn_settinngs.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS user_preferences 
        (user_id INTEGER PRIMARY KEY, 
        provider TEXT DEFAULT "openai", 
        model TEXT DEFAULT "gpt-3.5-turbo", 
        temperature FLOAT DEFAULT 0.7, 
        max_tokens INTEGER DEFAULT 512, 
        n INTEGER DEFAULT 1, 
        start_prompt TEXT DEFAULT ""
        )''')

# Settings 
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is None:
        logger.info(f"User {user_id} has no settings, now inserting default settings")
        c.execute('INSERT INTO user_preferences (user_id, start_prompt) VALUES (?, ?)', (user_id, DEFAULT_STARTING_MESSAGE))
        conn_settinngs.commit()
        c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        result = c.fetchone()
    _, provider, model, temperature, max_tokens, n, start_prompt = result

    context.user_data['settings'] = [provider, model, temperature, max_tokens, n, start_prompt]
    current_settings_message = tm.markdownify((
        f"__{BOT_NAME}__ | Settings\n"
        f"━━━━━━━━━━\n"
        f"*Provider:* `{provider}`\n"
        f"*Model:* `{model}`\n"
        f"*Temperature:* `{temperature}`\n"
        f"*Max tokens:* `{max_tokens}`\n"
        f"*N:* `{n}`\n"
        "*Starting Prompt:* \n"
        "> Select Starting Prompt to see the prompt\n\n"
        "*Image Settings:* \n"
        "> Select Image Settings to see the image settings"),
        max_line_length=None,
        normalize_whitespace=False
    )
    if update.message is None:
        query = update.callback_query
        await query.message.edit_text(
            current_settings_message,
            reply_markup=settingMenu.settings_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return SELECTING_OPTION
    message = await update.message.reply_text(
        current_settings_message,
        reply_markup=settingMenu.settings_keyboard(),
        parse_mode=ParseMode.MARKDOWN_V2
    )
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    return SELECTING_OPTION

async def option_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    option = query.data
    
    if option == "show_chats":
        from chat.chatMenu import start
        await start(update, context, False)
        return ConversationHandler.END
    elif option == "model":
        await query.edit_message_text(
            tm.markdownify((
                f"__{BOT_NAME}__ | Choose Model Provider\n"
                f"━━━━━━━━━━\n"
                f"*Current Provider:* {str(context.user_data['settings'][0])} \n"
                f"*Current Model:* {str(context.user_data['settings'][1])} \n\n"
                f"Select a provider:"
            ),
            max_line_length=None,
            normalize_whitespace=False
            ), 
            reply_markup=settingMenu.provider_keyboard(), 
            parse_mode=ParseMode.MARKDOWN_V2)
        return SELECTING_PROVIDER
    elif option == "temperature":
        await query.edit_message_text(
            tm.markdownify((
                f"__{BOT_NAME}__ | Set Temperature\n"
                f"━━━━━━━━━━\n"
                f"*Current Temperature:* {str(context.user_data['settings'][2])} \n\n"
                f"Enter a new temperature value (0.0 to 1.0):"
            ),
            max_line_length=None,
            normalize_whitespace=False
            ), 
            reply_markup=settingMenu.back_keyboard(), 
            parse_mode=ParseMode.MARKDOWN_V2
            )
        return ENTERING_TEMPERATURE
    elif option == "max_tokens":
        await query.edit_message_text(
            tm.markdownify((
                f"__{BOT_NAME}__ | Set Max Tokens\n"
                f"━━━━━━━━━━\n"
                f"*Current Max Tokens:* {str(context.user_data['settings'][3])} \n\n"
                f"Enter a new max tokens value (1 to 4096):"
            ),
            max_line_length=None,
            normalize_whitespace=False
            ), 
            reply_markup=settingMenu.back_keyboard(), 
            parse_mode=ParseMode.MARKDOWN_V2
            )
        return ENTERING_MAX_TOKENS
    elif option == "n":
        await query.edit_message_text(
            tm.markdownify((
                f"__{BOT_NAME}__ | Set N Value\n"
                "━━━━━━━━━━\n"
                f"*Current n value:* {str(context.user_data['settings'][4])} \n\n"
                f"Enter a new N value (0.0 to 1.0):"
            ),
            max_line_length=None,
            normalize_whitespace=False
            ), 
            reply_markup=settingMenu.back_keyboard(), 
            parse_mode=ParseMode.MARKDOWN_V2
            )
        return ENTERING_N
    elif option == "start_prompt":
        await query.edit_message_text(
            tm.markdownify((
                f"__{BOT_NAME}__ | Set Starting Prompt\n"
                "━━━━━━━━━━\n"
                f"*Current Starting Prompt:* \n\n"
                f"```prompt\n{str(context.user_data['settings'][5])}\n``` \n\n"
                f"Enter a new starting prompt:"
            ),
            max_line_length=None,
            normalize_whitespace=False
            ), 
            reply_markup=settingMenu.back_keyboard(),
            parse_mode=ParseMode.MARKDOWN_V2
            )
        return ENTERING_START_PROMPT
    elif option == "image_settings":
        from settings.imageGenHandler import image_settings
        await image_settings(update, context)
        return SELECTING_IMAGE_SETTINGS
    elif option == "reset_to_default":
        await query.edit_message_text(
            "Resetting to default settings..."
            )
        await reset_selected(update, context)
        return SELECTING_OPTION

async def model_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_settings":
        await settingMenu.show_current_settings(update, context)
        return SELECTING_OPTION
    
    selected_model = query.data.split("_model:")[1]
    context.user_data['settings'][1] = selected_model
    
    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE user_preferences SET model = ? WHERE user_id = ?', (selected_model, user_id))
    conn_settinngs.commit()
    
    await query.edit_message_text(f"Model updated to: {selected_model}")
    await settingMenu.show_current_settings(update, context)
    return SELECTING_OPTION

async def provider_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_settings":
        await settingMenu.show_current_settings(update, context)
        return SELECTING_OPTION
    elif query.data == "ollama":
        from providers.ollamaHandler import check_server_status
        if not check_server_status():
            message = await query.message.reply_text("Ollama is currently unavailable. Please try again later.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return SELECTING_PROVIDER
    
    selected_provider = query.data
    context.user_data['settings'][0] = selected_provider
    
    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE user_preferences SET provider = ? WHERE user_id = ?', (selected_provider, user_id))
    conn_settinngs.commit()
    
    # move to model selection
    await query.edit_message_text(
        tm.markdownify((
            f"__{BOT_NAME}__ | Select Model\n"
            "━━━━━━━━━━\n"
            f"*Current Provider:* {context.user_data['settings'][0]} \n"
            f"*Current Model:* {context.user_data['settings'][1]} \n\n"
            f"Select a model:"
        ),
        max_line_length=None,
        normalize_whitespace=False
        ), 
        reply_markup=settingMenu.provider_model_keyboard_switch(context.user_data['settings'][0]), 
        parse_mode=ParseMode.MARKDOWN_V2
        )
    return SELECTING_MODEL

async def temperature_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    try:
        temperature = float(user_input)
        if 0 <= temperature <= 1:
            context.user_data['settings'][2] = temperature
            
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET temperature = ? WHERE user_id = ?', (temperature, user_id))
            conn_settinngs.commit()

            message = await update.message.reply_text(f"Temperature updated to: {temperature}")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            from helpers.mainHelper import cleanup
            await cleanup(update, context)
            await settingMenu.show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            message = await update.message.reply_text("Please enter a value between 0 and 1.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return ENTERING_TEMPERATURE
    except ValueError:
        message = await update.message.reply_text("Please enter a valid number between 0 and 1.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return ENTERING_TEMPERATURE

async def max_tokens_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    try:
        max_tokens = int(user_input)
        if 0 < max_tokens <= 4096:
            context.user_data['settings'][3] = max_tokens
            
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET max_tokens = ? WHERE user_id = ?', (max_tokens, user_id))
            conn_settinngs.commit()
            
            message = await update.message.reply_text(f"Max tokens updated to: {max_tokens}")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            
            from helpers.mainHelper import cleanup
            await cleanup(update, context)

            await settingMenu.show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            message = await update.message.reply_text("Please enter a value between 1 and 4096.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return ENTERING_MAX_TOKENS
    except ValueError:
        message = await update.message.reply_text("Please enter a valid number between 1 and 4096.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return ENTERING_MAX_TOKENS

async def n_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    try:
        n = float(user_input)
        if 0 <= n <= 1:
            context.user_data['settings'][4] = n
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET n = ? WHERE user_id = ?', (n, user_id))
            conn_settinngs.commit()
            message = await update.message.reply_text(f"N updated to: {n}")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)

            from helpers.mainHelper import cleanup
            await cleanup(update, context)

            await settingMenu.show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            message = await update.message.reply_text("Please enter a value between 0 and 1.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            return ENTERING_N
    except ValueError:
        message = await update.message.reply_text("Please enter a valid number between 0 and 1.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return ENTERING_N

async def start_prompt_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    try:
        if user_input.strip().lower() == 'empty':
            context.user_data['settings'][5] = ''
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET start_prompt = ? WHERE user_id = ?', ('', user_id))
            conn_settinngs.commit()
            message = await update.message.reply_text("Starting prompt cleared.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)
            await settingMenu.show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            context.user_data['settings'][5] = user_input
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET start_prompt = ? WHERE user_id = ?', (user_input, user_id))
            conn_settinngs.commit()
            message = await update.message.reply_text("Starting prompt updated.")
            context.user_data.setdefault('sent_messages', []).append(message.message_id)

            from helpers.mainHelper import cleanup
            await cleanup(update, context)
            
            await settingMenu.show_current_settings(update, context)
            return SELECTING_OPTION
    except ValueError:
        message = await update.message.reply_text("Please enter a valid sentence or \"Empty\" if you do not want a starting prompt.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return ENTERING_N

async def reset_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    c.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
    conn_settinngs.commit()
    c.execute('INSERT INTO user_preferences (user_id, max_tokens, start_prompt) VALUES (?, ?, ?)', (user_id, DEFAULT_MAX_TOKENS, DEFAULT_STARTING_MESSAGE))
    conn_settinngs.commit()
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    _, provider, model, temperature, max_tokens, n, start_prompt = row
    context.user_data['settings'] = [provider, model, temperature, max_tokens, n, start_prompt]
    await settingMenu.show_current_settings(update, context)
    return SELECTING_OPTION

def settings_menu_handler():
    from chat.chatMenu import start
    from helpers.mainHelper import handle_unsupported_message, handle_unsupported_command
    return {
        SELECTING_OPTION: [
            CallbackQueryHandler(option_selected),
            CommandHandler("start", start),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
            ],
        SELECTING_PROVIDER: [
            CallbackQueryHandler(provider_selected),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
            ],
        SELECTING_MODEL: [
            CallbackQueryHandler(model_selected),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
            ],
        ENTERING_TEMPERATURE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, temperature_entered),
            CallbackQueryHandler(settingMenu.back_to_settings, pattern="^back_to_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        ENTERING_MAX_TOKENS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, max_tokens_entered),
            CallbackQueryHandler(settingMenu.back_to_settings, pattern="^back_to_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        ENTERING_N: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, n_entered),
            CallbackQueryHandler(settingMenu.back_to_settings, pattern="^back_to_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        ENTERING_START_PROMPT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, start_prompt_entered),
            CallbackQueryHandler(settingMenu.back_to_settings, pattern="^back_to_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        SELECT_RESET: [
            CallbackQueryHandler(reset_selected),
            CommandHandler("start", start),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
            ],
        SELECTING_IMAGE_SETTINGS: [
            CallbackQueryHandler(image_option_selected),
            CommandHandler("start", start),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
        ],
        SELECTING_IMAGE_SIZE: [
            CallbackQueryHandler(image_size_selected),
            CallbackQueryHandler(back_to_image_settings, pattern="^back_to_image_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
        ],
        SELECTING_IMAGE_MODEL: [
            CallbackQueryHandler(image_model_selected),
            CallbackQueryHandler(back_to_image_settings, pattern="^back_to_image_settings$"),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
        ],
    }

def get_current_settings(user_id) -> tuple:
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if row is not None:
        return row
    else:
        c.execute('INSERT INTO user_preferences (user_id, start_prompt) VALUES (?, ?)', (user_id, DEFAULT_STARTING_MESSAGE))
        conn_settinngs.commit()
        c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        row = c.fetchone()
    return row

def reset_user_settings(user_id) -> bool:
    try:
        c.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
        conn_settinngs.commit()
        c.execute('INSERT INTO user_preferences (user_id, start_prompt) VALUES (?, ?)', (user_id, DEFAULT_STARTING_MESSAGE))
        conn_settinngs.commit()
        return True
    except Exception as e:
        logger.error(f"An error occured while trying to reset user settings in chatCompletionHandler.py: {e}")
        return False

def kill_connection() -> None:
    conn_settinngs.close()
    logger.info("chatCompletionHandler DB Connection Closed")