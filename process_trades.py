import logging
from pathlib import Path
from decimal import Decimal, getcontext, ROUND_HALF_UP
import pandas as pd
import re
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Попытка импортировать библиотеки для работы с PDF
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    try:
        import pypdf
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False
        logging.warning("Библиотеки для работы с PDF не установлены. Установите PyPDF2 или pypdf")

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

    def _normalize_operation(self, raw_operation: str) -> str:
        """
        Нормализует название операции к двум значениям: 'Покупка' или 'Продажа'.
        Учитывает варианты из старого отчёта ('Купля') и составные строки
        (например, 'Открытие свопа акциями. Покупка.').
        """
        op = str(raw_operation or '').strip()
        op_lower = op.lower()
        if ('покуп' in op_lower) or ('купл' in op_lower) or ('buy' in op_lower):
            return 'Покупка'
        if ('продаж' in op_lower) or ('sell' in op_lower):
            return 'Продажа'
        # По умолчанию оставим как есть, но лучше явно вернуть один из двух
        return op

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Убираем пробелы в начале и конце названий колонок
        df.columns = df.columns.str.strip()
        return df

    def load_broker_report(self) -> pd.DataFrame:
        logger.info('Загрузка брокерского отчёта: %s', self.broker_path)
        
        # Определяем тип файла по расширению
        if self.broker_path.suffix.lower() == '.pdf':
            if not PDF_AVAILABLE:
                raise ValueError("Для обработки PDF файлов необходимо установить PyPDF2 или pypdf")
            return self._load_pdf_report()
        else:
            return self._load_excel_report()

    def _load_excel_report(self) -> pd.DataFrame:
        """Загружает Excel отчёт."""
        xls = pd.ExcelFile(self.broker_path, engine='openpyxl')
        # Ищем лист, который содержит 'Trades' в названии
        sheet = next(s for s in xls.sheet_names if 'Trades' in s)
        logger.info('Найден лист: %s', sheet)
        df = pd.read_excel(xls, sheet, engine='openpyxl')
        return self._normalize_columns(df)

    def _load_pdf_report(self) -> pd.DataFrame:
        """Загружает PDF отчёт старого формата."""
        logger.info('Загрузка PDF отчёта старого формата')
        
        try:
            # Читаем PDF файл
            if 'PyPDF2' in globals():
                with open(self.broker_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
            else:
                with open(self.broker_path, 'rb') as file:
                    pdf_reader = pypdf.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
            
            logger.info('PDF файл успешно прочитан')
            
            # Парсим сделки из текста
            trades = self._parse_pdf_trades(text)
            logger.info('Извлечено %d сделок из PDF', len(trades))
            
            return trades
            
        except Exception as e:
            logger.error('Ошибка при чтении PDF файла: %s', e)
            raise

    def _parse_pdf_trades(self, text: str) -> pd.DataFrame:
        """Парсит сделки из текста PDF отчёта."""
        trades = []
        
        # Ищем секцию с информацией о сделках
        # Ищем паттерн "5. Информация о совершенных сделках" или похожий
        section_pattern = r'5\.\s*Информация о совершенных сделках'
        section_match = re.search(section_pattern, text, re.IGNORECASE)
        
        if not section_match:
            # Попробуем найти по ключевым словам
            section_pattern = r'Информация о совершенных сделках|совершенных сделках|сделках'
            section_match = re.search(section_pattern, text, re.IGNORECASE)
        
        if not section_match:
            logger.warning('Секция с информацией о сделках не найдена')
            return pd.DataFrame()
        
        start_pos = section_match.end()
        
        # Ищем конец секции (следующий заголовок с номером)
        end_pattern = r'6\.\s*Обязательства клиента|6\.\s*[А-Я]'
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
        
        if end_match:
            end_pos = start_pos + end_match.start()
        else:
            end_pos = len(text)
        
        # Извлекаем текст секции со сделками
        trades_section = text[start_pos:end_pos]
        
        # Парсим строки со сделками
        # Паттерн для строки сделки: Тикер Вид Цена Кол-во Сумма Ком.брок Ком.бир Примечание Путь Место Время
        # Используем более гибкий подход - разбиваем по пробелам и обрабатываем по частям
        lines = trades_section.split('\n')
        for line in lines:
            # Убираем нумерацию страниц типа "2 из 3"
            line = re.sub(r'\s+\d+\s+из\s+\d+$', '', line.strip())
            
            if not line or 'Тикер |Вид |' in line or line.startswith('5.'):
                continue
            
            # Разбиваем строку по пробелам
            parts = line.split()
            if len(parts) < 11:
                continue
            
            try:
                # Извлекаем данные по позициям
                ticker = parts[0]
                operation = self._normalize_operation(parts[1])
                price = Decimal(parts[2].replace(',', '.'))
                # Количество в отчёте по продажам бывает со знаком, нормализуем к модулю
                quantity = abs(int(parts[3].replace(',', '')))
                # Сумма: в отчёте у покупок отрицательная, у продаж положительная.
                # Приводим к модулю и оставляем десятичную точку (убираем только разделитель тысяч).
                amount = Decimal(parts[4].replace(',', ''))
                broker_commission = Decimal(parts[5].replace(',', '.'))
                exchange_commission = Decimal(parts[6].replace(',', '.'))
                
                # Примечание может содержать пробелы, поэтому ищем с конца
                # Последние 4 части: Путь Место Дата Время
                path = parts[-4]
                place = parts[-3]
                date_time = f"{parts[-2]} {parts[-1]}"
                
                # Примечание - это всё что между комиссией и путём
                note = ' '.join(parts[7:-4])
                
                # Парсим дату и время
                date_part, time_part = date_time.split(' ')
                day, month, year = date_part.split('.')
                date_obj = pd.to_datetime(f"{year}-{month}-{day} {time_part}")
                
                # Определяем валюту (обычно USD для US рынков)
                currency = 'USD'
                
                # Создаём запись о сделке в стандартном формате
                trade = {
                    'Тикер': ticker,
                    'ISIN': '',  # В старом формате нет ISIN
                    'Рынок': place,
                    'Операция': operation,
                    'Количество': quantity,
                    'Цена': price,
                    'Валюта': currency,
                    'Сумма': abs(amount),
                    'P/L по закрытым сделкам': 0,  # В старом формате нет
                    'Комиссия': broker_commission + exchange_commission,
                    'Комиссия брокера руб': 0,  # Будет рассчитано позже
                    'Валюта комиссии': currency,
                    'Дата сделки': date_obj,
                    'Расчеты': date_obj,
                    'Order ID': '',  # В старом формате нет
                    'Stamp Tax': 0,  # В старом формате нет
                    'SMAT': ''  # В старом формате нет
                }
                
                trades.append(trade)
                
            except (ValueError, IndexError) as e:
                logger.warning('Не удалось распарсить строку: %s. Ошибка: %s', line, e)
                continue
        

        
        if not trades:
            logger.warning('Не удалось извлечь сделки из PDF')
            return pd.DataFrame()
        
        # Создаём DataFrame
        df = pd.DataFrame(trades)
        logger.info('Успешно создан DataFrame с %d сделками', len(df))
        
        return df

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
        
        # Логируем колонки для отладки
        logger.info('Колонки в trades: %s', self.trades.columns.tolist())
        
        if 'Валюта' in self.trades:
            self.trades['Валюта'] = self.trades['Валюта'].astype(str).str.strip()
            self.trades = self.trades[self.trades['Валюта'] == self.currency]
            logger.info('Отфильтровано %d сделок в валюте %s', len(self.trades), self.currency)
        else:
            logger.warning('Колонка "Валюта" не найдена в данных')

    def merge_and_calculate(self):
        df = self.trades.copy()
        # Нормализуем операцию ('Купля' -> 'Покупка', опции и свопы тоже переводим в базовую форму)
        df['Операция'] = df['Операция'].apply(self._normalize_operation)
        # Приводим количество к модулю, чтобы единообразно считать сальдо
        if 'Количество' in df:
            df['Количество'] = pd.to_numeric(df['Количество'], errors='coerce').abs()
        df['Расчеты'] = pd.to_datetime(df['Расчеты'])
        
        # Добавляем недостающие колонки для PDF отчётов
        if 'P/L по закрытым сделкам' not in df:
            df['P/L по закрытым сделкам'] = 0
        if 'Order ID' not in df:
            df['Order ID'] = ''
        if 'Stamp Tax' not in df:
            df['Stamp Tax'] = 0
        if 'SMAT' not in df:
            df['SMAT'] = ''
        
        merged = pd.merge_asof(df.sort_values('Расчеты'), self.rates.sort_values('data'),
                               left_on='Расчеты', right_on='data', direction='backward')
        merged = merged.drop(columns=['data']).rename(columns={'curs': 'Курс'})
        
        # Обрабатываем числовые колонки
        for col in ['Сумма', 'Комиссия', 'Количество']:
            if col in merged:
                merged[col] = (merged[col].astype(str)
                               .str.replace(',', '.')
                               .str.replace(r"\s+", '', regex=True)
                               .apply(Decimal))
        
        def calc_sum(row):
            amount = Decimal(str(row['Сумма'])) * Decimal(str(row['Курс']))
            return (-amount if 'Покупка' in str(row['Операция']) else amount).quantize(Decimal('0.01'))
        
        merged['Сумма в руб'] = merged.apply(calc_sum, axis=1)
        merged['Комиссия брокера руб'] = (
            merged['Комиссия'].apply(lambda v: Decimal(str(v))) * merged['Курс'].astype(str).apply(Decimal)
        ).apply(lambda x: x.quantize(Decimal('0.01')))
        merged['Итог в руб'] = (merged['Сумма в руб']
                                - merged['Комиссия брокера руб']).apply(lambda x: x.quantize(Decimal('0.01')))
        self.processed = merged

    def recalculate_additional_trades(self):
        """
        Пересчитывает курсы и суммы в рублях для дополнительных сделок из прошлого периода.
        """
        logger.info('Пересчёт курсов для дополнительных сделок из прошлого периода')
        
        # Находим сделки, которые ещё не имеют курса
        additional_trades = self.processed[self.processed['Курс'].isna()].copy()
        
        if additional_trades.empty:
            logger.info('Нет дополнительных сделок для пересчёта')
            return
        
        # Применяем курсы валют к дополнительным сделкам
        for idx, row in additional_trades.iterrows():
            trade_date = row['Расчеты']
            
            # Ищем ближайший курс валюты (не позже даты сделки)
            rate_row = self.rates[self.rates['data'] <= trade_date].iloc[-1] if len(self.rates[self.rates['data'] <= trade_date]) > 0 else None
            
            if rate_row is not None:
                rate = Decimal(str(rate_row['curs']))
                self.processed.loc[idx, 'Курс'] = rate
                
                # Пересчитываем суммы в рублях
                amount = Decimal(str(row['Сумма'])) * rate
                sum_in_rub = (-amount if 'Покупка' in str(row['Операция']) else amount).quantize(Decimal('0.01'))
                self.processed.loc[idx, 'Сумма в руб'] = sum_in_rub
                
                commission_in_rub = (Decimal(str(row['Комиссия'])) * rate).quantize(Decimal('0.01'))
                self.processed.loc[idx, 'Комиссия брокера руб'] = commission_in_rub
                
                self.processed.loc[idx, 'Итог в руб'] = (sum_in_rub - commission_in_rub).quantize(Decimal('0.01'))
                
                logger.info('Пересчитан тикер %s: курс %s, сумма в руб %s', 
                          row['Тикер'], rate, sum_in_rub)
            else:
                logger.warning('Не найден курс валюты для сделки %s от %s', row['Тикер'], trade_date)

    def aggregate_summary(self):
        df = self.processed.copy()
        # Используем подстроку, чтобы учитывать 'Покупка (прошлый период)'
        df['Кол-во signed'] = df.apply(
            lambda r: -r['Количество'] if ('Покупка' in str(r['Операция'])) else r['Количество'], axis=1
        )
        self.summary = df.groupby('Тикер').agg(
            Сальдо=('Кол-во signed', 'sum'),
            Финансовый_результат_в_руб=('Итог в руб', lambda s: sum(s).quantize(Decimal('0.01')))
        ).reset_index()

    def identify_negative_balance_tickers(self):
        """
        Выявляет тикеры с отрицательным сальдо и запрашивает отчёт за прошлый период.
        """
        negative_tickers = self.summary[self.summary['Сальдо'] < 0]
        
        if not negative_tickers.empty:
            logger.info('Найдено %d тикеров с отрицательным сальдо', len(negative_tickers))
            print("\n" + "="*60)
            print("ВНИМАНИЕ: Обнаружены тикеры с отрицательным сальдо!")
            print("="*60)
            print("Это означает, что за текущий период продано больше бумаг, чем куплено.")
            print("\nТикеры с отрицательным сальдо:")
            for _, row in negative_tickers.iterrows():
                print(f"  {row['Тикер']}: {row['Сальдо']} (необходимо найти покупки в прошлом периоде)")
            
            print(f"\nДля корректного расчёта финансовых результатов необходимо")
            print(f"загрузить отчёт за прошлый период (обычно предыдущий год).")
            print(f"\nПожалуйста, подготовьте Excel файл с отчётом за прошлый период")
            print(f"и запустите скрипт снова, указав его как третий аргумент.")
            print("\nПример команды:")
            print(f"python process_trades.py broker_report.xlsx currency_rates.xlsx previous_report.xlsx")
            print("="*60)
            
            return negative_tickers
        else:
            logger.info('Тикеров с отрицательным сальдо не найдено')
            return pd.DataFrame()

    def load_previous_period_report(self, previous_report_path: Path):
        """
        Загружает отчёт за прошлый период для покрытия отрицательного сальдо.
        """
        logger.info('Загрузка отчёта за прошлый период: %s', previous_report_path)
        
        try:
            xls = pd.ExcelFile(previous_report_path, engine='openpyxl')
            # Ищем лист с торговыми данными
            trades_sheet = next((s for s in xls.sheet_names if 'Trades' in s), None)
            
            if not trades_sheet:
                raise ValueError("В файле прошлого периода не найден лист с торговыми данными")
            
            logger.info('Найден лист: %s', trades_sheet)
            df = pd.read_excel(xls, trades_sheet, engine='openpyxl')
            df = self._normalize_columns(df)
            
            # Фильтруем только покупки в USD
            if 'Валюта' in df:
                df['Валюта'] = df['Валюта'].astype(str).str.strip()
                df = df[df['Валюта'] == self.currency]
            
            if 'Операция' in df:
                df['Операция'] = df['Операция'].astype(str).str.strip()
                # Ищем покупки ("Покупка", "Купля", "Buy", "Открытие свопа" и т.д.)
                buy_operations = df[df['Операция'].str.contains('Покупка|Купля|Buy|Открытие', case=False, na=False)]
                logger.info('Найдено %d покупок в прошлом периоде', len(buy_operations))
                return buy_operations
            else:
                raise ValueError("В файле прошлого периода не найдена колонка 'Операция'")
                
        except Exception as e:
            logger.error('Ошибка при загрузке отчёта за прошлый период: %s', e)
            raise

    def process_negative_balance_with_previous_data(self, previous_trades: pd.DataFrame):
        """
        Обрабатывает тикеры с отрицательным сальдо, используя данные прошлого периода.
        """
        logger.info('Обработка тикеров с отрицательным сальдо')
        
        # Получаем тикеры с отрицательным сальдо
        negative_tickers = self.summary[self.summary['Сальдо'] < 0]
        
        if negative_tickers.empty:
            logger.info('Нет тикеров с отрицательным сальдо для обработки')
            return
        
        # Сортируем покупки прошлого периода по дате (новые к старым)
        if 'Расчеты' in previous_trades:
            previous_trades['Расчеты'] = pd.to_datetime(previous_trades['Расчеты'])
            previous_trades = previous_trades.sort_values('Расчеты', ascending=False)
        
        # Обрабатываем каждый тикер с отрицательным сальдо
        for _, ticker_row in negative_tickers.iterrows():
            ticker = ticker_row['Тикер']
            current_balance = ticker_row['Сальдо']  # Отрицательное значение
            remaining_to_cover = abs(current_balance)  # Сколько нужно покрыть
            
            logger.info('Обработка тикера %s: нужно покрыть %d бумаг', ticker, remaining_to_cover)
            
            # Ищем покупки этого тикера в прошлом периоде
            previous_buys = previous_trades[previous_trades['Тикер'] == ticker].copy()
            
            if previous_buys.empty:
                logger.warning('Для тикера %s не найдено покупок в прошлом периоде', ticker)
                continue
            
            # Обрабатываем покупки в обратном порядке (от новых к старым)
            covered_amount = 0
            additional_trades = []
            
            for _, buy_row in previous_buys.iterrows():
                if covered_amount >= remaining_to_cover:
                    break
                
                available_amount = buy_row['Количество']
                needed_amount = remaining_to_cover - covered_amount
                amount_to_use = min(available_amount, needed_amount)
                
                # Создаём запись о дополнительной покупке
                additional_trade = {
                    'Тикер': ticker,
                    'Операция': 'Покупка (прошлый период)',
                    'Количество': amount_to_use,
                    'Цена': buy_row['Цена'],
                    'Валюта': buy_row['Валюта'],
                    'Сумма': buy_row['Сумма'] * (amount_to_use / available_amount),
                    'Комиссия': buy_row.get('Комиссия', 0) * (amount_to_use / available_amount),
                    'Расчеты': buy_row['Расчеты'],
                    'Курс': None,  # Будет рассчитан позже
                    'Сумма в руб': None,  # Будет рассчитан позже
                    'Комиссия брокера руб': None,  # Будет рассчитан позже
                    'Итог в руб': None  # Будет рассчитан позже
                }
                
                additional_trades.append(additional_trade)
                covered_amount += amount_to_use
                
                logger.info('  Покрыто %d бумаг из покупки %s по цене %s', 
                          amount_to_use, buy_row['Расчеты'].strftime('%Y-%m-%d'), buy_row['Цена'])
            
            # Добавляем дополнительные сделки к основным данным
            if additional_trades:
                additional_df = pd.DataFrame(additional_trades)
                self.processed = pd.concat([self.processed, additional_df], ignore_index=True)
                logger.info('Добавлено %d дополнительных сделок для тикера %s', len(additional_trades), ticker)
        
        # Пересчитываем сводки с учётом дополнительных данных
        self.aggregate_summary()
        self.compute_closed_summary()

    def compute_closed_summary(self):
        logger.info('Вычисление сводки по закрытым позициям')
        logger.info('Количество позиций в summary: %d', len(self.summary))
        logger.info('Позиции с нулевым сальдо: %d', len(self.summary[self.summary['Сальдо'] == 0]))
        
        rows = []
        for _, r in self.summary[self.summary['Сальдо'] == 0].iterrows():
            grp = self.processed.loc[self.processed['Тикер'] == r['Тикер']]
            ops = grp['Операция']
            
            # Убеждаемся, что все суммы являются Decimal
            sum_p = Decimal(str(grp.loc[ops == 'Покупка', 'Сумма в руб'].map(lambda x: -x).sum())).quantize(Decimal('0.01'))
            sum_s = Decimal(str(grp.loc[ops == 'Продажа', 'Сумма в руб'].sum())).quantize(Decimal('0.01'))
            sum_c = Decimal(str(grp['Комиссия брокера руб'].sum())).quantize(Decimal('0.01'))
            result = (sum_s - sum_p - sum_c).quantize(Decimal('0.01'))
            rows.append({'Тикер': r['Тикер'], 'Сумма покупок': sum_p,
                         'Сумма продаж': sum_s, 'Сумма комиссий': sum_c, 'Итог': result})
        
        df_closed = pd.DataFrame(rows)
        logger.info('Создано %d записей для закрытых позиций', len(df_closed))
        
        if not df_closed.empty:
            tot = {col: df_closed[col].sum().quantize(Decimal('0.01')) for col in ['Сумма покупок','Сумма продаж','Сумма комиссий','Итог']}
            tot['Тикер'] = 'Итого'
            df_closed = pd.concat([df_closed, pd.DataFrame([tot])], ignore_index=True)
            logger.info('Добавлена строка "Итого"')
        
        self.closed_summary = df_closed
        logger.info('Итоговый размер closed_summary: %d строк', len(self.closed_summary))

    def export_closed_pdf(self, output_file: Path):
        """
        Генерация PDF-отчёта по закрытым позициям в красивом формате с цветовой подсветкой.
        """
        # Проверяем, есть ли данные для отчёта
        if self.closed_summary.empty:
            logger.warning('Нет данных для PDF отчёта - closed_summary пуст')
            return
            
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
        
        # Проверяем, есть ли тикеры кроме "Итого"
        tickers_to_process = self.closed_summary[self.closed_summary['Тикер'] != 'Итого']
        if tickers_to_process.empty:
            logger.warning('Нет тикеров для обработки в PDF отчёте')
            return
            
        # Раздел для каждого тикера
        for ticker in tickers_to_process['Тикер']:
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
            
            # Создаем подписи для таблиц
            purchase_label = Paragraph('Покупки', normal_style)
            sale_label = Paragraph('Продажи', normal_style)
            
            table_p = Table(data_p, colWidths=[60, 40, 40, 60, 60])
            table_s = Table(data_s, colWidths=[60, 40, 40, 60, 60])
            # Общий стиль для таблиц
            tbl_style = TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), sans_font),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
            ])
            table_p.setStyle(tbl_style)
            table_s.setStyle(tbl_style)
            
            # Создаем таблицы с подписями
            purchase_with_label = Table([[purchase_label], [table_p]], colWidths=[270])
            sale_with_label = Table([[sale_label], [table_s]], colWidths=[270])
            
            wrapper = Table([[purchase_with_label, sale_with_label]], colWidths=[270, 270])
            wrapper.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
            elements.append(wrapper)
            elements.append(Spacer(1, 12))
            # Итог по тикеру
            val = self.summary.loc[self.summary['Тикер'] == ticker, 'Финансовый_результат_в_руб'].iloc[0]
            # Убеждаемся, что значение можно сравнить
            val_decimal = Decimal(str(val)) if not pd.isna(val) else Decimal('0')
            color = 'green' if val_decimal >= 0 else 'red'
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
            ('FONTSIZE', (0, 0), (-1, -1), 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
        ])
        result_val = total['Итог']
        txt_color = colors.green if result_val >= 0 else colors.red
        style_tot.add('TEXTCOLOR', (3, 1), (3, 1), txt_color)
        table_tot.setStyle(style_tot)
        elements.append(table_tot)
        # Строим документ
        doc.build(elements)
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
    parser.add_argument('previous', type=Path, nargs='?', help='Путь к отчёту за прошлый период (.xlsx)')
    parser.add_argument('--out', type=Path, default=Path('.'), help='Папка для сохранения результатов')
    args = parser.parse_args()
    
    proc = TradeReportProcessor(args.broker, args.rates)
    proc.preprocess()
    proc.merge_and_calculate()
    proc.aggregate_summary()
    
    # Проверяем наличие тикеров с отрицательным сальдо
    negative_tickers = proc.identify_negative_balance_tickers()
    
    if not negative_tickers.empty:
        if args.previous:
            # Загружаем и обрабатываем данные прошлого периода
            logger.info('Обработка данных прошлого периода для покрытия отрицательного сальдо')
            previous_trades = proc.load_previous_period_report(args.previous)
            proc.process_negative_balance_with_previous_data(previous_trades)
            proc.recalculate_additional_trades()
            proc.aggregate_summary()
            logger.info('Обработка данных прошлого периода завершена')
        else:
            # Если нет файла прошлого периода, сохраняем текущие результаты
            logger.warning('Файл прошлого периода не указан. Сохраняются результаты без учёта отрицательного сальдо.')
    
    proc.compute_closed_summary()
    proc.save(args.out)

if __name__ == '__main__':
    main()
