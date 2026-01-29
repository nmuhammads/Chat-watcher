from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def get_all_triggers():
    """Fetches all triggers from Supabase."""
    try:
        response = supabase.table("triggers").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error fetching triggers: {e}")
        return []

def save_chat_photo(chat_id: int, user_id: int, message_id: int, photo_data: dict, caption: str = None):
    """
    Saves photo information to the database.
    
    Args:
        chat_id: Telegram chat ID
        user_id: Telegram user ID
        message_id: Telegram message ID
        photo_data: Dict with file_id, file_unique_id, width, height, file_size
        caption: Optional caption text
    """
    try:
        data = {
            "chat_id": chat_id,
            "user_id": user_id,
            "message_id": message_id,
            "file_id": photo_data.get("file_id"),
            "file_unique_id": photo_data.get("file_unique_id"),
            "file_size": photo_data.get("file_size"),
            "width": photo_data.get("width"),
            "height": photo_data.get("height"),
            "caption": caption
        }
        response = supabase.table("chat_photos").insert(data).execute()
        print(f"📸 Photo saved: chat={chat_id}, user={user_id}")
        return response.data
    except Exception as e:
        print(f"Error saving photo: {e}")
        return None
