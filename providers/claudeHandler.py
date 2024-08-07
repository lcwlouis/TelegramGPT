import os
import re
import logging
from typing import Final
from anthropic import AsyncAnthropic
from helpers.dateHelper import get_current_date, get_current_weekday

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Since there is no API endpoint to check for available models, this is to be manually updated
ANTHROPIC_MODELS: Final = [
    'claude-3-haiku-20240307',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-5-sonnet-20240620',
]

# Set up Claude API credentials
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Create an instance of the Anthropic API
anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)

def build_message_list_claude(chat_history) -> list:
    # Claude enforces that assistant must alternate with user
    messages = []
    prev_message_type = ""
    image = None
    for message_type, message, role in chat_history:
        if role == 'system':
            continue
        if len(messages) > 0 and messages[-1].get('role') == 'user' and role == 'user':
            messages.append( {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Ignore this message"}
                ]
            })
        elif len(messages) > 0 and messages[-1].get('role') == 'assistant' and role == 'assistant':
            messages.append( {
            "role": "user",
            "content": [
                {"type": "text", "text": "Ignore this message"}
                ]
            })
        if prev_message_type == "image_url":
            messages.append({
            "role": role,
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image,
                    }
                },
                {"type": "text", "text": message}
                ]
            })
            prev_message_type = ""
            image = None
            continue
        if message_type == 'text':
            messages.append({
            "role": role, 
            "content": [
                {"type": message_type, f"{message_type}": message}
                ]
            })
        elif message_type == 'image_url':
            prev_message_type = message_type
            image = message
    
    return messages

# function to interact with Claude
async def chat_with_claude(messages, model='claude-3-haiku-20240307', temperature=0.5, max_tokens=100, system="") -> str:
    system = system.replace('{{DATE}}', get_current_date()).replace('{{DAY}}', get_current_weekday())
    response = await anthropic.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages
    )
    if response.type == 'error':
        print("Error: " + response.error)
        return None
    return process_response_from_claude(response)

def get_available_claude_models() -> list:
    return ANTHROPIC_MODELS

def process_response_from_claude(response) -> tuple:
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    role = response.role
    message = response.content[0].text
    # To manage the case where GPT still outputs unwanted tags that 
    # may cause telegram to fail to format the message properly
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message