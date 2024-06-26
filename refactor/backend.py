# Importing required libraries
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Create an instance of the OpenAI API
openai = OpenAI()

# Define to interact with OpenAI GPT
def chat_with_gpt(messages, model='gpt-4o', temperature=0.5, max_tokens=100, n=1, stop=None):
    response = openai.chat.completions.create(
        model=model,  # Specify the GPT-4 engine
        messages=messages,
        max_tokens=max_tokens,  # Set the maximum number of tokens in the response
        temperature=temperature,  # Control the randomness of the response
        n=n,  # Generate a single response
        top_p= 0.4,  # Control the diversity of the response 
        frequency_penalty=0,  # Control the diversity of the response
        presence_penalty=0,  # Control the diversity of the response
        stop=stop,  # Specify a custom stop sequence if needed
    )
    return response.choices[0].message.content.strip()

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
def get_available_models():
    response = openai.models.list()
    available_models = []
    for model in response.data:
        available_models.append(model.id)
    # Filter for only those containing GPT and sorted
    available_models = sorted([model for model in available_models if 'gpt' in model])
    return available_models

def process_response_for_telegram_style(response):
    # Ensures response is in the MarkdownV2 format that Telegram has required while maintaining formatting, not just escaping everything
    response = response.replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!') # .replace('_', '\\_').replace('*', '\\*').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('|', '\\|')
    return response
