from openai import AsyncOpenAI
import logging
from config import NANOGPT_API_KEY
from db import supabase
from collections import defaultdict

client = AsyncOpenAI(
    api_key=NANOGPT_API_KEY,
    base_url='https://nano-gpt.com/api/v1',
)

# Cache for AI config
_ai_config_cache = {}

import time

# In-memory chat history for context
# Structure: {chat_id: {"messages": [], "session_start": 0}}
_chat_history = defaultdict(lambda: {"messages": [], "session_start": 0})
MAX_HISTORY_LENGTH = 5  # Keep last 5 messages per chat
MEMORY_EXPIRATION_SECONDS = 6 * 3600  # 6 hours

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

def get_chat_history(chat_id: int) -> list:
    """Get chat history for context, with expiration check from session start."""
    history_data = _chat_history[chat_id]
    
    # Check for expiration from the START of the session
    if history_data["messages"] and (time.time() - history_data["session_start"] > MEMORY_EXPIRATION_SECONDS):
        logging.info(f"⏳ Chat history session expired for chat {chat_id} (6 hours passed since start)")
        clear_chat_history(chat_id)
        return []
        
    return history_data["messages"]

def add_to_history(chat_id: int, role: str, content: str):
    """Add message to chat history. Starts session timer on first message."""
    current_time = time.time()
    history_data = _chat_history[chat_id]
    
    # If starting a new session (no messages or expired)
    if not history_data["messages"] or (current_time - history_data["session_start"] > MEMORY_EXPIRATION_SECONDS):
        history_data["messages"] = []
        history_data["session_start"] = current_time
        logging.info(f"🆕 Started new 6-hour AI session for chat {chat_id}")

    history_data["messages"].append({"role": role, "content": content})
    
    # Trim to max length
    if len(history_data["messages"]) > MAX_HISTORY_LENGTH:
        history_data["messages"] = history_data["messages"][-MAX_HISTORY_LENGTH:]

def clear_chat_history(chat_id: int):
    """Clear chat history for a specific chat."""
    _chat_history[chat_id] = {"messages": [], "session_start": 0}
    logging.info(f"🗑 Chat history cleared for chat {chat_id}")

async def get_ai_response(system_prompt: str, user_message: str, model: str = None, chat_id: int = None) -> str:
    """
    Generates a response using NanoGPT with optional context memory.
    
    Args:
        system_prompt: System prompt for AI
        user_message: User message to respond to
        model: Optional custom model name. If None or 'default', uses app_config.ai_model
        chat_id: Optional chat ID for context memory. If provided, uses conversation history.
    """
    try:
        # Use custom model or fallback to app_config
        if model and model.lower() != 'default':
            used_model = model
        else:
            used_model = get_ai_config('ai_model', 'gpt-4o-mini')
        
        temperature = float(get_ai_config('ai_temperature', '0.7'))
        
        # Build messages with context
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history if chat_id provided
        if chat_id:
            history = get_chat_history(chat_id)
            messages.extend(history)
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        logging.info(f"🤖 AI Request [Model: {used_model}, Temp: {temperature}, History: {len(messages)-2}]:\nUser: {user_message}")
        completion = await client.chat.completions.create(
            model=used_model,
            temperature=temperature,
            messages=messages,
        )
        response_content = completion.choices[0].message.content
        logging.info(f"🤖 AI Response:\n{response_content}")
        
        # Save to history if chat_id provided
        if chat_id:
            add_to_history(chat_id, "user", user_message)
            add_to_history(chat_id, "assistant", response_content)
        
        return response_content
    except Exception as e:
        logging.error(f"NanoGPT Error: {e}")
        return "Sorry, I am having trouble thinking right now."
