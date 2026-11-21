"""Excel okuma/yazma ve yazdırma için HTML."""

from __future__ import annotations

import datetime as dt
import html
from pathlib import Path

YAZAR = "Mağazalar Arası Transfer"


# ------------------------------------------------------------------ Excel'den yükleme
def _baslik(v) -> str:
    t = str(v or "").strip().lower()
    for a, b in (("ı", "i"), ("İ", "i"), ("ü", "u"), ("ş", "s"), ("ö", "o"), ("ç", "c"), ("ğ", "g"), (" ", "")):
        t = t.replace(a, b)
    return t


BASLIKLAR = {
    "barkod": {"barkod", "barcode", "usedbarcode"},
    "adet": {"adet", "miktar", "qty", "qty1", "quantity"},
    "urun": {"urunkodu", "urun", "itemcode", "stokkodu", "model"},
    "renk": {"renk", "renkkodu", "colorcode", "color"},
    "beden": {"beden", "itemdim1code", "size", "bedenkodu"},
}


def excel_oku(yol: str | Path) -> list[dict]:
    """İlk sayfadaki tabloyu okur. Gerekli: Barkod + Adet  ya da  Ürün Kodu + Renk + Beden + Adet.
    Dönen satırlar: {'barkod','urun','renk','beden','adet','satir_no'}"""
    from openpyxl import load_workbook

    kitap = load_workbook(yol, read_only=True, data_only=True)
    sayfa = kitap.worksheets[0]
    satirlar = list(sayfa.iter_rows(values_only=True))
    kitap.close()
    for i, satir in enumerate(satirlar[:20]):
        sutun = {}
        for j, v in enumerate(satir):
            b = _baslik(v)
            for anahtar, adlar in BASLIKLAR.items():
                if b in adlar and anahtar not in sutun:
                    sutun[anahtar] = j
        if "adet" in sutun and ("barkod" in sutun or "urun" in sutun):
            break
    else:
        raise ValueError("Excel'de başlık bulunamadı. 'Barkod' ve 'Adet' (ya da 'Ürün Kodu', 'Renk', 'Beden', 'Adet') sütunları olmalı.")

    def al(satir, anahtar):
        j = sutun.get(anahtar)
        if j is None or j >= len(satir) or satir[j] is None:
            return ""
        v = satir[j]
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return str(v).strip()

    sonuc = []
    for no, satir in enumerate(satirlar[i + 1:], start=i + 2):
        if not satir or all(v in (None, "") for v in satir):
            continue
        adet_metin = al(satir, "adet").replace(",", ".")
        try:
            adet = float(adet_metin) if adet_metin else 0
        except ValueError:
            adet = 0
        kayit = {"barkod": al(satir, "barkod"), "urun": al(satir, "urun"), "renk": al(satir, "renk"),
                 "beden": al(satir, "beden"), "adet": adet, "satir_no": no}
        if kayit["barkod"] or kayit["urun"]:
            sonuc.append(kayit)
    return sonuc


# ------------------------------------------------------------------ Excel'e yazma
def excel_yaz(yol: str | Path, baslik: str, sutunlar: list[str], satirlar: list[list], bilgi: list[tuple[str, str]] | None = None) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    kitap = Workbook()
    kitap.properties.creator = YAZAR
    kitap.properties.lastModifiedBy = YAZAR
    kitap.properties.title = baslik
    s = kitap.active
    s.title = baslik[:31].replace("/", "-")
    s["A1"] = baslik
    s["A1"].font = Font(bold=True, size=14, color="1F3864")
    r = 2
    for etiket, deger in bilgi or []:
        s.cell(r, 1, etiket).font = Font(bold=True)
        s.cell(r, 2, deger)
        r += 1
    r += 1
    ince = Side(style="thin", color="BFBFBF")
    for j, ad in enumerate(sutunlar, 1):
        h = s.cell(r, j, ad)
        h.font = Font(bold=True, color="FFFFFF")
        h.fill = PatternFill("solid", fgColor="1F4E78")
        h.alignment = Alignment(horizontal="center", vertical="center")
        h.border = Border(top=ince, bottom=ince, left=ince, right=ince)
    ilk = r + 1
    for satir in satirlar:
        r += 1
        for j, v in enumerate(satir, 1):
            c = s.cell(r, j, v)
            c.border = Border(top=ince, bottom=ince, left=ince, right=ince)
            if isinstance(v, (dt.date, dt.datetime)):
                c.number_format = "dd.mm.yyyy"
    s.freeze_panes = s.cell(ilk, 1)
    if satirlar:
        s.auto_filter.ref = f"A{ilk - 1}:{get_column_letter(len(sutunlar))}{r}"
    for j, ad in enumerate(sutunlar, 1):
        uzun = max([len(str(ad))] + [len(str(x[j - 1])) for x in satirlar if j - 1 < len(x) and x[j - 1] is not None] or [10])
        s.column_dimensions[get_column_letter(j)].width = min(max(10, uzun + 2), 50)
    kitap.save(yol)


def sablon_yaz(yol: str | Path) -> None:
    excel_yaz(yol, "Transfer Listesi", ["Barkod", "Adet"], [["8680000000000", 1]],
              [("Not", "Barkod yerine 'Ürün Kodu', 'Renk', 'Beden' sütunları da kullanılabilir.")])


# ------------------------------------------------------------------ yazdırma
def fis_html(baslik: str, bilgi: list[tuple[str, str]], satirlar: list[list], sutunlar: list[str], not_metni: str = "") -> str:
    e = html.escape
    bilgi_html = "".join(f"<tr><td class='e'>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in bilgi)
    bas = "".join(f"<th>{e(s)}</th>" for s in sutunlar)
    gov = "".join("<tr>" + "".join(f"<td>{e('' if v is None else str(v))}</td>" for v in s) + "</tr>" for s in satirlar)
    return f"""<html><head><style>
body {{ font-family: 'Segoe UI', Arial; font-size: 10pt; }}
h2 {{ color: #1F3864; margin-bottom: 4px; }}
table.b td {{ padding: 2px 10px 2px 0; }} td.e {{ font-weight: bold; }}
table.s {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
table.s th {{ background: #1F4E78; color: white; padding: 4px; border: 1px solid #999; }}
table.s td {{ padding: 3px 4px; border: 1px solid #999; }}
p.n {{ margin-top: 14px; font-size: 9pt; color: #444; }}
</style></head><body>
<h2>{e(baslik)}</h2><table class='b'>{bilgi_html}</table>
<table class='s'><tr>{bas}</tr>{gov}</table>
<p class='n'>{e(not_metni)}</p>
<table class='b' style='margin-top:30px; width:100%'><tr><td>Teslim eden: ....................</td><td>Teslim alan: ....................</td></tr></table>
</body></html>"""
