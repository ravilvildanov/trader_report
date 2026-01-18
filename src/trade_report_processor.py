import logging
from pathlib import Path
from decimal import Decimal
from typing import Optional, List
import pandas as pd

from .font_manager import FontManager
from .data_loaders import DataLoaderFactory
from .currency_rates_loader import CurrencyRatesLoader
from .trade_data_processor import TradeDataProcessor
from .securities_calculator import SecuritiesCalculator
from .pdf_report_generator import PDFReportGenerator
from .securities_loader import SecuritiesLoader
from .SecuritiesMerger import SecuritiesMerger
from .PreviousTradesManager import PreviousTradesManager
from .finance_result_calculator import FinanceResultCalculator
from .splits_detector import SplitsDetector

logger = logging.getLogger(__name__)

class TradeReportProcessor:
    """Основной класс для обработки брокерских отчётов."""
    
    def __init__(self, broker_path: Path, rates_path: Path, currency: str = 'USD', previous_paths: Optional[List[Path]] = None):
        self.broker_path = broker_path
        self.rates_path = rates_path
        self.currency = currency
        self.previous_paths = previous_paths or []
        
        # Инициализация компонентов
        self.font_manager = FontManager()
        self.data_loader_factory = DataLoaderFactory()
        self.currency_rates_loader = CurrencyRatesLoader()
        self.trade_data_processor = TradeDataProcessor(currency)
        self.pdf_generator = PDFReportGenerator(self.font_manager)
        self.securities_loader = SecuritiesLoader()
        self.securities_calculator = SecuritiesCalculator()
        self.securities_merger = SecuritiesMerger()
        self.previousTradesManager = PreviousTradesManager()
        self.splits_detector = SplitsDetector()
        # Данные
        self.trades_df = pd.DataFrame()
        self.rates_df = pd.DataFrame()
        self.trades_in_rub_df = pd.DataFrame()
        self.securities_df = pd.DataFrame()
        self.calculated_securities_df = pd.DataFrame()
        self.merged_securities_df = pd.DataFrame()
        self.insufficient_tickers = pd.DataFrame()
        self.previous_trades_df = pd.DataFrame()
        self.finance_result_df = pd.DataFrame()
        self.finance_calculator = None
        self.balance_discrepancies = []  # Список тикеров с расхождениями в остатках
    
    def process(self):
        """Основной метод обработки."""
        self._load_data()
        self._load_and_normalize_previous_trades()
        self._load_splits()
        self._process_data()
        self._process_securities()
        self._calculate_finance_result()
        self._check_balance_discrepancies()
        self._check_splits_warnings()
    
    def _load_data(self):
        """Загружает исходные данные."""
        # Загружаем брокерский отчёт
        loader = self.data_loader_factory.create_loader(self.broker_path)
        self.trades_df = loader.load(self.broker_path)
        
        # Загружаем остатки бумаг
        self.securities_df = self.securities_loader.load(self.broker_path)
        
        # Фильтруем по валюте
        if 'Валюта' in self.trades_df:
            self.trades_df['Валюта'] = self.trades_df['Валюта'].astype(str).str.strip()
            self.trades_df = self.trades_df[self.trades_df['Валюта'] == self.currency]
            logger.info('Отфильтровано %d сделок в валюте %s', len(self.trades_df), self.currency)
        else:
            logger.warning('Колонка "Валюта" не найдена в данных')
        
        # Загружаем курсы валют
        self.rates_df = self.currency_rates_loader.load(self.rates_path)
    
    def _load_splits(self):
        """Загружает информацию о сплитах из листа, начинающегося с 'SecInOut'."""
        self.splits_detector.load_splits(self.broker_path)
    
    def _process_data(self):
        """Обрабатывает загруженные данные."""
        # Нормализуем операции
        normalized_trades = self.trade_data_processor.normalize_operations(self.trades_df)
        
        # Объединяем с курсами валют
        merged_data = self.trade_data_processor.merge_with_rates(normalized_trades, self.rates_df)
        
        # Вычисляем суммы в рублях
        self.trades_in_rub_df = self.trade_data_processor.calculate_rub_amounts(merged_data)
    
    def _process_securities(self):
        """Обрабатывает остатки."""
        self.calculated_securities_df = self.securities_calculator.calculate_securities(self.trades_in_rub_df)
        self.merged_securities_df = self.securities_merger.merge(
            self.securities_df,
            self.calculated_securities_df
        )
        self.insufficient_tickers = self.securities_merger.find_insufficient_tickers(self.merged_securities_df)

    def _load_and_normalize_previous_trades(self):
        """Обрабатывает сделки из прошлого периода при необходимости"""
        self.previous_selected_trades_df = pd.DataFrame()

        # Загружаем предыдущие сделки
        self.previous_trades_df = self.previousTradesManager.loadTrades(self.previous_paths)

        # Нормализуем операции в предыдущих сделках
        if not self.previous_trades_df.empty:
            self.previous_trades_df = self.trade_data_processor.normalize_operations(
                self.previous_trades_df
            )

    def _calculate_finance_result(self):
        """Рассчитывает финансовый результат по принципу FIFO/LIFO."""
        if self.trades_in_rub_df.empty:
            logger.warning('Нет данных для расчета финансового результата')
            self.finance_result_df = pd.DataFrame()
            return
        
        # Подготавливаем previous_trades_df для калькулятора
        # Если previous_trades_df не пустой, нужно обработать его так же, как trades_in_rub_df
        previous_trades_for_calc = pd.DataFrame()
        if not self.previous_trades_df.empty:
            # Объединяем с курсами валют
            merged_previous = self.trade_data_processor.merge_with_rates(
                self.previous_trades_df, 
                self.rates_df
            )
            # Вычисляем суммы в рублях
            previous_trades_for_calc = self.trade_data_processor.calculate_rub_amounts(merged_previous)
        
        # Создаем калькулятор и рассчитываем результат
        self.finance_calculator = FinanceResultCalculator(
            trades_in_rub_df=self.trades_in_rub_df,
            previous_trades_df=previous_trades_for_calc if not previous_trades_for_calc.empty else None
        )
        
        self.finance_result_df = self.finance_calculator.calculate()
        
        if not self.finance_result_df.empty:
            logger.info('Рассчитан финансовый результат для %d тикеров', len(self.finance_result_df))
        else:
            logger.warning('Не удалось рассчитать финансовый результат')

    def _check_balance_discrepancies(self):
        """Проверяет соответствие вычисленных остатков с реальными остатками."""
        self.balance_discrepancies = []
        
        if self.finance_result_df.empty or self.securities_df.empty:
            return
        
        # Создаем словарь с реальными остатками из securities_df
        real_balances = {}
        for _, row in self.securities_df.iterrows():
            ticker = row.get('Тикер', '')
            end_balance = row.get('На конец', 0)
            if ticker:
                try:
                    real_balances[ticker] = float(pd.to_numeric(end_balance, errors='coerce'))
                except (ValueError, TypeError):
                    real_balances[ticker] = 0
        
        # Сравниваем с вычисленными остатками
        for _, row in self.finance_result_df.iterrows():
            ticker = row['Тикер']
            calculated_balance = row['Остаток количества']
            real_balance = real_balances.get(ticker, 0)
            
            # Проверяем на расхождение (с учетом погрешности округления)
            if abs(calculated_balance - real_balance) > 0.01:
                self.balance_discrepancies.append({
                    'ticker': ticker,
                    'calculated': calculated_balance,
                    'real': real_balance,
                    'difference': calculated_balance - real_balance
                })
                logger.warning('Расхождение остатков для тикера %s: вычислено=%s, реально=%s, разница=%s',
                             ticker, calculated_balance, real_balance, calculated_balance - real_balance)
        
        if self.balance_discrepancies:
            logger.warning('Обнаружено расхождений в остатках для %d тикеров', len(self.balance_discrepancies))

    def _check_splits_warnings(self):
        """Проверяет наличие сплитов для тикеров из финансового результата."""
        if self.finance_result_df.empty:
            return
        
        # Получаем список тикеров из финансового результата
        result_tickers = self.finance_result_df['Тикер'].tolist()
        
        # Используем SplitsDetector для поиска тикеров со сплитами
        self.splits_detector.find_tickers_with_splits(result_tickers)

    def save_reports(self, output_dir: Path):
        """Сохраняет все отчёты."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем CSV файлы
        self.trades_in_rub_df.to_csv(output_dir / 'details.csv', index=False)
        self.calculated_securities_df.to_csv(output_dir / 'calculated_securities.csv', index=False)
        if not self.finance_result_df.empty:
            self.finance_result_df.to_csv(output_dir / 'finance_result.csv', index=False)
        
        # Генерируем PDF отчёт
        # self.pdf_generator.generate_closed_positions_report(
        #     self.closed_summary_df, self.trades_in_rub_df, self.summary_df,
        #     output_dir / 'closed_report.pdf'
        # )
        
        logger.info('Все отчёты сохранены в директории %s', output_dir)
