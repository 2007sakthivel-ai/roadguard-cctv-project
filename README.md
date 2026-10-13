# RoadGuard

Real-time road accident detection from a webcam, CCTV/RTSP stream, or video file,
with incident snapshots, a local incident history, and optional emergency-responder
webhook notifications.

> **Safety note:** This is an AI-assisted prototype, not a certified emergency
> dispatch system. A model can miss incidents or produce false positives. Keep a
> human in the response loop, validate the model on the target cameras, and follow
> local emergency procedures. The application does not contact emergency services
> unless you configure a webhook that does so.

## Requirements

- Python 3.10 or newer
- A trained Ultralytics YOLO `.pt` model that can recognize an accident class
- A camera/video stream; a CUDA-enabled GPU is recommended for high-resolution
  or multi-camera operation

The repository does not commit model weights or a dataset. Standard COCO YOLO
weights recognize objects such as cars and people, **not whether a road accident
has occurred**, so they must not be used as an accident detector. The optional
downloaded model is an externally maintained starting point, not a validated or
certified emergency system.

## Run locally

For Windows, double-click `RUN_ROADGUARD.bat`. It creates the virtual environment
and installs dependencies if needed, starts the server, and opens the dashboard
once the health endpoint is ready. Keep the RoadGuard Server window open while
using the app; press Ctrl+C in that window to stop the server.

Alternatively, run the setup and start scripts from PowerShell with execution
policy bypass for this invocation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Or create the environment manually:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

To try the application with a publicly shared pretrained model, run the pinned
download script:

```powershell
.\scripts\download_model.ps1
```

It downloads the YOLO11x accident/vehicle detector shared by
[Enos-123](https://huggingface.co/Enos-123/traffic-accident-detection-yolo11x)
and verifies its SHA-256 before installing it. The model card reports an MIT
license and evaluation metrics; those claims have not been independently
verified. Review the model card and validate the model on your own footage before
relying on its predictions. For production use, train/fine-tune your own model or
set `MODEL_PATH` to your reviewed weights.

Then start the dashboard. If PowerShell blocks script execution, use the
invocation below or double-click `RUN_ROADGUARD.bat`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Open <http://127.0.0.1:8000>. Enter `0` for the default webcam, a local video path,
or an RTSP URL, then click **Start monitoring**.

To view a source without loading the accident-detection model, click
**Camera preview only**. This opens the camera feed but performs no detection,
records no incidents, and sends no emergency alerts. Use **Start monitoring**
only when the model and its dependencies load successfully.

## Publish a secure website link

The Docker deployment uses a Linux VPS, Docker Compose, and Caddy. Caddy obtains
HTTPS certificates for a domain you control and sends traffic to the app.
Public deployment requires a domain name, a VPS with Docker Engine and the
Docker Compose plugin, and the reviewed model file at `models/accident.pt`.
Choose a VPS with enough CPU and memory for the model; a CPU-only VPS can be
significantly slower than a suitable GPU system.

1. Point your domain's DNS `A` record to the VPS public IP. Allow inbound ports
   80 and 443 in the VPS firewall; do not expose port 8000 publicly.
2. Copy the project source, `Dockerfile`, `docker-compose.yml`, `Caddyfile`, and
   `requirements.txt` to `/opt/roadguard` on the VPS. Do not copy `.env` or the
   Windows `.venv` directory. Upload the reviewed model separately to
   `/opt/roadguard/models/accident.pt`. Create `/opt/roadguard/data` for incident
   history and snapshots.
3. On the VPS, create `.env` from `.env.example`, then set `ROADGUARD_DOMAIN` to
   your domain, `PUBLIC_DEPLOYMENT=true`, and non-empty, strong, private
   `APP_USERNAME` and `APP_PASSWORD` values. Configure notification settings
   separately if needed. The app refuses public mode without login credentials.
4. From `/opt/roadguard`, run:

   ```sh
   docker compose up -d --build
   docker compose logs -f
   ```

   Once Caddy has obtained the HTTPS certificate, open
   `https://your-domain.example`. The browser will request the configured
   username and password. Keep `.env` private and use HTTPS; HTTP Basic
   authentication is not safe over unencrypted HTTP.

The model analyzes video **on the VPS**, not on the visitor's computer. A
webcam index such as `0` refers to a camera physically attached to the VPS.
For remote CCTV, provide an RTSP stream the VPS can reach over a trusted private
network or VPN; do not expose a camera stream directly to the public internet.
Keep a dashboard open and monitoring active for browser sound alerts.

Alternatively, set variables directly in PowerShell:

```powershell
$env:MODEL_PATH = "models/accident.pt"
$env:ALERT_WEBHOOK_URL = "https://your-responder-gateway.example/alerts"
uvicorn roadguard.api:app --host 127.0.0.1 --port 8000
```

Keep the server bound to localhost unless deployed behind an authenticated,
access-controlled reverse proxy. This prototype does not include user
authentication or RTSP credential management.

## Train or fine-tune a model

Prepare an Ultralytics detection dataset with YOLO-format labels and a dataset YAML.
The configured `ACCIDENT_CLASSES` must match one or more class names exactly
(case-insensitively); the default is `accident,crash,collision`.

Example dataset YAML:

```yaml
path: C:/datasets/road-accidents
train: images/train
val: images/val
names:
  0: accident
```

Train from a suitable pretrained base (use one trained for your data/domain):

```powershell
python scripts/train.py --data C:\datasets\road-accidents\data.yaml --model yolo11n.pt --epochs 100
```

Copy `runs/roadguard/accident/weights/best.pt` to `models/accident.pt`, or set
`MODEL_PATH` to that output. Do not deploy until precision/recall and alert latency
have been evaluated against representative camera footage and independently
reviewed.

## Automatic sound and voice alerts

When a new incident is recorded, the open dashboard displays a prominent
accident alert, plays three repeating warning tones every two seconds for at
least 60 seconds, and repeats the spoken announcement every 12 seconds:
“Accident detected. Accident detected. Please verify the camera footage and
contact emergency responders.” The dashboard shows a countdown while the alarm
is active. The **Test sound** button plays a short test announcement. Use
**Sound alerts: ON/OFF** to mute or enable audible alerts.

Browsers require a user interaction before they allow audio. Click **Start
monitoring** or **Test sound** once in the dashboard to enable audio playback.
Keep the dashboard tab open to hear new-incident alerts.

## Responder webhook alerts

Set `ALERT_WEBHOOK_URL` to an HTTPS endpoint controlled by your responder
integration. For each confirmed incident RoadGuard sends a JSON `POST` with the
incident ID, UTC creation time, source name, detected class, confidence, and
snapshot path. The webhook runs asynchronously, and delivery failures are logged
by the server. Secure the receiving endpoint, validate incoming requests, and
integrate with an approved dispatch workflow; do not expose webhook secrets in
the browser. The dashboard's sound and spoken alerts do not require a webhook.

### SMS and email notifications

RoadGuard can also send an SMS through an Android gateway app and email through
Gmail SMTP. In `.env`, set `SMS_GATEWAY_URL` to the gateway's HTTP endpoint and
`SMS_RECIPIENT` to the destination number. The gateway must accept a JSON `POST`
containing `to` and `message` fields; if supported, set `SMS_GATEWAY_TOKEN` for
Bearer-token authentication. Keep the phone and computer on the same trusted
network, and only use a gateway app you trust. Gateway apps may use a different
API format, so verify compatibility before relying on delivery.

For Gmail, set `SMTP_USERNAME`, `SMTP_PASSWORD`, and `ALERT_EMAIL_TO`. Use a
Google App Password for `SMTP_PASSWORD`, not your normal account password. Keep
credentials private in `.env` and never commit or share them. External SMS/email
alerts are disabled until their connection settings and credentials are complete.

Alert confirmation and duplicate suppression are configurable with
`CONFIRM_FRAMES` and `ALERT_COOLDOWN_SECONDS`. `CONFIRM_FRAMES=1` records and
alerts on the first positive detection; this is faster but can increase false
alarms. Increase it if needed. A 60-second cooldown prevents duplicate alerts.
The default `INFERENCE_SIZE` is 416 instead of 640; smaller values may make
small or distant accidents harder to detect.

## API

- `GET /api/health` — server health
- `GET /api/status` — worker state, FPS, model path, latest event, and alert setup
- `POST /api/start` — start processing; JSON body: `{"source":"0"}`
- `POST /api/preview` — open a camera feed without loading the model, detecting
  accidents, recording incidents, or sending alerts; JSON body: `{"source":"0"}`
- `POST /api/stop` — stop processing
- `GET /api/events?limit=50` — recent incident records
- `GET /api/events/{id}/snapshot` — saved event snapshot
- `GET /video_feed` — annotated MJPEG stream

Incidents are stored in `data/incidents.sqlite3`; snapshots are in
`data/snapshots/`.

## Tests

```powershell
pytest -q
```
