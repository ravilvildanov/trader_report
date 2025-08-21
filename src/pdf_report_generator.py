import logging
from decimal import Decimal
from typing import Dict, Any, List
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus.flowables import Flowable
from pathlib import Path

from .font_manager import FontManager

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Генерирует PDF отчёты."""
    
    def __init__(self, font_manager: FontManager):
        self.font_manager = font_manager
    
    def generate_closed_positions_report(self, closed_summary_df: pd.DataFrame, 
                                       processed_df: pd.DataFrame, summary_df: pd.DataFrame,
                                       output_file: Path):
        """Генерирует PDF отчёт по закрытым позициям."""
        if closed_summary_df.empty:
            logger.warning('Нет данных для PDF отчёта - closed_summary пуст')
            return
        
        doc = SimpleDocTemplate(str(output_file), pagesize=A4)
        styles = self._create_styles()
        elements = []
        
        # Раздел для каждого тикера
        tickers_to_process = closed_summary_df[closed_summary_df['Тикер'] != 'Итого']
        if tickers_to_process.empty:
            logger.warning('Нет тикеров для обработки в PDF отчёте')
            return
        
        for ticker in tickers_to_process['Тикер']:
            elements.extend(self._create_ticker_section(ticker, processed_df, summary_df, styles))
        
        # Глобальные итоги
        elements.extend(self._create_global_summary(closed_summary_df, styles))
        
        # Строим документ
        doc.build(elements)
        logger.info('PDF отчёт сохранён: %s', output_file)
    
    def _create_styles(self) -> Dict[str, Any]:
        """Создаёт стили для PDF отчёта."""
        styles_raw = getSampleStyleSheet()
        
        normal_style = styles_raw['Normal'].clone('normal')
        normal_style.fontName = self.font_manager.sans_font
        
        heading_style = styles_raw['Normal'].clone('heading')
        heading_style.fontName = self.font_manager.sans_font
        heading_style.fontSize = 14
        heading_style.leading = 16
        heading_style.spaceAfter = 6
        heading_style.spaceBefore = 12
        
        return {
            'normal': normal_style,
            'heading': heading_style
        }
    
    def _create_ticker_section(self, ticker: str, processed_df: pd.DataFrame, 
                              summary_df: pd.DataFrame, styles: Dict[str, Any]) -> List[Flowable]:
        """Создаёт секцию для тикера."""
        elements = []
        
        # Заголовок тикера
        elements.append(Paragraph(ticker, styles['heading']))
        
        # Данные тикера
        ticker_data = processed_df.loc[processed_df['Тикер'] == ticker].copy()
        ticker_data['Операция'] = ticker_data['Операция'].astype(str).str.strip()
        
        # Таблицы покупок и продаж
        purchase_table = self._create_operations_table(ticker_data, 'Покупка', styles)
        sale_table = self._create_operations_table(ticker_data, 'Продажа', styles)
        
        # Объединяем таблицы
        wrapper = Table([[purchase_table, sale_table]], colWidths=[270, 270])
        wrapper.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        
        elements.append(wrapper)
        elements.append(Spacer(1, 12))
        
        # Итог по тикеру
        financial_result = summary_df.loc[summary_df['Тикер'] == ticker, 'Финансовый_результат_в_руб'].iloc[0]
        result_decimal = Decimal(str(financial_result)) if not pd.isna(financial_result) else Decimal('0')
        color = 'green' if result_decimal >= 0 else 'red'
        
        elements.append(Paragraph(
            f"Итог по тикеру: <font color='{color}'>{financial_result}</font>",
            styles['normal']
        ))
        elements.append(Spacer(1, 24))
        
        return elements
    
    def _create_operations_table(self, ticker_data: pd.DataFrame, operation_type: str, 
                                styles: Dict[str, Any]) -> Table:
        """Создаёт таблицу операций."""
        operation_data = ticker_data[ticker_data['Операция'] == operation_type]
        
        # Ограничиваем количество строк для предотвращения переполнения страницы
        max_rows = 8
        if len(operation_data) > max_rows:
            operation_data = operation_data.head(max_rows)
            logger.info(f'Ограничено количество строк для {operation_type} до {max_rows}')
        
        data = [['Дата', 'Кол-во', 'Цена USD', 'Комиссия руб', 'Итог руб']]
        for _, row in operation_data.iterrows():
            data.append([
                row['Расчеты'].strftime('%Y-%m-%d'),
                str(row['Количество']),
                f"{row['Цена']}",
                str(row['Комиссия брокера руб']),
                str(row['Итог в руб'])
            ])
        
        # Создаём подпись и таблицу
        label = Paragraph(operation_type, styles['normal'])
        table = Table(data, colWidths=[60, 40, 40, 60, 60])
        
        # Стиль таблицы
        table_style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_manager.sans_font),
            ('FONTSIZE', (0, 0), (-1, -1), 6),  # Уменьшили размер шрифта
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),  # Уменьшили отступы
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1),   # Уменьшили отступы
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1)
        ])
        table.setStyle(table_style)
        
        # Объединяем подпись и таблицу
        combined = Table([[label], [table]], colWidths=[270])
        return combined
    
    def _create_global_summary(self, closed_summary_df: pd.DataFrame, styles: Dict[str, Any]) -> List[Flowable]:
        """Создаёт глобальную сводку."""
        elements = []
        
        elements.append(Paragraph('Глобальные итоги по закрытым позициям', styles['heading']))
        
        total_row = closed_summary_df.loc[closed_summary_df['Тикер'] == 'Итого'].iloc[0]
        
        data = [
            ['Сумма покупок', 'Сумма продаж', 'Сумма комиссий', 'Итог фин. результат'],
            [
                str(total_row['Сумма покупок']),
                str(total_row['Сумма продаж']),
                str(total_row['Сумма комиссий']),
                str(total_row['Итог'])
            ]
        ]
        
        table = Table(data, colWidths=[120] * 4)
        style = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), self.font_manager.sans_font),
            ('FONTSIZE', (0, 0), (-1, -1), 6),  # Уменьшили размер шрифта
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),  # Уменьшили отступы
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1),   # Уменьшили отступы
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1)
        ])
        
        result_val = total_row['Итог']
        text_color = colors.green if result_val >= 0 else colors.red
        style.add('TEXTCOLOR', (3, 1), (3, 1), text_color)
        
        table.setStyle(style)
        elements.append(table)
        
        return elements
