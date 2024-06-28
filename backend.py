# Importing required libraries
import re
import sqlite3
import os
import base64
import aiohttp
from io import BytesIO
from PIL import Image
from typing import Final
from anthropic import AsyncAnthropic
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Since there is no API endpoint to check for available models, this is to be manually updated
ANTHROPIC_MODELS: Final = [
    'claude-3-haiku-20240307',
    'claude-3-sonnet-20240229',
    'claude-3-opus-20240229',
    'claude-3-5-sonnet-20240620',
]

# Set up system prompt
DEFAULT_SYSTEM_PROMPT = open('./system_prompt.txt', 'r').read()
# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set up Claude API credentials
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Create an instance of the OpenAI API
openai = OpenAI()

# Create an instance of the Anthropic API
anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect('chats.db')

c = conn_chats.cursor()

# Message List Builder
def build_message_list(message_type, message, role, cur_list=[]) -> list:
    if message_type == 'text':
        cur_list.append({
        "role": role, 
        "content": [
            {"type": message_type, f"{message_type}": message}
            ]
        })
    # TODO to implement image history 
    return cur_list

# Define to interact with OpenAI GPT
def chat_with_gpt(messages, model='gpt-3.5-turbo', temperature=0.5, max_tokens=100, n=1) -> str:
    response = openai.chat.completions.create(
        model=model,  # Specify the GPT-4 engine
        messages=messages,
        max_tokens=max_tokens,  # Set the maximum number of tokens in the response
        temperature=temperature,  # Control the randomness of the response
        n=n,  # Generate a single response
    )
    return process_response_from_openai(response)

# function to interact with Claude
def chat_with_claude(messages, model='claude-3-haiku-20240307', temperature=0.5, max_tokens=100, system="") -> str:
    response = anthropic.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages
    )
    print("Claude: " + response)
    return response

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
