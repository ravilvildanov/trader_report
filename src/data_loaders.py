import logging
import re
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from decimal import Decimal
import pandas as pd

logger = logging.getLogger(__name__)

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


class DataLoader(ABC):
    """Абстрактный класс для загрузки данных из различных источников."""
    
    @abstractmethod
    def load(self, file_path: Path) -> pd.DataFrame:
        """Загружает данные из файла."""
        pass


class ExcelDataLoader(DataLoader):
    """Загружает данные из Excel файлов."""
    
    def load(self, file_path: Path) -> pd.DataFrame:
        """Загружает Excel отчёт."""
        xls = pd.ExcelFile(file_path, engine='openpyxl')
        sheet_name = next(s for s in xls.sheet_names if 'Trades' in s)
        logger.info('Найден лист: %s', sheet_name)
        
        df = pd.read_excel(xls, sheet_name, engine='openpyxl')
        return self._normalize_columns(df)
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Убирает пробелы в названиях колонок."""
        df = df.copy()
        df.columns = df.columns.str.strip()
        return df


class PDFDataLoader(DataLoader):
    """Загружает данные из PDF файлов."""
    
    def __init__(self):
        if not PDF_AVAILABLE:
            raise ValueError("Для обработки PDF файлов необходимо установить PyPDF2 или pypdf")
    
    def load(self, file_path: Path) -> pd.DataFrame:
        """Загружает PDF отчёт."""
        logger.info('Загрузка PDF отчёта: %s', file_path)
        
        try:
            text = self._extract_text_from_pdf(file_path)
            trades = self._parse_trades_from_text(text)
            logger.info('Извлечено %d сделок из PDF', len(trades))
            return trades
        except Exception as e:
            logger.error('Ошибка при чтении PDF файла: %s', e)
            raise
    
    def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Извлекает текст из PDF файла."""
        with open(file_path, 'rb') as file:
            if 'PyPDF2' in globals():
                pdf_reader = PyPDF2.PdfReader(file)
            else:
                pdf_reader = pypdf.PdfReader(file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        return text
    
    def _parse_trades_from_text(self, text: str) -> pd.DataFrame:
        """Парсит сделки из текста PDF отчёта."""
        trades_section = self._extract_trades_section(text)
        if not trades_section:
            return pd.DataFrame()
        
        trades = []
        lines = trades_section.split('\n')
        
        for line in lines:
            trade = self._parse_trade_line(line)
            if trade:
                trades.append(trade)
        
        if not trades:
            logger.warning('Не удалось извлечь сделки из PDF')
            return pd.DataFrame()
        
        df = pd.DataFrame(trades)
        logger.info('Успешно создан DataFrame с %d сделками', len(df))
        return df
    
    def _extract_trades_section(self, text: str) -> str:
        """Извлекает секцию с информацией о сделках."""
        section_pattern = r'5\.\s*Информация о совершенных сделках'
        section_match = re.search(section_pattern, text, re.IGNORECASE)
        
        if not section_match:
            section_pattern = r'Информация о совершенных сделках|совершенных сделках|сделках'
            section_match = re.search(section_pattern, text, re.IGNORECASE)
        
        if not section_match:
            logger.warning('Секция с информацией о сделках не найдена')
            return ""
        
        start_pos = section_match.end()
        end_pattern = r'6\.\s*Обязательства клиента|6\.\s*[А-Я]'
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)
        
        if end_match:
            end_pos = start_pos + end_match.start()
        else:
            end_pos = len(text)
        
        return text[start_pos:end_pos]
    
    def _parse_trade_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Парсит строку сделки."""
        # Убираем нумерацию страниц
        line = re.sub(r'\s+\d+\s+из\s+\d+$', '', line.strip())
        
        if not line or 'Тикер |Вид |' in line or line.startswith('5.'):
            return None
        
        parts = line.split()
        if len(parts) < 11:
            return None
        
        try:
            return self._create_trade_record(parts)
        except (ValueError, IndexError) as e:
            logger.warning('Не удалось распарсить строку: %s. Ошибка: %s', line, e)
            return None
    
    def _create_trade_record(self, parts: list) -> Optional[Dict[str, Any]]:
        """Создаёт запись о сделке из частей строки."""
        ticker = parts[0]
        operation = self._normalize_operation(parts[1])
        price = Decimal(parts[2].replace(',', '.'))
        quantity = abs(int(parts[3].replace(',', '')))
        amount = Decimal(parts[4].replace(',', ''))
        broker_commission = Decimal(parts[5].replace(',', '.'))
        exchange_commission = Decimal(parts[6].replace(',', '.'))
        
        # Последние 4 части: Путь Место Дата Время
        path = parts[-4]
        place = parts[-3]
        date_time = f"{parts[-2]} {parts[-1]}"
        
        # Примечание - это всё что между комиссией и путём
        note = ' '.join(parts[7:-4])
        
        # Пропускаем сделки с примечанием "Batch transfer TFOS"
        if "Batch transfer TFOS" in note:
            return None
        
        # Парсим дату и время
        date_part, time_part = date_time.split(' ')
        day, month, year = date_part.split('.')
        date_obj = pd.to_datetime(f"{year}-{month}-{day} {time_part}")

        # Добавляем место к тикеру как в новых отчетах
        ticker = f"{ticker}.{place}"
        
        return {
            'Тикер': ticker,
            'Операция': operation,
            'Количество': quantity,
            'Цена': price,
            'Валюта': 'USD',
            'Сумма': abs(amount),
            'Комиссия': (broker_commission + exchange_commission).quantize(Decimal('0.01')),
            'Валюта комиссии': 'USD',
            'Дата сделки': date_obj,
            'Расчеты': date_obj
        }
    
    def _normalize_operation(self, raw_operation: str) -> str:
        """Нормализует название операции."""
        op = str(raw_operation or '').strip()
        op_lower = op.lower()
        
        if ('покуп' in op_lower) or ('купл' in op_lower) or ('buy' in op_lower):
            return 'Покупка'
        if ('продаж' in op_lower) or ('sell' in op_lower):
            return 'Продажа'
        
        return op


class DataLoaderFactory:
    """Фабрика для создания загрузчиков данных."""
    
    @staticmethod
    def create_loader(file_path: Path) -> DataLoader:
        """Создаёт соответствующий загрузчик для файла."""
        if file_path.suffix.lower() == '.pdf':
            return PDFDataLoader()
        else:
            return ExcelDataLoader()
