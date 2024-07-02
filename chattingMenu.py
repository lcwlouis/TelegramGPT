import logging
import sqlite3
import base64
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv
from backend import build_message_list, build_message_list_gpt, build_message_list_claude, build_message_list_gemini, chat_with_gpt, chat_with_claude, chat_with_gemini ,image_gen_with_openai, VISION_MODELS
from settingsMenu import get_current_settings

# Define conversation states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'chats.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect(DB_PATH)

c = conn_chats.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS chats
    (id INTEGER PRIMARY KEY AUTOINCREMENT,
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

# Define start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from main import cleanup
    await cleanup(update, context)
    context.user_data.clear()
    return await show_chats(update, context)

# Chats Menu 
async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    c.execute("SELECT id, chat_title FROM chats WHERE user_id = ?", (user_id,))
    chats = c.fetchall()

    keyboard = []
    for chat_id, chat_title in chats:
        chat_title = f"💬 {chat_title}"
        keyboard.append([InlineKeyboardButton(chat_title, callback_data=f"open_chat_{chat_id}")])
    
    keyboard.append([InlineKeyboardButton("🆕New Chat", callback_data="create_new_chat")])
    keyboard.append([InlineKeyboardButton("⚙️Settings", callback_data="settings")])
    keyboard.append([InlineKeyboardButton("❓Help", callback_data="help")])
    keyboard.append([InlineKeyboardButton("🚫Exit", callback_data="exit_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if len(chats) > 0:
        message_text = f"<b><u>Hello {update.effective_user.first_name}</u></b>! Welcome to the <b>Universalis</b>, I am here to answer your questions about anything. \n\n<u>Select a chat or create a new one</u>:\n==================================="
    else:
        message_text = f"<b><u>Hello {update.effective_user.first_name}</u></b>! Welcome to the <b>Universalis</b>, I am here to answer your questions about anything. \n\n<u>Create a new chat</u>:\n==================================="
    
    # await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    try:
        query = update.callback_query
        await query.message.edit_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return SELECTING_CHAT
    except:
        # Edit existing /start message
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        
        return SELECTING_CHAT

async def create_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text="<b>What do you want to talk about?</b> (E.g. \"How to cook scrambled eggs\"):",
        parse_mode=ParseMode.HTML
    )
    return CREATE_NEW_CHAT

async def save_new_chat(prompt, user_id):
    # Generate a title for the new chat
    title_prompt = open("title_system_prompt.txt", "r").read()
    gen_prompt = "The user has asked: " + str(prompt)
    messages = []
    messages = build_message_list("text", title_prompt, "system", messages)
    messages = build_message_list("text", gen_prompt, "user", messages)

    response = await chat_with_gpt(messages, model='gpt-3.5-turbo', temperature=1, max_tokens=15, n=1)
    chat_title = response[3]
    
    c.execute("INSERT INTO chats (user_id, chat_title) VALUES (?, ?)", (user_id, chat_title))
    conn_chats.commit()
    
    c.execute("SELECT id FROM chats WHERE user_id = ? AND chat_title = ?", (user_id, chat_title))
    chat_id = c.fetchone()[0]

    return chat_id, chat_title

async def open_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    chat_id = int(query.data.split('_')[-1])
    
    c.execute("SELECT chat_title FROM chats WHERE id = ?", (chat_id,))
    chat_title = c.fetchone()[0]
    
    context.user_data['current_chat_id'] = chat_id
    context.user_data['current_chat_title'] = chat_title
    
    await query.answer()
    await query.edit_message_text(f"You are now chatting in: {chat_title}! You can save and exit using /end or /delete to delete the chat.")
    
    # Print the chat history if there is any
    c.execute("SELECT type, message, role FROM chat_history WHERE chat_id = ?", (chat_id,))
    chat_history = c.fetchall()
    c.execute("SELECT input_tokens, output_tokens FROM chats WHERE id = ?", (chat_id,))
    row = c.fetchone()
    input_tokens, output_tokens = row
    if chat_history:
        for message_type, message, role in chat_history:
            # print(f"{role}: {message}") # DEBUG_USE
            if role == 'user':
                if message_type == 'text':
                    try:
                        add_to_message_list = await query.message.reply_text(f"<b>You</b>: \n{message}", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error formatting the message: \n{message}")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                if message_type == 'image_url':
                    try:
                        decoded_bytes = base64.b64decode(message)
                        add_to_message_list = await query.message.reply_photo(decoded_bytes)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error sending the image")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                # add_to_message_list = await query.message.reply_text(f"<b>You</b>: \n{message}", parse_mode=ParseMode.HTML)
                # context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
            elif role == 'assistant':
                if message_type == 'text':
                    try:
                        add_to_message_list = await query.message.reply_text(f"<b>Academic Weapon</b>: \n{message}", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error formatting the message: \n{message}")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                if message_type == 'image_url':
                    try:
                        decoded_bytes = base64.b64decode(message)
                        add_to_message_list = await query.message.reply_photo(decoded_bytes)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error sending the image")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
            else:
                pass
        add_to_message_list = await query.message.reply_text(f"Type your message or /end to save and leave this conversation. \nCurrent usage of tokens(I/O): <code>{input_tokens}</code> / <code>{output_tokens}</code>", parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
    else:
        pass
    return CHATTING

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
    print(f"{user_id}: {user_message}") # DEBUG_USE
    # Get current settings
    _, provider, model, temperature, max_tokens, n, start_prompt = get_current_settings(user_id)
    chat_id = context.user_data.get('current_chat_id')
    if chat_id is None:
        chat_id, chat_title = await save_new_chat(user_message, user_id)
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

    # Format chat history for AI model
    # messages = []
    # for type, message, role in chat_history:
    #     messages = build_message_list(type, message, role, model, messages)

    # Generate AI response
    if provider == 'openai':
        messages = build_message_list_gpt(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        input_tokens, output_tokens, role, message = await chat_with_gpt(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n)
    elif provider == 'claude':
        messages = build_message_list_claude(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        input_tokens, output_tokens, role, message = await chat_with_claude(messages, model=model, temperature=temperature, max_tokens=max_tokens, system=start_prompt)
    elif provider == 'google':
        chat_history = build_message_list_gemini(chat_history)
        bot_message = await update.message.reply_text("Working hard...")
        context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        input_tokens, output_tokens, role, message = await chat_with_gemini(user_message, model=model, temperature=temperature, max_tokens=max_tokens, message_history=chat_history, system=start_prompt)

        # messages = build_message_list_google(chat_history)
        # bot_message = await update.message.reply_text("Working hard...")
        # context.user_data.setdefault('sent_messages', []).append(bot_message.message_id)
        # input_tokens, output_tokens, role, message = chat_with_google(messages, model=model, temperature=temperature, max_tokens=max_tokens, n=n)

    # Save AI response to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
              (chat_id, message, role))
    conn_chats.commit()
    
    # Get current token counts from database
    c.execute('SELECT input_tokens, output_tokens FROM chats WHERE id = ?', (chat_id,))
    row = c.fetchone()
    total_input_tokens, total_output_tokens = row

    # Update token counts in database
    total_input_tokens += input_tokens
    total_output_tokens += output_tokens
    c.execute('UPDATE chats SET input_tokens = ?, output_tokens = ? WHERE id = ?', (total_input_tokens, total_output_tokens, chat_id))
    conn_chats.commit()

    reply = f"<b>Academic Weapon</b>: \n{message} \n ------------------- \n<i>Input: {input_tokens} tokens  Output: {output_tokens} tokens</i> \n<i>Total input used: {total_input_tokens} tokens  Total output used: {total_output_tokens} tokens</i>"
    
    try:
        await bot_message.edit_text(reply, parse_mode=ParseMode.HTML)
    except Exception as e:
        message = await bot_message.reply_text(f"Message unable to format properly: {message}")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
    return CHATTING

async def gen_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = context.user_data.get('current_chat_id')
    # Extract prompt from behind /image command
    prompt = update.message.text.split(' ', 1)[1]
    # print(prompt) # DEBUG_USE
    stored_message = "Generate an image prompt: " + prompt
    
    # Save user message to database
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
              (chat_id, stored_message, 'user'))
    conn_chats.commit()

    # Call dalle API
    img_base64 = await image_gen_with_openai(prompt=prompt, model='dall-e-2',n=1, size="256x256")

    if img_base64:
        # Save AI response to database in base64 format
        c.execute("INSERT INTO chat_history (chat_id, type, message, role) VALUES (?, ?, ?, ?)",
                  (chat_id, 'image_url', img_base64, 'assistant'))
        conn_chats.commit()

        # Convert base64 to bytes
        img_bytes = base64.b64decode(img_base64)

        # Send the image
        message = await update.message.reply_photo(photo=img_bytes)
    else:
        message = await update.message.reply_text("Sorry, I couldn't generate the image. Please try again.")
    
    context.user_data.setdefault('sent_messages', []).append(message.message_id)

    return CHATTING

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from main import cleanup
    try:
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
    except KeyError:
        pass
    message = await update.message.reply_text("Chat ended. Returning to chat selection.")
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    await cleanup(update, context)
    await show_chats(update, context)
    return SELECTING_CHAT

async def del_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from main import cleanup
    chat_id = context.user_data.get('current_chat_id')
    
    c.execute("DELETE FROM chat_history WHERE chat_id = ?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
    conn_chats.commit()
    
    # print(f"Chat {chat_id} deleted successfully!") DEBUG_USE

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(f"Chat \"{context.user_data.get('current_chat_title')}\" deleted successfully!")
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
        await cleanup(update, context)
        await show_chats(update, context)
        return SELECTING_CHAT
    else:
        message = await update.message.reply_text(f"Chat \"{context.user_data.get('current_chat_title')}\" deleted successfully!")
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
        await cleanup(update, context)
        await show_chats(update, context)
        return SELECTING_CHAT

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        InlineKeyboardButton("Start", callback_data="show_chats")
    ]
    help_message = """
        <b><u>Help</u></b> 
        Here are the available commands: 
        /start - Brings you to starting menu
        /help - Brings you here. 
        /settings - Enter Settings Menu 
        /image [prompt] - Generates an image (Only use in a Conversation)
        /end - Ends the current conversation (Only use in a Conversation)
        /delete - Deletes the current conversation (Only use in a Conversation)
        """
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(help_message, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([keyboard]))
        return RETURN_TO_MENU
    else:
        message = await update.message.reply_text(help_message, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([keyboard]))
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return RETURN_TO_MENU

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name
    file_extension = os.path.splitext(file_name)[1].lower()

    allowed_extensions = ['.txt', '.pdf', '.docx', '.py']  # Add more as needed
    
    if file_extension not in allowed_extensions:
        await update.message.reply_text(f"Sorry, {file_extension} files are not supported.")
        return CHATTING

    file_path = f"downloads/{file_name}"
    await file.download_to_drive(file_path)

    # Process the file based on its type
    if file_extension == '.txt':
        with open(file_path, 'r') as f:
            file_content = f.read()
    else:
        # For other file types, you might need additional libraries to extract text
        # For example, use PyPDF2 for PDFs, python-docx for Word documents
        file_content = f"File received: {file_name}"

    # Save file info to chat history
    chat_id = context.user_data.get('current_chat_id')
    c.execute("INSERT INTO chat_history (chat_id, message, role) VALUES (?, ?, ?)", 
              (chat_id, f"User uploaded file: {file_name}", 'user'))
    conn_chats.commit()

    # Process file content with AI
    messages = [{"role": "user", "content": f"Analyze this file content: {file_content}"}]
    # Use your preferred AI model to process the file content
    response = chat_with_gpt(messages)  # or chat_with_claude

    await update.message.reply_text(f"File {file_name} processed. AI response: {response}")
    os.remove(file_path)  # Clean up the downloaded file
    return CHATTING

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, provider, model, temperature, max_tokens, n, start_prompt = get_current_settings(update.effective_user.id)
    # Check the model being used, if it is not a vision model as listed tell user to change the model choice
    if model not in VISION_MODELS:
        message =await update.message.reply_text(f"Please select a model from the list: {', '.join(VISION_MODELS)}")
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
        chat_id = context.user_data.get('current_chat_id')
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

def get_chat_handlers():
    from settingsMenu import settings
    from main import exit_menu
    return {
        SELECTING_CHAT: [
            CallbackQueryHandler(create_new_chat, pattern="^create_new_chat$"),
            CallbackQueryHandler(open_chat, pattern="^open_chat_"),
            CallbackQueryHandler(show_help, pattern="^help$"),
            CallbackQueryHandler(exit_menu, pattern="^exit_menu$"),
            CommandHandler("start", start)
        ],
        CREATE_NEW_CHAT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            CommandHandler("start", start),
        ],
        CHATTING: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo),
            CommandHandler("image", gen_image),
            CommandHandler("end", end_chat),
            CommandHandler("delete", del_chat),
            CommandHandler("start", end_chat)
        ],
        RETURN_TO_MENU: [
            CallbackQueryHandler(start, pattern="^show_chats$"),
            CommandHandler("start", start),
        ],
    }

def kill_connection():
    conn_chats.close()
    print("Chat DB Connection Closed")