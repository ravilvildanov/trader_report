import logging
from pathlib import Path
from decimal import Decimal, getcontext, ROUND_HALF_UP
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Настройка Decimal для точных денежных вычислений
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_UP

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Попытка зарегистрировать шрифты для поддержки кириллицы из стандартных директорий Mac
font_candidates = [
    '/Library/Fonts/Arial.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
    '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
]
sans_font = None
bold_font = None
for p in font_candidates:
    if Path(p).exists():
        try:
            pdfmetrics.registerFont(TTFont('CustomSans', p))
            sans_font = 'CustomSans'
            # предположим, что файл с "Bold" в имени для жирного шрифта
            bold_path = p.replace('.ttf', ' Bold.ttf')
            if Path(bold_path).exists():
                pdfmetrics.registerFont(TTFont('CustomSans-Bold', bold_path))
                bold_font = 'CustomSans-Bold'
            else:
                bold_font = sans_font
            logger.info(f"Используется шрифт {sans_font} из {p}")
            break
        except Exception as e:
            logger.warning(f"Не удалось зарегистрировать шрифт из {p}: {e}")
if sans_font is None:
    logger.warning("Шрифты для кириллицы не найдены. Будут использоваться стандартные шрифты без поддержки русского.")
    sans_font = 'Helvetica'
    bold_font = 'Helvetica-Bold'

class TradeReportProcessor:
    """
    Обработчик брокерских отчётов: загрузка, расчёты, агрегации и экспорт.
    """
    def __init__(self, broker_path: Path, rates_path: Path, currency: str = 'USD'):
        self.broker_path = broker_path
        self.rates_path = rates_path
        self.currency = currency
        self.trades = pd.DataFrame()
        self.rates = pd.DataFrame()
        self.processed = pd.DataFrame()
        self.summary = pd.DataFrame()
        self.closed_summary = pd.DataFrame()

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = df.columns.str.strip()
        return df

    def load_broker_report(self) -> pd.DataFrame:
        logger.info('Загрузка брокерского отчёта: %s', self.broker_path)
        xls = pd.ExcelFile(self.broker_path, engine='openpyxl')
        sheet = next(s for s in xls.sheet_names if s.startswith('Trades'))
        df = pd.read_excel(xls, sheet, engine='openpyxl')
        return self._normalize_columns(df)

    def load_currency_rates(self) -> pd.DataFrame:
        logger.info('Загрузка курсов ЦБ: %s', self.rates_path)
        df = pd.read_excel(self.rates_path, sheet_name='RC', engine='openpyxl')
        df = self._normalize_columns(df)
        df = df[df['cdx'].str.strip() == 'Доллар США'][['data', 'curs']]
        df['data'] = pd.to_datetime(df['data'], dayfirst=True)
        df['curs'] = (df['curs'].astype(str)
                      .str.replace(',', '.')
                      .str.replace(r"\s+", '', regex=True)
                      .apply(Decimal))
        return df.sort_values('data')

    def preprocess(self):
        self.trades = self.load_broker_report()
        self.rates = self.load_currency_rates()
        if 'Валюта' in self.trades:
            self.trades['Валюта'] = self.trades['Валюта'].astype(str).str.strip()
            self.trades = self.trades[self.trades['Валюта'] == self.currency]

    def merge_and_calculate(self):
        df = self.trades.copy()
        df['Операция'] = df['Операция'].astype(str).str.strip()
        df['Расчеты'] = pd.to_datetime(df['Расчеты'])
        merged = pd.merge_asof(df.sort_values('Расчеты'), self.rates.sort_values('data'),
                               left_on='Расчеты', right_on='data', direction='backward')
        merged = merged.drop(columns=['data']).rename(columns={'curs': 'Курс'})
        for col in ['Сумма', 'Комиссия', 'SMAT', 'Количество']:
            merged[col] = (merged[col].astype(str)
                           .str.replace(',', '.')
                           .str.replace(r"\s+", '', regex=True)
                           .apply(Decimal))
        def calc_sum(row):
            amount = row['Сумма'] * row['Курс']
            return (-amount if row['Операция'] == 'Покупка' else amount).quantize(Decimal('0.01'))
        merged['Сумма в руб'] = merged.apply(calc_sum, axis=1)
        merged['Комиссия брокера руб'] = (merged['Комиссия'] * merged['Курс']).apply(lambda x: x.quantize(Decimal('0.01')))
#        merged['Комиссия биржи руб'] = (merged['SMAT'] * merged['Курс']).apply(lambda x: x.quantize(Decimal('0.01')))
        merged['Итог в руб'] = (merged['Сумма в руб']
                                - merged['Комиссия брокера руб']).apply(lambda x: x.quantize(Decimal('0.01')))
        self.processed = merged

    def aggregate_summary(self):
        df = self.processed.copy()
        df['Кол-во signed'] = df.apply(lambda r: -r['Количество'] if r['Операция'] == 'Покупка' else r['Количество'], axis=1)
        self.summary = df.groupby('Тикер').agg(
            Сальдо=('Кол-во signed', 'sum'),
            Финансовый_результат_в_руб=('Итог в руб', lambda s: sum(s).quantize(Decimal('0.01')))
        ).reset_index()

    def compute_closed_summary(self):
        rows = []
        for _, r in self.summary[self.summary['Сальдо'] == 0].iterrows():
            grp = self.processed.loc[self.processed['Тикер'] == r['Тикер']]
            ops = grp['Операция']
            sum_p = grp.loc[ops == 'Покупка', 'Сумма в руб'].map(lambda x: -x).sum().quantize(Decimal('0.01'))
            sum_s = grp.loc[ops == 'Продажа', 'Сумма в руб'].sum().quantize(Decimal('0.01'))
            sum_c = (grp['Комиссия брокера руб']).sum().quantize(Decimal('0.01'))
            result = (sum_s - sum_p - sum_c).quantize(Decimal('0.01'))
            rows.append({'Тикер': r['Тикер'], 'Сумма покупок': sum_p,
                         'Сумма продаж': sum_s, 'Сумма комиссий': sum_c, 'Итог': result})
        df_closed = pd.DataFrame(rows)
        if not df_closed.empty:
            tot = {col: df_closed[col].sum().quantize(Decimal('0.01')) for col in ['Сумма покупок','Сумма продаж','Сумма комиссий','Итог']}
            tot['Тикер'] = 'Итого'
            df_closed = pd.concat([df_closed, pd.DataFrame([tot])], ignore_index=True)
        self.closed_summary = df_closed

    def export_closed_pdf(self, output_file: Path):
        """
        Генерация PDF-отчёта по закрытым позициям в красивом формате с цветовой подсветкой.
        """
        doc = SimpleDocTemplate(str(output_file), pagesize=A4)
        # Получаем базовые стили
        styles_raw = getSampleStyleSheet()
        # Создаём кастомные стили с поддержкой кириллицы
        normal_style = styles_raw['Normal'].clone('normal')
        normal_style.fontName = sans_font
        heading_style = styles_raw['Normal'].clone('heading')
        heading_style.fontName = sans_font
        heading_style.fontSize = 14
        heading_style.leading = 16
        heading_style.spaceAfter = 6
        heading_style.spaceBefore = 12
        elements = []
        # Раздел для каждого тикера
        for ticker in self.closed_summary[self.closed_summary['Тикер'] != 'Итого']['Тикер']:
            elements.append(Paragraph(ticker, heading_style))
            grp = self.processed.loc[self.processed['Тикер'] == ticker].copy()
            grp['Операция'] = grp['Операция'].astype(str).str.strip()
            # Данные для таблиц
            def make_data(op_type):
                df_op = grp[grp['Операция'] == op_type]
                data = [['Дата', 'Кол-во', 'Цена USD', 'Комиссия руб', 'Итог руб']]
                for _, r in df_op.iterrows():
                    data.append([
                        r['Расчеты'].strftime('%Y-%m-%d'),
                        str(r['Количество']),
                        f"{r['Цена']}",
                        str(r['Комиссия брокера руб']),
                        str(r['Итог в руб'])
                    ])
                return data
            data_p = make_data('Покупка')
            data_s = make_data('Продажа')
            table_p = Table(data_p, colWidths=[60, 40, 60, 60, 60])
            table_s = Table(data_s, colWidths=[60, 40, 60, 60, 60])
            # Общий стиль для таблиц
            tbl_style = TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), sans_font),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ])
            table_p.setStyle(tbl_style)
            table_s.setStyle(tbl_style)
            wrapper = Table([[table_p, table_s]], colWidths=[270, 270])
            wrapper.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            elements.append(wrapper)
            elements.append(Spacer(1, 12))
            # Итог по тикеру
            val = self.summary.loc[self.summary['Тикер'] == ticker, 'Финансовый_результат_в_руб'].iloc[0]
            color = 'green' if val >= 0 else 'red'
            elements.append(Paragraph(
                f"Итог по тикеру: <font color='{color}'>{val}</font>",
                normal_style
            ))
            elements.append(Spacer(1, 24))
        # Глобальный итог
        elements.append(Paragraph('Глобальные итоги по закрытым позициям', heading_style))
        total = self.closed_summary.loc[self.closed_summary['Тикер'] == 'Итого'].iloc[0]
        data_tot = [
            ['Сумма покупок', 'Сумма продаж', 'Сумма комиссий', 'Итог фин. результат'],
            [
                str(total['Сумма покупок']),
                str(total['Сумма продаж']),
                str(total['Сумма комиссий']),
                str(total['Итог'])
            ]
        ]
        table_tot = Table(data_tot, colWidths=[120] * 4)
        style_tot = TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), sans_font),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ])
        result_val = total['Итог']
        txt_color = colors.green if result_val >= 0 else colors.red
        style_tot.add('TEXTCOLOR', (3, 1), (3, 1), txt_color)
        table_tot.setStyle(style_tot)
        elements.append(table_tot)
        # Строим документ
        doc.build(elements)
        logger.info('PDF отчёт сохранён: %s', output_file)
        logger.info('PDF отчёт сохранён: %s', output_file)

    def save(self, out_dir: Path):
        out_dir.mkdir(parents=True, exist_ok=True)
        self.processed.to_csv(out_dir / 'details.csv', index=False)
        self.summary.to_csv(out_dir / 'summary.csv', index=False)
        self.closed_summary.to_csv(out_dir / 'closed_summary.csv', index=False)
        self.export_closed_pdf(out_dir / 'closed_report.pdf')
        logger.info('Все отчёты сохранены в директории %s', out_dir)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Обработка брокерских отчётов и курсов валют')
    parser.add_argument('broker', type=Path, help='Путь к брокерскому отчёту (.xlsx)')
    parser.add_argument('rates', type=Path, help='Путь к файлу курсов (.xlsx)')
    parser.add_argument('--out', type=Path, default=Path('.'), help='Папка для сохранения результатов')
    args = parser.parse_args()
    proc = TradeReportProcessor(args.broker, args.rates)
    proc.preprocess()
    proc.merge_and_calculate()
    proc.aggregate_summary()
    proc.compute_closed_summary()
    proc.save(args.out)

if __name__ == '__main__':
    main()
