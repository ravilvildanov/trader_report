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
        
        # Загрузка отчётов за прошлый период (опционально)
        previous_files = st.file_uploader(
            "Отчёты за прошлый период (опционально)",
            type=['xlsx', 'pdf'],
            accept_multiple_files=True,
            help="Загрузите один или несколько Excel/PDF файлов с отчётами за прошлый период для покрытия отрицательного сальдо"
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
                rates_path = Path('RC_F01_01_2023_T31_12_2025.xlsx')
                
                # Сохраняем файлы прошлого периода если есть
                previous_paths = []
                if previous_files:
                    for previous_file in previous_files:
                        previous_path = temp_path / previous_file.name
                        with open(previous_path, 'wb') as f:
                            f.write(previous_file.getvalue())
                        previous_paths.append(previous_path)
                
                # Обрабатываем отчёты
                with st.spinner("Обработка отчётов..."):
                    processor = TradeReportProcessor(
                        broker_path, 
                        rates_path,
                        currency=currency, 
                        previous_paths=previous_paths
                    )
                    
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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "💰 Финансовый результат",
        "trades_df", 
        "rates_df", 
        "trades_in_rub_df",
        "calculated_securities_df",
        "securities_df",
        "merged_securities_df",
        "insufficient_tickers",
        "previous_trades_df",
        "previous_selected_trades_df"
    ])
    
    with tab1:
        st.header("💰 Финансовый результат")
        
        if not processor.finance_result_df.empty:
            # Проверка расхождений в остатках
            if processor.balance_discrepancies:
                st.warning(f"⚠️ Обнаружено расхождений в остатках: {len(processor.balance_discrepancies)} тикер(ов)")
                
                for discrepancy in processor.balance_discrepancies:
                    ticker = discrepancy['ticker']
                    calculated = discrepancy['calculated']
                    real = discrepancy['real']
                    difference = discrepancy['difference']
                    
                    # Определяем цвет и текст в зависимости от типа расхождения
                    if calculated < real:
                        # Вычисленный остаток меньше реального - возможно не все продажи учтены
                        message = f"**{ticker}**: Вычисленный остаток ({calculated:.2f}) меньше реального ({real:.2f}) на {abs(difference):.2f}. " \
                                 f"Возможно, не все продажи или операции были учтены в текущем отчете."
                    else:
                        # Вычисленный остаток больше реального - не хватает покупок из прошлого
                        message = f"**{ticker}**: Вычисленный остаток ({calculated:.2f}) больше реального ({real:.2f}) на {abs(difference):.2f}. " \
                                 f"Скорее всего, необходимо загрузить отчеты за предыдущие периоды для корректного расчета покупок."
                    
                    st.markdown(f":orange[{message}]")
                
                st.markdown("---")
            
            # Проверка сплитов
            if processor.splits_detector.tickers_with_splits:
                st.warning(f"⚠️ Обнаружены сплиты: {len(processor.splits_detector.tickers_with_splits)} тикер(ов)")
                
                for ticker in processor.splits_detector.tickers_with_splits:
                    message = f"**{ticker}**: Для данного тикера был выполнен сплит акций. " \
                             f"Это может привести к ошибкам в расчетах количества и цен. " \
                             f"Рекомендуется проверить корректность данных вручную."
                    st.markdown(f":orange[{message}]")
                
                st.markdown("---")
            
            # Общая статистика
            col1, col2, col3, col4 = st.columns(4)
            
            total_sales = processor.finance_result_df['Продажи (руб)'].sum()
            total_purchases = processor.finance_result_df['Покупки (руб)'].sum()
            total_commissions = processor.finance_result_df['Комиссии (руб)'].sum()
            total_result = processor.finance_result_df['Финансовый результат (руб)'].sum()
            
            with col1:
                st.metric("Общие продажи", f"{total_sales:,.2f} ₽")
            with col2:
                st.metric("Общие покупки", f"{total_purchases:,.2f} ₽")
            with col3:
                st.metric("Общие комиссии", f"{total_commissions:,.2f} ₽")
            with col4:
                st.metric(
                    "Финансовый результат", 
                    f"{total_result:,.2f} ₽",
                    delta=f"{total_result:,.2f} ₽" if total_result != 0 else None
                )
            
            st.markdown("---")
            
            # Таблица с результатами
            st.subheader("Результаты по тикерам")
            display_df = processor.finance_result_df.copy()
            
            # Форматируем числа для отображения
            # Количество - целые числа
            for col in ['Продажи (количество)', 'Покупки (количество)', 'Остаток количества']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}")
            
            # Суммы в рублях - с копейками
            for col in ['Продажи (руб)', 'Покупки (руб)', 'Комиссии (руб)', 'Финансовый результат (руб)']:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=False
            )
            
            # График финансового результата по тикерам
            st.markdown("---")
            st.subheader("График финансового результата по тикерам")
            
            fig = px.bar(
                processor.finance_result_df,
                x='Тикер',
                y='Финансовый результат (руб)',
                title='Финансовый результат по тикерам',
                color='Финансовый результат (руб)',
                color_continuous_scale=['red', 'yellow', 'green'],
                labels={'Финансовый результат (руб)': 'Результат (₽)'}
            )
            fig.update_layout(
                xaxis_title="Тикер",
                yaxis_title="Финансовый результат (₽)",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Детальные сделки по тикерам
            st.markdown("---")
            st.subheader("📋 Детальные сделки по тикерам")
            st.caption("Раскройте тикер, чтобы увидеть все сделки, использованные для расчета")
            
            if processor.finance_calculator:
                for _, row in processor.finance_result_df.iterrows():
                    ticker = row['Тикер']
                    trades_details = processor.finance_calculator.get_trades_details(ticker)
                    
                    with st.expander(f"🔍 {ticker} - детали сделок"):
                        # Текущие сделки
                        st.write("**Текущие сделки:**")
                        current_trades = trades_details['current_trades']
                        if not current_trades.empty:
                            # Выбираем только важные колонки для отображения
                            display_cols = ['Дата сделки', 'Операция', 'Количество', 'Цена', 
                                          'Сумма в руб', 'Комиссия брокера руб']
                            available_cols = [col for col in display_cols if col in current_trades.columns]
                            st.dataframe(
                                current_trades[available_cols],
                                use_container_width=True,
                                hide_index=True
                            )
                        else:
                            st.info("Нет текущих сделок")
                        
                        # Сделки из предыдущего периода
                        previous_trades = trades_details['previous_trades']
                        if not previous_trades.empty:
                            st.write("**Сделки из предыдущего периода (использованные по LIFO):**")
                            display_cols = ['Дата сделки', 'Операция', 'Количество', 'Цена', 
                                          'Сумма в руб', 'Комиссия брокера руб']
                            available_cols = [col for col in display_cols if col in previous_trades.columns]
                            st.dataframe(
                                previous_trades[available_cols],
                                use_container_width=True,
                                hide_index=True
                            )
            
        else:
            st.warning("Нет данных для отображения")
    
    with tab2:
        st.header("trades_df")
        
        if not processor.trades_df.empty:
            st.dataframe(
                processor.trades_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab3:
        st.header("rates_df")
        
        if not processor.rates_df.empty:
            st.dataframe(
                processor.rates_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab4:
        st.header("trades_in_rub_df")
        
        if not processor.trades_in_rub_df.empty:
            st.dataframe(
                processor.trades_in_rub_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab5:
        st.header("calculated_securities_df")
        
        if not processor.calculated_securities_df.empty:
            st.dataframe(
                processor.calculated_securities_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")
    
    with tab6:
        st.header("securities_df")
        
        if not processor.securities_df.empty:
            st.dataframe(
                processor.securities_df,
                use_container_width=True,
                hide_index=False
            )
        else:
            st.warning("Нет данных для отображения")

    with tab7:
        st.header("merged_securities_df")
        
        if not processor.merged_securities_df.empty:
            st.dataframe(processor.merged_securities_df)
        else:
            st.warning("Нет данных для отображения")

    with tab8:
        st.header("insufficient_tickers")

        st.dataframe(processor.insufficient_tickers)

    with tab9:
        st.header("previous_trades_df")

        st.dataframe(processor.previous_trades_df)

    with tab10:
        st.header("previous_selected_trades_df")
        st.dataframe(processor.previous_selected_trades_df)

def show_demo_content():
    """Показывает демонстрационный контент"""
    st.markdown("""
    ## 🚀 Добро пожаловать в Freedom Calculator!
    
    Это приложение поможет вам обработать брокерские отчёты и получить детальную аналитику по вашим торговым операциям.
    
    ### 📋 Что нужно сделать:
    1. **Загрузите брокерский отчёт** - Excel или PDF файл с вашими сделками
    2. **Опционально** - загрузите один или несколько отчётов за прошлый период для корректного расчёта
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
