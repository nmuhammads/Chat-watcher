from openai import AsyncOpenAI
import logging
from config import NANOGPT_API_KEY
from db import supabase

client = AsyncOpenAI(
    api_key=NANOGPT_API_KEY,
    base_url='https://nano-gpt.com/api/v1',
)

# Cache for AI config
_ai_config_cache = {}

def get_ai_config(key: str, default: str = None) -> str:
    """
    Get AI config value from database.
    Caches values to avoid repeated DB calls.
    Use refresh_ai_config() to reload from DB.
    """
    if key in _ai_config_cache:
        return _ai_config_cache[key]
    
    try:
        response = supabase.table("app_config").select("value").eq("key", key).single().execute()
        if response.data:
            _ai_config_cache[key] = response.data['value']
            return _ai_config_cache[key]
    except Exception as e:
        logging.warning(f"Failed to get AI config '{key}': {e}")
    
    return default

def refresh_ai_config():
    """Reload AI config from database."""
    global _ai_config_cache
    _ai_config_cache = {}
    try:
        response = supabase.table("app_config").select("*").execute()
        for item in response.data:
            _ai_config_cache[item['key']] = item['value']
        logging.info(f"🔄 AI config reloaded: {list(_ai_config_cache.keys())}")
    except Exception as e:
        logging.error(f"Failed to refresh AI config: {e}")

async def get_ai_response(system_prompt: str, user_message: str) -> str:
    """
    Generates a response using NanoGPT.
    Model and temperature are fetched from app_config table.
    """
    try:
        model = get_ai_config('ai_model', 'gpt-4o-mini')
        temperature = float(get_ai_config('ai_temperature', '0.7'))
        
        logging.info(f"🤖 AI Request [Model: {model}, Temp: {temperature}]:\nUser: {user_message}")
        completion = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        response_content = completion.choices[0].message.content
        logging.info(f"🤖 AI Response:\n{response_content}")
        return response_content
    except Exception as e:
        logging.error(f"NanoGPT Error: {e}")
        return "Sorry, I am having trouble thinking right now."
