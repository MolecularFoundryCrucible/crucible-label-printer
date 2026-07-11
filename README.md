# Crucible Label Print Server

Crucible print server subscribes to an MQTT command topic and drives a Brother
P-touch via ptouch-print, generating QR + text labels with PIL.

Includes systemd service file, env.sample, and two test publishers.


# Hardware

 * Raspberry Pi 4/5
  * 16GB MicroSD
 * Brother D610BT label printer (Other Brother Tape printers supported)


# Configuring

Configure Raspberry Pi

Install Raspberry Pi OS (64bit Trixie 2026-06) using RPi Imager

Config:

* Username: lab
* password: see secrets
* hostname: `crucible-print1`
* wifi: `lbnl-open`
* enable SSH

add ssh key


Note, on ethernet at LBL IP address resolves to: `crucible-print1.dhcp.lbl.gov`

## packages

```
sudo apt install fonts-dejavu-core
curl -LsSf https://astral.sh/uv/install.sh | sh
```


## set up ptouch-print
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

# Clone Repo
```sh
git clone crucible-label-printer
```


# Setup as a systemd service

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