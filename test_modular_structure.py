#!/usr/bin/env python3
"""
Простой тест для проверки модульной структуры.
"""

import sys
from pathlib import Path

def test_imports():
    """Тестирует импорт всех модулей."""
    try:
        from src.font_manager import FontManager
        from src.data_loaders import DataLoader, ExcelDataLoader, PDFDataLoader, DataLoaderFactory
        from src.currency_rates_loader import CurrencyRatesLoader
        from src.trade_data_processor import TradeDataProcessor
        from src.trade_summary_calculator import TradeSummaryCalculator
        from src.negative_balance_handler import NegativeBalanceHandler
        from src.pdf_report_generator import PDFReportGenerator
        from src.trade_report_processor import TradeReportProcessor
        
        print("✅ Все модули успешно импортированы")
        return True
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_class_instantiation():
    """Тестирует создание экземпляров классов."""
    try:
        from src.font_manager import FontManager
        from src.data_loaders import DataLoaderFactory
        from src.currency_rates_loader import CurrencyRatesLoader
        from src.trade_data_processor import TradeDataProcessor
        from src.trade_summary_calculator import TradeSummaryCalculator
        from src.pdf_report_generator import PDFReportGenerator
        
        # Создаём экземпляры классов
        font_manager = FontManager()
        data_loader_factory = DataLoaderFactory()
        currency_rates_loader = CurrencyRatesLoader()
        trade_data_processor = TradeDataProcessor('USD')
        trade_summary_calculator = TradeSummaryCalculator()
        pdf_generator = PDFReportGenerator(font_manager)
        
        print("✅ Все классы успешно созданы")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания классов: {e}")
        return False

def test_file_structure():
    """Проверяет структуру файлов."""
    required_files = [
        'src/__init__.py',
        'src/font_manager.py',
        'src/data_loaders.py',
        'src/currency_rates_loader.py',
        'src/trade_data_processor.py',
        'src/trade_summary_calculator.py',
        'src/negative_balance_handler.py',
        'src/pdf_report_generator.py',
        'src/trade_report_processor.py',
        'main.py',
        'requirements.txt'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {missing_files}")
        return False
    else:
        print("✅ Все необходимые файлы присутствуют")
        return True

def main():
    """Основная функция тестирования."""
    print("🧪 Тестирование модульной структуры...")
    print("=" * 50)
    
    tests = [
        ("Проверка структуры файлов", test_file_structure),
        ("Проверка импортов", test_imports),
        ("Проверка создания классов", test_class_instantiation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ Тест '{test_name}' не пройден")
    
    print("\n" + "=" * 50)
    print(f"📊 Результаты: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Модульная структура работает корректно.")
        return 0
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте структуру модулей.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
