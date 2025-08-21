# 🚀 Развёртывание на Streamlit Cloud

## 📋 Требования

Для развёртывания на Streamlit Cloud используйте файл `requirements_streamlit.txt` вместо основного `requirements.txt`.

## 🔧 Настройка Streamlit Cloud

### 1. **Подготовка репозитория**

Убедитесь, что в корне репозитория есть:
- `streamlit_app.py` - основное приложение
- `requirements_streamlit.txt` - зависимости для Streamlit
- `.streamlit/config.toml` - конфигурация Streamlit
- `src/` - модули приложения

### 2. **Файл зависимостей**

Используйте `requirements_streamlit.txt`:
```txt
# Зависимости для Streamlit Cloud
streamlit>=1.28.0
pandas>=1.3.0
openpyxl>=3.0.0
reportlab>=3.6.0
plotly>=5.0.0
PyPDF2>=3.0.0
```

### 3. **Конфигурация Streamlit**

Файл `.streamlit/config.toml`:
```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

## 🌐 Развёртывание

### **Вариант 1: Streamlit Cloud (рекомендуется)**

1. Перейдите на [share.streamlit.io](https://share.streamlit.io)
2. Войдите через GitHub
3. Выберите репозиторий `FreedomCalculator`
4. Укажите путь к файлу: `streamlit_app.py`
5. В разделе "Advanced settings":
   - **Requirements file:** `requirements_streamlit.txt`
   - **Python version:** 3.9
6. Нажмите "Deploy!"

### **Вариант 2: Heroku**

1. Создайте `Procfile`:
```
web: streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
```

2. Создайте `runtime.txt`:
```
python-3.9.13
```

3. Разверните через Heroku CLI или GitHub Actions

### **Вариант 3: VPS/Сервер**

1. Установите зависимости:
```bash
pip install -r requirements_streamlit.txt
```

2. Запустите приложение:
```bash
streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=8501
```

## 🐛 Решение проблем

### **Ошибка "ModuleNotFoundError"**

**Проблема:** Отсутствуют зависимости в `requirements.txt`

**Решение:** 
- Используйте `requirements_streamlit.txt`
- Убедитесь, что все импорты указаны в зависимостях

### **Ошибка импорта модулей**

**Проблема:** Неправильные пути к модулям

**Решение:**
- Убедитесь, что структура `src/` корректна
- Проверьте `__init__.py` файлы

### **Проблемы с PDF**

**Проблема:** Отсутствуют библиотеки для работы с PDF

**Решение:**
- Добавьте `PyPDF2>=3.0.0` в зависимости
- Или используйте `pypdf>=3.0.0`

## ✅ Проверка развёртывания

### **Локальное тестирование**
```bash
# Установка зависимостей
pip install -r requirements_streamlit.txt

# Тест импортов
python -c "import streamlit; import plotly; print('✅ OK')"

# Запуск приложения
streamlit run streamlit_app.py
```

### **Проверка в браузере**
- Откройте приложение
- Загрузите тестовые файлы
- Проверьте все функции

## 🔄 Обновление приложения

1. Внесите изменения в код
2. Зафиксируйте в Git:
```bash
git add .
git commit -m "Update app"
git push origin main
```

3. Streamlit Cloud автоматически перезапустит приложение

## 📊 Мониторинг

### **Логи Streamlit Cloud**
- Перейдите в "Manage app"
- Откройте "Logs" для просмотра ошибок

### **Метрики**
- Время загрузки страницы
- Использование памяти
- Количество запросов

## 🎯 Рекомендации

1. **Используйте `requirements_streamlit.txt`** для Streamlit Cloud
2. **Тестируйте локально** перед развёртыванием
3. **Минимизируйте зависимости** для быстрой загрузки
4. **Используйте кэширование** для больших файлов
5. **Обрабатывайте ошибки** gracefully

## 🆘 Поддержка

При возникновении проблем:
1. Проверьте логи в Streamlit Cloud
2. Убедитесь в корректности зависимостей
3. Протестируйте локально
4. Обратитесь к документации Streamlit

---

**Успешного развёртывания!** 🚀
