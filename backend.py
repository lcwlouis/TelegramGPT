# Importing required libraries
import re
import sqlite3
import os
import base64
import aiohttp
import requests
import google.generativeai as gemini
from io import BytesIO
from PIL import Image
from typing import Final
from anthropic import AsyncAnthropic
from openai import OpenAI
from google.generativeai.types import HarmBlockThreshold, HarmCategory
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
    'llava-llama3:latest',
]

# Set up system prompt
DEFAULT_SYSTEM_PROMPT = open('./system_prompt.txt', 'r').read()
# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Set up Claude API credentials
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')

# Set up Google API credentials
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Set up url to Ollama API
OLLAMA_URL = os.getenv('OLLAMA_URL')

# Create an instance of the OpenAI API
openai = OpenAI()

# Create an instance of the Anthropic API
anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)

# Create an instance of the Gemini API
gemini.configure(api_key=GEMINI_API_KEY)


DB_DIR = os.getenv('DB_DIR')
DB_FILE = 'chats.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

os.makedirs(DB_DIR, exist_ok=True)

# Initialize sqlite database to store and retrieve the chat history
conn_chats = sqlite3.connect(DB_PATH)

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
    # Claude enforces that assistant must alternate with user
    messages = []
    prev_message_type = ""
    image = None
    for message_type, message, role in chat_history:
        if role == 'system':
            continue
        if len(messages) > 1 and messages[-1].get('role') == 'user' and role == 'user':
            messages.append( {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Ignore this message"}
                ]
            })
        elif len(messages) > 1 and messages[-1].get('role') == 'assistant' and role == 'assistant':
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
            # if len(messages) > 1 and messages[-1].get('role') == 'user' and role == 'user':
            #     messages.append( {
            #     "role": "assistant",
            #     "content": [
            #         {"type": "text", "text": "Blank"}
            #         ]
            #     })
            # elif len(messages) > 1 and messages[-1].get('role') == 'assistant' and role == 'assistant':
            #     messages.append( {
            #     "role": "user",
            #     "content": [
            #         {"type": "text", "text": "Blank"}
            #         ]
            #     })
            # else:
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

def build_message_list_gemini(chat_history) -> list:
    messages = []
    length_of_history = len(chat_history)
    for i in range(length_of_history):
        if i == 0 or i == length_of_history:
            continue
        message_type, message, role = chat_history[i]
        if role == 'assistant':
            role = "model"
        if message_type == 'text':
            messages.append({
            "role": role, 
            "parts": [
                f"{message}", 
                ]
            })
        elif message_type == 'image_url':
            messages.append({
            "role": role, 
            "parts": [
                f"Image was skipped due to technical limitation", 
                ]
            })
    return messages

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

# Define to interact with OpenAI GPT
async def chat_with_gpt(messages, model='gpt-3.5-turbo', temperature=0.5, max_tokens=100, n=1) -> str:
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

# function to interact with Gemini
async def chat_with_gemini(input_message, model='gemini-1.5-flash', temperature=0.5, max_tokens=100, message_history=[], system="") -> str:
    generation_config = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": max_tokens,
        "response_mime_type": "text/plain",
    }
    safety_settings = {
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    }
    model = gemini.GenerativeModel(
        model_name=model,
        generation_config=generation_config,
        safety_settings=safety_settings,
        system_instruction=system,
    )
    response = await model.generate_content_async(input_message)
    # chat_session = model.start_chat(history=message_history)
    # response = await chat_session.send_message_async(input_message)
    return process_response_from_gemini(response)

# function to interact with Ollama
async def chat_with_ollama(messages, model, temperature=0.5, max_tokens=100) -> str:
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


# function to interact with openai's dalle
async def image_gen_with_openai(prompt, model='dall-e-3',n=1, size="1024x1024") -> str:
    # response = openai.images.generate(
    #     model=model,
    #     prompt=prompt,
    #     n=n,
    #     size=size
    # )
    # Download the file and convert to base64
    # image_url = response.data[0].url
    
    image_url = "https://www.gstatic.com/webp/gallery/1.jpg" # DEBUG PLACEHOLDER URL

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

def get_available_ollama_models() -> list:
    # Get this via POST request
    available_models = []
    res = requests.get(f'{OLLAMA_URL}/api/tags')
    if res.status_code == 200:
        data = res.json().get('models', [])
        available_models = [data[i]['name'] for i in range(len(data)) if 'embed' not in data[i]['name']]
        available_models = sorted(available_models)
    return available_models

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

def process_response_from_gemini(response) -> tuple:
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    role = "assistant" if response.candidates[0].content.role == "model" else response.candidates[0].content.role
    message = response.text
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message

def process_response_from_ollama(response) -> tuple:
    input_tokens = response.get('prompt_eval_count')
    output_tokens = response.get('eval_count')
    role = response.get('message').get('role')
    message = response.get('message').get('content')
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message