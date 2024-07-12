import telegramify_markdown as tm
import os
import logging
from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import providers.gptHandler as gpt
import providers.claudeHandler as claude
import providers.geminiHandler as gemini
import providers.ollamaHandler as ollama

# Initialize logging
logger = logging.getLogger(__name__)

COLUMNS: Final = 2

# Define conversation states
SELECTING_OPTION, SELECTING_MODEL, ENTERING_TEMPERATURE, ENTERING_MAX_TOKENS, ENTERING_N, ENTERING_START_PROMPT, SELECT_RESET, SELECTING_PROVIDER, SELECTING_IMAGE_SETTINGS = range(4, 13)

BOT_NAME = os.getenv('BOT_NAME')

PROVIDERS: Final = [
    "openai",
    "claude",
    "google",
    "ollama",
]

def settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📚 Model", callback_data="model"),
        InlineKeyboardButton("🔆 Temperature", callback_data="temperature")],
        [InlineKeyboardButton("📐 Max tokens", callback_data="max_tokens"),
        InlineKeyboardButton("➕ N", callback_data="n")],
        [InlineKeyboardButton("💬 Starting Prompt", callback_data="start_prompt"),
        InlineKeyboardButton("🖼 Image Gen Settings", callback_data="image_settings")],
        [InlineKeyboardButton("🔁 Reset to Default", callback_data="reset_to_default"), InlineKeyboardButton("✅ Done", callback_data="show_chats")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_current_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = context.user_data['settings']
    keyboard = settings_keyboard()
    message_text = tm.markdownify((
        f"__{BOT_NAME}__ | Settings\n"
        f"━━━━━━━━━━\n"
        f"*Provider:* `{settings[0]}`\n"
        f"*Model:* `{settings[1]}`\n"
        f"*Temperature:* `{settings[2]}`\n"
        f"*Max tokens:* `{settings[3]}`\n"
        f"*N:* `{settings[4]}`\n"
        "*Starting Prompt:* \n"
        "> Select Starting Prompt to see the prompt\n\n"
        "*Image Settings:* \n"
        "> Select Image Settings to see the image settings"),
        max_line_length=None,
        normalize_whitespace=False
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        message = await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)

async def back_to_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # remove this message id from the list of messages to delete
    await show_current_settings(update, context)
    return SELECTING_OPTION

def back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)

def provider_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(provider.title(), callback_data=f"{provider}") for provider in PROVIDERS[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(PROVIDERS))
    ]
    keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_settings")])
    return InlineKeyboardMarkup(keyboard)

def claude_model_keyboard() -> InlineKeyboardMarkup:
    models = claude.get_available_claude_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

def openai_model_keyboard() -> InlineKeyboardMarkup:
    models = gpt.get_available_openai_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

def google_model_keyboard() -> InlineKeyboardMarkup:
    models = gemini.get_available_gemini_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

def ollama_model_keyboard() -> InlineKeyboardMarkup:
    models = ollama.get_available_ollama_models()
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_model:{model}") for model in models[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(models))
    ]
    return InlineKeyboardMarkup(keyboard)

def provider_model_keyboard_switch(provider : str) -> InlineKeyboardMarkup:
    if provider == "openai":
        return openai_model_keyboard()
    elif provider == "claude":
        return claude_model_keyboard()
    elif provider == "google":
        return google_model_keyboard()
    elif provider == "ollama":
        return ollama_model_keyboard()
    else:
        return InlineKeyboardMarkup([])





# Image gen settings menu
def image_model_keyboard() -> InlineKeyboardMarkup:
    from settings.imageGenHandler import IMAGE_MODELS
    keyboard = [
        [InlineKeyboardButton(model, callback_data=f"select_image_model:{model}") for model in IMAGE_MODELS[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(IMAGE_MODELS))
    ]
    keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_image_settings")])
    return InlineKeyboardMarkup(keyboard)

def image_size_keyboard(model : str) -> InlineKeyboardMarkup:
    from settings.imageGenHandler import IMAGE_SIZES_DALLE2, IMAGE_SIZES_DALLE3
    if model == "dall-e-2":
        IMAGE_SIZES = IMAGE_SIZES_DALLE2
    elif model == "dall-e-3":
        IMAGE_SIZES = IMAGE_SIZES_DALLE3
    keyboard = [
        [InlineKeyboardButton(size, callback_data=f"select_image_size:{size}") for size in IMAGE_SIZES[model_pair*COLUMNS:model_pair*COLUMNS+COLUMNS]]
        for model_pair in range(len(IMAGE_SIZES))
    ]
    keyboard.append([InlineKeyboardButton("Back", callback_data="back_to_image_settings")])
    return InlineKeyboardMarkup(keyboard)

# Add this to the existing image_settings_keyboard function
def image_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Model", callback_data="select_image_model"),
        InlineKeyboardButton("Image Size", callback_data="select_image_size")],
        [InlineKeyboardButton("Back", callback_data="back_to_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)