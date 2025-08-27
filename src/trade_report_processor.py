import logging
from pathlib import Path
from decimal import Decimal
from typing import Optional
import pandas as pd

from .font_manager import FontManager
from .data_loaders import DataLoaderFactory
from .currency_rates_loader import CurrencyRatesLoader
from .trade_data_processor import TradeDataProcessor
from .trade_summary_calculator import TradeSummaryCalculator
from .negative_balance_handler import NegativeBalanceHandler
from .pdf_report_generator import PDFReportGenerator

logger = logging.getLogger(__name__)


class TradeReportProcessor:
    """Основной класс для обработки брокерских отчётов."""
    
    def __init__(self, broker_path: Path, rates_path: Path, currency: str = 'USD'):
        self.broker_path = broker_path
        self.rates_path = rates_path
        self.currency = currency
        
        # Инициализация компонентов
        self.font_manager = FontManager()
        self.data_loader_factory = DataLoaderFactory()
        self.currency_rates_loader = CurrencyRatesLoader()
        self.trade_data_processor = TradeDataProcessor(currency)
        self.summary_calculator = TradeSummaryCalculator()
        self.negative_balance_handler = NegativeBalanceHandler(self.data_loader_factory)
        self.pdf_generator = PDFReportGenerator(self.font_manager)
        
        # Данные
        self.trades_df = pd.DataFrame()
        self.rates_df = pd.DataFrame()
        self.processed_df = pd.DataFrame()
        self.summary_df = pd.DataFrame()
        self.closed_summary_df = pd.DataFrame()
    
    def process(self):
        """Основной метод обработки."""
        self._load_data()
        self._process_data()
        self._calculate_summaries()
    
    def _load_data(self):
        """Загружает исходные данные."""
        # Загружаем брокерский отчёт
        loader = self.data_loader_factory.create_loader(self.broker_path)
        self.trades_df = loader.load(self.broker_path)
        
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
        self.processed_df = self.trade_data_processor.calculate_rub_amounts(merged_data)
    
    def _calculate_summaries(self):
        """Вычисляет сводки."""
        self.summary_df = self.summary_calculator.calculate_summary(self.processed_df)
        self.closed_summary_df = self.summary_calculator.calculate_closed_positions(
            self.processed_df, self.summary_df
        )
    
    def handle_negative_positions(self, previous_report_path: Optional[Path] = None):
        """Обрабатывает тикеры с отрицательным остатком."""
        negative_tickers = self.negative_balance_handler.identify_negative_balance_tickers(self.summary_df)
        
        if not negative_tickers.empty and previous_report_path:
            logger.info('Обработка данных прошлого периода для покрытия отрицательного остатка')
            previous_trades = self.negative_balance_handler.load_previous_period_data(previous_report_path)
            
            self.processed_df = self.negative_balance_handler.process_negative_balance(
                self.processed_df, self.summary_df, previous_trades
            )
            
            # Пересчитываем курсы для дополнительных сделок
            self._recalculate_additional_trades()
            
            # Пересчитываем сводки
            self._calculate_summaries()
            logger.info('Обработка данных прошлого периода завершена')
        elif not negative_tickers.empty:
            logger.warning('Файл прошлого периода не указан. Сохраняются результаты без учёта отрицательного остатка.')
    
    def _recalculate_additional_trades(self):
        """Пересчитывает курсы для дополнительных сделок."""
        logger.info('Пересчёт курсов для дополнительных сделок из прошлого периода')
        
        additional_trades = self.processed_df[self.processed_df['Курс'].isna()].copy()
        
        if additional_trades.empty:
            logger.info('Нет дополнительных сделок для пересчёта')
            return
        
        for idx, row in additional_trades.iterrows():
            trade_date = row['Расчеты']
            rate_row = self.rates_df[self.rates_df['data'] <= trade_date].iloc[-1] if len(
                self.rates_df[self.rates_df['data'] <= trade_date]
            ) > 0 else None
            
            if rate_row is not None:
                rate = Decimal(str(rate_row['curs']))
                self.processed_df.loc[idx, 'Курс'] = rate
                
                # Пересчитываем суммы в рублях
                amount = Decimal(str(row['Сумма'])) * rate
                sum_in_rub = (-amount if 'Покупка' in str(row['Операция']) else amount).quantize(Decimal('0.01'))
                self.processed_df.loc[idx, 'Сумма в руб'] = sum_in_rub
                
                commission_in_rub = (Decimal(str(row['Комиссия'])) * rate).quantize(Decimal('0.01'))
                self.processed_df.loc[idx, 'Комиссия брокера руб'] = commission_in_rub
                
                self.processed_df.loc[idx, 'Итог в руб'] = (sum_in_rub - commission_in_rub).quantize(Decimal('0.01'))
                
                logger.info('Пересчитан тикер %s: курс %s, сумма в руб %s',
                          row['Тикер'], rate, sum_in_rub)
            else:
                logger.warning('Не найден курс валюты для сделки %s от %s', row['Тикер'], trade_date)
                # Устанавливаем значения по умолчанию для сделок без курса
                self.processed_df.loc[idx, 'Курс'] = 0
                self.processed_df.loc[idx, 'Сумма в руб'] = 0
                self.processed_df.loc[idx, 'Комиссия брокера руб'] = 0
                self.processed_df.loc[idx, 'Итог в руб'] = 0
    
    def save_reports(self, output_dir: Path):
        """Сохраняет все отчёты."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Сохраняем CSV файлы
        self.processed_df.to_csv(output_dir / 'details.csv', index=False)
        self.summary_df.to_csv(output_dir / 'summary.csv', index=False)
        self.closed_summary_df.to_csv(output_dir / 'closed_summary.csv', index=False)
        
        # Генерируем PDF отчёт
        self.pdf_generator.generate_closed_positions_report(
            self.closed_summary_df, self.processed_df, self.summary_df,
            output_dir / 'closed_report.pdf'
        )
        
        logger.info('Все отчёты сохранены в директории %s', output_dir)
