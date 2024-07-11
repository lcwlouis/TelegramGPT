import re
import os
import aiohttp
import requests
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up url to Ollama API
OLLAMA_URL = os.getenv('OLLAMA_URL')

def build_message_list_ollama(chat_history) -> list:
    messages = []
    prev_message_type = ""
    image = None
    for message_type, message, role in chat_history:
        if prev_message_type == "image_url":
            messages.append({
            "role": role,
            "content": message,
            "images": [image]
            })
            prev_message_type = ""
            image = None
            continue
        if message_type == 'text':
            messages.append({
            "role": role, 
            "content": message
            })
        elif message_type == 'image_url':
            prev_message_type = message_type
            image = message

    return messages

async def chat_with_ollama(messages, model, temperature=0.5, max_tokens=100) -> str:
    # Check if Ollama is available
    if check_server_status() == False:
        return -1, -1, "assistant", "Ollama is not available. Please try again later."
    
    jsonData = {
            "model": model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            "keep_alive": "10m",
            "stream": False,
        }
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{OLLAMA_URL}/api/chat', json=jsonData) as response:
            data = await response.json()
            if data:
                return process_response_from_ollama(data)
            else:
                return 0, 0, "assistant", f"An error occurred while interacting with Ollama. Please try again later. Error code: {response.status_code}"

def get_available_ollama_models() -> list:
    # Check if Ollama is available
    if check_server_status() == False:
        return []

    # Get this via POST request
    available_models = []
    res = requests.get(f'{OLLAMA_URL}/api/tags')
    if res.status_code == 200:
        data = res.json().get('models', [])
        available_models = [data[i]['name'] for i in range(len(data)) if 'embed' not in data[i]['name']]
        available_models = sorted(available_models)
    return available_models

def process_response_from_ollama(response) -> tuple:
    input_tokens = response.get('prompt_eval_count')
    output_tokens = response.get('eval_count')
    role = response.get('message').get('role')
    message = response.get('message').get('content')
    # To manage the case where GPT still outputs unwanted tags that 
    # may cause telegram to fail to format the message properly
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message

def check_server_status() -> bool:
    try:
        res = requests.get(f'{OLLAMA_URL}', timeout=2.5)
        if res.status_code == 200:
            return True
        else:
            return False
    except (requests.exceptions.Timeout, requests.exceptions.RequestException):
        return False

print(check_server_status())