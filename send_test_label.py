import json
import os
import sys
import time
import uuid

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER = os.environ.get("MQTT_BROKER", "mqtt.mfdata.org")
PORT = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "crucible-printers")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_CA_CERTS = os.environ.get("MQTT_CA_CERTS")

CMD_TOPIC = "crucible-printer/ucd1/print"


def send_test_label(mfid: str = "MF0000000000001", name: str = "test sample") -> None:
    if not MQTT_USERNAME or not MQTT_PASSWORD:
        raise SystemExit("MQTT_USERNAME and MQTT_PASSWORD must be set")

    payload = {
        "job_id": str(uuid.uuid4()),
        "mfid": mfid,
        "name": name,
        "ts": time.time(),
    }

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-sender")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(ca_certs=MQTT_CA_CERTS)
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    info = client.publish(CMD_TOPIC, json.dumps(payload), qos=1)
    info.wait_for_publish(timeout=10)
    client.loop_stop()
    client.disconnect()
    print(f"Sent job {payload['job_id']} to {CMD_TOPIC}: {payload}")


if __name__ == "__main__":
    import mfid
    mfid = sys.argv[1] if len(sys.argv) > 1 else mfid.mfid()[0]
    name = sys.argv[2] if len(sys.argv) > 2 else "test sample"
    send_test_label(mfid, name)
