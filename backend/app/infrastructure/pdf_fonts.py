from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_PATHS = {
    "DejaVu": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVu-Bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}
_FALLBACK_FONT = "Helvetica"
_FALLBACK_FONT_BOLD = "Helvetica-Bold"

_registered = False


def register_fonts() -> tuple[str, str]:
    """Пытается зарегистрировать DejaVu (кириллица); если шрифтов нет — Helvetica (только латиница)."""
    global _registered
    if not _registered:
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", _FONT_PATHS["DejaVu"]))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", _FONT_PATHS["DejaVu-Bold"]))
        except Exception:
            pass
        _registered = True
    if "DejaVu" in pdfmetrics.getRegisteredFontNames():
        return "DejaVu", "DejaVu-Bold"
    return _FALLBACK_FONT, _FALLBACK_FONT_BOLD
