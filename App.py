from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import os

app = Flask(__name__)

# 🔐 RANDOM API KEY
API_KEY = "VC-7829-QX91-PL04"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

rooms = {}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Video Call Platform</title>
<style>
    body { background:#0f172a; color:white; text-align:center; font-family:sans-serif; margin:0; padding:20px; }
    .container { max-width: 800px; margin: auto; }
    input, button { padding:12px; margin:5px; border-radius:8px; border:none; font-size: 16px; }
    input { background: #1e293b; color: white; width: 200px; border: 1px solid #334155; }
    button { background:#22c55e; color:white; cursor:pointer; font-weight: bold; transition: 0.2s; }
    button:hover { background:#16a34a; }
    #videos { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:15px; margin-top:20px; }
    video { width:100%; border-radius:12px; background:#000; border: 2px solid #334155; transform: scaleX(-1); }
    .status-bar { margin-bottom: 20px; padding: 10px; border-radius: 8px; background: #1e293b; display: inline-block; }
</style>
</head>
<body>

<div class="container">
    <h2>🎥 Secure Video Call</h2>
    <div class="status-bar" id="status">Connecting to server...</div>
    <br>
    <input id="room" placeholder="Enter Room ID">
    <button onclick="joinRoom()">Join Room</button>
    <br><br>
    <button onclick="toggleMic()">🎤 Mic</button>
    <button onclick="toggleCamera()">📷 Camera</button>
    <div id="videos"></div>
</div>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
// 🔑 THE API KEY
const API_KEY = "VC-7829-QX91-PL04";

const socket = io({
    query: { token: API_KEY }
});

let localStream;
let peers = {};
let micEnabled = true;
let camEnabled = true;
let myId = localStorage.getItem("userId") || crypto.randomUUID();
localStorage.setItem("userId", myId);

socket.on("connect", () => {
    document.getElementById("status").innerText = "✅ Authorized & Online";
    document.getElementById("status").style.color = "#22c55e";
});

socket.on("connect_error", () => {
    document.getElementById("status").innerText = "❌ Authentication Failed";
    document.getElementById("status").style.color = "#ef4444";
});

async function joinRoom() {
    if (localStream) return;
    const room = document.getElementById("room").value;
    if (!room) return alert("Please enter a Room ID");

    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        addVideo(localStream, "me", true);
        socket.emit("join", { room: room, user_id: myId });
    } catch (e) {
        alert("Permissions denied. Please enable camera/mic.");
    }
}

socket.on("users", (data) => {
    data.users.forEach(id => {
        if (id !== myId && !peers[id]) createOffer(id);
    });
});

socket.on("signal", async (data) => {
    const { from, type } = data;
    if (type === "offer") await handleOffer(data);
    else if (type === "answer") await peers[from]?.setRemoteDescription(data.answer);
    else if (type === "candidate") await peers[from]?.addIceCandidate(data.candidate);
});

socket.on("user_left", (id) => {
    if (peers[id]) { peers[id].close(); delete peers[id]; }
    document.getElementById(id)?.remove();
});

function createPeer(id) {
    const pc = new RTCPeerConnection({
        iceServers: [{ urls: "stun:stun.l.google.com:19302" }]
    });
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
    pc.ontrack = (e) => addVideo(e.streams[0], id, false);
    pc.onicecandidate = (e) => {
        if (e.candidate) socket.emit("signal", { type:"candidate", candidate:e.candidate, target:id, from:myId });
    };
    peers[id] = pc;
    return pc;
}

function addVideo(stream, id, muted=false) {
    let v = document.getElementById(id);
    if (!v) {
        v = document.createElement("video");
        v.id = id; v.autoplay = true; v.playsInline = true; v.muted = muted;
        document.getElementById("videos").appendChild(v);
    }
    v.srcObject = stream;
}

async function createOffer(id) {
    const pc = createPeer(id);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    socket.emit("signal", { type:"offer", offer:offer, target:id, from:myId });
}

async function handleOffer(data) {
    const pc = createPeer(data.from);
    await pc.setRemoteDescription(data.offer);
    const ans = await pc.createAnswer();
    await pc.setLocalDescription(ans);
    socket.emit("signal", { type:"answer", answer:ans, target:data.from, from:myId });
}

function toggleMic() {
    micEnabled = !micEnabled;
    localStream.getAudioTracks()[0].enabled = micEnabled;
}

function toggleCamera() {
    camEnabled = !camEnabled;
    localStream.getVideoTracks()[0].enabled = camEnabled;
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@socketio.on("connect")
def connect():
    # Verify API Key from the connection query string
    token = request.args.get("token")
    if token != API_KEY:
        print(f"Unauthorized access attempt: {request.sid}")
        return False # Rejects the connection

@socketio.on("join")
def join(data):
    room = data["room"]
    user_id = data["user_id"]
    join_room(room)
    if room not in rooms: rooms[room] = {}
    rooms[room][user_id] = request.sid
    emit("users", {"users": list(rooms[room].keys())}, room=room)

@socketio.on("signal")
def signal(data):
    target = data.get("target")
    for room in rooms:
        if target in rooms[room]:
            emit("signal", data, room=rooms[room][target])

@socketio.on("disconnect")
def disconnect():
    for room in list(rooms.keys()):
        for user_id in list(rooms[room].keys()):
            if rooms[room][user_id] == request.sid:
                del rooms[room][user_id]
                emit("user_left", user_id, broadcast=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
