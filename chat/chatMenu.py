import sqlite3
import logging
import os
import base64
import time
import html
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Define conversation states
SELECTING_CHAT, CREATE_NEW_CHAT, CHATTING, RETURN_TO_MENU = range(4)

# Define max chats per page
MAX_CHATS_PER_PAGE = 5

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'chats.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect(DB_PATH)

c = conn_chats.cursor()

# Define start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, command_start: bool = True) -> int:
    from helpers.mainHelper import cleanup
    temp = []
    if command_start:
        temp.append(update.message.message_id)
    else:
        temp = context.user_data.get('start_cmd_ids', [])
    await cleanup(update, context)
    context.user_data.clear()
    context.user_data['chat_page'] = 0  # Reset the page to 0
    context.user_data.setdefault('start_cmd_ids', []).extend(temp)
    return await show_chats(update, context)

# Chats Menu 
async def show_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    page = context.user_data.get('chat_page', 0)
    chats_per_page = MAX_CHATS_PER_PAGE

    # Debounce mechanism
    current_time = time.time()
    last_update_time = context.user_data.get('last_update_time', 0)
    if current_time - last_update_time < 2:  # 2000ms debounce
        return SELECTING_CHAT
    context.user_data['last_update_time'] = current_time

    # Get total number of chats
    c.execute("SELECT COUNT(*) FROM chats WHERE user_id = ?", (user_id,))
    total_chats = c.fetchone()[0]

    # Calculate total pages
    total_pages = max(1, (total_chats - 1) // chats_per_page + 1)

    # Ensure page is within valid range
    page = max(0, min(page, total_pages - 1))
    context.user_data['chat_page'] = page

    # Get chats for current page
    c.execute("SELECT id, chat_title FROM chats WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", 
              (user_id, chats_per_page, page * chats_per_page))
    chats = c.fetchall()

    keyboard = []
    for chat_id, chat_title in chats:
        chat_title = f"💬 {chat_title}"
        keyboard.append([InlineKeyboardButton(chat_title, callback_data=f"open_chat_{chat_id}")])

    # Add pagination buttons if needed
    if total_pages > 1:
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"))
        else:
            pagination_buttons.append(InlineKeyboardButton("1️⃣ First Page", callback_data="no_page"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="next_page"))
        else:
            pagination_buttons.append(InlineKeyboardButton("Last Page 🔚", callback_data="no_page"))
        pagination_buttons.insert(1, InlineKeyboardButton("🆕New Chat", callback_data="create_new_chat"))
        keyboard.append(pagination_buttons)
    else:
        keyboard.append([InlineKeyboardButton("🆕New Chat", callback_data="create_new_chat")])

    keyboard.append([InlineKeyboardButton("❓Help", callback_data="help"), InlineKeyboardButton("⚙️Settings", callback_data="settings"), InlineKeyboardButton("🚫Exit", callback_data="exit_menu")])
    # keyboard.append([])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if total_pages > 1:
        message_text = (
            f"<u><b>Universalis</b></u> \n"
            f"<b>Hello {update.effective_user.first_name}</b>! I am here to answer your questions about anything. \n\n"
            f"Page {page + 1} of {total_pages}\n"
            f"<u>Select a chat or create a new one</u>:\n"
        )
    elif len(chats) > 0:
        message_text = (
            f"<u><b>Universalis</b></u> \n"
            f"<b>Hello {update.effective_user.first_name}</b>! I am here to answer your questions about anything. \n\n"
            f"<u>Select a chat or create a new one</u>:\n"
        )
    else:
        message_text = (
            f"<u><b>Universalis</b></u> \n"
            f"<b>Hello {update.effective_user.first_name}</b>! I am here to answer your questions about anything. \n\n"
            f"<u>Create a new one</u>:\n"
        )
    
    try:
        query = update.callback_query
        # await query.answer()  # Always answer the callback query
        if query.message.text != message_text or query.message.reply_markup != reply_markup:
            await query.message.edit_text(text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        return SELECTING_CHAT
    except:
        # This is not a callback query, so send a new message
        message = await context.bot.send_message(chat_id=update.effective_chat.id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return SELECTING_CHAT
    
    
async def create_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        text=
            "<u>How can Universalis help you today?</u> \n\n",
        parse_mode=ParseMode.HTML
    )
    return CREATE_NEW_CHAT

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
                        add_to_message_list = await query.message.reply_text(f"<u><b>You</b></u>: \n{message}", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"<u><b>You</b></u><b>Error formatting the message: </b>\n{html.escape(message)}", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                if message_type == 'image_url':
                    try:
                        decoded_bytes = base64.b64decode(message)
                        add_to_message_list = await query.message.reply_photo(decoded_bytes, caption=f"<u><b>You</b></u>: \n", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error sending the image")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                # add_to_message_list = await query.message.reply_text(f"<b>You</b>: \n{message}", parse_mode=ParseMode.HTML)
                # context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
            elif role == 'assistant':
                if message_type == 'text':
                    from helpers.chatHelper import smart_split
                    messages = smart_split(message)
                    for i, message_part in enumerate(messages):
                        try:
                            header = "<u><b>Universalis</b></u>: \n" if i == 0 else ""
                            add_to_message_list = await query.message.reply_text(f"{header}{message_part}", parse_mode=ParseMode.HTML)
                            context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                        except Exception as e:
                            header = "<u><b>Universalis</b></u><b>Error formatting the message: </b>\n" if i == 0 else ""
                            add_to_message_list = await query.message.reply_text(f"{header}{html.escape(message_part)}", parse_mode=ParseMode.HTML)
                            context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                if message_type == 'image_url':
                    try:
                        decoded_bytes = base64.b64decode(message)
                        add_to_message_list = await query.message.reply_photo(decoded_bytes, caption=f"<u><b>Universalis</b></u>: \n", parse_mode=ParseMode.HTML)
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
                    except Exception as e:
                        add_to_message_list = await query.message.reply_text(f"Error sending the image")
                        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
            else:
                pass
        add_to_message_list = await query.message.reply_text(f"Continue messaging or /end to safely exit or /delete to delete this conversation. \nCurrent usage of tokens(I/O): <code>{input_tokens}</code> / <code>{output_tokens}</code>", parse_mode=ParseMode.HTML)
        context.user_data.setdefault('sent_messages', []).append(add_to_message_list.message_id)
    else:
        pass
    return CHATTING

async def prev_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['chat_page'] = max(0, context.user_data.get('chat_page', 0) - 1)
    try:
        return await show_chats(update, context)
    except Exception as e:
        print(f"Ignoring spam press of button: {e}")
        return SELECTING_CHAT

async def next_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['chat_page'] = context.user_data.get('chat_page', 0) + 1
    try:
        return await show_chats(update, context)
    except Exception as e:
        print(f"Ignoring spam press of button: {e}")
        return SELECTING_CHAT

async def no_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Just answer the callback query without changing anything
    await update.callback_query.answer()
    return SELECTING_CHAT

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from helpers.mainHelper import cleanup
    try:
        del context.user_data['current_chat_id']
        del context.user_data['current_chat_title']
    except KeyError:
        pass
    message = await update.message.reply_text("Chat ended. Cleaning up. Returning to chat selection.")
    context.user_data.setdefault('sent_messages', []).append(message.message_id)
    await cleanup(update, context)
    await show_chats(update, context)
    return SELECTING_CHAT

async def del_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from helpers.mainHelper import cleanup
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
    help_message = (
        "<b><u>Universalis</u></b>\n"
        "Here are the available commands:\n"
        "/start - Brings you to starting menu\n"
        "/help - Brings you here.\n"
        "/image [prompt] - Generates an image (Only use in a Conversation)\n"
        "/end - Ends the current conversation (Only use in a Conversation)\n"
        "/delete - Deletes the current conversation (Only use in a Conversation)\n"
        )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(help_message, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([keyboard]))
        return RETURN_TO_MENU
    else:
        message = await update.message.reply_text(help_message, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([keyboard]))
        context.user_data.setdefault('sent_messages', []).append(message.message_id)
        return RETURN_TO_MENU
    
def kill_connection():
    conn_chats.close()
    print("chatMenu DB Connection Closed")