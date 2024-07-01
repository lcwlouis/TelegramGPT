# Importing required libraries
import re
import sqlite3
import os
import base64
import aiohttp
import google.generativeai as gemini
from io import BytesIO
from PIL import Image
from typing import Final
from anthropic import AsyncAnthropic
from openai import OpenAI
from dotenv import load_dotenv
from dateHelper import get_current_date, get_current_weekday

# Load environment variables from .env file
load_dotenv()

# Since there is no API endpoint to check for available models, this is to be manually updated
ANTHROPIC_MODELS: Final = [
    'claude-3-haiku-20240307',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-5-sonnet-20240620',
]

# Collection of Vision models
VISION_MODELS: Final = [
    'gpt-4-turbo',
    'gpt-4o',
    'claude-3-haiku-20240307',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-5-sonnet-20240620',
    'gemini-1.5-flash',
    'gemini-1.5-pro',
]

# Set up system prompt
DEFAULT_SYSTEM_PROMPT = open('./system_prompt.txt', 'r').read()
# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set up Claude API credentials
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Set up Google API credentials
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Create an instance of the OpenAI API
openai = OpenAI()

# Create an instance of the Anthropic API
anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)

# Create an instance of the Gemini API
gemini.configure(api_key=GEMINI_API_KEY)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect('chats.db')

c = conn_chats.cursor()

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

# Message list builder for gpt
def build_message_list_gpt(chat_history) -> list:
    messages = []
    for message_type, message, role in chat_history:
        if role == 'system':
            day = get_current_weekday()
            date = get_current_date()
            message = message.replace('{{DAY}}', day).replace('{{DATE}}', date)
        if message_type == 'text':
            messages.append({
            "role": role, 
            "content": [
                {"type": message_type, f"{message_type}": message}
                ]
            })
        elif message_type == 'image_url':
            message = f"data:image/jpeg;base64,{message}"
            messages.append({
            "role": role, 
            "content": [
                {"type": "text", "text": ""},
                {"type": message_type, f"{message_type}": {
                    "url": message
                }}
                ]
            })
    return messages

# Message list builder for claude
def build_message_list_claude(chat_history) -> list:
    messages = []
    prev_message_type = ""
    image = None
    for message_type, message, role in chat_history:
        if role == 'system':
            continue
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

# Define to interact with OpenAI GPT
def chat_with_gpt(messages, model='gpt-3.5-turbo', temperature=0.5, max_tokens=100, n=1) -> str:
    # print(messages)
    response = openai.chat.completions.create(
        model=model,  # Specify the GPT-4 engine
        messages=messages,
        max_tokens=max_tokens,  # Set the maximum number of tokens in the response
        temperature=temperature,  # Control the randomness of the response
        n=n,  # Generate a single response
    )
    return process_response_from_openai(response)

# function to interact with Claude
async def chat_with_claude(messages, model='claude-3-haiku-20240307', temperature=0.5, max_tokens=100, system="") -> str:
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

# function to interact with openai's dalle
async def image_gen_with_openai(prompt, model='dall-e-3',n=1, size="1024x1024") -> str:
    response = openai.images.generate(
        model=model,
        prompt=prompt,
        n=n,
        size=size
    )
    # Download the file and convert to base64
    image_url = response.data[0].url
    # DEBUG PLACEHOLDER URL
    # image_url = "https://www.gstatic.com/webp/gallery/1.jpg"
    # if response.data:
    if image_url:
        # image_url = response.data[0].url
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    image_data = await resp.read()
                    image = Image.open(BytesIO(image_data))
                    buffered = BytesIO()
                    image.save(buffered, format="jpeg")
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    return img_str
                else:
                    print(f"Failed to download image: HTTP {resp.status}")
                    return None
    else:
        print("No image data in the response")
        return None

# Function to get the available models
def get_available_openai_models() -> list:
    response = openai.models.list()
    available_models = []
    for model in response.data:
        available_models.append(model.id)
    # Filter for only those containing GPT and sorted
    available_models = sorted([model for model in available_models if 'gpt' in model])
    return available_models

def get_available_claude_models() -> list:
    available_models = ANTHROPIC_MODELS
    return available_models

def get_available_gemini_models() -> list:
    response = gemini.list_models()
    available_models = []
    for model in response:
        available_models.append(model.name.split('/')[-1])
    # Filter for only those containing gemini and sorted
    available_models = sorted([model for model in available_models if 'gemini' and '1.5' in model])
    return available_models

def process_response_for_telegram_style(response) -> str:
    # Ensures response is in the MarkdownV2 format that Telegram has required while maintaining formatting, not just escaping everything
    response = response.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!') # .replace('_', '\\_').replace('*', '\\*').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('|', '\\|')
    return response

def process_response_from_openai(response) -> tuple:
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    role = response.choices[0].message.role.strip()
    message = response.choices[0].message.content.strip()
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')

    return input_tokens, output_tokens, role, message

def process_response_from_claude(response) -> tuple:
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    role = response.role
    message = response.content[0].text
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')

    return input_tokens, output_tokens, role, message