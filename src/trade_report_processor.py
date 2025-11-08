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
        # Данные
        self.trades_df = pd.DataFrame()
        self.rates_df = pd.DataFrame()
        self.trades_in_rub_df = pd.DataFrame()
        self.securities_df = pd.DataFrame()
        self.calculated_securities_df = pd.DataFrame()
        self.merged_securities_df = pd.DataFrame()
        self.insufficient_tickers = pd.DataFrame()
        self.previous_trades_df = pd.DataFrame()
    
    def process(self):
        """Основной метод обработки."""
        self._load_data()
        self._process_data()
        self._process_securities()
        self._handle_previous_trades_if_needed()
    
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

    def _handle_previous_trades_if_needed(self):
        """Обрабатывает сделки из прошлого периода при необходимости"""
        if not self.insufficient_tickers.empty and self.previous_paths:
            self.previous_trades_df = self.previousTradesManager.loadTrades(self.previous_paths)

    def save_reports(self, output_dir: Path):
        """Сохраняет все отчёты."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем CSV файлы
        self.trades_in_rub_df.to_csv(output_dir / 'details.csv', index=False)
        self.calculated_securities_df.to_csv(output_dir / 'calculated_securities.csv', index=False)
        
        # Генерируем PDF отчёт
        # self.pdf_generator.generate_closed_positions_report(
        #     self.closed_summary_df, self.trades_in_rub_df, self.summary_df,
        #     output_dir / 'closed_report.pdf'
        # )
        
        logger.info('Все отчёты сохранены в директории %s', output_dir)
