import os
import re
import logging
from google.generativeai.types import HarmBlockThreshold, HarmCategory
import google.generativeai as gemini

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Google API credentials
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Create an instance of the Gemini API
gemini.configure(api_key=GEMINI_API_KEY)

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

def get_available_gemini_models() -> list:
    response = gemini.list_models()
    available_models = []
    for model in response:
        available_models.append(model.name.split('/')[-1])
    # Filter for only those containing gemini and sorted
    available_models = sorted([model for model in available_models if 'gemini' and '1.5' in model])
    return available_models

def process_response_from_gemini(response) -> tuple:
    input_tokens = response.usage_metadata.prompt_token_count
    output_tokens = response.usage_metadata.candidates_token_count
    role = "assistant" if response.candidates[0].content.role == "model" else response.candidates[0].content.role
    message = response.text
    # To manage the case where GPT still outputs unwanted tags that 
    # may cause telegram to fail to format the message properly
    message = re.sub(r'<(a|article|p|br|li|sup|sub|abbr|small|ul|/a|/article|/p|/li|/sup|/sub|/abbr|/small|/ul)>', '', message)
    message = message.replace('<h1>', '<b><u>').replace('</h1>', '</u></b>').replace('<h2>', '<b>').replace('</h2>', '</b>').replace('<h3>', '<u>').replace('</h3>', '</u>').replace('<h4>', '<i>').replace('</h4>', '</i>').replace('<h5>', '').replace('</h5>', '').replace('<h6>', '').replace('</h6>', '').replace('<big>', '<b>').replace('</big>', '</b>')
    return input_tokens, output_tokens, role, message