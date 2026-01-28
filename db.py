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
