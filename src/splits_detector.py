import logging
from pathlib import Path
from typing import List
import pandas as pd

logger = logging.getLogger(__name__)


class SplitsDetector:
    """Класс для обнаружения и работы со сплитами акций."""
    
    def __init__(self):
        self.splits_df = pd.DataFrame()
        self.tickers_with_splits = []
    
    def load_splits(self, file_path: Path) -> pd.DataFrame:
        """
        Загружает информацию о сплитах из листа, начинающегося с 'SecInOut'.
        
        Args:
            file_path: Путь к Excel файлу
            
        Returns:
            DataFrame с данными о сплитах
        """
        try:
            # Проверяем, что файл Excel
            if not (str(file_path).endswith('.xlsx') or str(file_path).endswith('.xls')):
                logger.info('Файл не в формате Excel, пропускаем загрузку сплитов')
                return pd.DataFrame()
            
            xls = pd.ExcelFile(file_path, engine='openpyxl')
            
            # Ищем лист, начинающийся с 'SecInOut'
            sheet_name = None
            for s in xls.sheet_names:
                if s.startswith('SecInOut'):
                    sheet_name = s
                    break
            
            if not sheet_name:
                logger.info('Лист, начинающийся с "SecInOut", не найден в файле')
                return pd.DataFrame()
            
            logger.info('Найден лист со сплитами: %s', sheet_name)
            self.splits_df = pd.read_excel(xls, sheet_name, engine='openpyxl')
            
            # Нормализуем названия колонок
            self.splits_df.columns = self.splits_df.columns.str.strip()
            
            logger.info('Загружено %d записей из листа со сплитами', len(self.splits_df))
            return self.splits_df
            
        except Exception as e:
            logger.warning('Ошибка при загрузке сплитов: %s', e)
            self.splits_df = pd.DataFrame()
            return pd.DataFrame()
    
    def find_tickers_with_splits(self, result_tickers: List[str]) -> List[str]:
        """
        Находит тикеры из списка, для которых были сплиты.
        
        Args:
            result_tickers: Список тикеров для проверки
            
        Returns:
            Список тикеров, у которых были сплиты
        """
        self.tickers_with_splits = []
        
        if self.splits_df.empty or not result_tickers:
            return []
        
        # Ищем колонку "тип" (может быть с разным регистром)
        type_col = self._find_column(['тип', 'type'])
        if type_col is None:
            logger.info('Колонка "тип" не найдена в данных о сплитах')
            return []
        
        # Ищем колонку "тикер"
        ticker_col = self._find_column(['тикер', 'ticker'])
        if ticker_col is None:
            logger.info('Колонка "тикер" не найдена в данных о сплитах')
            return []
        
        # Фильтруем сплиты
        splits_mask = self.splits_df[type_col].astype(str).str.lower().str.contains('сплит|split', na=False)
        splits_records = self.splits_df[splits_mask]
        
        if splits_records.empty:
            logger.info('Сплиты не найдены в данных')
            return []
        
        # Получаем тикеры со сплитами
        split_tickers = set(splits_records[ticker_col].astype(str).str.strip())
        
        # Проверяем, какие тикеры из списка имеют сплиты
        result_tickers_set = set(str(t).strip() for t in result_tickers)
        
        # Находим пересечение
        self.tickers_with_splits = sorted(list(split_tickers.intersection(result_tickers_set)))
        
        if self.tickers_with_splits:
            logger.warning('Обнаружены сплиты для %d тикеров: %s', 
                         len(self.tickers_with_splits), ', '.join(self.tickers_with_splits))
        
        return self.tickers_with_splits
    
    def _find_column(self, possible_names: List[str]) -> str:
        """
        Находит колонку по списку возможных названий (без учета регистра).
        
        Args:
            possible_names: Список возможных названий колонки
            
        Returns:
            Название найденной колонки или None
        """
        for col in self.splits_df.columns:
            if col.lower() in possible_names:
                return col
        return None
    
    def get_splits_info(self) -> pd.DataFrame:
        """
        Возвращает DataFrame со всеми сплитами.
        
        Returns:
            DataFrame с информацией о сплитах
        """
        return self.splits_df
