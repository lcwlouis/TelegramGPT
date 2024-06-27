# TeleGPT
A Gen AI bot for use on Telegram. No reason for it to exist besides the fact that I wanted to build it :D You could just use OpenAI's chatgpt.com instead xD

# What is this?
This is a simple telegram bot that allows an verified user id to access GPT or Claude or Gemini. It uses API of OpenAI only as of now. It allows the user to choose the model that they want to access with as well as the temperature and max tokens. It also allows the user to access the Gemini model.


## To Do List
- Add access to Gemini by Google
- Add access to Claude by Anthropic
- Add embeddings

## How to use
1. Clone the repository
2. Install the requirements
3. Create a .env file with the following
```
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TELEGRAM_WHITELISTED_IDS=YOUR_TELEGRAM
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
CLAUDE_API_KEY=YOUR_ANTHROPIC_API_KEY
GEMINI_API_KEY=YOUR_GOOGLE_GEMINI_API_KEY
TELEGRAM_BOT_USERNAME=YOUR_TELEGRAM_BOT_USERNAME
```
4. Create a system_prompt.txt in the root folder of this program and save your system prompt in it.
5. Run the bot using `pymon main.py`
