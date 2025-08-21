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
        
        # Загрузка файла курсов валют
        rates_file = st.file_uploader(
            "Курсы валют ЦБ",
            type=['xlsx'],
            help="Загрузите Excel файл с курсами валют от ЦБ"
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
    if process_button and broker_file and rates_file:
        try:
            # Создаём временные файлы
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Сохраняем загруженные файлы
                broker_path = temp_path / broker_file.name
                rates_path = temp_path / rates_file.name
                
                with open(broker_path, 'wb') as f:
                    f.write(broker_file.getvalue())
                
                with open(rates_path, 'wb') as f:
                    f.write(rates_file.getvalue())
                
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
                    
                    # Проверяем отрицательный остаток
                    negative_tickers = processor.negative_balance_handler.identify_negative_balance_tickers(processor.summary_df)
                    
                    if not negative_tickers.empty:
                        if previous_path:
                            st.warning("Обнаружены тикеры с отрицательным остатком. Обрабатываю данные прошлого периода...")
                            processor.handle_negative_positions(previous_path)
                        else:
                            st.warning("Обнаружены тикеры с отрицательным остатком. Для корректного расчёта загрузите отчёт за прошлый период.")
                    
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
        if not rates_file:
            st.error("Пожалуйста, загрузите файл с курсами валют")
    
    # Демонстрационные данные
    else:
        show_demo_content()

def display_results(processor, output_dir):
    """Отображает результаты обработки"""
    st.success("✅ Обработка завершена успешно!")
    
    # Вкладки для разных типов данных
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Общая сводка", 
        "💰 Закрытые позиции", 
        "📈 Детали сделок",
        "📋 Скачать отчёты",
        "📊 Визуализация"
    ])
    
    with tab1:
        st.header("Общая сводка по всем позициям")
        
        if not processor.summary_df.empty:
            # Метрики
            col1, col2, col3, col4 = st.columns(4)
            
            total_tickers = len(processor.summary_df)
            positive_balance = len(processor.summary_df[processor.summary_df['Остаток'] > 0])
            negative_balance = len(processor.summary_df[processor.summary_df['Остаток'] < 0])
            zero_balance = len(processor.summary_df[processor.summary_df['Остаток'] == 0])
            
            with col1:
                st.metric("Всего тикеров", total_tickers)
            with col2:
                st.metric("Длинные позиции", positive_balance)
            with col3:
                st.metric("Короткие позиции", negative_balance)
            with col4:
                st.metric("Закрытые позиции", zero_balance)
            
            # Таблица сводки
            st.dataframe(
                processor.summary_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab2:
        st.header("Сводка по закрытым позициям")
        
        if not processor.closed_summary_df.empty:
            # Итоговые метрики
            if 'Итого' in processor.closed_summary_df['Тикер'].values:
                total_row = processor.closed_summary_df[processor.closed_summary_df['Тикер'] == 'Итого'].iloc[0]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Сумма покупок", f"{total_row['Сумма покупок']:,.2f} ₽")
                with col2:
                    st.metric("Сумма продаж", f"{total_row['Сумма продаж']:,.2f} ₽")
                with col3:
                    st.metric("Комиссии", f"{total_row['Сумма комиссий']:,.2f} ₽")
                with col4:
                    result = total_row['Итог']
                    color = "normal" if result >= 0 else "inverse"
                    st.metric("Финансовый результат", f"{result:,.2f} ₽", delta=f"{result:,.2f}")
            
            # Таблица закрытых позиций
            closed_data = processor.closed_summary_df[processor.closed_summary_df['Тикер'] != 'Итого']
            if not closed_data.empty:
                st.subheader("Детали по тикерам")
                st.dataframe(
                    closed_data,
                    use_container_width=True,
                    hide_index=True
                )
            
            # График результатов по тикерам
            if not closed_data.empty:
                fig = px.bar(
                    closed_data,
                    x='Тикер',
                    y='Итог',
                    title="Финансовый результат по закрытым позициям",
                    color='Итог',
                    color_continuous_scale=['red', 'green']
                )
                fig.update_layout(
                    xaxis_title="Тикер",
                    yaxis_title="Результат (₽)",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Нет данных о закрытых позициях")
    
    with tab3:
        st.header("Детали всех сделок")
        
        if not processor.processed_df.empty:
            # Фильтры
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ticker_filter = st.selectbox(
                    "Фильтр по тикеру",
                    ["Все"] + sorted(processor.processed_df['Тикер'].unique().tolist())
                )
            
            with col2:
                operation_filter = st.selectbox(
                    "Фильтр по операции",
                    ["Все"] + sorted(processor.processed_df['Операция'].unique().tolist())
                )
            
            with col3:
                date_range = st.date_input(
                    "Период",
                    value=(
                        processor.processed_df['Расчеты'].min().date(),
                        processor.processed_df['Расчеты'].max().date()
                    )
                )
            
            # Применяем фильтры
            filtered_data = processor.processed_df.copy()
            
            if ticker_filter != "Все":
                filtered_data = filtered_data[filtered_data['Тикер'] == ticker_filter]
            
            if operation_filter != "Все":
                filtered_data = filtered_data[filtered_data['Операция'] == operation_filter]
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                filtered_data = filtered_data[
                    (filtered_data['Расчеты'].dt.date >= start_date) &
                    (filtered_data['Расчеты'].dt.date <= end_date)
                ]
            
            # Отображаем отфильтрованные данные
            st.dataframe(
                filtered_data,
                use_container_width=True,
                hide_index=True
            )
            
            # Статистика по отфильтрованным данным
            if not filtered_data.empty:
                st.subheader("Статистика по отфильтрованным данным")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    total_trades = len(filtered_data)
                    st.metric("Всего сделок", total_trades)
                
                with col2:
                    total_volume = filtered_data['Количество'].sum()
                    st.metric("Общий объём", f"{total_volume:,}")
                
                with col3:
                    total_amount = filtered_data['Сумма в руб'].sum()
                    st.metric("Общая сумма", f"{total_amount:,.2f} ₽")
        else:
            st.warning("Нет данных о сделках")
    
    with tab4:
        st.header("Скачать отчёты")
        
        # Создаём кнопки для скачивания
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if (output_dir / 'details.csv').exists():
                with open(output_dir / 'details.csv', 'r', encoding='utf-8') as f:
                    csv_data = f.read()
                st.download_button(
                    label="📊 Детали сделок (CSV)",
                    data=csv_data,
                    file_name="details.csv",
                    mime="text/csv"
                )
        
        with col2:
            if (output_dir / 'summary.csv').exists():
                with open(output_dir / 'summary.csv', 'r', encoding='utf-8') as f:
                    csv_data = f.read()
                st.download_button(
                    label="📋 Общая сводка (CSV)",
                    data=csv_data,
                    file_name="summary.csv",
                    mime="text/csv"
                )
        
        with col3:
            if (output_dir / 'closed_summary.csv').exists():
                with open(output_dir / 'closed_summary.csv', 'r', encoding='utf-8') as f:
                    csv_data = f.read()
                st.download_button(
                    label="💰 Закрытые позиции (CSV)",
                    data=csv_data,
                    file_name="closed_summary.csv",
                    mime="text/csv"
                )
        
        with col4:
            if (output_dir / 'closed_report.pdf').exists():
                with open(output_dir / 'closed_report.pdf', 'rb') as f:
                    pdf_data = f.read()
                st.download_button(
                    label="📄 PDF отчёт",
                    data=pdf_data,
                    file_name="closed_report.pdf",
                    mime="application/pdf"
                )
    
    with tab5:
        st.header("Визуализация данных")
        
        if not processor.processed_df.empty:
            # График сделок по времени
            fig1 = px.scatter(
                processor.processed_df,
                x='Расчеты',
                y='Сумма в руб',
                color='Операция',
                hover_data=['Тикер', 'Количество', 'Цена'],
                title="Сделки по времени"
            )
            fig1.update_layout(height=500)
            st.plotly_chart(fig1, use_container_width=True)
            
            # График распределения по тикерам
            ticker_counts = processor.processed_df['Тикер'].value_counts().head(20)
            fig2 = px.bar(
                x=ticker_counts.index,
                y=ticker_counts.values,
                title="Топ-20 тикеров по количеству сделок"
            )
            fig2.update_layout(
                xaxis_title="Тикер",
                yaxis_title="Количество сделок",
                height=400
                )
            st.plotly_chart(fig2, use_container_width=True)
            
            # Круговая диаграмма по операциям
            operation_counts = processor.processed_df['Операция'].value_counts()
            fig3 = px.pie(
                values=operation_counts.values,
                names=operation_counts.index,
                title="Распределение по типам операций"
            )
            fig3.update_layout(height=400)
            st.plotly_chart(fig3, use_container_width=True)

def show_demo_content():
    """Показывает демонстрационный контент"""
    st.markdown("""
    ## 🚀 Добро пожаловать в Freedom Calculator!
    
    Это приложение поможет вам обработать брокерские отчёты и получить детальную аналитику по вашим торговым операциям.
    
    ### 📋 Что нужно сделать:
    1. **Загрузите брокерский отчёт** - Excel или PDF файл с вашими сделками
    2. **Загрузите файл курсов валют** - Excel файл с курсами ЦБ
    3. **Опционально** - загрузите отчёт за прошлый период для корректного расчёта
    4. **Нажмите "Обработать отчёты"** и получите результаты
    
    ### ✨ Возможности:
    - 📊 Анализ всех позиций и сделок
    - 💰 Расчёт финансовых результатов по закрытым позициям
    - 📈 Визуализация данных и графики
    - 📋 Экспорт в CSV и PDF форматах
    - 🔄 Автоматический расчёт курсов валют
    
    ### 📁 Поддерживаемые форматы:
    - **Брокерский отчёт**: Excel (.xlsx), PDF (.pdf)
    - **Курсы валют**: Excel (.xlsx)
    - **Выходные форматы**: CSV, PDF
    
    ---
    
    **Начните работу, загрузив файлы в боковой панели слева!** 🎯
    """)

if __name__ == "__main__":
    main()
