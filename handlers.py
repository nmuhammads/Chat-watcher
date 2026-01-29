from aiogram import Router, F, types
from aiogram.filters import Command
from db import get_all_triggers, save_chat_photo
from utils import check_message_for_triggers, CooldownManager
from ai_client import get_ai_response, refresh_ai_config, get_ai_config

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

@router.message(Command("reloadai"))
async def reloadai_handler(message: types.Message):
    """Reloads AI configuration from database. Admin only."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied. Admin only.")
        return
    
    refresh_ai_config()
    model = get_ai_config('ai_model', 'gpt-4o-mini')
    temp = get_ai_config('ai_temperature', '0.7')
    await message.answer(f"🔄 AI config reloaded!\n\n📊 **Current settings:**\n• Model: `{model}`\n• Temperature: `{temp}`", parse_mode="Markdown")

@router.message(Command("aiconfig"))
async def aiconfig_handler(message: types.Message):
    """Shows current AI configuration. Admin only."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Access denied. Admin only.")
        return
    
    model = get_ai_config('ai_model', 'gpt-4o-mini')
    temp = get_ai_config('ai_temperature', '0.7')
    await message.answer(
        f"🤖 <b>AI Configuration</b>\n\n"
        f"• <b>Model:</b> <code>{model}</code>\n"
        f"• <b>Temperature:</b> <code>{temp}</code>\n\n"
        f"<i>Change in Supabase → app_config, then /reloadai</i>",
        parse_mode="HTML"
    )

@router.message(F.photo)
async def photo_handler(message: types.Message):
    """Saves photos sent directly to the bot and forwards to admin."""
    from config import ADMIN_ID
    
    # Check if we should save this photo:
    # 1. Private chat (direct message to bot)
    # 2. Reply to bot's message
    # 3. Bot mentioned in caption
    
    is_private = message.chat.type == 'private'
    
    is_reply_to_bot = False
    if message.reply_to_message and message.reply_to_message.from_user:
        is_reply_to_bot = message.reply_to_message.from_user.id == message.bot.id
    
    is_bot_mentioned = False
    bot_info = await message.bot.get_me()
    bot_username = f"@{bot_info.username}".lower() if bot_info.username else None
    if bot_username and message.caption:
        is_bot_mentioned = bot_username in message.caption.lower()
    
    # Skip if none of the conditions are met
    if not (is_private or is_reply_to_bot or is_bot_mentioned):
        return
    
    # Get the largest photo (last in the array)
    photo = message.photo[-1]
    
    photo_data = {
        "file_id": photo.file_id,
        "file_unique_id": photo.file_unique_id,
        "file_size": photo.file_size,
        "width": photo.width,
        "height": photo.height
    }
    
    save_chat_photo(
        chat_id=message.chat.id,
        user_id=message.from_user.id,
        message_id=message.message_id,
        photo_data=photo_data,
        caption=message.caption
    )
    
    # Forward photo to admin
    if ADMIN_ID:
        try:
            user = message.from_user
            chat_title = message.chat.title or "Private Chat"
            username = f"@{user.username}" if user.username else "No username"
            
            # Build message link
            msg_link = "No link"
            if message.chat.username:
                msg_link = f"https://t.me/{message.chat.username}/{message.message_id}"
            elif message.chat.id < 0:
                cid = str(message.chat.id).replace("-100", "")
                msg_link = f"https://t.me/c/{cid}/{message.message_id}"
            
            # Indicate why photo was captured
            reason = "📩 Direct" if is_private else ("↩️ Reply" if is_reply_to_bot else "📣 Mention")
            
            info_text = (
                f"📸 <b>New Photo</b> ({reason})\n\n"
                f"👤 <b>From:</b> {user.full_name} ({username})\n"
                f"💬 <b>Chat:</b> {chat_title}\n"
                f"🔗 <a href=\"{msg_link}\">View message</a>"
            )
            
            if message.caption:
                info_text += f"\n📝 <b>Caption:</b> {message.caption[:100]}"
            
            await message.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo.file_id,
                caption=info_text,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Failed to forward photo to admin: {e}")
    
    # Continue to check for triggers in caption
    if message.caption:
        await process_triggers(message, message.caption)

async def process_triggers(message: types.Message, text: str):
    """Process triggers for a message with given text."""
    if message.chat.type == 'private':
        return
    
    if not TRIGGERS_CACHE:
        await refresh_triggers()
    
    trigger = check_message_for_triggers(text, TRIGGERS_CACHE, chat_id=message.chat.id)
    
    if trigger:
        chat_id = message.chat.id
        trigger_id = trigger['id']
        cooldown = trigger.get('cooldown', 60)
        msg_date = message.date.timestamp()

        if cooldown_manager.can_trigger(chat_id, trigger_id, cooldown, timestamp=msg_date):
            cooldown_manager.mark_triggered(chat_id, trigger_id, timestamp=msg_date)
            
            response_text = trigger['response']
            resp_type = trigger.get('type', 'text')
            
            try:
                if resp_type == 'ai':
                    custom_model = trigger.get('ai_model')
                    response_text = await get_ai_response(
                        system_prompt=response_text,
                        user_message=text,
                        model=custom_model
                    )
                    await message.reply(response_text, parse_mode="Markdown")
                elif resp_type == 'sticker':
                    await message.reply_sticker(response_text)
                elif resp_type == 'photo':
                    await message.reply_photo(response_text)
                else:
                    await message.reply(response_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Failed to send response: {e}")

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
            # Mark as triggered IMMEDIATELY to prevent race conditions with async AI requests
            cooldown_manager.mark_triggered(chat_id, trigger_id, timestamp=msg_date)
            
            response_text = trigger['response']
            resp_type = trigger.get('type', 'text')
            
            try:
                if resp_type == 'ai':
                    # For AI, response_text acts as the system prompt
                    # Use custom model from trigger if specified
                    custom_model = trigger.get('ai_model')
                    response_text = await get_ai_response(
                        system_prompt=response_text,
                        user_message=text,
                        model=custom_model
                    )
                    await message.reply(response_text, parse_mode="Markdown")
                elif resp_type == 'sticker':
                    await message.reply_sticker(response_text)
                elif resp_type == 'photo':
                     await message.reply_photo(response_text)
                else:
                    # Text triggers with Markdown support
                    await message.reply(response_text, parse_mode="Markdown")

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

                    # Escape Markdown special characters in user-provided text
                    def escape_markdown(text: str) -> str:
                        """Escape Markdown special characters."""
                        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                        for char in special_chars:
                            text = text.replace(char, '\\' + char)
                        return text
                    
                    trigger_snippet = escape_markdown(text[:50])
                    if len(text) > 50:
                        trigger_snippet += "..."

                    notification_text = (
                        f"🔔 **Trigger Used!**\n"
                        f"👤 **User:** {escape_markdown(user)} (@{username})\n"
                        f"📍 **Chat:** {escape_markdown(chat_title)}\n"
                        f"🔗 **Link:** [Message]({msg_link})\n"
                        f"📝 **Trigger:** {trigger_snippet}"
                    )
                    
                    try:
                        await message.bot.send_message(chat_id=ADMIN_ID, text=notification_text, parse_mode="Markdown")
                    except Exception as e:
                        # If Markdown fails, send as plain text
                        print(f"Failed to notify admin with Markdown: {e}")
                        try:
                            plain_notification = (
                                f"🔔 Trigger Used!\n"
                                f"👤 User: {user} (@{username})\n"
                                f"📍 Chat: {chat_title}\n"
                                f"🔗 Link: {msg_link}\n"
                                f"📝 Trigger: {text[:50]}{'...' if len(text) > 50 else ''}"
                            )
                            await message.bot.send_message(chat_id=ADMIN_ID, text=plain_notification)
                        except Exception as e2:
                            print(f"Failed to notify admin even with plain text: {e2}")
            except Exception as e:
                print(f"Failed to send response: {e}")
