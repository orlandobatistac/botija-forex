#!/bin/bash
# Setup SSL/TLS con Let's Encrypt para Nginx

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="${1:?Domain required. Usage: ./setup-ssl.sh example.com}"
VPS_IP="74.208.146.203"
NGINX_CONFIG="/etc/nginx/sites-available/botija"
EMAIL="${2:-admin@${DOMAIN}}"

echo -e "${YELLOW}🔐 Configurando SSL/TLS con Let's Encrypt${NC}"
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# 1. Install certbot
echo -e "${YELLOW}1️⃣ Instalando certbot...${NC}"
apt-get update
apt-get install -y certbot python3-certbot-nginx

# 2. Create certificate
echo -e "${YELLOW}2️⃣ Generando certificado SSL...${NC}"
certbot certonly \
  --nginx \
  --non-interactive \
  --agree-tos \
  --email "$EMAIL" \
  -d "$DOMAIN" \
  -d "www.$DOMAIN" \
  || echo -e "${RED}⚠️  Certbot falló. Verifica que DNS apunte correctamente a $VPS_IP${NC}"

# 3. Update Nginx config for HTTPS
echo -e "${YELLOW}3️⃣ Actualizando configuración de Nginx...${NC}"

# Backup original
cp "$NGINX_CONFIG" "${NGINX_CONFIG}.backup.$(date +%s)"

# Create new config with SSL
cat > "$NGINX_CONFIG" << 'NGINX_CONFIG_EOF'
# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name _;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name _;
    
    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN_PLACEHOLDER/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Root
    root /root/botija/frontend;
    
    # Serve index.html
    location / {
        try_files $uri $uri/ /index.html;
        expires 1h;
    }
    
    # Static files with long cache
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    
    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8002;
    }
    
    # Deny access to dot files
    location ~ /\. {
        deny all;
    }
}
NGINX_CONFIG_EOF

# Replace domain placeholder
sed -i "s|DOMAIN_PLACEHOLDER|${DOMAIN}|g" "$NGINX_CONFIG"

# 4. Test and reload Nginx
echo -e "${YELLOW}4️⃣ Validando configuración de Nginx...${NC}"
nginx -t

echo -e "${YELLOW}5️⃣ Recargando Nginx...${NC}"
systemctl reload nginx

# 5. Setup auto-renewal
echo -e "${YELLOW}6️⃣ Configurando renovación automática...${NC}"
systemctl enable certbot.timer
systemctl start certbot.timer

# 6. Show renewal schedule
echo ""
echo -e "${GREEN}✅ SSL/TLS configurado exitosamente${NC}"
echo ""
echo "Details:"
certbot certificates
echo ""
echo "Auto-renewal:"
systemctl status certbot.timer
echo ""
echo -e "${GREEN}🎉 Tu bot es ahora accesible en: https://${DOMAIN}${NC}"
echo ""
echo "Próximos pasos:"
echo "1. Verifica que DNS apunte a 74.208.146.203"
echo "2. Accede a https://${DOMAIN} en el navegador"
echo "3. Los certificados se renovarán automáticamente"
