# Crucible Label Print Server

Crucible print server subscribes to an MQTT command topic and drives a Brother
P-touch via ptouch-print, generating QR + text labels with PIL.

Includes systemd service file, env.sample, and two test publishers.


# Hardware

 * Raspberry Pi 4/5
  * 16GB MicroSD
 * Brother PT-710BT label printer (Other Brother Tape printers supported, D610BT tested)

# Software

 * Raspberry Pi OS Trixie Lite
 * Print driver / CLI: https://dominic.familie-radermacher.ch/projekte/ptouch-print/
    https://git.familie-radermacher.ch/linux/ptouch-print.git
 * fleet management: Ansible


# Configuring


### Install Raspberry Pi OS Lite (64bit Trixie 2026-06) using RPi Imager

Config:

* Username: `lab`
* password: (GCP secret`crucible-print-lab-password`)
* hostname: `crucible-print-42` or similar
* wifi: `lbnl-open`
* enable SSH with password

Note, on ethernet at LBL IP address resolves to: `crucible-print-42.dhcp.lbl.gov` or `crucible-print-42.dhcp.lbl.us`

### First ssh login (may have to log in twice):

ssh lab@crucible-print-42.dhcp.lbl.gov (try .us if it does not work)

#### add ssh key:

Note: the ssh key created and stored in google cloud secrets using `ansible/create-ssh-key-store-google-secret.sh`

write the public key into `/home/lab/.ssh/authorized_keys`

Public key
`ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPi8DzXTC0ZXdXHmo0QiDZYYL43lt/nYRWYGqTQc+N+i crucible-print-ssh-key-for-ansible
`

or use:
```sh
gcloud secrets versions access latest --secret=crucible-print-ssh-key-pub --project="mf-crucible" \
  | ssh lab@PRINT_HOST "cat >> ~/.ssh/authorized_keys"
```

#### connect to tailnet

To get remote access when directly connected to LAN network, we use tailscale / headscale VPN. 

On our headscale server (on GCP), get a temporary pre-authorization key:

```sh
headscale-server$ sudo headscale preauthkeys create --user 1 --expiration 24h --reusable
```

On new raspberry pi:

Install tailscale client and register node with headscale server:

```sh
new-pi$ curl -fsSL https://tailscale.com/install.sh | sh
new-pi$ sudo tailscale up --login-server=https://headscale.mfdata.org --authkey=<your-preauth-key>
```

and verify connection:

```sh
new-pi$ tailscale whoami
Machine:
  Name:          crucible-print-b67-1201.ts.mfdata.org
  ID:            4
  Addresses:     [100.64.0.4/32 fd7a:115c:a1e0::4/128]
User:
  Name:     crucible-printers
  ID:       1
```

# Ansible (preferred deployment method)

Most of the manual steps below have been incorporated into an Ansible playbook in `ansible/`.
This is the preferred way to set up a Pi once SSH key + Tailscale are done above — the "Manual
Install" section further down is kept only as a fallback/reference.

You should run ansible from a machine that's already on the tailnet — `headscale-server` is a
good option since it's a member of the `crucible-printers` tailnet. Clone the
`crucible-label-printer` repo onto that control machine.

```sh
# on headscale-server (or another tailnet-joined control machine):
git clone https://github.com/MolecularFoundryCrucible/crucible-label-printer.git
cd crucible-label-printer/ansible
```

Add the new Pi to `inventory.yaml` under `crucible_print_servers.hosts`, using the tailnet
hostname from `tailscale status` and a `print_id` of your choosing (this becomes the MQTT topic
`crucible-printer/<print_id>/print`, and is what you'll set as `PRINTER_ID` in
`crucible-upload-uis`):

```yaml
crucible-print-42.ts.mfdata.org:
  print_id: <your-print-id>
  hardware: rpi5-4gb
```

`ansible/load-ssh-key.sh` grabs the fleet SSH private key from Google Secret Manager and loads
it into the active `ssh-agent` for the terminal session. Run:

```sh
source ./load-ssh-key.sh
```

If this fails with `agent refused operation`, it usually means `$SSH_AUTH_SOCK` was already
pointing at a stale or forwarded agent that won't accept new keys. Start a fresh one and re-run:

```sh
eval "$(ssh-agent -s)"
source ./load-ssh-key.sh
```

Make sure `gcloud auth login` has been run on the control machine (needed both for the SSH key
fetch above and for the MQTT password secret pulled during the playbook run), and that
`ansible` itself is installed (`ansible --version`; `sudo apt install ansible` if missing).

Then run the playbook — `--limit` scopes it to just your new host, useful when testing a single
new Pi without touching the rest of the fleet:

```sh
ansible-playbook deploy.yaml --limit crucible-print-51.ts.mfdata.org --ask-become-pass
```

When prompted for the **BECOME password**, that's the `lab` user's own sudo password on the
target Pi (the same one set during imaging).

After it completes, verify on the Pi:

```sh
systemctl status crucible-label-printer     # check it's running
journalctl -u crucible-label-printer -f     # tail logs, confirm it connects/subscribes
```

## Manual Install (fallback / reference — Ansible is preferred, see above)

### packages

```
sudo apt install fonts-dejavu-core
curl -LsSf https://astral.sh/uv/install.sh | sh
```


### set up ptouch-print
```
# dependencies
sudo apt update
sudo apt install git build-essential autoconf autopoint pkg-config \
  libgd-dev libusb-1.0-0-dev gettext

# get the source
git clone https://git.familie-radermacher.ch/linux/ptouch-print.git
cd ptouch-print

# build
autoreconf -fi
./configure
make
sudo make install
```

or snap

```
sudo apt install snapd
sudo snap install ptouch-print
sudo snap connect ptouch-print:raw-usb
sudo usermod -aG lp lab # give access to device
```

### Clone Repo
```sh
git clone crucible-label-printer
```


### Setup as a systemd service

```sh
sudo systemctl enable /home/lab/crucible-label-printer/crucible-label-printer.service
sudo systemctl start crucible-label-printer.service
```

Follow ups:
```sh
systemctl status crucible-label-printer     # check it's running
journalctl -u crucible-label-printer -f     # tail logs
sudo systemctl daemon-reload                # after editing the .service file
sudo systemctl restart crucible-label-printer
sudo systemctl disable crucible-label-printer   # remove from boot
```

### Manual testing

Once the service is running, two scripts under the repo root can publish a test print job
directly (edit the hardcoded `CMD_TOPIC`/topic in either script to match your `print_id` first):

```sh
uv run python send_test_label_single.py "MF0000000000001" "test sample"
```

Watch `journalctl -u crucible-label-printer -f` on the Pi to confirm the job is received and
printed. To sanity-check the printer/USB/driver chain in isolation, without MQTT involved at
all, run directly on the Pi:

```sh
ptouch-print --info
ptouch-print --text "hello"
```

