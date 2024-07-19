import logging
import sqlite3
import os
import base64
import html
import telegramify_markdown
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

import providers.miscHandler as miscHandler
import providers.gptHandler as gpt
import providers.claudeHandler as claude
import providers.geminiHandler as gemini
import providers.ollamaHandler as ollama
import settings.chatCompletionHandler as chatCompletionHandler
import settings.imageGenHandler as imageGenHandler
from helpers.chatHelper import smart_split

# Define conversation states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

BOT_NAME = os.getenv('BOT_NAME')

# Initialize logging
logger = logging.getLogger(__name__)

# Initialise path to db
DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'chats.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# Initialise path to title system prompt
PROMPT_DIR = os.getenv('PROMPT_DIR')
PROMPT_FILE = 'title_system_prompt.txt'
TITLE_PROMPT_PATH = os.path.join(PROMPT_DIR, PROMPT_FILE)

os.makedirs(PROMPT_DIR, exist_ok=True)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect(DB_PATH)

c = conn_chats.cursor()

c.execute('''
    CREATE TABLE IF NOT EXISTS chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_title TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0)
''')
conn_chats.commit()

# Create chat history table
c.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        chat_id INTEGER,
        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'text',
        message TEXT,
        role TEXT,
        FOREIGN KEY (chat_id) REFERENCES chats(id)
    )
''')
conn_chats.commit()

async def handle_save_new_chat(prompt, user_id):
    # Generate a title for the new chat
    title_prompt = open(TITLE_PROMPT_PATH, "r").read()
    gen_prompt = "The user has asked: " + str(prompt)
    messages = []
    messages = miscHandler.build_message_list("text", title_prompt, "system", messages)
    messages = miscHandler.build_message_list("text", gen_prompt, "user", messages)

    response = await gpt.chat_with_gpt(messages, model='gpt-4o-mini', temperature=1, max_tokens=30, n=1)
    chat_title = response[3]
    
    c.execute("INSERT INTO chats (user_id, chat_title) VALUES (?, ?)", 
            (user_id, chat_title))
    conn_chats.commit()
    
    c.execute("SELECT id FROM chats WHERE user_id = ? AND chat_title = ?", 
            (user_id, chat_title))
    chat_id = c.fetchone()[0]

    return chat_id, chat_title

def check_if_chat_history_exists(chat_id: int, SYSTEM_PROMPT: str) -> None:
    c.execute("SELECT COUNT(*) FROM chat_history WHERE chat_id = ?", (chat_id,))
    count = c.fetchone()[0]
    if count == 0:
        # If chat history is empty add system prompt to chat history
        c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
                (chat_id, SYSTEM_PROMPT, 'system'))
        conn_chats.commit()
        # print(f"Chat history for chat {chat_id} created") DEBUG_USE

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    logger.info(f"{user_id}: {user_message}")
    # Get current settings
    _, provider, model, temperature, max_tokens, n, start_prompt = chatCompletionHandler.get_current_settings(user_id)
    chat_id = context.user_data.get('current_chat_id')
    if chat_id is None:
        chat_id, chat_title = await handle_save_new_chat(user_message, user_id)
        context.user_data['current_chat_id'] = chat_id
        context.user_data['current_chat_title'] = chat_title
        message = await update.message.reply_text(f"You are now chatting in: {chat_title}! You can save and exit using /end or /delete to delete the chat.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
    else:
        pass
    # Check if chat history is empty for the current chat
    check_if_chat_history_exists(chat_id, start_prompt)
    
    # Save user message to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
            (chat_id, user_message, 'user'))
    conn_chats.commit()
    
    # Retrieve chat history
    c.execute("SELECT type, message, role FROM chat_history WHERE chat_id = ? ORDER BY rowid", (chat_id,))
    chat_history = c.fetchall()

    # Generate AI response chat completion
    return await handle_chat_completion(provider, model, temperature, max_tokens, n, start_prompt, chat_history, user_message, chat_id, update, context)

async def handle_gen_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = context.user_data.get('current_chat_id')
    chat_title = context.user_data.get('current_chat_title')
    # Extract prompt from behind /image command
    if len(update.message.text.split(' ', 1)) == 1:
        message = await update.message.reply_text("Please enter an image prompt.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING
    prompt = update.message.text.split(' ', 1)[1]
    # print(prompt) # DEBUG_USE
    stored_message = "Generate an image prompt: " + prompt

    # Retrieve image gen settings from database
    _, model, size = imageGenHandler.get_image_settings(update.effective_user.id)

    # Call dalle API
    try:
        img_base64 = await gpt.image_gen_with_openai(prompt=prompt, model=model,n=1, size=size)
        # Save user message to database only if image was generated
        c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
                (chat_id, stored_message, 'user'))
        conn_chats.commit()
    except Exception as e:
        logger.error(f"An error occurred while generating the image in chatHandler.py: {e}.")
        error_msg = telegramify_markdown.markdownify(f"__{BOT_NAME}__ | Error \nAn error occurred while generating the image: {e}. The image prompt will not be saved.", max_line_length=None, normalize_whitespace=False)
        message_id = await update.message.reply_text(
            error_msg, 
            parse_mode=ParseMode.MARKDOWN_V2
            )
        context.user_data.setdefault('sent_messages', []).append(message_id.message_id)
        return CHATTING

    if img_base64:
        # Save AI response to database in base64 format
        c.execute("INSERT INTO chat_history (chat_id, type, message, role) VALUES (?, ?, ?, ?)", 
                (chat_id, 'image_url', img_base64, 'assistant'))
        conn_chats.commit()

        # Convert base64 to bytes
        img_bytes = base64.b64decode(img_base64)

        # Send the image
        caption = telegramify_markdown.markdownify(f"__{BOT_NAME}__ | Chat: {chat_title}", max_line_length=None, normalize_whitespace=False)
        message = await update.message.reply_photo(photo=img_bytes, caption=caption, parse_mode=ParseMode.MARKDOWN_V2)
    else:
        error_msg = telegramify_markdown.markdownify(f"__{BOT_NAME}__ | Error\nAn error occurred while generating the image.", max_line_length=None, normalize_whitespace=False)
        message = await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
    
    context.user_data.setdefault('sent_messages', []).append(message.message_id)

    return CHATTING

# RAG TO BE IMPLMENTED
# async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     file = await update.message.document.get_file()
#     file_name = update.message.document.file_name
#     file_extension = os.path.splitext(file_name)[1].lower()

#     allowed_extensions = ['.txt', '.pdf', '.docx', '.py']  # Add more as needed
    
#     if file_extension not in allowed_extensions:
#         await update.message.reply_text(f"Sorry, {file_extension} files are not supported.")
#         return CHATTING

#     file_path = f"downloads/{file_name}"
#     await file.download_to_drive(file_path)

#     # Process the file based on its type
#     if file_extension == '.txt':
#         with open(file_path, 'r') as f:
#             file_content = f.read()
#     else:
#         # For other file types, you might need additional libraries to extract text
#         # For example, use PyPDF2 for PDFs, python-docx for Word documents
#         file_content = f"File received: {file_name}"

#     # Save file info to chat history
#     chat_id = context.user_data.get('current_chat_id')
#     c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
#             (chat_id, f"User uploaded file: {file_name}", 'user'))
#     conn_chats.commit()

#     # Process file content with AI
#     messages = [{"role": "user", "content": f"Analyze this file content: {file_content}"}]
#     # Use your preferred AI model to process the file content
#     response = gpt.chat_with_gpt(messages)  # or chat_with_claude

#     await update.message.reply_text(f"File {file_name} processed. AI response: {response}")
#     os.remove(file_path)  # Clean up the downloaded file
#     return CHATTING

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, provider, model, temperature, max_tokens, n, start_prompt = chatCompletionHandler.get_current_settings(update.effective_user.id)
    # Check the model being used, if it is not a vision model as listed tell user to change the model choice
    if model not in miscHandler.VISION_MODELS:
        message =await update.message.reply_text(f"Please select a model from the list: {', '.join(miscHandler.VISION_MODELS)}")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING
    photo_file = await update.message.photo[-1].get_file()
    # Ensure incoming file format is jpg
    if not (('.jpg' in photo_file.file_path) or ('.jpeg' in photo_file.file_path)):
        message = await update.message.reply_text("Unfortunately we only accept a .jpg or .jpeg image.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING
    
    # Download the photo as a variable
    image_bytes = await photo_file.download_as_bytearray()
    image_in_base64 = base64.b64encode(image_bytes).decode('utf-8')

    # Save photo info to chat history
    if image_in_base64 is not None:
        logger.info(f"User uploaded caption with image: {update.message.caption}")
        if update.message.caption is not None:
            user_message = update.message.caption
            user_id = update.effective_user.id
            # Get current settings
            _, provider, model, temperature, max_tokens, n, start_prompt = chatCompletionHandler.get_current_settings(user_id)
            chat_id = context.user_data.get('current_chat_id')
            if chat_id is None:
                chat_id, chat_title = await handle_save_new_chat(user_message, user_id)
                context.user_data['current_chat_id'] = chat_id
                context.user_data['current_chat_title'] = chat_title
                message = await update.message.reply_text(f"You are now chatting in: {chat_title}! You can save and exit using /end or /delete to delete the chat.")
                context.user_data.setdefault('sent_messages', []).append(message.message_id)
            else:
                pass
            # Check if chat history is empty for the current chat
            check_if_chat_history_exists(chat_id, start_prompt)

            c.execute("INSERT INTO chat_history (chat_id, type, message, role) VALUES (?, ?, ?, ?)", 
                    (chat_id, "image_url", image_in_base64, 'user'))
            conn_chats.commit()
            
            # Save user message to database
            c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
                    (chat_id, user_message, 'user'))
            conn_chats.commit()
            
            # Retrieve chat history
            c.execute("SELECT type, message, role FROM chat_history WHERE chat_id = ? ORDER BY rowid", (chat_id,))
            chat_history = c.fetchall()

            # Generate AI response
            return await handle_chat_completion(provider, model, temperature, max_tokens, n, start_prompt, chat_history, user_message, chat_id, update, context)
        chat_id = context.user_data.get('current_chat_id')
        check_if_chat_history_exists(chat_id, start_prompt)
        c.execute("INSERT INTO chat_history (chat_id, type, message, role) VALUES (?, ?, ?, ?)", 
                (chat_id, "image_url", image_in_base64, 'user'))
        conn_chats.commit()
        message = await update.message.reply_text("Photo received. Continue typing your message.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING

    if image_in_base64 is None:
        message = await update.message.reply_text("Failed to download image.")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING
    
    # os.remove(file_path)  # Clean up the downloaded file
    return CHATTING

async def handle_chat_completion(provider, model, temperature, max_tokens, n, start_prompt, chat_history, user_message, chat_id, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_tokens = 0
    output_tokens = 0
    role = None
    message = None
    if provider == 'openai':
        messages = gpt.build_message_list_gpt(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        try:
            input_tokens, output_tokens, role, message = await gpt.chat_with_gpt(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n)
        except Exception as e:
            logger.error(f"An error occurred while talking to GPT in chatHandler.py: {e}.")
            error_msg = f"__{BOT_NAME}__ | Error \nAn error occurred while talking to GPT: {e}"
            error_msg = telegramify_markdown.markdownify(error_msg, max_line_length=None, normalize_whitespace=False)
            await bot_message.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
            return CHATTING
    elif provider == 'claude':
        messages = claude.build_message_list_claude(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        try:
            input_tokens, output_tokens, role, message = await claude.chat_with_claude(messages, model=model, temperature=temperature, max_tokens=max_tokens, system=start_prompt)
        except Exception as e:
            logger.error(f"An error occurred while talking to Claude in chatHandler.py: {e}.")
            error_msg = f"__{BOT_NAME}__ | Error \nAn error occurred while talking to Claude: {e}"
            error_msg = telegramify_markdown.markdownify(error_msg, max_line_length=None, normalize_whitespace=False)
            await bot_message.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
            return CHATTING
    elif provider == 'google':
        # Add user message to chat history for gemini only
        chat_history = gemini.build_message_list_gemini(chat_history, user_message)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        try:
            input_tokens, output_tokens, role, message = await gemini.chat_with_gemini(model=model, temperature=temperature, max_tokens=max_tokens, message_history=chat_history, system=start_prompt)
        except Exception as e:
            logger.error(f"An error occurred while talking to Gemini in chatHandler.py: {e}.")
            error_msg = f"__{BOT_NAME}__ | Error \nAn error occurred while talking to Gemini: {e}"
            error_msg = telegramify_markdown.markdownify(error_msg, max_line_length=None, normalize_whitespace=False)
            await bot_message.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
            return CHATTING
    elif provider == 'ollama':
        # Check if Ollama is available
        from providers.ollamaHandler import check_server_status
        if not check_server_status():
            message = telegramify_markdown.markdownify(f"__{BOT_NAME}__ | Error \nSorry Ollama is currently unavailable. \nPlease /end and change model in settings.", max_line_length=None, normalize_whitespace=False)
            await bot_message.edit_text(message, parse_mode=ParseMode.MARKDOWN_V2)
            return CHATTING

        chat_history = ollama.build_message_list_ollama(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        try:
            input_tokens, output_tokens, role, message = await ollama.chat_with_ollama(chat_history, model=model, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"An error occurred while talking to Ollama in chatHandler.py: {e}.")
            error_msg = f"__{BOT_NAME}__ | Error\nAn error occurred while talking to {provider.title()}: {e}"
            error_msg = telegramify_markdown.markdownify(error_msg, max_line_length=None, normalize_whitespace=False)
            await bot_message.edit_text(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
            return CHATTING

    # Save AI response to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
            (chat_id, message, role))
    conn_chats.commit()
    
    # Get current token counts from database
    c.execute('SELECT input_tokens, output_tokens FROM chats WHERE id = ?', (chat_id,))
    row = c.fetchone()
    total_input_tokens, total_output_tokens = row

    # Update token counts in database
    if input_tokens is not None:
        total_input_tokens += input_tokens
    if output_tokens is not None:
        total_output_tokens += output_tokens
    c.execute('UPDATE chats SET input_tokens = ?, output_tokens = ? WHERE id = ?', 
            (total_input_tokens, total_output_tokens, chat_id))
    conn_chats.commit()

    reply_heading = telegramify_markdown.markdownify(f"__{BOT_NAME}__ \n", max_line_length=None, normalize_whitespace=False)
    reply_end = (
        f"\nInput: `{input_tokens}` tokens | Output: `{output_tokens}` tokens\n"
        f"Total input used: `{total_input_tokens}` tokens | Total output used: `{total_output_tokens}` tokens\n"
    )
    reply_end = telegramify_markdown.markdownify(reply_end, max_line_length=None, normalize_whitespace=False)
    message_parts = smart_split(message)
    message_parts[0] = reply_heading + message_parts[0]
    message_parts[-1] = message_parts[-1] + reply_end
    for i, message_part in enumerate(message_parts):
        if i == 0:
            try:
                await bot_message.edit_text(message_part, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception as e:
                logger.error(f"An error occurred while editing the message in handle_chat_completion in chatHandler.py: {e}.")
                message = await bot_message.reply_text(f"<b>Message unable to format properly: </b> {html.escape(message)}", parse_mode=ParseMode.HTML)
                context.user_data.setdefault('sent_messages', []).append(message.message_id)
        else:
            try:
                message = await bot_message.reply_text(message_part, parse_mode=ParseMode.MARKDOWN_V2)
                context.user_data.setdefault('sent_messages', []).append(message.message_id)
            except Exception as e:
                logger.error(f"An error occurred while replying to the message in handle_chat_completion in chatHandler.py: {e}.")
                message = await bot_message.reply_text(f"<b>Message unable to format properly: </b> {html.escape(message)}", parse_mode=ParseMode.HTML)
                context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return CHATTING

def get_chat_handlers():
    from helpers.mainHelper import exit_menu, handle_unsupported_command, handle_unsupported_message
    from chat.chatMenu import create_new_chat, open_chat, show_help, start, del_chat, end_chat, prev_page, next_page, no_page, show_chats
    return {
        SELECTING_CHAT: [
            CallbackQueryHandler(create_new_chat, pattern="^create_new_chat$"),
            CallbackQueryHandler(open_chat, pattern="^open_chat_"),
            CallbackQueryHandler(show_help, pattern="^help$"),
            CallbackQueryHandler(exit_menu, pattern="^exit_menu$"),
            CallbackQueryHandler(prev_page, pattern="^prev_page$", block=False),
            CallbackQueryHandler(next_page, pattern="^next_page$", block=False),
            CallbackQueryHandler(no_page, pattern="^no_page$"),
            CommandHandler("start", start,),
            CommandHandler("help", show_help),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        CREATE_NEW_CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo),
            CommandHandler("start", start),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        CHATTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo),
            CommandHandler("image", handle_gen_image),
            CommandHandler("end", end_chat),
            CommandHandler("delete", del_chat),
            CommandHandler("start", end_chat),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
        ],
        RETURN_TO_MENU: [
            CallbackQueryHandler(show_chats, pattern="^show_chats$"),
            CommandHandler("start", start),
            # Handle unsupported commands
            MessageHandler(filters.COMMAND, handle_unsupported_command),
            MessageHandler(~filters.COMMAND, handle_unsupported_message),
        ],

    }

def kill_connection():
    conn_chats.close()
    logger.info("chatHandler DB Connection Closed")
