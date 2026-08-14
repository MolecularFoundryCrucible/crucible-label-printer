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
* hostname: `crucible-print1` or similar
* wifi: `lbnl-open`
* enable SSH with password

Note, on ethernet at LBL IP address resolves to: `crucible-print1.dhcp.lbl.gov`

### First ssh login:

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





## Manual Install (replaced by Ansible now)

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


# Ansible

Most of the previous steps have been now incorporated into an Ansible playbook in `ansible/`

You should run ansible on a machine on the tailnet, `headscale-server` is a good option since it is part of the crucible-printers tailnet.

`ansible/load-ssh-key.sh` will grab the SSH private key from Google Secret Manager and put in the active `ssh-agent` for the terminal session.

```sh
cd ansible/
sh ./load-ssh-key.sh
ansible-playbook deploy.yaml
```

Note that with tailnet configuration, we should run the ansible commands on `headscale.mfdata.org` which is also a noder on the `crucible-printer` tailnet. 

Use IAP SSH access to get `headscale.mfdata.org` then login `glcloud auth login` to get access to secrets needed for ansible commands.


