from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

# Set up your OpenAI API credentials
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Create an instance of the OpenAI API
openai = OpenAI()

# Define a function to interact with the chatbot
def chat_with_gpt(messages, model='gpt-4-0125-preview', temperature=0.8, max_tokens=100, n=1, stop=None):
    response = openai.chat.completions.create(
        model=model,  # Specify the GPT-4 engine
        messages=messages,
        max_tokens=max_tokens,  # Set the maximum number of tokens in the response
        temperature=temperature,  # Control the randomness of the response
        n=n,  # Generate a single response
        stop=stop,  # Specify a custom stop sequence if needed
    )
    return response.choices[0].message.content.strip()

# Get list of GPT models available
def get_models():
    # SyncPage[Model](data=[Model(id='gpt-4-vision-preview', created=1698894917, object='model', owned_by='system'), Model(id='dall-e-3', created=1698785189, object='model', owned_by='system'), Model(id='gpt-3.5-turbo-0613', created=1686587434, object='model', owned_by='openai'), Model(id='text-embedding-3-large', created=1705953180, object='model', owned_by='system'), Model(id='gpt-3.5-turbo-instruct-0914', created=1694122472, object='model', owned_by='system'), Model(id='dall-e-2', created=1698798177, object='model', owned_by='system'), Model(id='whisper-1', created=1677532384, object='model', owned_by='openai-internal'), Model(id='babbage-002', created=1692634615, object='model', owned_by='system'), Model(id='text-embedding-ada-002', created=1671217299, object='model', owned_by='openai-internal'), Model(id='gpt-3.5-turbo-0125', created=1706048358, object='model', owned_by='system'), Model(id='gpt-3.5-turbo', created=1677610602, object='model', owned_by='openai'), Model(id='text-embedding-3-small', created=1705948997, object='model', owned_by='system'), Model(id='gpt-3.5-turbo-0301', created=1677649963, object='model', owned_by='openai'), Model(id='gpt-3.5-turbo-16k', created=1683758102, object='model', owned_by='openai-internal'), Model(id='gpt-3.5-turbo-instruct', created=1692901427, object='model', owned_by='system'), Model(id='tts-1', created=1681940951, object='model', owned_by='openai-internal'), Model(id='tts-1-1106', created=1699053241, object='model', owned_by='system'), Model(id='gpt-4-0125-preview', created=1706037612, object='model', owned_by='system'), Model(id='gpt-3.5-turbo-1106', created=1698959748, object='model', owned_by='system'), Model(id='tts-1-hd', created=1699046015, object='model', owned_by='system'), Model(id='gpt-4', created=1687882411, object='model', owned_by='openai'), Model(id='tts-1-hd-1106', created=1699053533, object='model', owned_by='system'), Model(id='gpt-4-turbo-preview', created=1706037777, object='model', owned_by='system'), Model(id='gpt-4-0613', created=1686588896, object='model', owned_by='openai'), Model(id='gpt-3.5-turbo-16k-0613', created=1685474247, object='model', owned_by='openai'), Model(id='gpt-4-1106-preview', created=1698957206, object='model', owned_by='system'), Model(id='davinci-002', created=1692634301, object='model', owned_by='system')], object='list')
    # retrieve the model id
    response = openai.models.list()
    available_models = []
    for model in response.data:
        available_models.append(model.id)
    return available_models

# Function for generating a response using Dall E
# def generate_dalle_response(prompt):
#     response = openai.Completion.create(
#         engine='dalle-003',  # Specify the DALL-E engine
#         prompt=prompt,
#         max_tokens=100,  # Set the maximum number of tokens in the response
#         temperature=0.8,  # Control the randomness of the response
#         n=1,  # Generate a single response
#         stop=None  # Specify a custom stop sequence if needed
#     )
#     return response

# message=[
#         {"role": "system", "content": "You are a personal assistant. Particularly helping students in University with their questions regard their majors and their events. Answer as logically as possible to help them."}
#     ]
# message.append({"role": "user", "content": "What is BCNF in databases?"})
# response = chat_with_gpt(message)
# message.append({"role": "system", "content": response})
# print(response)
# print(message)

# Function to handle input (for text generation) from the user
def handle_input_text(user_message, model, temperature, max_tokens, n, stop, chat_history=[]):
    # Handle if chat history is empty
    # if len(chat_history) == 0:
    #     chat_history = [
    #         {"role": "system", "content": "You are a personal assistant. Particularly helping students in University with their questions regard their majors and their events. Answer as logically as possible to help them."}
    #     ]
    #     
    # # Get the user's message
    # user_message = user_message
    
    # add message into chat history
    chat_history.append({"role": "user", "content": user_message})

    # Generate a response using GPT-4
    response = chat_with_gpt(chat_history, model=model, temperature=temperature, max_tokens=max_tokens, n=n, stop=stop)
    
    # chat_history.append({"role": "system", "content": response})

    # Return the response
    return response


# Example usage
# chat_history = []
# user_input = input("You: ")
# while user_input.lower() != 'bye':
#     chat_history.append("User: " + user_input)
#     response = chat_with_gpt("\n".join(chat_history), chat_history)
#     print("AI:", response)
#     chat_history.append("AI: " + response)
#     user_input = input("You: ")
