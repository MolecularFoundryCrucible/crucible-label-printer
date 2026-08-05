import json
import os
import sys
import time
import uuid

import paho.mqtt.publish as publish
from dotenv import load_dotenv

load_dotenv()

BROKER = os.environ.get("MQTT_BROKER", "mqtt.mfdata.org")
PORT = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "crucible-printers")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_CA_CERTS = os.environ.get("MQTT_CA_CERTS")

CMD_TOPIC = "crucible-printer/ucd1/print"
CMD_TOPIC = "crucible-printer/b30-113/print"

def send_test_label(mfid: str = "MF0000000000001", name: str = "test sample") -> None:
    if not MQTT_USERNAME or not MQTT_PASSWORD:
        raise SystemExit("MQTT_USERNAME and MQTT_PASSWORD must be set")

    payload = {
        "job_id": str(uuid.uuid4()),
        "mfid": mfid,
        "name": name,
        "ts": time.time(),
    }

    publish.single(
        topic=CMD_TOPIC,
        payload=json.dumps(payload),
        qos=1,
        hostname=BROKER,
        port=PORT,
        client_id="test-sender-single",
        auth={"username": MQTT_USERNAME, "password": MQTT_PASSWORD},
        tls={"ca_certs": MQTT_CA_CERTS},
    )
    print(f"Sent job {payload['job_id']} to {CMD_TOPIC}: {payload}")


if __name__ == "__main__":
    import mfid as mfid_mod
    mfid = sys.argv[1] if len(sys.argv) > 1 else mfid_mod.mfid()[0]
    name = sys.argv[2] if len(sys.argv) > 2 else "test sample"
    send_test_label(mfid, name)
