import os
import asyncio
from dotenv import load_dotenv
from band.client.rest import AsyncRestClient

load_dotenv()

async def main():
    # Use scout's API key
    api_key = os.environ.get("SCOUT_API_KEY")
    if not api_key:
        print("No SCOUT_API_KEY")
        return
    client = AsyncRestClient(api_key=api_key)
    
    # Try to create a room
    print("Creating room...")
    try:
        room = await client.create_room({
            "name": "Vendor Vetting Test",
        })
        print("Room created:", room)
        
        # Try to fetch messages
        print("Fetching messages...")
        messages = await client.get_messages(room.id)
        print("Messages:", messages)
    except Exception as e:
        print("Error:", e)
        
if __name__ == "__main__":
    asyncio.run(main())
