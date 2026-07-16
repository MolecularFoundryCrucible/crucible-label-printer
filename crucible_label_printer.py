import json
import os
import queue
import socket
import subprocess
import threading
import time
import logging

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crucible-printserver")

BROKER = os.environ.get("MQTT_BROKER", "mqtt.mfdata.org")
PORT = int(os.environ.get("MQTT_PORT", "8883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "crucible-printers")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_CA_CERTS = os.environ.get("MQTT_CA_CERTS")  # optional path to CA bundle
PRINTER_NAME = os.environ.get("PRINTER_NAME","crucible-printer/printer1")
CMD_TOPIC = PRINTER_NAME + "/print"
STATUS_TOPIC = PRINTER_NAME + "/status"
RESULT_TOPIC = PRINTER_NAME + "/result"

job_queue: "queue.Queue[dict]" = queue.Queue()
seen_job_ids: dict[str, float] = {}  # for dedupe
DEDUPE_WINDOW = 60  # seconds


def get_ip_address() -> str:
    # Open a UDP socket to a public address to discover the outbound IP.
    # No packets are actually sent.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "unknown"
    finally:
        s.close()


def get_fqdn(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return socket.getfqdn()


IP_ADDRESS = get_ip_address()
HOSTNAME = get_fqdn(IP_ADDRESS)
print("HOSTNAME", HOSTNAME)


def status_payload(state: str, **extra) -> str:
    return json.dumps({
        "state": state,
        "hostname": HOSTNAME,
        "ip": IP_ADDRESS,
        **extra,
    })


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        log.info("Connected to broker")
        client.subscribe(CMD_TOPIC, qos=1)
        client.publish(STATUS_TOPIC, status_payload("online"), qos=1, retain=True)
    else:
        log.error("Connect failed: %s", reason_code)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.warning("Bad payload: %s", e)
        return

    job_id = payload.get("job_id")
    now = time.time()
    # dedupe
    if job_id:
        if job_id in seen_job_ids and now - seen_job_ids[job_id] < DEDUPE_WINDOW:
            log.info("Duplicate job %s ignored", job_id)
            return
        seen_job_ids[job_id] = now

    log.info("Queued job %s", job_id)
    job_queue.put(payload)


def print_label(job: dict) -> None:
    """Replace this with your actual printer driver call."""
    mfid_str = job["mfid"]
    name_str = job['name']

    from image_print import make_25mm_image, make_qr
    
    qr_img = make_qr(mfid_str, qr_size=(100,100))

    # label image
    make_25mm_image(qr_img, [name_str, mfid_str[0:13]], "label.png")

    subprocess.run(
        ["ptouch-print", "--image", "label.png"],
        check=True,
        capture_output=True,
        text=True,
    )


def worker(client: mqtt.Client) -> None:
    while True:
        job = job_queue.get()
        job_id = job.get("job_id")
        try:
            print_label(job)
            result = {"job_id": job_id, "status": "ok"}
        except Exception as e:
            log.exception("Print failed for %s", job_id)
            result = {"job_id": job_id, "status": "error", "error": str(e)}
        client.publish(RESULT_TOPIC, json.dumps(result), qos=1)
        job_queue.task_done()


def heartbeat(client: mqtt.Client) -> None:
    while True:
        client.publish(STATUS_TOPIC, status_payload("online", ts=time.time()),
                       qos=0, retain=True)
        time.sleep(30)


def main():
    client_id = os.environ.get("MQTT_CLIENT_ID") or PRINTER_NAME.replace("/", "-")
    log.info("Connecting with client_id=%s", client_id)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    client.on_connect = on_connect
    client.on_message = on_message

    if not MQTT_USERNAME or not MQTT_PASSWORD:
        raise SystemExit("MQTT_USERNAME and MQTT_PASSWORD must be set")
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set(ca_certs=MQTT_CA_CERTS)  # uses system CAs when ca_certs is None

    # Last Will: broker publishes this if we drop unexpectedly
    client.will_set(STATUS_TOPIC, status_payload("offline"), qos=1, retain=True)

    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # start worker + heartbeat threads
    threading.Thread(target=worker, args=(client,), daemon=True).start()
    threading.Thread(target=heartbeat, args=(client,), daemon=True).start()

    client.connect(BROKER, PORT, keepalive=60)
    client.loop_forever()  # handles reconnects automatically


if __name__ == "__main__":
    main()