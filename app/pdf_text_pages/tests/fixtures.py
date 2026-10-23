"""Synthetic, nonconfidential PDFs generated locally; expected answers below."""

import io

from PIL import Image, ImageDraw
from reportlab.lib.pdfencrypt import StandardEncryption
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas


def make_pdf(
    word: str = "ALPHA",
    mixed: bool = False,
    encrypted: bool = False,
    pages: int = 1,
    size: tuple[int, int] = (595, 842),
) -> bytes:
    buf = io.BytesIO()
    c = Canvas(
        buf,
        pagesize=size,
        invariant=1,
        encrypt=StandardEncryption("test-password") if encrypted else None,
    )
    for index in range(pages):
        c.setFont("Helvetica", 14)
        c.drawString(
            40, size[1] - 60, f"{word} physical page {index + 1}; amount 42 kg"
        )
        c.setStrokeColorRGB(0, 0, 1)
        c.line(100, 120, 200, 120)
        if word == "BETA":
            c.line(100, 120, 112, 132)
            c.line(100, 120, 112, 108)
        else:
            c.line(200, 120, 188, 132)
            c.line(200, 120, 188, 108)
        c.showPage()
    if mixed:
        image = Image.new("RGB", (300, 100), "white")
        ImageDraw.Draw(image).rectangle((10, 10, 290, 90), fill="green")
        c.drawImage(ImageReader(image), 40, 400, width=300, height=100)
        c.showPage()
        c.showPage()  # Intentionally blank; not categorized from missing text alone.
        c.setPageSize((842, 595))
        c.setPageRotation(90)
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        c.setFont("HeiseiMin-W3", 18)
        c.drawString(50, 300, "日本語の凡例：42キログラム")
        c.showPage()
    c.save()
    return buf.getvalue()
