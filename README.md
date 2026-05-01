# 🎛️ Pi Stream Deck

A DIY Stream Deck built with a **Raspberry Pi 4B** and the official **Raspberry Pi Touch Display 2** (7"). Runs as a full-screen touch UI in Chromium kiosk mode, served by a local Flask app.

Controls **OBS Studio** via WebSocket and **Home Assistant** via its REST API — all configurable through a built-in web editor, no coding required after setup.


---

## ✨ Features

- **Touch-optimized grid UI** — configurable columns/rows, scales to any screen size
- **Live layout editor** — drag to reorder, click to edit, push changes instantly via SSE
- **OBS actions** — switch scenes, toggle mute, start/stop stream & recording, trigger hotkeys, set volume
- **Home Assistant actions** — call any HA service/entity with one tap
- **Custom URL / webhook** — fire any HTTP GET with a button press
- **Per-button customization** — emoji icon, label, background color with swatches
- **Screensaver** — auto-dims after 30 s of inactivity, wakes on touch; turns off the DSI backlight to save power
- **Auto-reconnect** — OBS connection retries automatically in the background
- **Shutdown button support** — cleanly power off the Pi from a button

---

## 🖼️ Hardware

| Part | Notes |
|------|-------|
| Raspberry Pi 4B (2 GB+ RAM) | Any 4B revision works |
| Raspberry Pi Touch Display 2 (7") | Connected via DSI ribbon cable |
| microSD card (16 GB+) | Class 10 / A1 recommended |
| USB-C power supply (5V 3A) | Official Pi PSU recommended |
| Case (optional) | Any case that exposes the DSI display | I used this one: https://www.thingiverse.com/thing:7095324/files




---

## 🗺️ Architecture

```
┌─────────────────────────────────────────┐
│            Raspberry Pi 4B              │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  Flask app  (app.py, port 5000) │    │
│  │  • /           → deck UI        │    │
│  │  • /editor     → layout editor  │    │
│  │  • /api/action → OBS / HA calls │    │
│  │  • /api/events → SSE push       │    │
│  └────────┬────────────────────────┘    │
│           │ localhost                   │
│  ┌────────▼──────────────────────────┐  │
│  │  Chromium (kiosk, DSI display)    │  │
│  └───────────────────────────────────┘  │
└───────────┬─────────────┬───────────────┘
            │ WebSocket   │ HTTP REST
     ┌──────▼──────┐  ┌───▼──────────────┐
     │ OBS Studio  │  │  Home Assistant  │
     │ (LAN PC)    │  │  (LAN server)    │
     └─────────────┘  └──────────────────┘
```

---

## 🚀 Setup

### 1. Flash Raspberry Pi OS

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) to flash **Raspberry Pi OS (64-bit, full desktop)** to your microSD card. Enable SSH in the imager's advanced options to make headless setup easier.

### 2. Clone this repo

```bash
git clone https://github.com/lizardgartixa/Elraspo-stream-deck.git
cd Elraspo-stream-deck
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure credentials

```bash
cp .env.example .env
nano .env
```

Fill in your OBS WebSocket IP/port/password and your Home Assistant URL + Long-Lived Access Token.

> **How to get a HA Long-Lived Access Token:**  
> HA → Profile (bottom-left avatar) → scroll to *Long-Lived Access Tokens* → Create Token

Then load the `.env` before starting the app:

```bash
export $(cat .env | xargs)
python app.py
```

Or use a tool like [python-dotenv](https://pypi.org/project/python-dotenv/) — see [Advanced: systemd service](#advanced-systemd-service) for a cleaner production approach.

### 5. Enable OBS WebSocket

In OBS: **Tools → WebSocket Server Settings** → enable it, set a port (default `4455`) and password. Match these in your `.env`.

### 6. Run the app

```bash
python app.py
```

Visit `http://<pi-ip>:5000` from any browser on your network to see the deck, or `http://<pi-ip>:5000/editor` to edit the layout.

### 7. Set up the kiosk display

The `start-ui.sh` script configures the DSI-1 display, corrects the touch coordinate matrix, hides the cursor, and launches Chromium in kiosk mode.

```bash
chmod +x start-ui.sh
```

Edit the script if your display output name is different (check with `xrandr --listmonitors`). Then launch it after the Flask app is running:

```bash
DISPLAY=:0 bash start-ui.sh
```

---

## ⚙️ Advanced: systemd service

Run Flask automatically at boot with a systemd unit:

```ini
# /etc/systemd/system/streamdeck.service
[Unit]
Description=Pi Stream Deck Flask App
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/pi-stream-deck
EnvironmentFile=/home/pi/pi-stream-deck/.env
ExecStart=/usr/bin/python3 /home/pi/pi-stream-deck/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable streamdeck
sudo systemctl start streamdeck
```

To also auto-launch the kiosk on login, add a call to `start-ui.sh` to your `~/.config/lxsession/LXDE-pi/autostart` or a `.desktop` file in `~/.config/autostart/`.

---

## 🎨 Button Actions Reference

| Action | Value field | Description |
|--------|-------------|-------------|
| `none` | *(empty)* | Decoration only — no action fired |
| `scene` | Scene name | Switch OBS to the named scene |
| `toggle_mute` | Input name | Toggle mute on an OBS audio input |
| `toggle_stream` | *(empty)* | Start / stop the OBS stream |
| `toggle_record` | *(empty)* | Start / stop OBS recording |
| `toggle_pause_record` | *(empty)* | Pause / resume OBS recording |
| `hotkey` | Hotkey name | Trigger an OBS hotkey by name |
| `set_volume` | `InputName:dB` | Set OBS input volume in dB (e.g. `Mic/Aux:-10`) |
| `ha_service` | `domain.service\|entity_id` | Call any HA service (e.g. `light.turn_on\|light.desk_lamp`) |
| `url` | Full URL | Fire an HTTP GET to any URL / webhook |

---

## 📁 Project Structure

```
pi-stream-deck/
├── app.py              # Flask backend — OBS, HA, layout API, SSE
├── templates/
│   ├── index.html      # Touch deck UI (served to the Pi display)
│   └── editor.html     # Web-based layout editor
├── start-ui.sh         # Kiosk launcher script for the Pi display
├── requirements.txt
├── .env.example        # Credential template — copy to .env
├── .gitignore
└── layout.json         # Auto-generated on first save (gitignored)
```

> **Note:** `index.html` and `editor.html` are served via Flask's template engine. Move them into a `templates/` folder as shown above, or adjust the `render_template()` calls in `app.py` if you keep them alongside it.

---

## 🔒 Security notes

- The Flask app binds to `0.0.0.0:5000` — anyone on your LAN can reach it. If that's a concern, bind to `127.0.0.1` instead and access it only from the Pi itself.
- Never commit your `.env` file. It's listed in `.gitignore`.
- The HA token grants broad access; use a dedicated HA user with only the permissions you need.

---

## 🛠️ Troubleshooting

**OBS not connecting**  
Check that OBS is running, WebSocket is enabled, and the IP/port/password in `.env` match. The app retries every 5 seconds and logs failures to stdout.

**Touch input is wrong (rotated / mirrored)**  
Adjust the transformation matrix in `start-ui.sh`. Use `xinput list` to find your touch device ID, then experiment with the matrix values. [This guide](https://wiki.ubuntu.com/X/InputCoordinateTransformation) explains the math.

**Home Assistant returns 401**  
Your HA token is invalid or expired. Generate a new Long-Lived Access Token from your HA profile.

**Home Assistant returns connection error**  
Check `HA_URL` in `.env` — it must not have a trailing slash, and must include the port (e.g. `http://192.168.1.100:8123`).

**Screen doesn't turn off / on**  
The screensaver calls `xrandr` on output `DSI-1`. Verify your output name with `xrandr --listmonitors` and update both `app.py` and `start-ui.sh` if it differs.

---

## 🤝 Contributing

PRs welcome! Some ideas for improvements:

- [ ] Multi-page / folder support
- [ ] Button state feedback (e.g. show current OBS scene, HA entity state)
- [ ] Long-press actions
- [ ] Import / export layout as JSON
- [ ] Configurable screensaver timeout

---

## 📄 License

MIT — see [LICENSE](LICENSE).
