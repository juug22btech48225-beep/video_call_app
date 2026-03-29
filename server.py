import asyncio
import websockets
import json
import uuid
import os

rooms = {}

async def handler(websocket):
    user_id = str(uuid.uuid4())
    room = None

    try:
        async for message in websocket:
            data = json.loads(message)

            if data["type"] == "join":
                room = data["room"]

                if room not in rooms:
                    rooms[room] = {}

                rooms[room][user_id] = websocket

                await websocket.send(json.dumps({
                    "type": "users",
                    "users": list(rooms[room].keys()),
                    "your_id": user_id
                }))

            else:
                target = data.get("target")
                if room and target in rooms[room]:
                    await rooms[room][target].send(json.dumps({
                        **data,
                        "from": user_id
                    }))

    except:
        pass
    finally:
        if room and user_id in rooms.get(room, {}):
            del rooms[room][user_id]

async def main():
    port = int(os.environ.get("PORT", 8765))  # ✅ IMPORTANT FOR RENDER

    async with websockets.serve(handler, "0.0.0.0", port):
        print(f"🚀 Server running on port {port}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
