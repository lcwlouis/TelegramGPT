# Importing required libraries
import sqlite3
import os
import base64
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
    cur_list.append({
        "role": role, 
        "content": [
            {"type": message_type, "text": message}
            ]
        })
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
    # return response.choices[0].message.content.strip()
    print("GPT: " + response)
    return response

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

# Function to handle input (for text generation) from the user
def handle_input_text(user_message, model, temperature, max_tokens, n, stop, chat_history=[]):
    # add message into chat history
    chat_history.append({"role": "user", "content": user_message})

    # Generate a response using GPT-4
    response = chat_with_gpt(chat_history, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)
    
    chat_history.append({"role": "system", "content": response})
    
    # Process response for Telegram style
    response = process_response_for_telegram_style(response)

    # Return the response
    return response


# Function to get the available models
def get_available_openai_models():
    response = openai.models.list()
    available_models = []
    for model in response.data:
        available_models.append(model.id)
    # Filter for only those containing GPT and sorted
    available_models = sorted([model for model in available_models if 'gpt' in model])
    return available_models

def get_available_claude_models():
    available_models = ANTHROPIC_MODELS
    return available_models

def process_response_for_telegram_style(response):
    # Ensures response is in the MarkdownV2 format that Telegram has required while maintaining formatting, not just escaping everything
    response = response.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!') # .replace('_', '\\_').replace('*', '\\*').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('|', '\\|')
    return response
