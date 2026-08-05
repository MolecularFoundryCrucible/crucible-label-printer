# Set Up a HeadScale VM in GCP

This VM will allow portable access to all the printer nodes for ansible actions via tailscale network regardless of their physical location.

## Create a dedicated VPC network and subnet

```sh
$$ gcloud compute networks create headscale-net --subnet-mode=custom

Created [https://www.googleapis.com/compute/v1/projects/mf-crucible/global/networks/headscale-net].
NAME           SUBNET_MODE  BGP_ROUTING_MODE  IPV4_RANGE  GATEWAY_IPV4  INTERNAL_IPV6_RANGE
headscale-net  CUSTOM       REGIONAL

Instances on this network will not be reachable until firewall rules
are created. As an example, you can allow all internal traffic between
instances as well as SSH, RDP, and ICMP by running:

$ gcloud compute firewall-rules create <FIREWALL_NAME> --network headscale-net --allow tcp,udp,icmp --source-ranges <IP_RANGE>
$ gcloud compute firewall-rules create <FIREWALL_NAME> --network headscale-net --allow tcp:22,tcp:3389,icmp


$$ gcloud compute networks subnets create headscale-subnet \
  --network=headscale-net \
  --region=us-central1 \
  --range=10.10.0.0/24

Created [https://www.googleapis.com/compute/v1/projects/mf-crucible/regions/us-central1/subnetworks/headscale-subnet].
NAME              REGION       NETWORK        RANGE         STACK_TYPE  IPV6_ACCESS_TYPE  INTERNAL_IPV6_PREFIX  EXTERNAL_IPV6_PREFIX
headscale-subnet  us-central1  headscale-net  10.10.0.0/24  IPV4_ONLY
  
```

## Reserve a static external IP

```sh
$$ gcloud compute addresses create headscale-ip --region=us-central1

Created [https://www.googleapis.com/compute/v1/projects/mf-crucible/regions/us-central1/addresses/headscale-ip].
```

## Create the VM in the new network

```sh
$$ gcloud compute instances create headscale-server \
  --zone=us-central1-a \
  --machine-type=e2-small \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --network=headscale-net \
  --subnet=headscale-subnet \
  --address=headscale-ip \
  --tags=headscale-server

NAME              ZONE           MACHINE_TYPE  PREEMPTIBLE  INTERNAL_IP  EXTERNAL_IP     STATUS
headscale-server  us-central1-a  e2-small                   10.10.0.2    34.136.197.107  RUNNING
```

## Create firewall rules scoped to this new network only

SSH access via IAP only, no open internet exposure:

```sh
$$ gcloud compute firewall-rules create allow-iap-ssh \
  --network=headscale-net \
  --allow=tcp:22 \
  --target-tags=headscale-server \
  --source-ranges=35.235.240.0/20

  Creating firewall...⠹Created [https://www.googleapis.com/compute/v1/projects/mf-crucible/global/firewalls/allow-iap-ssh]. 
Creating firewall...done.                                                                                                 
NAME           NETWORK        DIRECTION  PRIORITY  ALLOW   DENY  DISABLED
allow-iap-ssh  headscale-net  INGRESS    1000      tcp:22        False
```

HTTPS for Headscale's control/API traffic:

```sh
% gcloud compute firewall-rules create allow-headscale-https \
  --network=headscale-net \
  --allow=tcp:443 \
  --target-tags=headscale-server \
  --source-ranges=0.0.0.0/0

Creating firewall...⠹Created [https://www.googleapis.com/compute/v1/projects/mf-crucible/global/firewalls/allow-headscale-https].
Creating firewall... done.                                                                                                 
NAME                   NETWORK        DIRECTION  PRIORITY  ALLOW    DENY  DISABLED
allow-headscale-https  headscale-net  INGRESS    1000      tcp:443        False
```


## Get static IP and put in DNS

```sh
gcloud compute addresses describe headscale-ip --region=us-central1 --format="get(address)"

34.136.197.107
```

Go to cloudflare console, add DNS record:

```
headscale.mfdata.org
A
34.136.197.107
DNS only
```

## Confirm IAP SSH access and system architecture

```sh
% gcloud compute ssh headscale-server --zone=us-central1-a --tunnel-through-iap
$ dpkg --print-architecture
amd64
```

## Cloudflare and Certbot

Cloudflare API token

In Cloudflare → My Profile → API Tokens → Create Token → use the **"Edit zone DNS"** template, scoped to the `mfdata.org` zone. Copy the token.

```
account: b029a96...
token: cfut_...
```

On the VM:

```bash
sudo mkdir -p /root/.secrets
sudo nano /root/.secrets/cloudflare.ini
```

Contents:

```
dns_cloudflare_api_token = YOUR_TOKEN_HERE
```

Lock it down (certbot will warn otherwise):

```bash
sudo chmod 600 /root/.secrets/cloudflare.ini
```

Install certbot

```bash
sudo apt update
sudo apt upgrade
sudo apt install -y certbot python3-certbot-dns-cloudflare
```

Get the certificate

```bash
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /root/.secrets/cloudflare.ini \
  --dns-cloudflare-propagation-seconds 30 \
  -d headscale.mfdata.org \
  --agree-tos \
  -m edbarnard@gmail.com \
  --non-interactive

Saving debug log to /var/log/letsencrypt/letsencrypt.log
Account registered.
Requesting a certificate for headscale.mfdata.org
Waiting 30 seconds for DNS changes to propagate

Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/headscale.mfdata.org/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/headscale.mfdata.org/privkey.pem
This certificate expires on 2026-11-03.
These files will be updated when the certificate renews.
Certbot has set up a scheduled task to automatically renew this certificate in the background.
```

Certs land in `/etc/letsencrypt/live/headscale.mfdata.org/`. Because this is DNS-01, port 80 never needs to be open.

## Install headscale

```sh
HEADSCALE_VERSION="0.29.3"
wget --output-document=headscale.deb \
  "https://github.com/juanfont/headscale/releases/download/v${HEADSCALE_VERSION}/headscale_${HEADSCALE_VERSION}_linux_amd64.deb"
sudo apt install ./headscale.deb

----------------------------------------------------------------------
 headscale package has been successfully installed.

 Please follow the next steps to start the software:

    sudo systemctl enable headscale
    sudo systemctl start headscale

 Configuration settings can be adjusted here:
    /etc/headscale/config.yaml

----------------------------------------------------------------------

$ sudo systemctl enable headscale
$ sudo systemctl start headscale

Created symlink /etc/systemd/system/multi-user.target.wants/headscale.service → /lib/systemd/system/headscale.service.

```

## Configure headscale

`sudo nano /etc/headscale/config.yaml`:

These are the import settings to change

```yaml
server_url: https://headscale.mfdata.org
listen_addr: 0.0.0.0:443

tls_cert_path: /etc/headscale/certs/fullchain.pem
tls_key_path: /etc/headscale/certs/privkey.pem

database:

  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite

dns:
  magic_dns: true
  base_domain: ts.mfdata.org
  nameservers:
    global:
      - 1.1.1.1
      - 8.8.8.8
```

## setup certs to be copied to headscale accessible folder

```
sudo mkdir -p /etc/headscale/certs
```

Script when certificate renews
```
sudo tee /etc/letsencrypt/renewal-hooks/deploy/copy-to-headscale.sh <<'EOF'
#!/bin/bash
cp /etc/letsencrypt/live/headscale.mfdata.org/fullchain.pem /etc/headscale/certs/
cp /etc/letsencrypt/live/headscale.mfdata.org/privkey.pem /etc/headscale/certs/
chown headscale:headscale /etc/headscale/certs/*.pem
chmod 600 /etc/headscale/certs/*.pem
systemctl restart headscale
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/copy-to-headscale.sh
```

Test to verify that cert renewal works

```
sudo certbot renew --dry-run
Saving debug log to /var/log/letsencrypt/letsencrypt.log

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Processing /etc/letsencrypt/renewal/headscale.mfdata.org.conf
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Account registered.
Simulating renewal of an existing certificate for headscale.mfdata.org
Waiting 30 seconds for DNS changes to propagate

- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Congratulations, all simulated renewals succeeded: 
  /etc/letsencrypt/live/headscale.mfdata.org/fullchain.pem (success)
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
```

# Starting headscale

```sh
sudo systemctl restart headscale
sudo systemctl status headscale
sudo journalctl -u headscale -f
```

verify its reachable from the internet:

```
curl -v https://headscale.mfdata.org/health
```
You should get a valid TLS handshake and a response, confirming the cert chain and Headscale's HTTP server are both working correctly.

## Configure tailnet

```
sudo headscale users create crucible-printers
sudo headscale preauthkeys create --user 1 --expiration 24h --reusable
```

sudo headscale preauthkeys create --user 1 --expiration 24h --reusable
hskey-auth-tcoNtcewEesy-...

On each node:

```
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --login-server=https://headscale.mfdata.org --authkey=<your-preauth-key>
```