# SSL Certificate Setup

Place your SSL certificates in this directory:

- `fullchain.pem` — Full certificate chain
- `privkey.pem` — Private key

## Using Let's Encrypt (recommended)

```bash
# Install certbot
sudo apt install certbot

# Generate certificates
sudo certbot certonly --standalone -d yourdomain.com

# Copy to this directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./
```

## For local development

Generate self-signed certificates:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem -out fullchain.pem \
  -subj '/CN=localhost'
```
