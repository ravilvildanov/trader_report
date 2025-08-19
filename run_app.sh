#!/bin/bash

# Freedom Calculator - Streamlit App Launcher
# Скрипт для быстрого запуска приложения

echo "🚀 Запуск Freedom Calculator..."
echo "================================"

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

# Проверяем наличие pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не найден. Установите pip"
    exit 1
fi

# Проверяем наличие виртуального окружения
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📚 Установка зависимостей..."
pip install -r requirements.txt

# Запускаем приложение
echo "🌐 Запуск Streamlit приложения..."
echo "📱 Откройте браузер и перейдите по адресу: http://localhost:8501"
echo "🛑 Для остановки нажмите Ctrl+C"
echo ""

streamlit run streamlit_app.py --server.port 8501
