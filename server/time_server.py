#!/usr/bin/env python3
# File: server/time_server.py
# Description: Flask web server for ESP32 SmartAlarm
# Place this file under the `server/` directory in your GitHub repository.

from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import paho.mqtt.client as mqtt
import threading, time, json
from datetime import datetime, timedelta

# =============
# === CONFIG ===
# =============

# Data model: tracks current timezone and alarm list
currentZone = 0
TIMEZONES = ["UTC", "CET", "Tashkent", "EST"]
alarms = []   # list of {"time":"HH:MM","zone":"ZoneName"}

# MQTT broker connection settings
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set("new_user", "first")
# Broker is assumed to run on the same machine; adjust to your host if needed
mqtt_client.connect("localhost", 1883, 60)

# ===============
# === MQTT HOOK ===
# ===============

def on_mqtt_message(client, userdata, msg):
    """
    Handle incoming MQTT messages from the ESP32 device.
    Subscribed topics: clock/zone
    """
    global currentZone
    if msg.topic == "clock/zone":
        new_zone = msg.payload.decode()
        if new_zone in TIMEZONES:
            currentZone = TIMEZONES.index(new_zone)

# Bind callback and subscribe to zone changes
mqtt_client.on_message = on_mqtt_message
mqtt_client.subscribe("clock/zone")
# Start MQTT network loop in background thread
mqtt_client.loop_start()

# ====================
# === SYNC THREAD ====
# ====================

def mqtt_loop():
    """
    Periodically publish the UTC epoch to `clock/sync` every 15 minutes.
    ESP32 uses this to correct its RTC drift.
    """
    while True:
        epoch = int(datetime.utcnow().timestamp())
        mqtt_client.publish("clock/sync", json.dumps({"epoch": epoch}))
        time.sleep(15 * 60)

# Launch the sync thread as a daemon so it stops with the main process
threading.Thread(target=mqtt_loop, daemon=True).start()

# ====================
# === FLASK APP ======
# ====================
app = Flask(__name__)

# Local mapping of timezone names to offsets (seconds east of UTC)
timezone_offsets = {
    "UTC": 0,
    "CET": 2 * 3600,      # CEST (UTC+2) in summer
    "Tashkent": 5 * 3600,
    "EST": -4 * 3600      # EDT (UTC-4) in summer
}

# ====================
# === API ENDPOINTS ==
# ====================

@app.route("/api/alarms", methods=["GET"])
def get_alarms():
    """Return the current list of alarms as JSON."""
    return jsonify(alarms)

@app.route("/api/alarms", methods=["POST"])
def add_alarm():
    """
    Add a new alarm to the list and publish to MQTT immediately.
    Expects form or JSON with `time` and `zone`.
    """
    data = request.form or request.get_json()
    t = data.get("time")
    z = data.get("zone")
    if not t or not z or z not in TIMEZONES:
        return "Invalid input", 400

    # Append locally
    alarms.append({"time": t, "zone": z})
    # Publish updated alarms list
    mqtt_client.publish("clock/alarms", json.dumps(alarms))
    # Also trigger immediate time sync
    epoch = int(datetime.utcnow().timestamp())
    mqtt_client.publish("clock/sync", json.dumps({"epoch": epoch}))

    return redirect(url_for("index"))

@app.route("/api/alarms/<int:idx>/delete", methods=["POST"])
def delete_alarm(idx):
    """
    Delete alarm at index `idx`, publish updated list and a sync.
    """
    if 0 <= idx < len(alarms):
        alarms.pop(idx)
        mqtt_client.publish("clock/alarms", json.dumps(alarms))
        epoch = int(datetime.utcnow().timestamp())
        mqtt_client.publish("clock/sync", json.dumps({"epoch": epoch}))
        return redirect(url_for("index"))
    return "Not found", 404

# ====================
# === WEB UI ROUTES ==
# ====================

# HTML template for the main UI; uses Jinja2 syntax
TEMPLATE = '''
<!doctype html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    body { font-family: sans-serif; padding:1rem; max-width:480px; margin:auto; }
    ul { list-style:none; padding:0; }
    li { margin:0.5rem 0; display:flex; justify-content:space-between; }
    form.inline { display:inline; }
    label { display:block; margin:0.5rem 0; }
    button { margin-left:0.5rem; }
    #now { font-size:1.2rem; margin-bottom:1rem; }
  </style>
</head>
<body>
  <h1>Clock Alarm Setter</h1>
  <p id="now">--:--:--</p>
  <button onclick="cycleZone()">Cycle Timezone</button>

  <h2>Active Alarms</h2>
  <ul>
    {% for i, a in enumerate(alarms) %}
      <li>
        {{a.time}} ({{a.zone}})
        <form class="inline" action="/api/alarms/{{i}}/delete" method="post">
          <button>Cancel</button>
        </form>
      </li>
    {% else %}
      <li><em>No alarms set.</em></li>
    {% endfor %}
  </ul>

  <h2>Set New Alarm</h2>
  <form method="post">
    <label>Time: <input type="time" name="time" required></label>
    <label>Zone:
      <select name="zone">
        {% for z in timezones %}
          <option value="{{z}}">{{z}}</option>
        {% endfor %}
      </select>
    </label>
    <button type="submit">Set Alarm</button>
  </form>

  <script>
    function updateNow() {
      fetch('/api/time')
        .then(r=>r.json())
        .then(d=>document.getElementById('now').textContent = d.time+' '+d.zone)
        .catch(_=>{});
    }
    setInterval(updateNow,1000);
    updateNow();
    function cycleZone(){
      fetch('/cycle-zone',{method:'POST'})
        .then(r=>r.json())
        .then(d=>updateNow());
    }
  </script>
</body>
</html>
'''

@app.route("/", methods=["GET", "POST"])
def index():
    """Render the main UI or handle form submissions."""
    if request.method == "POST":
        return add_alarm()
    return render_template_string(
        TEMPLATE,
        alarms=alarms,
        timezones=TIMEZONES,
        enumerate=enumerate
    )

@app.route("/cycle-zone", methods=["POST"])
def cycle_zone():
    """Advance the timezone and broadcast to MQTT."""
    global currentZone
    currentZone = (currentZone + 1) % len(TIMEZONES)
    new_zone = TIMEZONES[currentZone]
    mqtt_client.publish("clock/zone", new_zone)
    return jsonify({"zone": new_zone})

@app.route("/api/time", methods=["GET"])
def api_time():
    """Return the current server time adjusted to the active zone."""
    utc_now = datetime.utcnow()
    offset = timezone_offsets[TIMEZONES[currentZone]]
    local_time = utc_now + timedelta(seconds=offset)
    return jsonify({
        "time": local_time.strftime("%H:%M:%S"),
        "zone": TIMEZONES[currentZone]
    })

# ====================
# === MAIN ==========
# ====================

if __name__ == "__main__":
    # Launch the Flask dev server on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)

# ======================================
# === Requirements file: server/requirements.txt ===
# Flask
# paho-mqtt

