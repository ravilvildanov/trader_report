import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import tempfile
import os
from decimal import Decimal
import logging
from src.trade_report_processor import TradeReportProcessor

# Настройка страницы
st.set_page_config(
    page_title="Freedom Calculator - Обработка брокерских отчётов",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSS для красивого оформления
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(90deg, #f0f2f6, #e1e5e9);
        border-radius: 10px;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .warning-message {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #ffeaa7;
    }
    .error-message {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Заголовок
    st.markdown('<div class="main-header">📊 Freedom Calculator</div>', unsafe_allow_html=True)
    st.markdown("### Обработка брокерских отчётов и расчёт финансовых результатов")
    
    # Боковая панель для загрузки файлов
    with st.sidebar:
        st.header("📁 Загрузка файлов")
        
        # Загрузка брокерского отчёта
        broker_file = st.file_uploader(
            "Брокерский отчёт",
            type=['xlsx', 'pdf'],
            help="Загрузите Excel или PDF файл с брокерским отчётом"
        )
        
        # Загрузка отчёта за прошлый период (опционально)
        previous_file = st.file_uploader(
            "Отчёт за прошлый период (опционально)",
            type=['xlsx', 'pdf'],
            help="Загрузите Excel файл с отчётом за прошлый период для покрытия отрицательного сальдо"
        )
        
        # Настройки
        st.header("⚙️ Настройки")
        currency = st.selectbox(
            "Валюта для обработки",
            ["USD", "EUR", "GBP"],
            index=0
        )
        
        # Кнопка обработки
        process_button = st.button(
            "🚀 Обработать отчёты",
            type="primary",
            use_container_width=True
        )
        
        # Информация о приложении
        st.header("ℹ️ О приложении")
        st.info("""
        **Freedom Calculator** - это инструмент для анализа брокерских отчётов.
        
        **Возможности:**
        - Загрузка Excel и PDF отчётов
        - Расчёт курсов валют
        - Анализ закрытых позиций
        - Генерация сводных отчётов
        """)
    
    # Основная область
    if process_button and broker_file:
        try:
            # Создаём временные файлы
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Сохраняем загруженные файлы
                broker_path = temp_path / broker_file.name
                
                with open(broker_path, 'wb') as f:
                    f.write(broker_file.getvalue())
                
                # Используем фиксированный файл курсов валют
                rates_path = Path('USD_01_01_2021_31_12_2024.xlsx')
                
                # Сохраняем файл прошлого периода если есть
                previous_path = None
                if previous_file:
                    previous_path = temp_path / previous_file.name
                    with open(previous_path, 'wb') as f:
                        f.write(previous_file.getvalue())
                
                # Обрабатываем отчёты
                with st.spinner("Обработка отчётов..."):
                    processor = TradeReportProcessor(broker_path, rates_path)
                    
                    # Основная обработка
                    processor.process()
                    
                    # Сохраняем результаты
                    output_dir = temp_path / "output"
                    processor.save_reports(output_dir)
                
                # Отображаем результаты
                display_results(processor, output_dir)
                
        except Exception as e:
            st.error(f"Ошибка при обработке: {str(e)}")
            logger.error(f"Ошибка: {e}")
    
    elif process_button:
        if not broker_file:
            st.error("Пожалуйста, загрузите брокерский отчёт")
    
    # Демонстрационные данные
    else:
        show_demo_content()

def display_results(processor, output_dir):
    """Отображает результаты обработки"""
    st.success("✅ Обработка завершена успешно!")
    
    # Вкладки для разных типов данных
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "trades_df", 
        "rates_df", 
        "trades_in_rub_df",
        "calculated_securities_df",
        "securities_df",
        "securities_differences_df"
    ])
    
    with tab1:
        st.header("trades_df")
        
        if not processor.trades_df.empty:
            st.dataframe(
                processor.trades_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab2:
        st.header("rates_df")
        
        if not processor.rates_df.empty:
            st.dataframe(
                processor.rates_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab3:
        st.header("trades_in_rub_df")
        
        if not processor.trades_in_rub_df.empty:
            st.dataframe(
                processor.trades_in_rub_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab4:
        st.header("calculated_securities_df")
        
        if not processor.calculated_securities_df.empty:
            st.dataframe(
                processor.calculated_securities_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab5:
        st.header("securities_df")
        
        if not processor.securities_df.empty:
            st.dataframe(
                processor.securities_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")

    with tab6:
        st.header("securities_differences_df")
        
        if not processor.securities_differences_df.empty:
            st.dataframe(
                processor.securities_differences_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")

def show_demo_content():
    """Показывает демонстрационный контент"""
    st.markdown("""
    ## 🚀 Добро пожаловать в Freedom Calculator!
    
    Это приложение поможет вам обработать брокерские отчёты и получить детальную аналитику по вашим торговым операциям.
    
    ### 📋 Что нужно сделать:
    1. **Загрузите брокерский отчёт** - Excel или PDF файл с вашими сделками
    2. **Опционально** - загрузите отчёт за прошлый период для корректного расчёта
    3. **Нажмите "Обработать отчёты"** и получите результаты
    
    ### ✨ Возможности:
    - 📊 Анализ всех позиций и сделок
    - 💰 Расчёт финансовых результатов по закрытым позициям
    - 📈 Визуализация данных и графики
    - 📋 Экспорт в CSV и PDF форматах
    - 🔄 Автоматический расчёт курсов валют
    
    ### 📁 Поддерживаемые форматы:
    - **Брокерский отчёт**: Excel (.xlsx), PDF (.pdf)
    - **Выходные форматы**: CSV, PDF
    
    ---
    
    **Начните работу, загрузив файлы в боковой панели слева!** 🎯
    """)

if __name__ == "__main__":
    main()
