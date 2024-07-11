# TeleGPT: A Versatile Telegram-based AI Assistant

TeleGPT is a Telegram bot that provides users with access to powerful language models, including GPT, Claude, Gemini, and Ollama. This project allows users to interact with these AI models directly through Telegram, enabling a wide range of conversational and creative capabilities.

## Features

- **Multi-Model Access**: Users can seamlessly switch between different language models, including GPT, Claude, Gemini, and Ollama.
- **Chat Completion**: Engage in natural language conversations and receive intelligent responses from the AI models.
- **Vision Capabilities**: Utilize applicable models to process and analyze images.
- **Customizable Prompts and Settings**: Tailor the bot's behavior by adjusting prompts, temperature, max tokens, and other settings.
- **Image Generation**: Generate unique images based on user prompts.
- **Chat History and Pagination**: Keep track of conversation history and navigate through chat pages.

## Roadmap

- Implement a `/long` command to handle multi-message prompts
- Automatically filter the keyboard to show only available models and providers
- Add support for embeddings
- Enhance photo handling capabilities
- Implement search functionality

## Installation and Setup

1. Clone the repository
2. Install the required dependencies: `pip install -r requirements.txt`
3. Create a `.env` file in the project root and populate it with the necessary environment variables:

   ```
   # Environment
   ENVIRONMENT=DEV

   # Telegram Bot
   TELEGRAM_BOT_TOKEN_DEV=YOUR_TELEGRAM_BOT_TOKEN_FOR_DEV_TESTING
   TELEGRAM_BOT_TOKEN_PROD=YOUR_TELEGRAM_BOT_TOKEN
   TELEGRAM_WHITELISTED_IDS=123456789,987654321
   TELEGRAM_ADMIN_ID=YOUR_TELEGRAM_ADMIN_ID
   TELEGRAM_ERROR_CHAT_ID=TELEGRAM_CHAT_ID

   # API Keys
   OPENAI_API_KEY=YOUR_OPENAI_API_KEY
   CLAUDE_API_KEY=YOUR_ANTHROPIC_API_KEY
   GEMINI_API_KEY=YOUR_GOOGLE_GEMINI_API_KEY
   OLLAMA_URL=YOUR_OLLAMA_URL

   # Directories
   DB_DIR=data
   PROMPT_DIR=prompts
   ```


4. Create a folder in the project root called `/prompts` and store your custom prompts in `system_prompt.txt` and `title_system_prompt.txt`.
5. Run the bot using `python main.py`.

## Technologies Used

TeleGPT is built using a variety of technologies, including:
- [Python Telegram Bot Framework](https://github.com/python-telegram-bot/python-telegram-bot)
- [Python](https://www.python.org)
- [Docker](https://www.docker.com)
- [SQLite](https://www.sqlite.org)
- [OpenAI](https://openai.com)
- [Anthropic](https://anthropic.com)
- [Google Gemini](https://deepmind.google/technologies/gemini/)
- [Ollama](https://ollama.com/)


<!-- ## Contributing

We welcome contributions from the community! If you'd like to report issues, suggest features, or submit pull requests, please follow the guidelines outlined in the [CONTRIBUTING.md](CONTRIBUTING.md) file. -->
