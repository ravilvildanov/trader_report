# 🚀 Деплой на Heroku

## 📋 Подготовка файлов

### 1. Создайте `Procfile`
```bash
echo "web: streamlit run streamlit_app.py --server.port=\$PORT --server.address=0.0.0.0" > Procfile
```

### 2. Создайте `setup.sh`
```bash
mkdir -p ~/.streamlit/
echo "\
[server]\n\
headless = true\n\
port = \$PORT\n\
enableCORS = false\n\
" > ~/.streamlit/config.toml
```

### 3. Обновите `requirements.txt`
```txt
streamlit>=1.28.0
pandas>=1.5.0
plotly>=5.15.0
openpyxl>=3.0.10
reportlab>=3.6.12
PyPDF2>=3.0.0
pypdf>=3.15.0
```

## 🚀 Деплой

### 1. Установите Heroku CLI
```bash
# macOS
brew install heroku/brew/heroku

# Или скачайте с heroku.com
```

### 2. Войдите в Heroku
```bash
heroku login
```

### 3. Создайте приложение
```bash
heroku create freedom-calculator-app
```

### 4. Деплой
```bash
git add .
git commit -m "Prepare for Heroku deployment"
git push heroku main
```

### 5. Откройте приложение
```bash
heroku open
```

## 💰 Стоимость
- **Free tier**: больше не доступен
- **Basic Dyno**: $7/месяц
- **Standard Dyno**: $25/месяц

---

## 🎯 Итоговый URL будет выглядеть так:
**https://freedom-calculator-app.herokuapp.com**
