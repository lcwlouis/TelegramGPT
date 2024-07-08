import sqlite3
import os
from typing import Final
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import settings.settingMenu as settingMenu


SELECTING_IMAGE_SETTINGS, SELECTING_IMAGE_MODEL, SELECTING_IMAGE_SIZE = range(12,15)
SELECTING_OPTION = 4

# DEFINE LIST OF MODELS, SIZES
IMAGE_MODELS: Final = [
    "dall-e-2",
    "dall-e-3",
]

IMAGE_SIZES_DALLE2: Final = [
    "256x256",
    "512x512",
    "1024x1024",
]

IMAGE_SIZES_DALLE3: Final = [
    "1024x1024",
    "1024x1792",
    "1792x1024",
]

# Initialise path to db
DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'user_preferences.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# start sqlite3
conn_settinngs = sqlite3.connect(DB_PATH)


# Store user preferences in database
c = conn_settinngs.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS image_gen_user_preferences 
        (user_id INTEGER PRIMARY KEY,
        model TEXT DEFAULT "dall-e-2", 
        size TEXT DEFAULT "256x256"
        )''')

async def image_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    _, model, size = get_image_settings(user_id)

    context.user_data['image_settings'] = [model, size]
    if update.message is None:
        query = update.callback_query
        await query.message.edit_text(f"<b><u>Current image gen settings:</u></b>\n<b>Model:</b> {model}\n<b>Image Size:</b> {size}", 
                                    reply_markup=settingMenu.image_settings_keyboard(), 
                                    parse_mode=ParseMode.HTML)
        return SELECTING_IMAGE_SETTINGS
    message = await update.message.reply_text(f"<b><u>Current image gen settings:</u></b>\n<b>Model:</b> {model}\n<b>Image Size:</b> {size}", 
                                            reply_markup=settingMenu.image_settings_keyboard(),
                                            parse_mode=ParseMode.HTML)
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    return SELECTING_IMAGE_SETTINGS

async def image_option_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    option = query.data

    if option == "select_image_model":
        await query.edit_message_text(
            f"Current image model: {context.user_data['image_settings'][0]}\n\nSelect a new image model:",
            reply_markup=settingMenu.image_model_keyboard()
        )
        return SELECTING_IMAGE_MODEL
    elif option == "select_image_size":
        model = context.user_data['image_settings'][0]
        await query.edit_message_text(
            f"Current image size: {context.user_data['image_settings'][1]}\n\nSelect a new image size:",
            reply_markup=settingMenu.image_size_keyboard(model)
        )
        return SELECTING_IMAGE_SIZE
    elif option == "back_to_settings":
        await settingMenu.show_current_settings(update, context)
        return SELECTING_OPTION

async def image_model_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_image_settings":
        await image_settings(update, context)
        return SELECTING_IMAGE_SETTINGS
    
    selected_model = query.data.split(":")[1]
    context.user_data['image_settings'][0] = selected_model

    # Check if the image size is applicable to model selected
    if selected_model == "dall-e-2":
        context.user_data['image_settings'][1] = "256x256"
    elif selected_model == "dall-e-3":
        context.user_data['image_settings'][1] = "1024x1024"
    
    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE image_gen_user_preferences SET model = ?, size = ? WHERE user_id = ?', (selected_model, context.user_data['image_settings'][1], user_id))
    conn_settinngs.commit()
    
    await query.edit_message_text(f"Image model updated to: {selected_model} \nImage size has been updated to default: {context.user_data['image_settings'][1]}")
    await image_settings(update, context)
    return SELECTING_IMAGE_SETTINGS

async def image_size_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "back_to_image_settings":
        await image_settings(update, context)
        return SELECTING_IMAGE_SETTINGS
    
    selected_size = query.data.split(":")[1]
    context.user_data['image_settings'][1] = selected_size

    # Update the database
    user_id = update.effective_user.id
    c.execute('UPDATE image_gen_user_preferences SET size = ? WHERE user_id = ?', (selected_size, user_id))
    conn_settinngs.commit()
    
    await query.edit_message_text(f"Image size updated to: {selected_size}")
    await image_settings(update, context)
    return SELECTING_IMAGE_SETTINGS

async def back_to_image_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await image_settings(update, context)
    return SELECTING_IMAGE_SETTINGS

def get_image_settings(user_id):
    # Ensure the user_id has a row in the database
    c.execute('SELECT * FROM image_gen_user_preferences WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result is None:
        c.execute('INSERT INTO image_gen_user_preferences (user_id) VALUES (?)', (user_id,))
        conn_settinngs.commit()
        c.execute('SELECT * FROM image_gen_user_preferences WHERE user_id = ?', (user_id,))
        result = c.fetchone()
    return result

def kill_connection() -> None:
    conn_settinngs.close()
    print("Image Gen Settings DB Connection Closed")