from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# Get API keys from the environment
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY') or os.getenv('openai.api_key')
