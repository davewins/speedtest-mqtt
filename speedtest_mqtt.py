#!/usr/bin/env python3
"""
Runs the official Ookla speedtest CLI on a schedule and publishes results
to MQTT with Home Assistant MQTT discovery, so sensors appear automatically
in HA without any manual YAML configuration.
"""

import json
import logging
import os
import subprocess
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("speedtest-mqtt")

MQTT_HOST = os.environ.get("MQTT_BROKER", "192.168.1.5")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER") or None
MQTT_PASS = os.environ.get("MQTT_PASSWORD") or None
TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "speedtest")
INTERVAL_SECONDS = int(os.environ.get("TEST_INTERVAL", str(60 * 60)))  # hourly default

DEVICE_ID = TOPIC_PREFIX
DEVICE_NAME = "Internet Speedtest"
STATE_TOPIC = f"{TOPIC_PREFIX}/state"
AVAILABILITY_TOPIC = f"{TOPIC_PREFIX}/availability"

# (key in results, HA unit, HA device_class, friendly name, HA state_class)
SENSORS = [
    ("download_mbps", "Mbit/s", "data_rate", "Download", "measurement"),
    ("upload_mbps", "Mbit/s", "data_rate", "Upload", "measurement"),
    ("ping_ms", "ms", None, "Ping", "measurement"),
    ("jitter_ms", "ms", None, "Jitter", "measurement"),
    ("packet_loss_pct", "%", None, "Packet Loss", "measurement"),
    ("server_name", None, None, "Server", None),
    ("isp", None, None, "ISP", None),
]


def on_connect(client, userdata, flags, rc):
    # Runs on the first connect and on every automatic reconnect, so
    # availability is restored after the broker has fired the LWT.
    if rc == 0:
        log.info("Connected to MQTT broker")
        client.publish(AVAILABILITY_TOPIC, "online", qos=1, retain=True)
    else:
        log.error("MQTT connect failed, rc=%s", rc)


def build_client():
    client = mqtt.Client(client_id=DEVICE_ID)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=60)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    return client


def publish_discovery(client):
    device_info = {
        "identifiers": [DEVICE_ID],
        "name": DEVICE_NAME,
        "manufacturer": "Ookla (via speedtest-mqtt)",
    }
    for key, unit, device_class, name, state_class in SENSORS:
        config_topic = f"homeassistant/sensor/{TOPIC_PREFIX}/{key}/config"
        payload = {
            "name": name,
            "unique_id": f"{DEVICE_ID}_{key}",
            "state_topic": STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "value_template": f"{{{{ value_json.{key} }}}}",
            "device": device_info,
        }
        if unit:
            payload["unit_of_measurement"] = unit
        if device_class:
            payload["device_class"] = device_class
        if state_class:
            payload["state_class"] = state_class
        client.publish(config_topic, json.dumps(payload), retain=True)
    log.info("Published HA MQTT discovery configs for %d sensors", len(SENSORS))


def run_speedtest():
    log.info("Running speedtest...")
    result = subprocess.run(
        ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(f"speedtest failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)

    download_mbps = round(data["download"]["bandwidth"] * 8 / 1_000_000, 2)
    upload_mbps = round(data["upload"]["bandwidth"] * 8 / 1_000_000, 2)

    return {
        "download_mbps": download_mbps,
        "upload_mbps": upload_mbps,
        "ping_ms": round(data["ping"]["latency"], 1),
        "jitter_ms": round(data["ping"]["jitter"], 1),
        "packet_loss_pct": round(data.get("packetLoss", 0.0), 2),
        "server_name": f"{data['server']['name']} ({data['server']['location']})",
        "isp": data.get("isp", "unknown"),
        "result_url": data.get("result", {}).get("url"),
    }


def main():
    client = build_client()
    publish_discovery(client)

    while True:
        try:
            results = run_speedtest()
            client.publish(STATE_TOPIC, json.dumps(results), retain=True)
            log.info(
                "Published: %.1f Mbps down / %.1f Mbps up / %.1f ms ping",
                results["download_mbps"], results["upload_mbps"], results["ping_ms"],
            )
        except Exception as e:
            log.error("Speedtest run failed: %s", e)

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
