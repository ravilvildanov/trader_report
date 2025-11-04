import logging
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)


class SecuritiesCalculator:
    """Вычисляет остатки бумаг."""
    
    def calculate_securities(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет остатки бумаг."""
        df = trades_df.copy()
        df['Кол-во signed'] = df.apply(
            lambda r: r['Количество'] if ('Покупка' in str(r['Операция'])) else -r['Количество'],
            axis=1
        )
        
        result = df.groupby('Тикер').agg(
            Вычисленный_остаток=('Кол-во signed', 'sum'),
        ).reset_index()
        
        return result