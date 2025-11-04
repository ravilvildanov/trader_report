import pandas as pd

class SecuritiesComparator:
    """Сравнивает фактические и вычисленные остатки бумаг и выявляет расхождения."""

    def compare(
        self, 
        securities_df: pd.DataFrame, 
        calculated_securities_df: pd.DataFrame
    ) -> pd.DataFrame:
        """озвращает строки, где фактические и вычисленные остатки отличаются."""
        # Объединяем по столбцу 'Тикер'
        joined = pd.merge(securities_df, calculated_securities_df, on='Тикер', how='left')
        
        # Извлекаем только данные для сравнения
        differences = joined[['Тикер', 'Вычисленный_остаток', 'На конец']].copy()
        
        # Оставляем только те строки, где 'Вычисленный_остаток' и 'На конец' не равны
        differences = differences[differences['Вычисленный_остаток'] != differences['На конец']]
        
        return differences