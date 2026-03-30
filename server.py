from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room
import uuid
import os

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

rooms = {}

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Video Call</title>

<style>
body {
  margin:0;
  font-family:Arial;
  background:#0f172a;
  color:white;
  text-align:center;
}

input, button {
  padding:10px;
  margin:5px;
  border-radius:6px;
  border:none;
}

button {
  background:#22c55e;
  color:white;
  cursor:pointer;
}

#videos {
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(250px,1fr));
  gap:10px;
  padding:20px;
}

video {
  width:100%;
  border-radius:10px;
  background:black;
}
</style>
</head>

<body>

<h2>🎥 Video Call App</h2>

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
let myId;

let micEnabled = true;
let camEnabled = true;

async function joinRoom() {
    const room = document.getElementById("room").value;

    localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        }
    });

    addVideo(localStream, "me", true); // muted local

    socket.emit("join", { room: room });

    socket.on("users", (data) => {
        myId = data.your_id;

        data.users.forEach(id => {
            if (id !== myId) createOffer(id);
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

        const video = document.getElementById(id);
        if (video) video.remove();
    });
}

function createPeer(id) {
    const pc = new RTCPeerConnection({
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            {
                urls: "turn:openrelay.metered.ca:80",
                username: "openrelayproject",
                credential: "openrelayproject"
            },
            {
                urls: "turn:openrelay.metered.ca:443",
                username: "openrelayproject",
                credential: "openrelayproject"
            }
        ]
    });

    localStream.getTracks().forEach(track =>
        pc.addTrack(track, localStream)
    );

    pc.ontrack = (event) => {
        addVideo(event.streams[0], id, false);
    };

    pc.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit("signal", {
                type: "candidate",
                candidate: event.candidate,
                target: id,
                from: myId
            });
        }
    };

    peers[id] = pc;
    return pc;
}

function addVideo(stream, id, muted=false) {
    let video = document.getElementById(id);

    if (!video) {
        video = document.createElement("video");
        video.id = id;
        video.autoplay = true;
        video.playsInline = true;
        video.muted = muted;
        document.getElementById("videos").appendChild(video);
    }

    video.srcObject = stream;
}

async function createOffer(id) {
    const pc = createPeer(id);

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    socket.emit("signal", {
        type: "offer",
        offer: offer,
        target: id,
        from: myId
    });
}

async function handleOffer(data) {
    const pc = createPeer(data.from);

    await pc.setRemoteDescription(data.offer);

    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);

    socket.emit("signal", {
        type: "answer",
        answer: answer,
        target: data.from,
        from: myId
    });
}

// 🎤 MIC TOGGLE
function toggleMic() {
    micEnabled = !micEnabled;
    localStream.getAudioTracks()[0].enabled = micEnabled;
}

// 📷 CAMERA TOGGLE
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
def handle_join(data):
    room = data["room"]
    user_id = str(uuid.uuid4())

    join_room(room)

    if room not in rooms:
        rooms[room] = {}

    rooms[room][user_id] = request.sid

    emit("users", {
        "users": list(rooms[room].keys()),
        "your_id": user_id
    })

@socketio.on("signal")
def handle_signal(data):
    target = data.get("target")

    for room in rooms:
        if target in rooms[room]:
            sid = rooms[room][target]
            emit("signal", data, room=sid)
            break

@socketio.on("disconnect")
def handle_disconnect():
    for room in list(rooms.keys()):
        for user_id in list(rooms[room].keys()):
            if rooms[room][user_id] == request.sid:
                del rooms[room][user_id]
                emit("user_left", user_id, broadcast=True)
                return

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on port {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
