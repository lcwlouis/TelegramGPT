import os
import re
import aiohttp
import base64
import logging
import telegramify_markdown as tm
from io import BytesIO
from PIL import Image
from openai import OpenAI
from helpers.dateHelper import get_current_date, get_current_weekday
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(override=True)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Create an instance of the OpenAI API
openai = OpenAI()

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
    
    # image_url = "https://www.gstatic.com/webp/gallery/1.jpg" # DEBUG PLACEHOLDER URL

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

def process_response_from_openai(response) -> tuple:
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    role = response.choices[0].message.role.strip()
    message = tm.markdownify(
        response.choices[0].message.content.strip(),
        max_line_length=None,
        normalize_whitespace=False,
    )
    # To manage the case where GPT still outputs unwanted tags that 
    # may cause telegram to fail to format the message properly
    # message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    # message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message