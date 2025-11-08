import logging
from pathlib import Path
from typing import List
import pandas as pd

from .data_loaders import DataLoaderFactory

logger = logging.getLogger(__name__)


class PreviousTradesManager:
    """Класс для загрузки предыдущих сделок из нескольких файлов."""
    
    def __init__(self):
        self.data_loader_factory = DataLoaderFactory()
    
    def loadTrades(self, previous_paths: List[Path]) -> pd.DataFrame:
        """Загружает сделки из массива путей к отчётам за прошлые периоды."""
        if not previous_paths:
            logger.info('Нет путей к отчётам за прошлые периоды')
            return pd.DataFrame()
        
        all_trades = []
        
        for broker_path in previous_paths:
            try:
                loader = self.data_loader_factory.create_loader(broker_path)
                previous_trades_df = loader.load(broker_path)
                all_trades.append(previous_trades_df)
                logger.info('Загружено %d сделок из файла %s', len(previous_trades_df), broker_path)
            except Exception as e:
                logger.error('Ошибка при загрузке файла %s: %s', broker_path, e)
                continue
        
        if not all_trades:
            logger.warning('Не удалось загрузить данные из предыдущих отчётов')
            return pd.DataFrame()
        
        # Объединяем все DataFrame в один
        previous_trades_df = pd.concat(all_trades, ignore_index=True)
        logger.info('Всего загружено %d сделок из предыдущих отчётов', len(previous_trades_df))
        
        # Сортируем по столбцу "Дата сделки" по возрастанию
        if 'Дата сделки' in previous_trades_df.columns and len(previous_trades_df) > 0:
            # Преобразуем столбец в datetime, если он ещё не в этом формате
            try:
                previous_trades_df['Дата сделки'] = pd.to_datetime(previous_trades_df['Дата сделки'], errors='coerce')
                previous_trades_df = previous_trades_df.sort_values('Дата сделки', ascending=True).reset_index(drop=True)
                logger.info('Сделки отсортированы по дате по возрастанию')
            except Exception as e:
                logger.warning('Не удалось отсортировать по дате: %s', e)
        
        return previous_trades_df
