import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class SecuritiesLoader:
    """Загружает остатки бумаг из основного отчёта."""

    def load(self, file_path: Path) -> pd.DataFrame:
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        sheet_name = next(s for s in xls.sheet_names if 'Securities' in s)
        logger.info('Найден лист: %s', sheet_name)
        
        df = pd.read_excel(xls, sheet_name, engine='openpyxl')
        return self._normalize_columns(df)
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Убирает пробелы в названиях колонок."""
        df = df.copy()
        df.columns = df.columns.str.strip()
        return df