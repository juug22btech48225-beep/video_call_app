import asyncio
import websockets
import json
import uuid
import os
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import threading

rooms = {}

# -----------------------------
# WEBSOCKET HANDLER
# -----------------------------
async def ws_handler(websocket):
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

# -----------------------------
# HTTP SERVER (SERVE WEBSITE)
# -----------------------------
def start_http():
    port = int(os.environ.get("PORT", 10000))
    handler = SimpleHTTPRequestHandler
    with TCPServer(("", port), handler) as httpd:
        print(f"🌐 HTTP running on port {port}")
        httpd.serve_forever()

# -----------------------------
# WEBSOCKET SERVER
# -----------------------------
async def start_ws():
    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        print("🔌 WebSocket running on port 8765")
        await asyncio.Future()

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    threading.Thread(target=start_http).start()
    asyncio.run(start_ws())
