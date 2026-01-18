import logging
from decimal import Decimal
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class FinanceResultCalculator:
    """Класс для расчета финансового результата по принципу FIFO/LIFO."""
    
    def __init__(self, trades_in_rub_df: pd.DataFrame, previous_trades_df: Optional[pd.DataFrame] = None):
        """
        Инициализирует калькулятор финансового результата.
        
        Args:
            trades_in_rub_df: DataFrame с текущими сделками в рублях
            previous_trades_df: DataFrame с предыдущими сделками (опционально)
        """
        self.trades_in_rub_df = trades_in_rub_df.copy() if not trades_in_rub_df.empty else pd.DataFrame()
        self.previous_trades_df = previous_trades_df.copy() if previous_trades_df is not None and not previous_trades_df.empty else pd.DataFrame()
        self.result_df = pd.DataFrame()
        self.trades_details = {}  # Словарь с детальными сделками по каждому тикеру
    
    def calculate(self) -> pd.DataFrame:
        """
        Рассчитывает финансовый результат по принципу FIFO для текущих сделок
        и LIFO для предыдущих сделок при необходимости.
        
        Returns:
            DataFrame с финансовым результатом по каждому тикеру
        """
        if self.trades_in_rub_df.empty:
            logger.warning('Нет текущих сделок для расчета')
            return pd.DataFrame()
        
        results = []
        
        # Группируем по тикерам
        tickers = self.trades_in_rub_df['Тикер'].unique()
        
        for ticker in tickers:
            ticker_result = self._calculate_ticker_result(ticker)
            if ticker_result:
                results.append(ticker_result)
        
        if not results:
            return pd.DataFrame()
        
        self.result_df = pd.DataFrame(results)
        return self.result_df
    
    def get_trades_details(self, ticker: str) -> dict:
        """
        Получает детальную информацию о сделках для указанного тикера.
        
        Args:
            ticker: Тикер для получения деталей
            
        Returns:
            Словарь с ключами 'current_trades' и 'previous_trades' (DataFrames)
        """
        return self.trades_details.get(ticker, {
            'current_trades': pd.DataFrame(),
            'previous_trades': pd.DataFrame()
        })
    
    def _calculate_ticker_result(self, ticker: str) -> Optional[dict]:
        """
        Рассчитывает финансовый результат для одного тикера.
        
        Args:
            ticker: Тикер для расчета
            
        Returns:
            Словарь с результатами расчета или None
        """
        # Фильтруем сделки по тикеру
        ticker_trades = self.trades_in_rub_df[
            self.trades_in_rub_df['Тикер'] == ticker
        ].copy()
        
        if ticker_trades.empty:
            return None
        
        # Сортируем по дате сделки (FIFO - сначала старые)
        ticker_trades = ticker_trades.sort_values('Дата сделки', ascending=True).reset_index(drop=True)
        
        # Сохраняем сделки для этого тикера (для детального просмотра)
        self.trades_details[ticker] = {
            'current_trades': ticker_trades,
            'previous_trades': pd.DataFrame()
        }
        
        # Инициализируем переменные для расчета
        total_sales = Decimal('0')  # Общая сумма продаж
        total_purchases = Decimal('0')  # Общая сумма покупок
        total_commissions = Decimal('0')  # Общая сумма комиссий
        total_purchase_quantity = Decimal('0')  # Общее количество покупок
        total_sale_quantity = Decimal('0')  # Общее количество продаж
        
        # Обрабатываем текущие сделки - суммируем все продажи, покупки и комиссии
        for _, trade in ticker_trades.iterrows():
            operation = str(trade['Операция']).strip()
            quantity = Decimal(str(trade['Количество']))
            amount_rub = Decimal(str(trade['Сумма в руб']))
            commission_rub = Decimal(str(trade['Комиссия брокера руб']))
            
            if operation == 'Покупка':
                total_purchases += abs(amount_rub)  # Покупка всегда отрицательная, берем модуль
                total_commissions += commission_rub
                total_purchase_quantity += quantity
                
            elif operation == 'Продажа':
                total_sales += abs(amount_rub)  # Продажа всегда положительная
                total_commissions += commission_rub
                total_sale_quantity += quantity
        
        # Если продаж больше чем покупок, используем предыдущие сделки по LIFO
        remaining_quantity = total_purchase_quantity - total_sale_quantity
        if remaining_quantity < 0 and not self.previous_trades_df.empty:
            needed_quantity = abs(remaining_quantity)
            previous_purchases, previous_trades_used = self._get_previous_purchases_lifo(ticker, needed_quantity)
            
            # Сохраняем использованные сделки из предыдущего периода
            if not previous_trades_used.empty:
                self.trades_details[ticker]['previous_trades'] = previous_trades_used
            
            # Подсчитываем общее количество использованных покупок из предыдущих сделок
            used_previous_quantity = Decimal('0')
            for purchase in previous_purchases:
                total_purchases += purchase['amount']
                used_previous_quantity += purchase['quantity']
                # Комиссии из предыдущих сделок не учитываются
            
            # Обновляем remaining_quantity с учетом использованных покупок из предыдущих сделок
            remaining_quantity += used_previous_quantity
        
        # Рассчитываем финансовый результат
        financial_result = total_sales - total_purchases - total_commissions
        
        return {
            'Тикер': ticker,
            'Продажи (руб)': float(total_sales),
            'Продажи (количество)': float(total_sale_quantity),
            'Покупки (руб)': float(total_purchases),
            'Покупки (количество)': float(total_purchase_quantity),
            'Комиссии (руб)': float(total_commissions),
            'Финансовый результат (руб)': float(financial_result),
            'Остаток количества': float(remaining_quantity)
        }
    
    def _get_previous_purchases_lifo(self, ticker: str, needed_quantity: Decimal) -> tuple:
        """
        Получает покупки из предыдущих сделок по принципу LIFO.
        
        Args:
            ticker: Тикер для поиска
            needed_quantity: Необходимое количество
            
        Returns:
            Кортеж: (список словарей с информацией о покупках, DataFrame с использованными сделками)
        """
        if self.previous_trades_df.empty:
            return [], pd.DataFrame()
        
        # Фильтруем покупки по тикеру
        previous_purchases = self.previous_trades_df[
            (self.previous_trades_df['Тикер'] == ticker) &
            (self.previous_trades_df['Операция'] == 'Покупка')
        ].copy()
        
        if previous_purchases.empty:
            return [], pd.DataFrame()
        
        # Сортируем по дате сделки по убыванию (LIFO - сначала новые)
        previous_purchases = previous_purchases.sort_values('Дата сделки', ascending=False).reset_index(drop=True)
        
        purchases_used = []
        trades_used_indices = []
        remaining_needed = needed_quantity
        
        # Берем покупки начиная с самых новых (LIFO)
        for idx, purchase in previous_purchases.iterrows():
            if remaining_needed <= 0:
                break
            
            quantity = Decimal(str(purchase['Количество']))
            
            # Определяем сумму покупки в рублях
            # Проверяем наличие колонки 'Сумма в руб', если нет - используем 'Сумма' и 'Курс'
            if 'Сумма в руб' in purchase:
                amount_rub = Decimal(str(purchase['Сумма в руб']))
            elif 'Сумма' in purchase and 'Курс' in purchase:
                amount = Decimal(str(purchase['Сумма']))
                rate = Decimal(str(purchase['Курс']))
                amount_rub = abs(amount) * rate
            elif 'Сумма' in purchase:
                # Предполагаем, что сумма уже в рублях
                amount_rub = Decimal(str(purchase['Сумма']))
            else:
                logger.warning('Не удалось определить сумму покупки для тикера %s', ticker)
                continue
            
            # Вычисляем цену за единицу
            if quantity > 0:
                price_per_unit = abs(amount_rub) / quantity
            else:
                continue
            
            # Определяем, сколько нужно взять из этой покупки
            quantity_to_use = min(quantity, remaining_needed)
            amount_to_use = price_per_unit * quantity_to_use
            
            purchases_used.append({
                'quantity': quantity_to_use,
                'amount': amount_to_use,
                'date': purchase.get('Дата сделки', None)
            })
            
            trades_used_indices.append(idx)
            remaining_needed -= quantity_to_use
        
        logger.info('Для тикера %s использовано %d покупок из предыдущих сделок (LIFO), количество: %s',
                   ticker, len(purchases_used), needed_quantity - remaining_needed)
        
        # Формируем DataFrame с использованными сделками
        trades_used_df = previous_purchases.iloc[trades_used_indices].copy() if trades_used_indices else pd.DataFrame()
        
        return purchases_used, trades_used_df
