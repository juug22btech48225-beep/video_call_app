from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import os
import uuid

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

rooms = {}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Video Call</title>

<style>
body { background:#0f172a; color:white; text-align:center; font-family:Arial; }
input, button { padding:10px; margin:5px; border-radius:6px; border:none; }
button { background:#22c55e; color:white; cursor:pointer; }
#videos { display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:10px; padding:20px; }
video { width:100%; border-radius:10px; background:black; }
</style>
</head>

<body>

<h2>🎥 Video Call Platform</h2>

<input id="room" placeholder="Room ID">
<button onclick="joinRoom()">Join</button>

<br><br>

<button onclick="toggleMic()">🎤 Mic</button>
<button onclick="toggleCamera()">📷 Camera</button>

<div id="videos"></div>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

<script>
const socket = io();

let localStream;
let peers = {};
let micEnabled = true;
let camEnabled = true;

// 🔁 SAME USER ID
let myId = localStorage.getItem("userId");
if (!myId) {
    myId = crypto.randomUUID();
    localStorage.setItem("userId", myId);
}

// 🔐 ASK PERMISSION ON LOAD
window.onload = async () => {
    try {
        await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch (e) {
        alert("Camera & Mic permission required!");
    }
};

// JOIN ROOM
async function joinRoom() {

    if (localStream) {
        alert("Already joined!");
        return;
    }

    const room = document.getElementById("room").value;

    // 🔥 FORCE ONLY MIC DEVICE
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mic = devices.find(d => d.kind === "audioinput");

    localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: {
            deviceId: mic ? { exact: mic.deviceId } : undefined,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            channelCount: 1
        }
    });

    // 🔇 MUTE SELF (IMPORTANT)
    addVideo(localStream, "me", true);

    socket.emit("join", {
        room: room,
        user_id: myId
    });

    socket.on("users", (data) => {
        data.users.forEach(id => {
            if (id !== myId && !peers[id]) {
                createOffer(id);
            }
        });
    });

    socket.on("signal", async (data) => {
        const { from, type } = data;

        if (type === "offer") await handleOffer(data);
        else if (type === "answer") await peers[from]?.setRemoteDescription(data.answer);
        else if (type === "candidate") await peers[from]?.addIceCandidate(data.candidate);
    });

    socket.on("user_left", (id) => {
        if (peers[id]) {
            peers[id].close();
            delete peers[id];
        }
        const v = document.getElementById(id);
        if (v) v.remove();
    });
}

// PEER CONNECTION
function createPeer(id) {
    const pc = new RTCPeerConnection({
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "turn:openrelay.metered.ca:80", username:"openrelayproject", credential:"openrelayproject" },
            { urls: "turn:openrelay.metered.ca:443", username:"openrelayproject", credential:"openrelayproject" }
        ]
    });

    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    pc.ontrack = (e) => {
        addVideo(e.streams[0], id, false); // remote audio only
    };

    pc.onicecandidate = (e) => {
        if (e.candidate) {
            socket.emit("signal", {
                type:"candidate",
                candidate:e.candidate,
                target:id,
                from:myId
            });
        }
    };

    peers[id] = pc;
    return pc;
}

// VIDEO ELEMENT
function addVideo(stream, id, muted=false) {
    let v = document.getElementById(id);

    if (!v) {
        v = document.createElement("video");
        v.id = id;
        v.autoplay = true;
        v.playsInline = true;
        v.muted = muted; // 🔥 prevents self echo
        document.getElementById("videos").appendChild(v);
    }

    v.srcObject = stream;
}

// OFFER
async function createOffer(id) {
    const pc = createPeer(id);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    socket.emit("signal", {
        type:"offer",
        offer:offer,
        target:id,
        from:myId
    });
}

// ANSWER
async function handleOffer(data) {
    const pc = createPeer(data.from);

    await pc.setRemoteDescription(data.offer);
    const ans = await pc.createAnswer();
    await pc.setLocalDescription(ans);

    socket.emit("signal", {
        type:"answer",
        answer:ans,
        target:data.from,
        from:myId
    });
}

// MIC TOGGLE
function toggleMic() {
    micEnabled = !micEnabled;
    localStream.getAudioTracks()[0].enabled = micEnabled;
}

// CAMERA TOGGLE
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

@socketio.on("join")
def join(data):
    room = data["room"]
    user_id = data["user_id"]

    join_room(room)

    if room not in rooms:
        rooms[room] = {}

    # 🔁 remove old session if rejoining
    if user_id in rooms[room]:
        old_sid = rooms[room][user_id]
        emit("user_left", user_id, room=old_sid)

    rooms[room][user_id] = request.sid

    emit("users", {
        "users": list(rooms[room].keys()),
        "your_id": user_id
    })

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
                return

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
