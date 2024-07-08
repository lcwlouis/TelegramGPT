# TeleGPT
A Gen AI bot for use on Telegram. No reason for it to exist besides the fact that I wanted to build it :D You could just use OpenAI's chatgpt.com instead xD

# What is this?
This is a simple telegram bot that allows an verified user id to access GPT or Claude or Gemini. It uses API of OpenAI only as of now. It allows the user to choose the model that they want to access with as well as the temperature and max tokens. It also allows the user to access the Gemini model.


## To Do List
- Add embeddings
- Add more types of photos handling
- Add search functionality

## How to use
1. Clone the repository
2. Install the requirements
3. Create a .env file with the following
```
ENVIRONMENT=DEV
TELEGRAM_BOT_TOKEN_DEV=YOUR_TELEGRAM_BOT_TOKEN_FOR_DEV_TESTING // You can modify the code in main for this portion to remove this
TELEGRAM_BOT_TOKEN_PROD=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_WHITELISTED_IDS=TELEGRAM IDS // Separated by comma eg. 123456789,987654321
TELEGRAM_ADMIN_ID=YOUR_TELEGRAM_ADMIN_ID // This only takes one id
TELEGRAM_ERROR_CHAT_ID=TELEGRAM_CHAT_ID // This only takes one id and will require you to add the bot to a group chat for it to report
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
CLAUDE_API_KEY=YOUR_ANTHROPIC_API_KEY
GEMINI_API_KEY=YOUR_GOOGLE_GEMINI_API_KEY
OLLAMA_URL=YOUR_OLLAMA_URL
DB_DIR=data // You can choose your own directory to store your data
PROMPT_DIR=prompts // You can choose your own directory to store your prompts
```
4. Create a folder in root "/prompts" and store your prompts in system_prompt.txt and title_system_prompt.txt
5. Run the bot using `pymon main.py`
