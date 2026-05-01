from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from obswebsocket import obsws, requests as obsrequests
import json, os, time, threading, queue, urllib.request, urllib.error
import subprocess

# ── Load .env file if present (no extra dependencies needed) ───────────
def _load_dotenv():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

_load_dotenv()

app = Flask(__name__)

# ── OBS config ─────────────────────────────────────────────────────────
# Set these via environment variables or edit directly for local use
OBS_IP       = os.environ.get("OBS_IP",       "192.168.1.100")
OBS_PORT     = int(os.environ.get("OBS_PORT", "4455"))
OBS_PASSWORD = os.environ.get("OBS_PASSWORD", "your_obs_password")

# ── Home Assistant config ───────────────────────────────────────────────
# HA_URL: e.g. "http://192.168.1.100:8123"
# HA_TOKEN: Long-Lived Access Token from your HA profile page
HA_URL   = os.environ.get("HA_URL",   "http://192.168.1.100:8123")
HA_TOKEN = os.environ.get("HA_TOKEN", "")

LAYOUT_FILE = os.path.join(os.path.dirname(__file__), "layout.json")

# ── OBS connection with auto-reconnect ─────────────────────────────────
ws = None
obs_connected = False

def connect_obs():
    global ws, obs_connected
    while True:
        try:
            new_ws = obsws(OBS_IP, OBS_PORT, OBS_PASSWORD)
            new_ws.connect()
            ws = new_ws
            obs_connected = True
            print("OBS connected")

            # Poll to detect disconnection
            while True:
                time.sleep(5)
                try:
                    ws.call(obsrequests.GetVersion())
                except Exception:
                    print("OBS disconnected. Reconnecting...")
                    obs_connected = False
                    break

        except Exception as e:
            print(f"OBS connection failed: {e}. Retrying in 5s...")
            obs_connected = False
            time.sleep(5)

threading.Thread(target=connect_obs, daemon=True).start()

# ── Layout helpers ──────────────────────────────────────────────────────
DEFAULT_LAYOUT = {
    "cols": 3,
    "rows": 4,
    "buttons": [
        {"id": "1", "col": 0, "row": 0, "label": "Starting Soon", "icon": "🎬", "color": "#1a1a2e", "action": "scene",         "value": "Starting Soon"},
        {"id": "2", "col": 1, "row": 0, "label": "Live",          "icon": "🔴", "color": "#16213e", "action": "scene",         "value": "Live"},
        {"id": "3", "col": 2, "row": 0, "label": "BRB",           "icon": "☕", "color": "#0f3460", "action": "scene",         "value": "BRB"},
        {"id": "4", "col": 0, "row": 1, "label": "Ending",        "icon": "🏁", "color": "#533483", "action": "scene",         "value": "Ending"},
        {"id": "5", "col": 1, "row": 1, "label": "Mute Mic",      "icon": "🎙️", "color": "#2d2d2d", "action": "toggle_mute",  "value": "Mic/Aux"},
        {"id": "6", "col": 2, "row": 1, "label": "Stream",        "icon": "📡", "color": "#1b4332", "action": "toggle_stream", "value": ""},
    ]
}

def load_layout():
    if os.path.exists(LAYOUT_FILE):
        with open(LAYOUT_FILE) as f:
            return json.load(f)
    return DEFAULT_LAYOUT

def save_layout(layout):
    with open(LAYOUT_FILE, "w") as f:
        json.dump(layout, f, indent=2)

# ── Home Assistant helper ───────────────────────────────────────────────
def ha_call(domain, service, entity_id):
    if not HA_TOKEN:
        raise Exception("HA_TOKEN not configured. Set the HA_TOKEN environment variable.")
    url  = f"{HA_URL}/api/services/{domain}/{service}"
    data = json.dumps({"entity_id": entity_id}).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {HA_TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status

# ── Routes ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/editor")
def editor():
    return render_template("editor.html")

@app.route("/api/layout", methods=["GET"])
def get_layout():
    return jsonify(load_layout())

@app.route("/api/layout", methods=["POST"])
def post_layout():
    layout = request.get_json()
    save_layout(layout)
    notify_clients("reload")
    return jsonify({"status": "ok"})

@app.route("/api/action", methods=["POST"])
def action():
    data = request.get_json()
    act  = data.get("action")
    val  = data.get("value", "")

    if act == "ha_service":
        try:
            # value format: "domain.service|entity_id"
            # examples:
            #   "light.turn_on|light.desk_lamp"
            #   "light.turn_off|light.desk_lamp"
            #   "switch.toggle|switch.stream_lights"
            #   "scene.turn_on|scene.gaming_mode"
            parts = val.split("|")
            if len(parts) != 2:
                return jsonify({"status": "error", "message": "HA value must be 'domain.service|entity_id'"}), 400
            ds      = parts[0].split(".")
            domain  = ds[0]
            service = ds[1]
            entity  = parts[1]
            ha_call(domain, service, entity)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if act == "url":
        try:
            urllib.request.urlopen(val, timeout=3)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    if act == "none":
        return jsonify({"status": "ok"})

    if not obs_connected:
        return jsonify({"status": "error", "message": "OBS not connected"}), 503

    try:
        if act == "scene":
            ws.call(obsrequests.SetCurrentProgramScene(sceneName=val))
        elif act == "toggle_mute":
            ws.call(obsrequests.ToggleInputMute(inputName=val))
        elif act == "toggle_stream":
            ws.call(obsrequests.ToggleStream())
        elif act == "toggle_record":
            ws.call(obsrequests.ToggleRecord())
        elif act == "toggle_pause_record":
            ws.call(obsrequests.ToggleRecordPause())
        elif act == "set_volume":
            parts = val.split(":")
            ws.call(obsrequests.SetInputVolume(inputName=parts[0], inputVolumeDb=float(parts[1])))
        elif act == "studio_mode":
            ws.call(obsrequests.SetStudioModeEnabled(studioModeEnabled=True))
        elif act == "hotkey":
            ws.call(obsrequests.TriggerHotkeyByName(hotkeyName=val))
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/obs/scenes", methods=["GET"])
def get_scenes():
    if not obs_connected:
        return jsonify({"scenes": [], "error": "OBS not connected"}), 503  # ← add error + 503
    try:
        resp   = ws.call(obsrequests.GetSceneList())
        scenes = [s["sceneName"] for s in resp.getScenes()]
        return jsonify({"scenes": scenes})
    except Exception as e:
        return jsonify({"scenes": [], "error": str(e)}), 503

@app.route("/api/obs/inputs", methods=["GET"])
def get_inputs():
    if not obs_connected:
        return jsonify({"inputs": []})
    try:
        resp   = ws.call(obsrequests.GetInputList())
        inputs = [i["inputName"] for i in resp.getInputs()]
        return jsonify({"inputs": inputs})
    except Exception as e:
        return jsonify({"inputs": [], "error": str(e)})

@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    subprocess.Popen(["sudo", "shutdown", "-h", "now"])
    return jsonify({"status": "ok"})

@app.route("/api/display", methods=["POST"])
def display():
    state = request.get_json().get("state")
    if state == "off":
        subprocess.Popen(["xrandr", "--display", ":0", "--output", "DSI-1", "--off"])
    elif state == "on":
        subprocess.Popen(["xrandr", "--display", ":0", "--output", "DSI-1", "--mode", "720x1280", "--rotate", "left"])
    return jsonify({"status": "ok"})

# ── SSE ─────────────────────────────────────────────────────────────────
sse_clients = []

@app.route("/api/events")
def events():
    q = queue.Queue()
    sse_clients.append(q)
    def stream():
        try:
            while True:
                msg = q.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            sse_clients.remove(q)
    return Response(stream_with_context(stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

def notify_clients(msg="reload"):
    for q in sse_clients:
        q.put(msg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)