from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit, join_room
import uuid

app = Flask(__name__)

# ✅ FIX: use threading (NO eventlet)
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

h2 { padding:20px; }

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

<h2>🎥 Flask Video Call</h2>

<input id="room" placeholder="Room ID">
<button onclick="joinRoom()">Join</button>

<div id="videos"></div>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>

<script>
const socket = io();

let localStream;
let peers = {};
let myId;

async function joinRoom() {
    const room = document.getElementById("room").value;

    localStream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true
    });

    addVideo(localStream, "me");

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
}

function createPeer(id) {
    const pc = new RTCPeerConnection({
        iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            {
                urls: "turn:openrelay.metered.ca:80",
                username: "openrelayproject",
                credential: "openrelayproject"
            }
        ]
    });

    localStream.getTracks().forEach(track =>
        pc.addTrack(track, localStream)
    );

    pc.ontrack = e => addVideo(e.streams[0], id);

    pc.onicecandidate = e => {
        if (e.candidate) {
            socket.emit("signal", {
                type: "candidate",
                candidate: e.candidate,
                target: id,
                from: myId
            });
        }
    };

    peers[id] = pc;
    return pc;
}

function addVideo(stream, id) {
    let v = document.getElementById(id);

    if (!v) {
        v = document.createElement("video");
        v.id = id;
        v.autoplay = true;
        document.getElementById("videos").appendChild(v);
    }

    v.srcObject = stream;
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
        rooms[room] = []

    rooms[room].append(user_id)

    emit("users", {
        "users": rooms[room],
        "your_id": user_id
    })

@socketio.on("signal")
def handle_signal(data):
    emit("signal", data, broadcast=True, include_self=False)

if __name__ == "__main__":
    print("🚀 Server running at http://localhost:5000")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
