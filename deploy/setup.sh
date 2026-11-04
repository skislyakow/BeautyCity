#!/bin/bash
set -e

PROJECT_DIR="/var/www/beauty"
REPO_URL="git@github.com:skislyakow/BeautyCity.git"

echo "=== 1. System packages ==="
apt update
apt install -y nginx certbot python3-certbot-nginx git curl

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "=== 2. Create project directory ==="
mkdir -p $PROJECT_DIR
mkdir -p /var/log/beauty

echo "=== 3. Clone repo ==="
if [ -d "$PROJECT_DIR/.git" ]; then
    cd $PROJECT_DIR && git pull origin main
else
    git clone $REPO_URL $PROJECT_DIR
fi

echo "=== 4. Virtual env ==="
cd $PROJECT_DIR
uv sync --frozen --no-dev

echo "=== 5. .env ==="
if [ ! -f ".env" ]; then
    cat > .env << 'ENVEOF'
DJANGO_SECRET_KEY=CHANGE_ME_TO_RANDOM_SECRET
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=beauty.kislyakov.pro,localhost
ENVEOF
    echo ".env created — edit it with real values!"
fi

echo "=== 6. Collect static & migrate ==="
uv run --frozen --no-dev python manage.py collectstatic --noinput
uv run --frozen --no-dev python manage.py migrate --noinput

echo "=== 7. Copy systemd services ==="
cp deploy/beauty.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable beauty

echo "=== 8. Copy nginx config ==="
cp deploy/beauty.kislyakov.pro /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/beauty.kislyakov.pro /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== 9. SSL ==="
certbot --nginx -d beauty.kislyakov.pro --non-interactive --agree-tos -m admin@kislyakov.pro || true

echo "=== 10. Start service ==="
systemctl start beauty

echo ""
echo "=== Done! ==="
echo "Check status: systemctl status beauty"
echo "Site: https://beauty.kislyakov.pro"
