# DEPLOYMENT_GUIDE.md

## Guía de Deployment - Kraken AI Trading Bot

### 🚀 Deployment Automático

El deployment ocurre automáticamente al hacer push a `main`:

1. GitHub Actions ejecuta tests
2. Si pasan, se conecta al VPS via SSH
3. Actualiza código y dependencias
4. Reinicia servicios
5. Verifica que todo esté funcionando

### 🔧 Configuración Manual del VPS (Primera Vez)

#### 1. Preparar Servidor
```bash
# SSH al VPS
ssh root@YOUR_VPS_IP

# Actualizar sistema
apt update && apt upgrade -y

# Instalar requisitos
apt install -y python3.12 python3.12-venv python3.12-dev
apt install -y nginx postgresql postgresql-contrib
apt install -y certbot python3-certbot-nginx
apt install -y git curl wget
```

#### 2. Clonar Repositorio
```bash
# Crear directorio
mkdir -p /var/www/kraken-ai-trading-bot
cd /var/www/kraken-ai-trading-bot

# Clonar
git clone https://github.com/orlandobatistac/botija.git .
```

#### 3. Crear Virtual Environment
```bash
python3.12 -m venv /root/.venv_kraken
source /root/.venv_kraken/bin/activate

# Instalar dependencias
pip install -r backend/requirements.txt
```

#### 4. Configurar Variables de Entorno
```bash
cp .env.example .env
nano .env
# Editar con valores reales:
# - KRAKEN_API_KEY
# - KRAKEN_SECRET_KEY
# - OPENAI_API_KEY
# - TELEGRAM_TOKEN
# - SECRET_KEY (generar uno fuerte)
```

#### 5. Crear Systemd Service
```bash
cat > /etc/systemd/system/kraken-ai-trading-bot.service << EOF
[Unit]
Description=Kraken AI Trading Bot
After=network.target

[Service]
Type=notify
User=root
WorkingDirectory=/var/www/kraken-ai-trading-bot/backend
Environment="PATH=/root/.venv_kraken/bin"
ExecStart=/root/.venv_kraken/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Habilitar servicio
systemctl daemon-reload
systemctl enable kraken-ai-trading-bot.service
systemctl start kraken-ai-trading-bot.service
```

#### 6. Configurar Nginx
```bash
cat > /etc/nginx/sites-available/kraken-ai-trading-bot << EOF
server {
    listen 80;
    server_name YOUR_DOMAIN.com;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Habilitar sitio
ln -s /etc/nginx/sites-available/kraken-ai-trading-bot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

#### 7. SSL/TLS con Let's Encrypt
```bash
certbot --nginx -d YOUR_DOMAIN.com

# Auto-renew
systemctl enable certbot.timer
systemctl start certbot.timer
```

#### 8. Crear PostgreSQL Database (Producción)
```bash
sudo -u postgres psql

CREATE USER kraken_user WITH PASSWORD 'strong_password';
CREATE DATABASE kraken_trading OWNER kraken_user;
GRANT ALL PRIVILEGES ON DATABASE kraken_trading TO kraken_user;
\q
```

### 📋 Configurar GitHub Secrets

En GitHub → Settings → Secrets and variables:

```
VPS_HOST = 123.45.67.89
VPS_USER = root
VPS_SSH_KEY = (contenido de tu clave privada SSH)
VPS_PORT = 22 (opcional)
```

### 🚀 Realizar Deployment

```bash
# En local, hacer push a main
git push origin main

# GitHub Actions automáticamente:
# 1. Ejecuta tests
# 2. Si todo OK, deploya a VPS
# 3. Reinicia servicios

# Ver progreso en GitHub → Actions
```

### 📊 Monitorear en VPS

```bash
# Ver estado del servicio
systemctl status kraken-ai-trading-bot

# Ver logs
sudo journalctl -u kraken-ai-trading-bot -f

# Ver logs de Nginx
sudo tail -f /var/log/nginx/error.log

# Verificar que está escuchando
curl http://localhost:8001/health
```

### 🔄 Rollback a Versión Anterior

```bash
# En el VPS
cd /var/www/kraken-ai-trading-bot
git log --oneline | head -20
git revert COMMIT_HASH
systemctl restart kraken-ai-trading-bot
```

### 📦 Backup y Mantenimiento

```bash
# Backup de database
pg_dump kraken_trading > kraken_backup_$(date +%Y%m%d).sql

# Limpiar logs viejos
journalctl --vacuum-time=30d

# Actualizar certificado SSL
certbot renew --dry-run
```

---

Más detalles en `/workspaces/botija/docs/`
