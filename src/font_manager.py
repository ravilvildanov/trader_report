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
        """Регистрирует TTF-шрифты с поддержкой кириллицы. Без изменения внешнего API."""
        # Пары Regular/Bold, которые реально содержат кириллицу на популярных ОС
        candidates = [
            # Linux
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
             "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
            # macOS
            ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            ("/System/Library/Fonts/Supplemental/Arial.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            # Windows
            (r"C:\Windows\Fonts\arial.ttf",
             r"C:\Windows\Fonts\arialbd.ttf"),
            (r"C:\Windows\Fonts\segoeui.ttf",
             r"C:\Windows\Fonts\segoeuib.ttf"),
        ]

        for regular, bold in candidates:
            if not Path(regular).exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont("CustomSans", regular))
                if Path(bold).exists():
                    pdfmetrics.registerFont(TTFont("CustomSans-Bold", bold))
                    self.bold_font = "CustomSans-Bold"
                else:
                    self.bold_font = "CustomSans"  # нет явного bold — используем regular

                self.sans_font = "CustomSans"
                logger.info(f"Используется шрифт {self.sans_font} ({regular})")
                return
            except Exception as e:
                logger.warning(f"Не удалось зарегистрировать {regular} / {bold}: {e}")

        # Фолбэк: стандартные шрифты ReportLab не покрывают кириллицу
        logger.warning("Не найден подходящий TTF с кириллицей. Используются Helvetica/Helvetica-Bold.")
        logger.warning("Русский текст может отображаться как квадраты.")