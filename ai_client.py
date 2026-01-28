from openai import AsyncOpenAI
import logging
from config import NANOGPT_API_KEY, NANOGPT_MODEL

client = AsyncOpenAI(
    api_key=NANOGPT_API_KEY,
    base_url='https://nano-gpt.com/api/v1',
)

async def get_ai_response(system_prompt: str, user_message: str) -> str:
    """
    Generates a response using NanoGPT.
    """
    try:
        logging.info(f"🤖 AI Request [Model: {NANOGPT_MODEL}]:\nUser: {user_message}")
        completion = await client.chat.completions.create(
            model=NANOGPT_MODEL,
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
