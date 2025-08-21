#!/usr/bin/env python3
"""
Основной файл для запуска обработки брокерских отчётов.
"""

import logging
from pathlib import Path
from src.trade_report_processor import TradeReportProcessor

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Основная функция."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Обработка брокерских отчётов и курсов валют')
    parser.add_argument('broker', type=Path, help='Путь к брокерскому отчёту (.xlsx)')
    parser.add_argument('rates', type=Path, help='Путь к файлу курсов (.xlsx)')
    parser.add_argument('previous', type=Path, nargs='?', help='Путь к отчёту за прошлый период (.xlsx)')
    parser.add_argument('--out', type=Path, default=Path('.'), help='Папка для сохранения результатов')
    
    args = parser.parse_args()
    
    # Создаём и запускаем процессор
    processor = TradeReportProcessor(args.broker, args.rates)
    processor.process()
    
    # Обрабатываем отрицательный остаток
    processor.handle_negative_positions(args.previous)
    
    # Сохраняем результаты
    processor.save_reports(args.out)


if __name__ == '__main__':
    main()
