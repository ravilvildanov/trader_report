# 🚀 Деплой на VPS сервер

## 📋 Требования к серверу
- **ОС**: Ubuntu 20.04+ или CentOS 8+
- **RAM**: минимум 2GB
- **CPU**: 1 ядро
- **Диск**: 20GB
- **Сеть**: статический IP

## 🛠️ Настройка сервера

### 1. Подключение к серверу
```bash
ssh root@your-server-ip
```

### 2. Обновление системы
```bash
apt update && apt upgrade -y
```

### 3. Установка Python и зависимостей
```bash
apt install python3 python3-pip python3-venv nginx -y
```

### 4. Создание пользователя для приложения
```bash
adduser streamlit
usermod -aG sudo streamlit
su - streamlit
```

### 5. Клонирование репозитория
```bash
git clone https://github.com/your-username/FreedomCalculator.git
cd FreedomCalculator
```

### 6. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🚀 Запуск приложения

### 1. Создание systemd сервиса
```bash
sudo nano /etc/systemd/system/freedom-calculator.service
```

Содержимое файла:
```ini
[Unit]
Description=Freedom Calculator Streamlit App
After=network.target

[Service]
Type=simple
User=streamlit
WorkingDirectory=/home/streamlit/FreedomCalculator
Environment=PATH=/home/streamlit/FreedomCalculator/venv/bin
ExecStart=/home/streamlit/FreedomCalculator/venv/bin/streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

### 2. Запуск сервиса
```bash
sudo systemctl daemon-reload
sudo systemctl enable freedom-calculator
sudo systemctl start freedom-calculator
sudo systemctl status freedom-calculator
```

## 🌐 Настройка Nginx

### 1. Создание конфигурации
```bash
sudo nano /etc/nginx/sites-available/freedom-calculator
```

Содержимое:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Активация сайта
```bash
sudo ln -s /etc/nginx/sites-available/freedom-calculator /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 3. Настройка SSL (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com
```

## 🔧 Мониторинг и логи

### Просмотр логов
```bash
sudo journalctl -u freedom-calculator -f
```

### Перезапуск приложения
```bash
sudo systemctl restart freedom-calculator
```

## 💰 Стоимость
- **VPS**: $5-20/месяц (DigitalOcean, Linode, Vultr)
- **Домен**: $10-15/год
- **SSL**: бесплатно (Let's Encrypt)

---

## 🎯 Итоговый URL будет выглядеть так:
**https://your-domain.com**

## ✨ Преимущества VPS:
- 🆓 **Полный контроль** над сервером
- 💰 **Низкая стоимость** в долгосрочной перспективе
- 🔒 **Безопасность** на уровне сервера
- 📊 **Мониторинг** и логи
- 🚀 **Масштабируемость**
