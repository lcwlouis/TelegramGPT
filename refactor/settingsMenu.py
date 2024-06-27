import sqlite3
from typing import Final, List
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters
from backend import get_available_openai_models, get_available_claude_models

# start sqlite3
conn_settinngs = sqlite3.connect('user_preferences.db')

COLUMNS: Final = 2

# Define conversation states
SELECTING_OPTION, SELECTING_MODEL, ENTERING_TEMPERATURE, ENTERING_MAX_TOKENS, ENTERING_N, ENTERING_START_PROMPT, SELECT_RESET, SELECTING_PROVIDER = range(8)

# Default starting message from file system_prompt.txt
DEFAULT_STARTING_MESSAGE = open('./system_prompt.txt', 'r').read()

# Store user preferences in database
c = conn_settinngs.cursor()
c.execute('CREATE TABLE IF NOT EXISTS user_preferences (user_id INTEGER PRIMARY KEY, provider TEXT DEFAULT "openai", model TEXT DEFAULT "gpt-3.5-turbo", temperature FLOAT DEFAULT 0.5, max_tokens INTEGER DEFAULT 200, n INTEGER DEFAULT 1, start_prompt TEXT DEFAULT "{0}")'.format(DEFAULT_STARTING_MESSAGE))
conn_settinngs.commit()

# Settings 
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id: int = update.effective_user.id
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute('INSERT INTO user_preferences (user_id) VALUES (?)', (user_id,))
        conn_settinngs.commit()
        c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        result = c.fetchone()
    _, provider, model, temperature, max_tokens, n, start_prompt = result

    context.user_data['settings'] = [provider, model, temperature, max_tokens, n, start_prompt]
    if update.message is None:
        query = update.callback_query
        await query.message.edit_text(
            f"<b><u>Current settings:</u></b>\n<b>Provider: </b>{provider}\n<b>Model:</b> {model}\n<b>Temperature:</b> {temperature}\n<b>Max tokens:</b> {max_tokens}\n<b>N:</b> {n}\n<b>Starting Prompt:</b> <blockquote>{start_prompt}</blockquote>",
            reply_markup=settings_keyboard(),
            parse_mode="HTML"
        )
        return SELECTING_OPTION
    await update.message.reply_text(
        f"<b><u>Current settings:</u></b>\n<b>Provider: </b>{provider}\n<b>Model:</b> {model}\n<b>Temperature:</b> {temperature}\n<b>Max tokens:</b> {max_tokens}\n<b>N:</b> {n}\n<b>Starting Prompt:</b> <blockquote>{start_prompt}</blockquote>",
        reply_markup=settings_keyboard(),
        parse_mode="HTML"
    )
    return SELECTING_OPTION

def settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Model", callback_data="model"),
         InlineKeyboardButton("Temperature", callback_data="temperature")],
        [InlineKeyboardButton("Max tokens", callback_data="max_tokens"),
         InlineKeyboardButton("N", callback_data="n")],
        [InlineKeyboardButton("Starting Prompt", callback_data="start_prompt"),
         InlineKeyboardButton("Reset to Default", callback_data="reset_to_default")],
        [InlineKeyboardButton("Done", callback_data="done")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_current_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.user_data['settings']
    keyboard = settings_keyboard()
    message_text = (
        f"<b><u>Current settings:</u></b>\n"
        f"<b>Provider:</b> {settings[0]}\n"
        f"<b>Model:</b> {settings[1]}\n"
        f"<b>Temperature:</b> {settings[2]}\n"
        f"<b>Max tokens:</b> {settings[3]}\n"
        f"<b>N:</b> {settings[4]}\n"
        f"<b>Starting Prompt:</b> <blockquote>{settings[5]}</blockquote>"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode="HTML")

async def back_to_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # remove this message id from the list of messages to delete
    await show_current_settings(update, context)
    return SELECTING_OPTION

async def option_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    option = query.data
    
    if option == "done":
        await query.edit_message_text("Settings updated. /start to go back to the main menu.")
        return ConversationHandler.END
    elif option == "model":
        await query.edit_message_text(f"<b><u>Current Provider</u>: </b>{str(context.user_data['settings'][0])} \n<b><u>Current Model</u>: </b>{str(context.user_data['settings'][1])} \n\nSelect a provider:", reply_markup=provider_keyboard(), parse_mode="HTML")
        return SELECTING_PROVIDER
    elif option == "temperature":
        await query.edit_message_text(f"<b><u>Current Temperature</u>: </b>{str(context.user_data['settings'][2])} \n\nEnter a new temperature value (0.0 to 1.0):", reply_markup=back_keyboard(), parse_mode="HTML")
        return ENTERING_TEMPERATURE
    elif option == "max_tokens":
        await query.edit_message_text(f"<b><u>Current Max Tokens</u>: </b>{str(context.user_data['settings'][3])} \n\nEnter a new max tokens value (1 to 16384):", reply_markup=back_keyboard(), parse_mode="HTML")
        return ENTERING_MAX_TOKENS
    elif option == "n":
        await query.edit_message_text(f"<b><u>Current n value</u>: </b>{str(context.user_data['settings'][4])} \n\nEnter a new N value (0.0 to 1.0):", reply_markup=back_keyboard(), parse_mode="HTML")
        return ENTERING_N
    elif option == "start_prompt":
        await query.edit_message_text(f"<b><u>Current Starting Prompt</u>: </b> <code>{str(context.user_data['settings'][5])}</code> \n\nEnter a new starting prompt:", reply_markup=back_keyboard(), parse_mode="HTML")
        return ENTERING_START_PROMPT
    elif option == "reset_to_default":
        await query.edit_message_text("Resetting to default settings...", parse_mode="HTML")
        await reset_selected(update, context)
        return SELECTING_OPTION


def back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

def provider_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("OpenAI", callback_data="openai"),
         InlineKeyboardButton("Claude", callback_data="claude")],
        [InlineKeyboardButton("Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

def claude_model_keyboard() -> InlineKeyboardMarkup:
    models = get_available_claude_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

def openai_model_keyboard() -> InlineKeyboardMarkup:
    models = get_available_openai_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

async def model_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_settings":
        await show_current_settings(update, context)
        return SELECTING_OPTION
    
    selected_model = query.data.split(":")[1]
    context.user_data['settings'][1] = selected_model
    
    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE user_preferences SET model = ? WHERE user_id = ?', (selected_model, user_id))
    conn_settinngs.commit()
    
    await query.edit_message_text(f"Model updated to: {selected_model}")
    await show_current_settings(update, context)
    return SELECTING_OPTION

async def provider_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == "back_to_settings":
        await show_current_settings(update, context)
        return SELECTING_OPTION
    
    selected_provider = query.data
    context.user_data['settings'][0] = selected_provider
    
    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE user_preferences SET provider = ? WHERE user_id = ?', (selected_provider, user_id))
    conn_settinngs.commit()
    
    # move to model selection
    await query.edit_message_text(f"<b><u>Current Provider</u>: </b>{context.user_data['settings'][0]} \n<b><u>Current Model</u>: </b>{context.user_data['settings'][1]} \nSelect a model:", reply_markup=provider_model_keyboard_switch(context.user_data['settings'][0]), parse_mode="HTML")
    return SELECTING_MODEL

def provider_model_keyboard_switch(provider : str) -> InlineKeyboardMarkup:
    if provider == "openai":
        return openai_model_keyboard()
    elif provider == "claude":
        return claude_model_keyboard()
    else:
        return InlineKeyboardMarkup([])

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

            await update.message.reply_text(f"Temperature updated to: {temperature}")
            await show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            await update.message.reply_text("Please enter a value between 0 and 1.")
            return ENTERING_TEMPERATURE
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 0 and 1.")
        return ENTERING_TEMPERATURE

async def max_tokens_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    try:
        max_tokens = int(user_input)
        if 0 < max_tokens <= 16384:
            context.user_data['settings'][3] = max_tokens
            
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET max_tokens = ? WHERE user_id = ?', (max_tokens, user_id))
            conn_settinngs.commit()
            
            await update.message.reply_text(f"Max tokens updated to: {max_tokens}")
            
            # Clear the chat history on Telegram
            chat_history = []
            context.user_data['chat_history'] = chat_history
            await show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            await update.message.reply_text("Please enter a value between 1 and 16384.")
            return ENTERING_MAX_TOKENS
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 16384.")
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
            await update.message.reply_text(f"N updated to: {n}")
            await show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            await update.message.reply_text("Please enter a value between 0 and 1.")
            return ENTERING_N
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 0 and 1.")
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
            await update.message.reply_text("Starting prompt cleared.")
            await show_current_settings(update, context)
            return SELECTING_OPTION
        else:
            context.user_data['settings'][5] = user_input
            # Update the database
            user_id = update.effective_user.id
            c.execute('UPDATE user_preferences SET start_prompt = ? WHERE user_id = ?', (user_input, user_id))
            conn_settinngs.commit()
            await update.message.reply_text("Starting prompt updated.")
            await show_current_settings(update, context)
            return SELECTING_OPTION
    except ValueError:
        await update.message.reply_text("Please enter a valid sentence or \"Empty\" if you do not want a starting prompt.")
        return ENTERING_N

async def reset_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    c.execute('DELETE FROM user_preferences WHERE user_id = ?', (user_id,))
    conn_settinngs.commit()
    c.execute('INSERT INTO user_preferences (user_id) VALUES (?)', (user_id,))
    conn_settinngs.commit()
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    _, provider, model, temperature, max_tokens, n, start_prompt = row
    context.user_data['settings'] = [provider, model, temperature, max_tokens, n, start_prompt]
    await show_current_settings(update, context)
    return SELECTING_OPTION

def settings_menu_handler():
    return {
            SELECTING_OPTION: [CallbackQueryHandler(option_selected)],
            SELECTING_PROVIDER: [CallbackQueryHandler(provider_selected)],
            SELECTING_MODEL: [CallbackQueryHandler(model_selected)],
            ENTERING_TEMPERATURE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, temperature_entered),
                CallbackQueryHandler(back_to_settings, pattern="^back_to_settings$")
            ],
            ENTERING_MAX_TOKENS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, max_tokens_entered),
                CallbackQueryHandler(back_to_settings, pattern="^back_to_settings$")
                ],
            ENTERING_N: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, n_entered),
                CallbackQueryHandler(back_to_settings, pattern="^back_to_settings$")
                ],
            ENTERING_START_PROMPT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_prompt_entered),
                CallbackQueryHandler(back_to_settings, pattern="^back_to_settings$")
                ],
            SELECT_RESET: [CallbackQueryHandler(reset_selected)]
        }

def get_current_settings(user_id):
    c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    if row is not None:
        return row
    else:
        c.execute('INSERT INTO user_preferences (user_id) VALUES (?)', (user_id,))
        conn_settinngs.commit()
        c.execute('SELECT * FROM user_preferences WHERE user_id = ?', (user_id,))
        row = c.fetchone()
    return row

def kill_connection():
    conn_settinngs.close()
    print("Settings DB Connection Closed")