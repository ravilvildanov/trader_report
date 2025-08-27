import logging
from pathlib import Path
from decimal import Decimal
import pandas as pd
from .data_loaders import DataLoaderFactory

logger = logging.getLogger(__name__)


class NegativeBalanceHandler:
    """Обрабатывает тикеры с отрицательным остатком."""
    
    def __init__(self, data_loader_factory: DataLoaderFactory):
        self.data_loader_factory = data_loader_factory
    
    def identify_negative_balance_tickers(self, summary_df: pd.DataFrame) -> pd.DataFrame:
        """Выявляет тикеры с отрицательным остатком."""
        negative_tickers = summary_df[summary_df['Остаток'] < 0]
        
        if not negative_tickers.empty:
            self._log_negative_balance_warning(negative_tickers)
        
        return negative_tickers
    
    def _log_negative_balance_warning(self, negative_tickers: pd.DataFrame):
        """Логирует предупреждение о тикерах с отрицательным остатком."""
        logger.info('Найдено %d тикеров с отрицательным остатком', len(negative_tickers))
        print("\n" + "="*60)
        print("ВНИМАНИЕ: Обнаружены тикеры с отрицательным остатком!")
        print("="*60)
        print("Это означает, что за текущий период продано больше бумаг, чем куплено.")
        print("\nТикеры с отрицательным остатком:")
        
        for _, row in negative_tickers.iterrows():
            print(f"  {row['Тикер']}: {row['Остаток']} (необходимо найти покупки в прошлом периоде)")
        
        print(f"\nДля корректного расчёта финансовых результатов необходимо")
        print(f"загрузить отчёт за прошлый период (обычно предыдущий год).")
        print(f"\nПожалуйста, подготовьте Excel файл с отчётом за прошлый период")
        print(f"и запустите скрипт снова, указав его как третий аргумент.")
        print("\nПример команды:")
        print(f"python process_trades.py broker_report.xlsx currency_rates.xlsx previous_report.xlsx")
        print("="*60)
    
    def load_previous_period_data(self, previous_report_path: Path) -> pd.DataFrame:
        """Загружает данные за прошлый период."""
        logger.info('Загрузка отчёта за прошлый период: %s', previous_report_path)
        
        loader = self.data_loader_factory.create_loader(previous_report_path)
        df = loader.load(previous_report_path)
        
        # Фильтруем только покупки в USD
        if 'Валюта' in df:
            df['Валюта'] = df['Валюта'].astype(str).str.strip()
            df = df[df['Валюта'] == 'USD']
        
        if 'Операция' in df:
            df['Операция'] = df['Операция'].astype(str).str.strip()
            buy_operations = df[df['Операция'].str.contains('Покупка|Купля|Buy|Открытие', case=False, na=False)]
            logger.info('Найдено %d покупок в прошлом периоде', len(buy_operations))
            return buy_operations
        else:
            raise ValueError("В файле прошлого периода не найдена колонка 'Операция'")
    
    def process_negative_balance(self, processed_df: pd.DataFrame, summary_df: pd.DataFrame, 
                                previous_trades_df: pd.DataFrame) -> pd.DataFrame:
        """Обрабатывает тикеры с отрицательным остатком."""
        logger.info('Обработка тикеров с отрицательным остатком')
        
        negative_tickers = summary_df[summary_df['Остаток'] < 0]
        if negative_tickers.empty:
            return processed_df
        
        # Сортируем покупки прошлого периода по дате
        if 'Расчеты' in previous_trades_df:
            previous_trades_df['Расчеты'] = pd.to_datetime(previous_trades_df['Расчеты'])
            previous_trades_df = previous_trades_df.sort_values('Расчеты', ascending=False)
        
        additional_trades = []
        
        for _, ticker_row in negative_tickers.iterrows():
            ticker = ticker_row['Тикер']
            remaining_to_cover = abs(ticker_row['Остаток'])
            
            logger.info('Обработка тикера %s: нужно покрыть %d бумаг', ticker, remaining_to_cover)
            
            previous_buys = previous_trades_df[previous_trades_df['Тикер'] == ticker].copy()
            if previous_buys.empty:
                continue
            
            covered_amount = 0
            for _, buy_row in previous_buys.iterrows():
                if covered_amount >= remaining_to_cover:
                    break
                
                available_amount = buy_row['Количество']
                needed_amount = remaining_to_cover - covered_amount
                amount_to_use = min(available_amount, needed_amount)
                
                additional_trade = {
                    'Тикер': ticker,
                    'Операция': 'Покупка (прошлый период)',
                    'Количество': amount_to_use,
                    'Цена': buy_row['Цена'],
                    'Валюта': buy_row['Валюта'],
                    'Сумма': (Decimal(str(buy_row['Сумма'])) * Decimal(str(amount_to_use)) / Decimal(str(available_amount))).quantize(Decimal('0.01')),
                    'Комиссия': (Decimal(str(buy_row.get('Комиссия', 0))) * Decimal(str(amount_to_use)) / Decimal(str(available_amount))).quantize(Decimal('0.01')),
                    'Валюта комиссии': buy_row.get('Валюта комиссии', 'USD'),
                    'Дата сделки': buy_row['Дата сделки'],
                    'Расчеты': buy_row['Расчеты'],
                    'Курс': None,
                    'Сумма в руб': None,
                    'Комиссия брокера руб': None,
                    'Итог в руб': None
                }
                
                additional_trades.append(additional_trade)
                covered_amount += amount_to_use
                
                logger.info('Покрыто %d бумаг из покупки %s по цене %s',
                          amount_to_use, buy_row['Расчеты'].strftime('%Y-%m-%d'), buy_row['Цена'])
        
        if additional_trades:
            additional_df = pd.DataFrame(additional_trades)
            processed_df = pd.concat([processed_df, additional_df], ignore_index=True)
            logger.info('Добавлено %d дополнительных сделок', len(additional_trades))
        
        return processed_df
