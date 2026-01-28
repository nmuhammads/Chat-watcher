import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
NANOGPT_API_KEY = os.getenv("NANOGPT_API_KEY")
NANOGPT_MODEL = os.getenv("NANOGPT_MODEL", "gpt-4o-mini")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in environment variables")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE connection details are missing")
if not NANOGPT_API_KEY:
    print("WARNING: NANOGPT_API_KEY is not set. AI features will fail.")

ADMIN_ID = os.getenv("ADMIN_ID")
if not ADMIN_ID:
    print("WARNING: ADMIN_ID is not set. Admin notifications will not be sent.")
