import os
import asyncio
from dotenv import load_dotenv
from band.client.rest import AsyncRestClient

load_dotenv()

async def main():
    scout_key = os.environ.get("SCOUT_API_KEY")
    if not scout_key:
        print("No SCOUT_API_KEY")
        return
        
    client = AsyncRestClient(api_key=scout_key)
    print("Creating chat...")
    try:
        chat_resp = await client.agent_api_chats.create_agent_chat(chat={"name": "HealthVet Assessment: Test"})
        chat_id = chat_resp.id
        print("Chat created:", chat_id)
        
        print("Adding forensics...")
        forensics_id = os.environ.get("FORENSICS_AGENT_ID")
        await client.agent_api_participants.add_agent_chat_participant(chat_id, participant={"id": forensics_id})
        print("Participant added!")
        
        print("Sending message...")
        await client.agent_api_messages.create_agent_chat_message(chat_id, message={
            "content": "This is a test message",
        })
        print("Message sent!")
        
        print("Listing messages...")
        msgs_resp = await client.agent_api_messages.list_agent_messages(chat_id)
        print("Messages:", msgs_resp)
        
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()
        
if __name__ == "__main__":
    asyncio.run(main())
