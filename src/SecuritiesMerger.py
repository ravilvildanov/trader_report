import pandas as pd
import logging

logger = logging.getLogger(__name__)

class SecuritiesMerger:
    """Сопоставляет фактические и вычисленные остатки бумаг"""

    def merge(
        self, 
        securities_df: pd.DataFrame, 
        calculated_securities_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Сопоставляет фактические и вычисленные остатки бумаг"""
        # Объединяем по столбцу 'Тикер'
        joined = pd.merge(securities_df, calculated_securities_df, on='Тикер', how='outer')
        
        # Извлекаем только нужные столбцы
        result = joined[['Тикер', 'Вычисленный_остаток', 'На конец']].copy()
        
        return result

    def find_insufficient_tickers(self, merged_securities_df: pd.DataFrame) -> pd.DataFrame:
        """
        Определяет бумаги, по которым недостаточно данных.
        
        По тикеру достаточно данных если:
        1. Вычисленный_остаток = 0 и На конец пусто (NaN)
        2. Вычисленный_остаток = На конец
        
        В остальных случаях данных недостаточно.
        
        Args:
            merged_securities_df: DataFrame с объединёнными данными о бумагах
            
        Returns:
            DataFrame с бумагами, по которым недостаточно данных
        """
        if merged_securities_df.empty:
            return pd.DataFrame(columns=['Тикер', 'Вычисленный_остаток', 'На конец'])
        
        # Создаём копию для работы
        df = merged_securities_df.copy()
        
        # Заменяем пустые значения на NaN для корректной обработки
        df['Вычисленный_остаток'] = pd.to_numeric(df['Вычисленный_остаток'], errors='coerce')
        df['На конец'] = pd.to_numeric(df['На конец'], errors='coerce')
        
        # Определяем условия достаточности данных
        # Условие 1: Вычисленный_остаток = 0 и На конец пусто (NaN)
        condition1 = (df['Вычисленный_остаток'] == 0) & (df['На конец'].isna())
        
        # Условие 2: Вычисленный_остаток = На конец (оба не пустые)
        condition2 = (df['Вычисленный_остаток'].notna()) & \
                     (df['На конец'].notna()) & \
                     (df['Вычисленный_остаток'] == df['На конец'])
        
        # Бумаги с достаточными данными
        sufficient_data = condition1 | condition2
        
        # Бумаги с недостаточными данными - инверсия достаточных
        insufficient_data = ~sufficient_data
        
        # Возвращаем только бумаги с недостаточными данными
        result = df[insufficient_data].copy()
        
        logger.info('Найдено %d бумаг с недостаточными данными из %d', 
                   len(result), len(df))
        
        return result

    