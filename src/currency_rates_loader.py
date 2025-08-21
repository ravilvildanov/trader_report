import logging
from pathlib import Path
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)


class CurrencyRatesLoader:
    """Загружает и обрабатывает курсы валют."""
    
    def load(self, rates_path: Path) -> pd.DataFrame:
        """Загружает курсы валют."""
        logger.info('Загрузка курсов ЦБ: %s', rates_path)
        
        df = pd.read_excel(rates_path, sheet_name='RC', engine='openpyxl')
        df.columns = df.columns.str.strip()
        
        # Фильтруем только доллары США
        df = df[df['cdx'].str.strip() == 'Доллар США'][['data', 'curs']]
        df['data'] = pd.to_datetime(df['data'], dayfirst=True)
        df['curs'] = (df['curs'].astype(str)
                      .str.replace(',', '.')
                      .str.replace(r"\s+", '', regex=True)
                      .apply(Decimal))
        
        return df.sort_values('data')
