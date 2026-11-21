"""Arayüz yardımcıları: arka plan işleri, aranabilir açılır liste, tablo, yazdırma."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QCompleter, QHeaderView, QMessageBox,
                               QTableWidget, QTableWidgetItem, QWidget)

_canli: set = set()


class _Sinyal(QObject):
    bitti = Signal(object)
    hata = Signal(object)


class _Is(QRunnable):
    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self.sinyal = _Sinyal()

    def run(self):
        try:
            try:
                sonuc = self.fn()
            except Exception as exc:  # noqa: BLE001
                self.sinyal.hata.emit(exc)
            else:
                self.sinyal.bitti.emit(sonuc)
        except RuntimeError:  # pencere/uygulama kapanırken sinyal nesnesi silinmiş olabilir
            pass


def arkada(fn: Callable[[], Any], tamam: Callable[[Any], None], hata: Callable[[Exception], None] | None = None,
           mesgul: QWidget | None = None) -> None:
    """fn'i arka planda çalıştırır; sonuç/hata ana iş parçacığında geri çağrılır."""
    is_ = _Is(fn)
    _canli.add(is_)
    if mesgul is not None:
        mesgul.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    def bitir():
        _canli.discard(is_)
        if mesgul is not None:
            mesgul.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def ok(sonuc):
        bitir()
        tamam(sonuc)

    def err(exc):
        bitir()
        if hata:
            hata(exc)
        else:
            hata_goster(None, exc)

    is_.sinyal.bitti.connect(ok)
    is_.sinyal.hata.connect(err)
    QThreadPool.globalInstance().start(is_)


def hata_goster(ust: QWidget | None, exc: Exception | str, baslik: str = "Hata") -> None:
    QMessageBox.warning(ust, baslik, str(exc) or exc.__class__.__name__)


def aranabilir(cb: QComboBox) -> QComboBox:
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    tamamlayici = cb.completer()
    tamamlayici.setFilterMode(Qt.MatchFlag.MatchContains)
    tamamlayici.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
    tamamlayici.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    return cb


def tablo(sutunlar: list[str], secim_coklu: bool = True) -> QTableWidget:
    t = QTableWidget(0, len(sutunlar))
    t.setHorizontalHeaderLabels(sutunlar)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if secim_coklu
                       else QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    t.horizontalHeader().setStretchLastSection(True)
    return t


def hucre(deger: Any, sayi: bool = False) -> QTableWidgetItem:
    if isinstance(deger, float):
        metin = f"{deger:,.0f}".replace(",", ".") if deger.is_integer() else f"{deger:,.2f}"
    else:
        metin = "" if deger is None else str(deger)
    item = QTableWidgetItem(metin)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if sayi or isinstance(deger, (int, float)):
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


def adet_metni(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".") if float(x).is_integer() else f"{x:,.2f}"


def yazdir(ust: QWidget, html: str) -> None:
    yazici = QPrinter(QPrinter.PrinterMode.HighResolution)
    onizleme = QPrintPreviewDialog(yazici, ust)
    onizleme.setWindowTitle("Yazdır")

    def ciz(p):
        belge = QTextDocument()
        belge.setHtml(html)
        belge.print_(p)

    onizleme.paintRequested.connect(ciz)
    onizleme.resize(900, 700)
    onizleme.exec()
