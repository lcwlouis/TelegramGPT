# Importing required libraries
import logging
from typing import Final
from helpers.dateHelper import get_current_date, get_current_weekday

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Collection of Vision models
VISION_MODELS: Final = [
    'gpt-4-turbo',
    'gpt-4o',
    'claude-3-haiku-20240307',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-5-sonnet-20240620',
    'llava-llama3:latest',
]

# Set up system prompt
DEFAULT_SYSTEM_PROMPT = open('./system_prompt.txt', 'r').read()

# Message List Builder
def build_message_list(message_type, message, role, cur_list=[]) -> list:
    if role == 'system':
        day = get_current_weekday()
        date = get_current_date()
        message = message.replace('{{DAY}}', day).replace('{{DATE}}', date)
    if message_type == 'text':
        cur_list.append({
        "role": role, 
        "content": [
            {"type": message_type, f"{message_type}": message}
            ]
        })
    return cur_list