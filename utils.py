import time
from thefuzz import fuzz

class CooldownManager:
    def __init__(self):
        # self.last_triggered[chat_id][trigger_id] = timestamp
        self.last_triggered = {}

    def can_trigger(self, chat_id: int, trigger_id: int, cooldown_seconds: int, timestamp: float = None) -> bool:
        if chat_id not in self.last_triggered:
            self.last_triggered[chat_id] = {}
        
        last_time = self.last_triggered[chat_id].get(trigger_id, 0)
        current_time = timestamp if timestamp is not None else time.time()
        
        if current_time - last_time < cooldown_seconds:
            return False
            
        return True

    def mark_triggered(self, chat_id: int, trigger_id: int, timestamp: float = None):
        if chat_id not in self.last_triggered:
            self.last_triggered[chat_id] = {}
        current_time = timestamp if timestamp is not None else time.time()
        self.last_triggered[chat_id][trigger_id] = current_time

def check_message_for_triggers(message_text: str, triggers_data: list) -> dict | None:
    """
    Checks if message contains any of the triggers.
    Returns the trigger object if found, else None.
    Uses fuzzy matching.
    """
    if not message_text:
        return None
        
    message_words = message_text.lower().split()
    
    for trigger_obj in triggers_data:
        keywords = trigger_obj.get('triggers', [])
        for keyword in keywords:
            keyword = keyword.lower()
            # Exact match check first for speed
            if keyword in message_text.lower():
                 return trigger_obj
            
            # Fuzzy match word by word
            for word in message_words:
                ratio = fuzz.ratio(keyword, word)
                if ratio >= 85: # Threshold for match
                    return trigger_obj
                    
    return None
