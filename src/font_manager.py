import logging
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class FontManager:
    """Управляет шрифтами для поддержки кириллицы в PDF отчётах."""
    
    def __init__(self):
        self.sans_font = 'Helvetica'
        self.bold_font = 'Helvetica-Bold'
        self._register_custom_fonts()
    
    def _register_custom_fonts(self):
        """Регистрирует кастомные шрифты для поддержки кириллицы."""
        font_candidates = [
            '/Library/Fonts/Arial.ttf',
            '/Library/Fonts/Arial Unicode.ttf',
            '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        ]
        
        for font_path in font_candidates:
            if Path(font_path).exists():
                try:
                    pdfmetrics.registerFont(TTFont('CustomSans', font_path))
                    self.sans_font = 'CustomSans'
                    
                    # Ищем жирный шрифт
                    bold_path = font_path.replace('.ttf', ' Bold.ttf')
                    if Path(bold_path).exists():
                        pdfmetrics.registerFont(TTFont('CustomSans-Bold', bold_path))
                        self.bold_font = 'CustomSans-Bold'
                    else:
                        self.bold_font = self.sans_font
                    
                    logger.info(f"Используется шрифт {self.sans_font} из {font_path}")
                    break
                except Exception as e:
                    logger.warning(f"Не удалось зарегистрировать шрифт из {font_path}: {e}")
        
        if self.sans_font == 'Helvetica':
            logger.warning("Шрифты для кириллицы не найдены. Будут использоваться стандартные шрифты.")
