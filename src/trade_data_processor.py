import logging
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)


class TradeDataProcessor:
    """Обрабатывает торговые данные."""
    
    def __init__(self, currency: str = 'USD'):
        self.currency = currency
    
    def normalize_operations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Нормализует операции в данных."""
        df = df.copy()
        
        # Оставляем только нужные колонки
        required_columns = [
            'Тикер', 'Операция', 'Количество', 'Цена', 'Валюта', 
            'Сумма', 'Комиссия', 'Валюта комиссии', 'Дата сделки', 'Расчеты'
        ]
        
        # Проверяем наличие необходимых колонок
        missing_columns = []
        for col in required_columns:
            if col not in df.columns:
                missing_columns.append(col)
        
        if missing_columns:
            logger.warning(f'Отсутствуют колонки: {missing_columns}')
            # Создаём недостающие колонки с значениями по умолчанию
            for col in missing_columns:
                if col in ['Количество', 'Цена', 'Сумма', 'Комиссия']:
                    df[col] = 0
                elif col in ['Валюта', 'Валюта комиссии']:
                    df[col] = 'USD'
                elif col in ['Дата сделки', 'Расчеты']:
                    df[col] = pd.Timestamp.now()
                else:
                    df[col] = ''
        
        # Нормализуем операции
        df['Операция'] = df['Операция'].apply(self._normalize_operation)
        
        # Обрабатываем числовые колонки
        if 'Количество' in df:
            df['Количество'] = pd.to_numeric(df['Количество'], errors='coerce').abs()
        
        # Обрабатываем даты
        if 'Дата сделки' in df:
            df['Дата сделки'] = pd.to_datetime(df['Дата сделки'], errors='coerce')
        if 'Расчеты' in df:
            df['Расчеты'] = pd.to_datetime(df['Расчеты'], errors='coerce')
        
        # Фильтруем только нужные колонки
        df = df[required_columns]
        
        return df
    
    def _normalize_operation(self, raw_operation: str) -> str:
        """Нормализует название операции."""
        op = str(raw_operation or '').strip()
        op_lower = op.lower()
        
        if ('покуп' in op_lower) or ('купл' in op_lower) or ('buy' in op_lower):
            return 'Покупка'
        if ('продаж' in op_lower) or ('sell' in op_lower):
            return 'Продажа'
        
        return op
    
    def merge_with_rates(self, trades_df: pd.DataFrame, rates_df: pd.DataFrame) -> pd.DataFrame:
        """Объединяет торговые данные с курсами валют."""
        merged = pd.merge_asof(
            trades_df.sort_values('Расчеты'),
            rates_df.sort_values('data'),
            left_on='Расчеты',
            right_on='data',
            direction='backward'
        )
        
        merged = merged.drop(columns=['data']).rename(columns={'curs': 'Курс'})
        return merged
    
    def calculate_rub_amounts(self, df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет суммы в рублях."""
        df = df.copy()
        
        # Обрабатываем числовые колонки
        for col in ['Сумма', 'Комиссия', 'Количество']:
            if col in df:
                df[col] = (df[col].astype(str)
                           .str.replace(',', '.')
                           .str.replace(r"\s+", '', regex=True)
                           .apply(Decimal))
        
        # Вычисляем суммы в рублях
        def calc_sum(row):
            amount = Decimal(str(row['Сумма'])) * Decimal(str(row['Курс']))
            return (-amount if 'Покупка' in str(row['Операция']) else amount).quantize(Decimal('0.01'))
        
        df['Сумма в руб'] = df.apply(calc_sum, axis=1)
        
        # Вычисляем комиссию в рублях
        df['Комиссия брокера руб'] = (
            df['Комиссия'].apply(lambda v: Decimal(str(v))) * 
            df['Курс'].astype(str).apply(Decimal)
        ).apply(lambda x: x.quantize(Decimal('0.01')))
        
        df['Итог в руб'] = (
            df['Сумма в руб'] - df['Комиссия брокера руб']
        ).apply(lambda x: x.quantize(Decimal('0.01')))
        
        return df
