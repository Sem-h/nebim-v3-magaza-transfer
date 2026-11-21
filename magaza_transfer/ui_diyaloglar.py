"""Bağlantı ayarları, sorgu kurulumu, ürün arama, kayıt önizleme ve fiş detayı pencereleri."""

from __future__ import annotations

import copy
import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidgetItem, QVBoxLayout)

from . import belgeler, kurulum
from .ayarlar import Ayarlar
from .integrator import Integrator
from .servis import Magaza, Satir, TransferOzet, TransferServisi, TransferSonuc
from .ui_ortak import adet_metni, arkada, hata_goster, hucre, tablo, yazdir

EIRSALIYE_NOTU = ("e-İrsaliye bu programla kesilmez: transfer fişi oluştuktan sonra gönderen mağaza "
                  "e-İrsaliyeyi Nebim'den keser.")


# ====================================================================== Bağlantı
class BaglantiPenceresi(QDialog):
    def __init__(self, ayarlar: Ayarlar, ust=None):
        super().__init__(ust)
        self.setWindowTitle("Nebim Integrator Bağlantısı")
        self.ayarlar = ayarlar
        self.setMinimumWidth(520)
        d = QVBoxLayout(self)
        d.addWidget(QLabel("Nebim V3 Integrator bilgilerini girin. Program kendi veritabanını kullanmaz; "
                           "her şey bu bağlantı üzerinden yapılır."))
        f = QFormLayout()
        self.url = QLineEdit(ayarlar.url)
        self.url.setPlaceholderText("http://sunucu:port")
        self.db = QLineEdit(ayarlar.veritabani)
        self.grup = QLineEdit(ayarlar.kullanici_grubu)
        self.kul = QLineEdit(ayarlar.kullanici)
        self.sifre = QLineEdit(ayarlar.sifre)
        self.sifre.setEchoMode(QLineEdit.EchoMode.Password)
        self.sifre.setPlaceholderText("Gerekmiyorsa boş bırakın")
        f.addRow("Integrator adresi", self.url)
        f.addRow("Veritabanı adı", self.db)
        f.addRow("Kullanıcı grubu", self.grup)
        f.addRow("Kullanıcı adı", self.kul)
        f.addRow("Şifre", self.sifre)
        d.addLayout(f)

        g = QGroupBox("Transfer ayarları")
        gf = QFormLayout(g)
        self.kabul = QCheckBox("Transfer hedef mağazanın kabulüne düşsün (önerilen)")
        self.kabul.setChecked(ayarlar.kabul_beklensin)
        self.kabul.setToolTip("İşaretliyse mal yolda görünür, alan mağaza kasadan kabul eder. "
                              "İşaretsizse transfer kabul edilmiş yazılır ve alan depoya hemen girer.")
        gf.addRow(self.kabul)
        d.addWidget(g)

        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        d.addWidget(self.durum)
        alt = QHBoxLayout()
        self.test = QPushButton("Bağlantıyı Test Et")
        self.test.clicked.connect(self._test)
        alt.addWidget(self.test)
        alt.addStretch()
        kutu = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        kutu.button(QDialogButtonBox.StandardButton.Save).setText("Kaydet")
        kutu.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        kutu.accepted.connect(self._kaydet)
        kutu.rejected.connect(self.reject)
        alt.addWidget(kutu)
        d.addLayout(alt)

    def _degerler(self) -> Ayarlar:
        a = copy.copy(self.ayarlar)
        a.url, a.veritabani = self.url.text().strip(), self.db.text().strip()
        a.kullanici_grubu, a.kullanici, a.sifre = self.grup.text().strip(), self.kul.text().strip(), self.sifre.text()
        a.kabul_beklensin = self.kabul.isChecked()
        return a

    def _test(self):
        a = self._degerler()
        if not a.tamam:
            self.durum.setText("Adres, veritabanı, kullanıcı grubu ve kullanıcı adı zorunlu.")
            return
        self.durum.setText("Bağlanılıyor…")
        servis = TransferServisi(Integrator(a))

        def calis():
            servis.nebim.baglan()
            return servis.kurulu_surum()

        def tamam(surum):
            if surum and surum[0] == kurulum.SURUM and surum[1] == kurulum.SURUM:
                self.durum.setText(f"✔ Bağlantı tamam. Program sorguları ve yordamı Nebim'de kurulu (sürüm {surum[0]}).")
            else:
                self.durum.setText("✔ Bağlantı tamam. Program sorguları/yordamı Nebim'de kurulu değil ya da eski; "
                                   "kaydettikten sonra 'Kurulum' penceresi açılacak.")

        arkada(calis, tamam, lambda e: self.durum.setText(f"✖ {e}"), mesgul=self)

    def _kaydet(self):
        a = self._degerler()
        if not a.tamam:
            QMessageBox.warning(self, "Eksik bilgi", "Adres, veritabanı, kullanıcı grubu ve kullanıcı adı zorunlu.")
            return
        for alan in ("url", "veritabani", "kullanici_grubu", "kullanici", "sifre", "kabul_beklensin"):
            setattr(self.ayarlar, alan, getattr(a, alan))
        try:
            self.ayarlar.kaydet()
        except OSError as exc:
            hata_goster(self, f"Ayar dosyası yazılamadı: {exc}")
            return
        self.accept()


# ====================================================================== Kurulum
class KurulumPenceresi(QDialog):
    def __init__(self, servis: TransferServisi, kurulu: tuple[str, str] | None, sirket_db: str, ust=None):
        super().__init__(ust)
        self.servis = servis
        self.kuruldu = False
        self.setWindowTitle("Nebim Kurulumu")
        self.setMinimumWidth(600)
        d = QVBoxLayout(self)
        if kurulu:
            durum = f"Nebim'de kurulu: sorgular <b>{kurulu[0] or '-'}</b>, yordam <b>{kurulu[1] or 'yok'}</b>"
        else:
            durum = "Nebim'de program sorguları <b>kurulu değil</b>"
        adlar = ", ".join(a for a, _ in kurulum.SORGULAR)
        bilgi = QLabel(
            f"{durum} · Program sürümü: <b>{kurulum.SURUM}</b><br><br>"
            "Program kendi veritabanını kullanmaz; Nebim'e bir kez şu SQL nesnelerini kurar (sürüm değişince tekrar):<br>"
            f"• <i>NebimV3Master.dbo.bsReportQuery</i>: {len(kurulum.SORGULAR)} okuma sorgusu ({adlar}). "
            "Integrator yalnız burada kayıtlı sorguları çalıştırır.<br>"
            f"• Şirket veritabanı: <i>dbo.{kurulum.YORDAM}</i> transfer kayıt yordamı (Integrator RunProc ile çağrılır).<br>"
            "Başka hiçbir tabloya dokunulmaz.<br><br>"
            "<b>Yol 1:</b> SQL Server yetkili hesabıyla buradan kurun (bilgiler kaydedilmez).<br>"
            "<b>Yol 2:</b> Kurulum betiğini kaydedip BT'ye SSMS'te çalıştırtın.")
        bilgi.setWordWrap(True)
        bilgi.setTextFormat(Qt.TextFormat.RichText)
        d.addWidget(bilgi)

        g = QGroupBox("SQL Server (tek seferlik, kaydedilmez)")
        f = QFormLayout(g)
        self.sunucu = QLineEdit()
        self.sunucu.setPlaceholderText("sunucu\\örnek,port")
        self.win = QCheckBox("Windows kimliğiyle bağlan")
        self.kul = QLineEdit()
        self.sifre = QLineEdit()
        self.sifre.setEchoMode(QLineEdit.EchoMode.Password)
        self.sirket = QLineEdit(sirket_db)
        self.master = QLineEdit("NebimV3Master")
        self.win.toggled.connect(lambda x: (self.kul.setEnabled(not x), self.sifre.setEnabled(not x)))
        f.addRow("Sunucu", self.sunucu)
        f.addRow(self.win)
        f.addRow("Kullanıcı", self.kul)
        f.addRow("Şifre", self.sifre)
        f.addRow("Şirket veritabanı", self.sirket)
        f.addRow("Master veritabanı", self.master)
        d.addWidget(g)

        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        d.addWidget(self.durum)
        alt = QHBoxLayout()
        b_kur = QPushButton("Kur")
        b_kur.clicked.connect(self._kur)
        b_betik = QPushButton("Kurulum Betiğini Kaydet…")
        b_betik.clicked.connect(self._betik)
        b_kapat = QPushButton("Kapat")
        b_kapat.clicked.connect(self.accept)
        alt.addWidget(b_kur)
        alt.addWidget(b_betik)
        alt.addStretch()
        alt.addWidget(b_kapat)
        d.addLayout(alt)

    def _dbler(self) -> tuple[str, str]:
        return self.sirket.text().strip(), self.master.text().strip() or "NebimV3Master"

    def _betik(self):
        sirket, master = self._dbler()
        if not sirket:
            QMessageBox.warning(self, "Eksik bilgi", "Şirket veritabanı adı gerekli.")
            return
        yol, _ = QFileDialog.getSaveFileName(self, "Kurulum betiği", f"MagazaTransfer_Kurulum_{kurulum.SURUM}.sql", "SQL (*.sql)")
        if not yol:
            return
        with open(yol, "w", encoding="utf-8-sig") as f:
            f.write(kurulum.kurulum_betigi(sirket, master))
        self.durum.setText(f"Betik kaydedildi: {yol}")

    def _kur(self):
        sunucu = self.sunucu.text().strip()
        sirket, master = self._dbler()
        if not sunucu or not sirket or (not self.win.isChecked() and not self.kul.text().strip()):
            QMessageBox.warning(self, "Eksik bilgi", "Sunucu, şirket veritabanı ve kullanıcı (ya da Windows kimliği) gerekli.")
            return
        adlar = ", ".join(a for a, _ in kurulum.SORGULAR)
        if QMessageBox.question(self, "Onay", f"Nebim'e şunlar kurulacak:\n\n• {master}.dbo.bsReportQuery: {adlar}\n"
                                f"• {sirket}.dbo.{kurulum.YORDAM}\n\nBaşka tabloya dokunulmaz. Devam edilsin mi?") != QMessageBox.StandardButton.Yes:
            return
        kul, sifre, win = self.kul.text().strip(), self.sifre.text(), self.win.isChecked()
        self.durum.setText("Kuruluyor…")

        def calis():
            eklenen = kurulum.kur(sunucu, kul, sifre, win, sirket, master)
            return eklenen, self.servis.kurulu_surum()

        def tamam(sonuc):
            eklenen, surum = sonuc
            self.sifre.clear()
            self.kuruldu = True
            okunan = f"sorgular {surum[0]}, yordam {surum[1] or 'yok'}" if surum else "okunamadı"
            self.durum.setText(f"✔ {len(eklenen)} nesne kuruldu. Integrator'dan okunan: {okunan}")

        arkada(calis, tamam, lambda e: self.durum.setText(f"✖ Kurulum başarısız: {e}"), mesgul=self)


# ====================================================================== Ürün arama
class UrunAramaPenceresi(QDialog):
    SUTUN = ["Ürün Kodu", "Ürün Adı", "Renk", "Beden", "Stok", "Transfer Adedi"]

    def __init__(self, servis: TransferServisi, depo: str, ust=None):
        super().__init__(ust)
        self.servis, self.depo = servis, depo
        self.secilen: list[Satir] = []
        self._satirlar: list[Satir] = []
        self.setWindowTitle(f"Ürün Ara — {depo} deposu")
        self.resize(860, 560)
        d = QVBoxLayout(self)
        ust_ = QHBoxLayout()
        self.metin = QLineEdit()
        self.metin.setPlaceholderText("Ürün kodunun başı ya da ürün adından bir parça (en az 3 karakter)")
        self.metin.returnPressed.connect(self._ara)
        self.stoklu = QCheckBox("Yalnız stokta olanlar")
        self.stoklu.setChecked(True)
        b = QPushButton("Ara")
        b.clicked.connect(self._ara)
        ust_.addWidget(self.metin, 1)
        ust_.addWidget(self.stoklu)
        ust_.addWidget(b)
        d.addLayout(ust_)
        self.tablo = tablo(self.SUTUN)
        self.tablo.setEditTriggers(self.tablo.EditTrigger.DoubleClicked | self.tablo.EditTrigger.AnyKeyPressed
                                   | self.tablo.EditTrigger.SelectedClicked)
        d.addWidget(self.tablo, 1)
        self.bilgi = QLabel("Transfer adedi sütununa adet yazın; boş/0 olanlar eklenmez.")
        d.addWidget(self.bilgi)
        kutu = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        kutu.button(QDialogButtonBox.StandardButton.Ok).setText("Listeye Ekle")
        kutu.button(QDialogButtonBox.StandardButton.Cancel).setText("Kapat")
        kutu.accepted.connect(self._ekle)
        kutu.rejected.connect(self.reject)
        d.addWidget(kutu)

    def _ara(self):
        metin = self.metin.text()
        if len(metin.strip()) < 3:
            self.bilgi.setText("En az 3 karakter yazın.")
            return
        self.bilgi.setText("Aranıyor…")
        arkada(lambda: self.servis.urun_ara(self.depo, metin, self.stoklu.isChecked()), self._goster,
               lambda e: self.bilgi.setText(f"✖ {e}"), mesgul=self)

    def _goster(self, satirlar: list[Satir]):
        self._satirlar = satirlar
        t = self.tablo
        t.setRowCount(len(satirlar))
        for i, s in enumerate(satirlar):
            t.setItem(i, 0, hucre(s.urun))
            t.setItem(i, 1, hucre(s.urun_adi))
            t.setItem(i, 2, hucre(f"{s.renk} {s.renk_adi}".strip()))
            t.setItem(i, 3, hucre(" ".join(x for x in (s.beden, s.boyut2, s.boyut3) if x)))
            t.setItem(i, 4, hucre(s.stok or 0.0))
            adet = QTableWidgetItem("")
            adet.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            adet.setBackground(QColor("#FFF8DC"))
            t.setItem(i, 5, adet)
        t.resizeColumnsToContents()
        self.bilgi.setText(f"{len(satirlar)} varyant bulundu." if satirlar else "Sonuç yok.")

    def _ekle(self):
        self.secilen = []
        for i, s in enumerate(self._satirlar):
            metin = (self.tablo.item(i, 5).text() if self.tablo.item(i, 5) else "").replace(",", ".").strip()
            try:
                adet = float(metin) if metin else 0
            except ValueError:
                adet = 0
            if adet > 0:
                yeni = copy.copy(s)
                yeni.adet = adet
                self.secilen.append(yeni)
        if not self.secilen:
            self.bilgi.setText("Adet girilmiş satır yok.")
            return
        self.accept()


# ====================================================================== Kayıt önizleme
class OnizlemePenceresi(QDialog):
    def __init__(self, kaynak: Magaza, kaynak_depo: str, hedef: Magaza, hedef_depo: str, tarih: dt.date,
                 aciklama: str, satirlar: list[Satir], kabul_beklensin: bool, sonuc: TransferSonuc, ust=None):
        super().__init__(ust)
        self.setWindowTitle("Transfer Önizleme — Nebim'e kaydetmeden önce kontrol edin")
        self.resize(900, 600)
        d = QVBoxLayout(self)
        toplam = sum(s.adet for s in satirlar)
        yetersiz = [s for s in satirlar if s.stok_yetersiz]
        bilgi = QLabel(
            f"<b>Kaynak:</b> {kaynak.etiket} · depo {kaynak_depo}<br>"
            f"<b>Hedef:</b> {hedef.etiket} · depo {hedef_depo}<br>"
            f"<b>Tarih:</b> {tarih:%d.%m.%Y} · <b>Açıklama:</b> {aciklama or '-'}<br>"
            f"<b>{len(satirlar)} satır, toplam {adet_metni(toplam)} adet</b><br>"
            f"Nebim'de oluşacak: transfer siparişi <b>{sonuc.siparis_no}</b> + sevkiyat fişi <b>{sonuc.fis_no}</b> "
            f"(numaralar tahmini, kayıtta kesinleşir; örnek alınan kasa fişi {sonuc.ornek_fis})<br>"
            + ("Transfer hedef mağazanın <b>kabulüne düşecek</b> (mal yolda görünür)."
               if kabul_beklensin else "Transfer <b>kabul edilmiş</b> olarak yazılacak (hedef stoğa hemen girer).")
            + f"<br><span style='color:#7a4b00'>{EIRSALIYE_NOTU}</span>")
        bilgi.setTextFormat(Qt.TextFormat.RichText)
        bilgi.setWordWrap(True)
        d.addWidget(bilgi)
        t = tablo(["Barkod", "Ürün Kodu", "Ürün Adı", "Renk", "Beden", "Adet", "Kaynak Stok"])
        t.setRowCount(len(satirlar))
        for i, s in enumerate(satirlar):
            for j, v in enumerate([s.barkod, s.urun, s.urun_adi, f"{s.renk} {s.renk_adi}".strip(), s.beden, float(s.adet),
                                   float(s.stok) if s.stok is not None else "?"]):
                c = hucre(v)
                if s.stok_yetersiz:
                    c.setBackground(QColor("#F8D7DA"))
                t.setItem(i, j, c)
        t.resizeColumnsToContents()
        d.addWidget(t, 1)
        kutu = QDialogButtonBox()
        if yetersiz:
            uyari = QLabel(f"✖ {len(yetersiz)} satırda kaynak stok yetersiz. Bu satırları düzeltmeden kayıt yapılamaz.")
            uyari.setStyleSheet("color:#a00; font-weight:bold")
            d.addWidget(uyari)
        else:
            kaydet = kutu.addButton("Nebim'e Kaydet", QDialogButtonBox.ButtonRole.AcceptRole)
            kaydet.setStyleSheet("font-weight:bold")
        kutu.addButton("Vazgeç", QDialogButtonBox.ButtonRole.RejectRole)
        kutu.accepted.connect(self.accept)
        kutu.rejected.connect(self.reject)
        d.addWidget(kutu)


# ====================================================================== Fiş detayı
def fis_bilgisi(t: TransferOzet) -> list[tuple[str, str]]:
    return [
        ("Fiş No", t.fis_no), ("Tarih", f"{t.tarih:%d.%m.%Y} {t.saat}" if t.tarih else ""),
        ("Gönderen", f"{t.kaynak} — {t.kaynak_adi} (depo {t.kaynak_depo})"),
        ("Alan", f"{t.hedef} — {t.hedef_adi} (depo {t.hedef_depo})"),
        ("Durum", f"Kabul edildi {t.kabul_tarihi:%d.%m.%Y}" if t.kabul and t.kabul_tarihi else ("Kabul edildi" if t.kabul else "Yolda (hedef kabul etmedi)")),
        ("e-İrsaliye", t.eirsaliye or "Kesilmedi"), ("Açıklama", t.aciklama), ("Oluşturan", t.olusturan),
    ]


SATIR_SUTUN = ["Sıra", "Barkod", "Ürün Kodu", "Ürün Adı", "Renk", "Beden", "Adet"]


def satir_degerleri(satirlar: list[Satir]) -> list[list]:
    return [[i, s.barkod, s.urun, s.urun_adi, f"{s.renk} {s.renk_adi}".strip(),
             " ".join(x for x in (s.beden, s.boyut2, s.boyut3) if x), s.adet] for i, s in enumerate(satirlar, 1)]


def fis_yazdir(ust, t: TransferOzet, satirlar: list[Satir]) -> None:
    degerler = satir_degerleri(satirlar)
    degerler.append(["", "", "", "TOPLAM", "", "", sum(s.adet for s in satirlar)])
    yazdir(ust, belgeler.fis_html("Mağazalar Arası Transfer Fişi", fis_bilgisi(t), degerler, SATIR_SUTUN, EIRSALIYE_NOTU))


def fis_excel(ust, t: TransferOzet, satirlar: list[Satir]) -> None:
    yol, _ = QFileDialog.getSaveFileName(ust, "Excel'e aktar", f"Transfer_{t.fis_no}.xlsx", "Excel (*.xlsx)")
    if yol:
        belgeler.excel_yaz(yol, f"Transfer {t.fis_no}", SATIR_SUTUN, satir_degerleri(satirlar), fis_bilgisi(t))


class FisDetayPenceresi(QDialog):
    def __init__(self, t: TransferOzet, satirlar: list[Satir], ust=None):
        super().__init__(ust)
        self.setWindowTitle(f"Transfer Fişi {t.fis_no}")
        self.resize(900, 560)
        d = QVBoxLayout(self)
        bilgi = QLabel("<br>".join(f"<b>{a}:</b> {b}" for a, b in fis_bilgisi(t)))
        bilgi.setTextFormat(Qt.TextFormat.RichText)
        d.addWidget(bilgi)
        tb = tablo(SATIR_SUTUN)
        degerler = satir_degerleri(satirlar)
        tb.setRowCount(len(degerler))
        for i, satir in enumerate(degerler):
            for j, v in enumerate(satir):
                tb.setItem(i, j, hucre(float(v) if j == 6 else v))
        tb.resizeColumnsToContents()
        d.addWidget(tb, 1)
        d.addWidget(QLabel(f"Toplam {adet_metni(sum(s.adet for s in satirlar))} adet, {len(satirlar)} satır"))
        alt = QHBoxLayout()
        b1 = QPushButton("Yazdır")
        b1.clicked.connect(lambda: fis_yazdir(self, t, satirlar))
        b2 = QPushButton("Excel'e Aktar")
        b2.clicked.connect(lambda: fis_excel(self, t, satirlar))
        b3 = QPushButton("Kapat")
        b3.clicked.connect(self.accept)
        alt.addWidget(b1)
        alt.addWidget(b2)
        alt.addStretch()
        alt.addWidget(b3)
        d.addLayout(alt)
