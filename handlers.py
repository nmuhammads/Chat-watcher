from aiogram import Router, F, types
from aiogram.filters import Command
from db import get_all_triggers
from utils import check_message_for_triggers, CooldownManager

router = Router()
cooldown_manager = CooldownManager()
TRIGGERS_CACHE = []

async def refresh_triggers():
    global TRIGGERS_CACHE
    TRIGGERS_CACHE = await get_all_triggers()
    print(f"Loaded {len(TRIGGERS_CACHE)} triggers.")

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    from config import ADMIN_ID
    if not ADMIN_ID:
        return False
    return str(user_id) == str(ADMIN_ID)

@router.message(Command("start"))
async def start_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("Bot is running! I am watching the chat.")
    if not TRIGGERS_CACHE:
        await refresh_triggers()

@router.message(Command("reload"))
async def reload_handler(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied. Admin only.")
        return
    
    await refresh_triggers()
    await message.answer("Triggers reloaded from database.")

@router.message(Command("chatid"))
async def chatid_handler(message: types.Message):
    """Returns the current chat ID for trigger configuration. Available to all users."""
    chat_id = message.chat.id
    chat_title = message.chat.title or "Private Chat"
    await message.answer(
        f"📍 **Chat Info**\n"
        f"**Title:** {chat_title}\n"
        f"**Chat ID:** `{chat_id}`\n\n"
        f"_Use this ID in Supabase to create chat-specific triggers._",
        parse_mode="Markdown"
    )

from ai_client import get_ai_response

# ... imports ...

@router.message()
async def message_handler(message: types.Message):
    # Skip trigger processing in private chats (only work in groups/channels)
    if message.chat.type == 'private':
        return
    
    if not TRIGGERS_CACHE:
        await refresh_triggers()
        
    text = message.text or message.caption or ""
    if not text:
        return

    trigger = check_message_for_triggers(text, TRIGGERS_CACHE, chat_id=message.chat.id)
    
    if trigger:
        chat_id = message.chat.id
        trigger_id = trigger['id']
        cooldown = trigger.get('cooldown', 60)
        
        # Use message date for strict cooldown (avoids lag issues)
        msg_date = message.date.timestamp()

        if cooldown_manager.can_trigger(chat_id, trigger_id, cooldown, timestamp=msg_date):
            response_text = trigger['response']
            resp_type = trigger.get('type', 'text')
            
            try:
                if resp_type == 'ai':
                    # For AI, response_text acts as the system prompt
                    response_text = await get_ai_response(
                        system_prompt=response_text,
                        user_message=text
                    )
                    await message.reply(response_text, parse_mode="Markdown")
                elif resp_type == 'sticker':
                    await message.reply_sticker(response_text)
                elif resp_type == 'photo':
                     await message.reply_photo(response_text)
                else:
                    # Text triggers with Markdown support
                    await message.reply(response_text, parse_mode="Markdown")
                
                cooldown_manager.mark_triggered(chat_id, trigger_id, timestamp=msg_date)

                # Admin Notification
                from config import ADMIN_ID
                if ADMIN_ID:
                    chat_title = message.chat.title or "Private Chat"
                    user = message.from_user.full_name or "Unknown"
                    username = message.from_user.username or "NoUsername"
                    
                    # Try to build a message link
                    msg_link = "No link available"
                    if message.chat.username:
                        msg_link = f"https://t.me/{message.chat.username}/{message.message_id}"
                    elif message.chat.id < 0:
                        # Private group IDs start with -100, remove it for link
                        cid = str(message.chat.id).replace("-100", "")
                        msg_link = f"https://t.me/c/{cid}/{message.message_id}"

                    notification_text = (
                        f"🔔 **Trigger Used!**\n"
                        f"👤 **User:** {user} (@{username})\n"
                        f"📍 **Chat:** {chat_title}\n"
                        f"🔗 **Link:** [Message]({msg_link})\n"
                        f"📝 **Trigger:** `{text[:50]}...`" # Show snippet of triggered text
                    )
                    try:
                        await message.bot.send_message(chat_id=ADMIN_ID, text=notification_text, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Failed to notify admin: {e}")
            except Exception as e:
                print(f"Failed to send response: {e}")
