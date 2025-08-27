import logging
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)


class TradeSummaryCalculator:
    """Вычисляет сводки по торговым данным."""
    
    def calculate_summary(self, processed_df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет сводку по тикерам."""
        df = processed_df.copy()
        df['Кол-во signed'] = df.apply(
            lambda r: r['Количество'] if ('Покупка' in str(r['Операция'])) else -r['Количество'],
            axis=1
        )
        
        summary = df.groupby('Тикер').agg(
            Остаток=('Кол-во signed', 'sum'),
            Финансовый_результат_в_руб=('Итог в руб', lambda s: sum(s.dropna()).quantize(Decimal('0.01')) if s.notna().any() else Decimal('0.00'))
        ).reset_index()
        
        return summary
    
    def calculate_closed_positions(self, processed_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
        """Вычисляет сводку по закрытым позициям."""
        logger.info('Вычисление сводки по закрытым позициям')
        
        closed_positions = summary_df[summary_df['Остаток'] == 0]
        rows = []
        
        for _, row in closed_positions.iterrows():
            ticker_data = processed_df.loc[processed_df['Тикер'] == row['Тикер']]
            operations = ticker_data['Операция']
            
            # Суммы покупок и продаж
            sum_purchases = Decimal(str(
                ticker_data.loc[operations == 'Покупка', 'Сумма в руб'].map(lambda x: -x).sum()
            )).quantize(Decimal('0.01'))
            
            sum_sales = Decimal(str(
                ticker_data.loc[operations == 'Продажа', 'Сумма в руб'].sum()
            )).quantize(Decimal('0.01'))
            
            sum_commission = Decimal(str(
                ticker_data['Комиссия брокера руб'].sum()
            )).quantize(Decimal('0.01'))
            
            result = (sum_sales - sum_purchases - sum_commission).quantize(Decimal('0.01'))
            
            rows.append({
                'Тикер': row['Тикер'],
                'Сумма покупок': sum_purchases,
                'Сумма продаж': sum_sales,
                'Сумма комиссий': sum_commission,
                'Итог': result
            })
        
        closed_summary = pd.DataFrame(rows)
        
        if not closed_summary.empty:
            # Добавляем строку "Итого"
            totals = {
                col: closed_summary[col].sum().quantize(Decimal('0.01'))
                for col in ['Сумма покупок', 'Сумма продаж', 'Сумма комиссий', 'Итог']
            }
            totals['Тикер'] = 'Итого'
            closed_summary = pd.concat([closed_summary, pd.DataFrame([totals])], ignore_index=True)
        
        return closed_summary
