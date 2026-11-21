"""Ana pencere: Yeni Transfer ve Transfer Geçmişi."""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QFileDialog, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSpinBox,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from . import belgeler, kurulum
from .ayarlar import Ayarlar
from .integrator import Integrator, KayitBelirsizHatasi
from .servis import Magaza, Satir, TransferOzet, TransferServisi
from .ui_diyaloglar import (BaglantiPenceresi, FisDetayPenceresi, KurulumPenceresi, OnizlemePenceresi,
                            UrunAramaPenceresi, fis_yazdir)
from .ui_ortak import adet_metni, aranabilir, arkada, hata_goster, hucre, tablo


def _magaza_doldur(cb: QComboBox, magazalar: list[Magaza], secili: str = "", bos: str = "") -> None:
    cb.blockSignals(True)
    cb.clear()
    if bos:
        cb.addItem(bos, "")
    for m in magazalar:
        cb.addItem(m.etiket, m.kod)
    i = cb.findData(secili)
    cb.setCurrentIndex(i if i >= 0 else (0 if bos else -1))
    cb.blockSignals(False)


# ====================================================================== Yeni transfer
class YeniTransferSekmesi(QWidget):
    SUTUN = ["Barkod", "Ürün Kodu", "Ürün Adı", "Renk", "Beden", "Adet", "Kaynak Stok", "Durum"]
    ADET = 5

    def __init__(self, ana: "AnaPencere"):
        super().__init__()
        self.ana = ana
        self.satirlar: list[Satir] = []
        self._stok: dict[tuple, float] = {}       # (depo, ürün, renk, beden, b2, b3) -> stok
        self._stok_yuklu: set[tuple] = set()      # (depo, ürün)
        d = QVBoxLayout(self)

        g = QGroupBox("Kaynak ve hedef")
        gl = QGridLayout(g)
        self.cb_kaynak = aranabilir(QComboBox())
        self.cb_kaynak_depo = QComboBox()
        self.cb_hedef = aranabilir(QComboBox())
        self.cb_hedef_depo = QComboBox()
        self.tarih = QDateEdit(QDate.currentDate())
        self.tarih.setCalendarPopup(True)
        self.tarih.setDisplayFormat("dd.MM.yyyy")
        self.aciklama = QLineEdit()
        self.aciklama.setMaxLength(200)
        self.aciklama.setPlaceholderText("Fiş açıklaması (isteğe bağlı)")
        gl.addWidget(QLabel("Gönderen mağaza"), 0, 0)
        gl.addWidget(self.cb_kaynak, 0, 1)
        gl.addWidget(QLabel("Depo"), 0, 2)
        gl.addWidget(self.cb_kaynak_depo, 0, 3)
        gl.addWidget(QLabel("Alan mağaza"), 1, 0)
        gl.addWidget(self.cb_hedef, 1, 1)
        gl.addWidget(QLabel("Depo"), 1, 2)
        gl.addWidget(self.cb_hedef_depo, 1, 3)
        gl.addWidget(QLabel("Tarih"), 2, 0)
        gl.addWidget(self.tarih, 2, 1)
        gl.addWidget(QLabel("Açıklama"), 2, 2)
        gl.addWidget(self.aciklama, 2, 3)
        gl.setColumnStretch(1, 2)
        gl.setColumnStretch(3, 2)
        d.addWidget(g)

        okut = QHBoxLayout()
        self.barkod = QLineEdit()
        self.barkod.setPlaceholderText("Barkodu okutun ya da yazıp Enter'a basın (örnek: 3*8690000000000)")
        self.barkod.returnPressed.connect(self._barkod_okut)
        self.adet = QSpinBox()
        self.adet.setRange(1, 99999)
        self.adet.setPrefix("Adet: ")
        b_ara = QPushButton("Ürün Ara…")
        b_ara.clicked.connect(self._urun_ara)
        b_excel = QPushButton("Excel'den Yükle…")
        b_excel.clicked.connect(self._excel_yukle)
        b_sablon = QPushButton("Şablon")
        b_sablon.setToolTip("Boş Excel şablonu kaydet")
        b_sablon.clicked.connect(self._sablon)
        okut.addWidget(self.barkod, 3)
        okut.addWidget(self.adet)
        okut.addWidget(b_ara)
        okut.addWidget(b_excel)
        okut.addWidget(b_sablon)
        d.addLayout(okut)

        self.tablo = tablo(self.SUTUN)
        self.tablo.itemChanged.connect(self._adet_degisti)
        d.addWidget(self.tablo, 1)

        alt = QHBoxLayout()
        self.ozet = QLabel("Satır yok.")
        b_sil = QPushButton("Seçili Satırları Sil")
        b_sil.clicked.connect(self._sil)
        b_temizle = QPushButton("Listeyi Temizle")
        b_temizle.clicked.connect(self._temizle_sor)
        b_stok = QPushButton("Stokları Yenile")
        b_stok.clicked.connect(lambda: self._stok_yukle(yenile=True))
        self.b_olustur = QPushButton("Transferi Oluştur…")
        self.b_olustur.setStyleSheet("font-weight:bold; padding:6px 16px")
        self.b_olustur.clicked.connect(self._olustur)
        alt.addWidget(self.ozet, 1)
        alt.addWidget(b_sil)
        alt.addWidget(b_temizle)
        alt.addWidget(b_stok)
        alt.addWidget(self.b_olustur)
        d.addLayout(alt)

        self.cb_kaynak.currentIndexChanged.connect(lambda: self._depolari_doldur(self.cb_kaynak, self.cb_kaynak_depo))
        self.cb_hedef.currentIndexChanged.connect(lambda: self._depolari_doldur(self.cb_hedef, self.cb_hedef_depo))
        self.cb_kaynak_depo.currentIndexChanged.connect(lambda: self._stok_yukle(yenile=False))

    # ------------------------------------------------------------ mağaza/depo
    @property
    def servis(self) -> TransferServisi:
        return self.ana.servis

    def magazalari_yukle(self, magazalar: list[Magaza]):
        a = self.ana.ayarlar
        _magaza_doldur(self.cb_kaynak, magazalar, self.cb_kaynak.currentData() or a.son_kaynak)
        _magaza_doldur(self.cb_hedef, magazalar, self.cb_hedef.currentData() or a.son_hedef)
        self._depolari_doldur(self.cb_kaynak, self.cb_kaynak_depo)
        self._depolari_doldur(self.cb_hedef, self.cb_hedef_depo)

    def _depolari_doldur(self, cb: QComboBox, cb_depo: QComboBox):
        cb_depo.blockSignals(True)
        cb_depo.clear()
        m = self.servis.magaza(cb.currentData() or "") if self.servis._magazalar else None
        if m:
            for dp in m.depolar:
                cb_depo.addItem(f"{dp.kod} — {dp.ad}" + (" (varsayılan)" if dp.varsayilan else ""), dp.kod)
            vd = m.varsayilan_depo
            cb_depo.setCurrentIndex(max(0, cb_depo.findData(vd.kod if vd else "")))
        cb_depo.blockSignals(False)
        if cb_depo is self.cb_kaynak_depo:
            self._stok_yukle(yenile=False)

    def _kaynak(self) -> tuple[Magaza | None, str]:
        return self.servis.magaza(self.cb_kaynak.currentData() or ""), self.cb_kaynak_depo.currentData() or ""

    def _hedef(self) -> tuple[Magaza | None, str]:
        return self.servis.magaza(self.cb_hedef.currentData() or ""), self.cb_hedef_depo.currentData() or ""

    # ------------------------------------------------------------ satırlar
    def _ekle(self, yeni: list[Satir]):
        for s in yeni:
            mevcut = next((x for x in self.satirlar if x.anahtar == s.anahtar), None)
            if mevcut:
                mevcut.adet += s.adet
                if s.barkod and not mevcut.barkod:
                    mevcut.barkod = s.barkod
            else:
                self.satirlar.append(s)
        self._stok_yukle(yenile=False)
        self._yenile()

    def _barkod_okut(self):
        metin = self.barkod.text().strip()
        self.barkod.clear()
        if not metin:
            return
        adet = float(self.adet.value())
        if "*" in metin:
            sol, sag = metin.split("*", 1)
            try:
                adet, metin = float(sol.replace(",", ".")), sag.strip()
            except ValueError:
                pass
        self.adet.setValue(1)

        def tamam(sozluk: dict[str, Satir]):
            s = sozluk.get(metin)
            if not s:
                self.ana.durum(f"✖ Barkod bulunamadı: {metin}", hata=True)
                QApplication_beep()
                return
            s.adet = adet * (s.adet or 1)
            self._ekle([s])
            self.ana.durum(f"✔ {s.urun} {s.renk} {s.beden} eklendi ({adet_metni(s.adet)})")

        arkada(lambda: self.servis.barkodlar([metin]), tamam, lambda e: self.ana.durum(f"✖ {e}", hata=True))

    def _urun_ara(self):
        kaynak, depo = self._kaynak()
        if not kaynak or not depo:
            QMessageBox.information(self, "Ürün ara", "Önce gönderen mağaza ve depoyu seçin.")
            return
        p = UrunAramaPenceresi(self.servis, depo, self)
        if p.exec() and p.secilen:
            for s in p.secilen:
                self._stok[(depo,) + s.anahtar] = s.stok or 0
            self._ekle(p.secilen)

    def _sablon(self):
        yol, _ = QFileDialog.getSaveFileName(self, "Şablon kaydet", "Transfer_Sablon.xlsx", "Excel (*.xlsx)")
        if yol:
            belgeler.sablon_yaz(yol)
            self.ana.durum(f"Şablon kaydedildi: {yol}")

    def _excel_yukle(self):
        yol, _ = QFileDialog.getOpenFileName(self, "Excel'den yükle", "", "Excel (*.xlsx *.xlsm)")
        if not yol:
            return

        def calis():
            kayitlar = belgeler.excel_oku(yol)
            barkodlu = [k for k in kayitlar if k["barkod"]]
            sozluk = self.servis.barkodlar([k["barkod"] for k in barkodlu]) if barkodlu else {}
            eklenecek, hatali = [], []
            for k in kayitlar:
                if k["adet"] <= 0:
                    hatali.append(f"Satır {k['satir_no']}: adet yok")
                    continue
                if k["barkod"]:
                    s = sozluk.get(k["barkod"])
                    if not s:
                        hatali.append(f"Satır {k['satir_no']}: barkod bulunamadı ({k['barkod']})")
                        continue
                    s = Satir(**{**s.__dict__})
                    s.adet = k["adet"] * (s.adet or 1)
                else:
                    s = Satir(k["urun"], "", k["renk"], "", k["beden"], adet=k["adet"])
                eklenecek.append(s)
            return eklenecek, hatali

        def tamam(sonuc):
            eklenecek, hatali = sonuc
            self._ekle(eklenecek)
            mesaj = f"{len(eklenecek)} satır eklendi."
            if hatali:
                mesaj += f"\n\n{len(hatali)} satır eklenmedi:\n" + "\n".join(hatali[:30])
                if len(hatali) > 30:
                    mesaj += f"\n… ve {len(hatali) - 30} satır daha"
            QMessageBox.information(self, "Excel'den yükleme", mesaj)

        arkada(calis, tamam, lambda e: hata_goster(self, e), mesgul=self.ana)

    def _stok_yukle(self, yenile: bool, sonra=None):
        kaynak, depo = self._kaynak()
        if not depo or not self.satirlar:
            self._yenile()
            if sonra:
                sonra()
            return
        if yenile:
            self._stok_yuklu = {x for x in self._stok_yuklu if x[0] != depo}
        eksik = sorted({s.urun for s in self.satirlar if (depo, s.urun) not in self._stok_yuklu})
        if not eksik:
            self._yenile()
            if sonra:
                sonra()
            return

        def tamam(stok: dict[tuple, float]):
            for u in eksik:
                self._stok_yuklu.add((depo, u))
                for k in [k for k in self._stok if k[0] == depo and k[1] == u]:
                    del self._stok[k]
            for anahtar, miktar in stok.items():
                self._stok[(depo,) + anahtar] = miktar
            self._yenile()
            if sonra:
                sonra()

        arkada(lambda: self.servis.stoklar(depo, eksik), tamam, lambda e: self.ana.durum(f"✖ Stok okunamadı: {e}", hata=True))

    def _yenile(self):
        _, depo = self._kaynak()
        t = self.tablo
        t.blockSignals(True)
        t.setRowCount(len(self.satirlar))
        yetersiz = 0
        for i, s in enumerate(self.satirlar):
            if (depo, s.urun) in self._stok_yuklu or (depo,) + s.anahtar in self._stok:
                s.stok = self._stok.get((depo,) + s.anahtar, 0.0)
            else:
                s.stok = None
            if s.stok_yetersiz:
                yetersiz += 1
            durum = "Stok bekleniyor" if s.stok is None else ("Stok yetersiz" if s.stok_yetersiz else "Tamam")
            degerler = [s.barkod, s.urun, s.urun_adi, f"{s.renk} {s.renk_adi}".strip(),
                        " ".join(x for x in (s.beden, s.boyut2, s.boyut3) if x), float(s.adet),
                        float(s.stok) if s.stok is not None else "…", durum]
            for j, v in enumerate(degerler):
                c = hucre(v)
                if j == self.ADET:
                    c = QTableWidgetItem(adet_metni(s.adet))
                    c.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    c.setBackground(QColor("#FFF8DC"))
                elif s.stok_yetersiz:
                    c.setBackground(QColor("#F8D7DA"))
                t.setItem(i, j, c)
        t.blockSignals(False)
        t.setEditTriggers(t.EditTrigger.DoubleClicked | t.EditTrigger.AnyKeyPressed | t.EditTrigger.SelectedClicked)
        t.resizeColumnsToContents()
        toplam = sum(s.adet for s in self.satirlar)
        self.ozet.setText(f"{len(self.satirlar)} satır · toplam {adet_metni(toplam)} adet"
                          + (f" · <span style='color:#a00'>{yetersiz} satırda stok yetersiz</span>" if yetersiz else ""))

    def _adet_degisti(self, item: QTableWidgetItem):
        if item.column() != self.ADET or item.row() >= len(self.satirlar):
            return
        try:
            adet = float(item.text().replace(".", "").replace(",", ".")) if item.text().strip() else 0
        except ValueError:
            adet = self.satirlar[item.row()].adet
        if adet <= 0:
            del self.satirlar[item.row()]
        else:
            self.satirlar[item.row()].adet = adet
        QTimer.singleShot(0, self._yenile)

    def _sil(self):
        satirlar = sorted({i.row() for i in self.tablo.selectedIndexes()}, reverse=True)
        for r in satirlar:
            del self.satirlar[r]
        self._yenile()

    def _temizle_sor(self):
        if self.satirlar and QMessageBox.question(self, "Temizle", "Liste temizlensin mi?") == QMessageBox.StandardButton.Yes:
            self.temizle()

    def temizle(self):
        self.satirlar.clear()
        self.aciklama.clear()
        self._yenile()

    # ------------------------------------------------------------ kayıt
    def _olustur(self):
        kaynak, kdepo = self._kaynak()
        hedef, hdepo = self._hedef()
        if not kaynak or not kdepo or not hedef or not hdepo:
            QMessageBox.warning(self, "Eksik bilgi", "Gönderen ve alan mağaza/depo seçilmeli.")
            return
        if kaynak.kod == hedef.kod:
            QMessageBox.warning(self, "Hatalı seçim", "Gönderen ve alan mağaza aynı olamaz.")
            return
        if not self.satirlar:
            QMessageBox.warning(self, "Boş liste", "Transfer edilecek ürün yok.")
            return
        self._stok_yukle(yenile=True, sonra=lambda: self._onizle(kaynak, kdepo, hedef, hdepo))

    def _onizle(self, kaynak: Magaza, kdepo: str, hedef: Magaza, hdepo: str):
        """Önce Nebim'de kontrol (yordam Kaydet=0, hiçbir şey yazılmaz), sonra önizleme ve onayla kayıt."""
        if any(s.stok is None for s in self.satirlar):
            hata_goster(self, "Stoklar okunamadı; tekrar deneyin.")
            return
        a = self.ana.ayarlar
        tarih = self.tarih.date().toPython()
        aciklama = self.aciklama.text().strip()
        satirlar = list(self.satirlar)
        kabul = not a.kabul_beklensin

        def calistir(kaydet: bool):
            return self.servis.transfer_calistir(kaynak, kdepo, hedef, hdepo, satirlar, tarih, aciklama, kabul, kaydet,
                                                 a.nebim_kullanici)

        def kontrol_tamam(onizleme):
            self._yenile()
            p = OnizlemePenceresi(kaynak, kdepo, hedef, hdepo, tarih, aciklama, satirlar, a.kabul_beklensin, onizleme, self)
            if p.exec():
                arkada(lambda: calistir(True), kayit_tamam, kayit_hata, mesgul=self.ana)

        def kayit_tamam(sonuc):
            a.son_kaynak, a.son_hedef = kaynak.kod, hedef.kod
            try:
                a.kaydet()
            except OSError:
                pass
            self.temizle()
            self._stok_yuklu.clear()
            self.ana.durum(f"✔ Transfer oluşturuldu: {sonuc.fis_no}")
            m = QMessageBox(self)
            m.setWindowTitle("Transfer oluşturuldu")
            m.setText(f"Nebim transfer fişi: <b>{sonuc.fis_no}</b> (sipariş {sonuc.siparis_no})<br>"
                      f"{kaynak.etiket} → {hedef.etiket}<br>"
                      f"{sonuc.satir} satır, {adet_metni(sonuc.adet)} adet"
                      + (" · alan mağazanın kabulünü bekliyor." if a.kabul_beklensin else " · kabul edildi.")
                      + "<br><br>e-İrsaliyeyi Nebim'den kesmeyi unutmayın.")
            b_yaz = m.addButton("Yazdır", QMessageBox.ButtonRole.ActionRole)
            m.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)
            m.exec()
            if m.clickedButton() is b_yaz:
                ozet = TransferOzet(sonuc.fis_no, tarih, "", kaynak.kod, kaynak.ad, kdepo, hedef.kod, hedef.ad, hdepo,
                                    sonuc.adet, sonuc.satir, kabul, tarih if kabul else None, "", aciklama, a.nebim_kullanici, None)
                fis_yazdir(self, ozet, satirlar)
            self.ana.gecmis.getir()

        def kayit_hata(exc):
            if isinstance(exc, KayitBelirsizHatasi):
                QMessageBox.warning(self, "Sonuç belirsiz", str(exc))
            else:
                hata_goster(self, f"Transfer Nebim'e kaydedilemedi (hiçbir şey yazılmadı):\n\n{exc}")

        arkada(lambda: calistir(False), kontrol_tamam,
               lambda e: hata_goster(self, f"Nebim kontrolü geçmedi:\n\n{e}"), mesgul=self.ana)


def QApplication_beep():
    from PySide6.QtWidgets import QApplication
    QApplication.beep()


# ====================================================================== Geçmiş
class GecmisSekmesi(QWidget):
    SUTUN = ["Fiş No", "Tarih", "Saat", "Gönderen", "Alan", "Adet", "Satır", "Durum", "Kabul Tarihi", "e-İrsaliye",
             "Açıklama", "Oluşturan"]

    def __init__(self, ana: "AnaPencere"):
        super().__init__()
        self.ana = ana
        self.liste: list[TransferOzet] = []
        d = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.bas = QDateEdit(QDate.currentDate().addDays(-7))
        self.bit = QDateEdit(QDate.currentDate())
        for x in (self.bas, self.bit):
            x.setCalendarPopup(True)
            x.setDisplayFormat("dd.MM.yyyy")
        self.cb_magaza = aranabilir(QComboBox())
        self.cb_magaza.setMinimumWidth(260)
        self.yolda = QCheckBox("Yalnız yoldakiler (kabul edilmemiş)")
        b_getir = QPushButton("Getir")
        b_getir.clicked.connect(self.getir)
        for w in (QLabel("Başlangıç"), self.bas, QLabel("Bitiş"), self.bit, QLabel("Mağaza"), self.cb_magaza, self.yolda, b_getir):
            ust.addWidget(w)
        ust.addStretch()
        d.addLayout(ust)
        self.tablo = tablo(self.SUTUN)
        self.tablo.setSortingEnabled(True)
        self.tablo.doubleClicked.connect(lambda _: self._detay())
        d.addWidget(self.tablo, 1)
        alt = QHBoxLayout()
        self.ozet = QLabel("")
        b_detay = QPushButton("Fiş Detayı")
        b_detay.clicked.connect(self._detay)
        b_yaz = QPushButton("Fişi Yazdır")
        b_yaz.clicked.connect(lambda: self._detay(yazdir=True))
        b_excel = QPushButton("Listeyi Excel'e Aktar")
        b_excel.clicked.connect(self._excel)
        alt.addWidget(self.ozet, 1)
        for b in (b_detay, b_yaz, b_excel):
            alt.addWidget(b)
        d.addLayout(alt)

    def magazalari_yukle(self, magazalar: list[Magaza]):
        _magaza_doldur(self.cb_magaza, magazalar, self.cb_magaza.currentData() or "", bos="Tüm mağazalar")

    def getir(self):
        if not self.ana.hazir:
            return
        bas, bit = self.bas.date().toPython(), self.bit.date().toPython()
        magaza, yolda = self.cb_magaza.currentData() or "", self.yolda.isChecked()
        self.ozet.setText("Getiriliyor…")
        arkada(lambda: self.ana.servis.transferler(bas, bit, magaza, yolda), self._goster,
               lambda e: self.ozet.setText(f"✖ {e}"))

    def _goster(self, liste: list[TransferOzet]):
        self.liste = liste
        t = self.tablo
        t.setSortingEnabled(False)
        t.setRowCount(len(liste))
        for i, x in enumerate(liste):
            durum = "Kabul edildi" if x.kabul else "Yolda"
            degerler = [x.fis_no, x.tarih.strftime("%d.%m.%Y") if x.tarih else "", x.saat, f"{x.kaynak} {x.kaynak_adi}",
                        f"{x.hedef} {x.hedef_adi}", x.adet, x.satir, durum,
                        x.kabul_tarihi.strftime("%d.%m.%Y") if x.kabul_tarihi else "", x.eirsaliye, x.aciklama, x.olusturan]
            for j, v in enumerate(degerler):
                c = hucre(v)
                c.setData(Qt.ItemDataRole.UserRole, i)
                if not x.kabul:
                    c.setBackground(QColor("#FFF3CD"))
                t.setItem(i, j, c)
        t.setSortingEnabled(True)
        t.resizeColumnsToContents()
        yolda = sum(1 for x in liste if not x.kabul)
        self.ozet.setText(f"{len(liste)} fiş · {adet_metni(sum(x.adet for x in liste))} adet · {yolda} fiş yolda")

    def _secili(self) -> TransferOzet | None:
        r = self.tablo.currentRow()
        if r < 0:
            return None
        i = self.tablo.item(r, 0).data(Qt.ItemDataRole.UserRole)
        return self.liste[i]

    def _detay(self, yazdir: bool = False):
        x = self._secili()
        if not x:
            return

        def tamam(satirlar):
            if yazdir:
                fis_yazdir(self, x, satirlar)
            else:
                FisDetayPenceresi(x, satirlar, self).exec()

        arkada(lambda: self.ana.servis.transfer_satirlari(x.fis_no), tamam, lambda e: hata_goster(self, e), mesgul=self.ana)

    def _excel(self):
        if not self.liste:
            return
        yol, _ = QFileDialog.getSaveFileName(self, "Excel'e aktar", f"Transferler_{dt.date.today():%Y%m%d}.xlsx", "Excel (*.xlsx)")
        if not yol:
            return
        satirlar = [[x.fis_no, x.tarih, x.saat, x.kaynak, x.kaynak_adi, x.hedef, x.hedef_adi, x.adet, x.satir,
                     "Kabul edildi" if x.kabul else "Yolda", x.kabul_tarihi, x.eirsaliye, x.aciklama, x.olusturan]
                    for x in self.liste]
        belgeler.excel_yaz(yol, "Mağazalar Arası Transferler",
                           ["Fiş No", "Tarih", "Saat", "Gönderen", "Gönderen Adı", "Alan", "Alan Adı", "Adet", "Satır",
                            "Durum", "Kabul Tarihi", "e-İrsaliye", "Açıklama", "Oluşturan"], satirlar,
                           [("Dönem", f"{self.bas.date().toPython():%d.%m.%Y} – {self.bit.date().toPython():%d.%m.%Y}")])
        self.ana.durum(f"Excel kaydedildi: {yol}")


# ====================================================================== Ana pencere
class AnaPencere(QMainWindow):
    def __init__(self, surum: str):
        super().__init__()
        self.setWindowTitle(f"Mağazalar Arası Transfer {surum} — Nebim V3")
        self.resize(1200, 760)
        self.ayarlar = Ayarlar.yukle()
        self.servis = TransferServisi(Integrator(self.ayarlar))
        self.hazir = False

        self.sekmeler = QTabWidget()
        self.yeni = YeniTransferSekmesi(self)
        self.gecmis = GecmisSekmesi(self)
        self.sekmeler.addTab(self.yeni, "Yeni Transfer")
        self.sekmeler.addTab(self.gecmis, "Transfer Geçmişi")
        self.setCentralWidget(self.sekmeler)

        menu = self.menuBar().addMenu("Ayarlar")
        for ad, fn in (("Nebim Integrator Bağlantısı…", self._baglanti), ("Nebim Kurulumu…", lambda: self._kurulum()),
                       ("Mağazaları Yenile", self.basla)):
            act = QAction(ad, self)
            act.triggered.connect(fn)
            menu.addAction(act)
        self.baglanti_etiketi = QLabel("")
        self.statusBar().addPermanentWidget(self.baglanti_etiketi)
        QTimer.singleShot(100, self._ilk)

    def durum(self, metin: str, hata: bool = False):
        self.statusBar().setStyleSheet("color:#a00" if hata else "")
        self.statusBar().showMessage(metin, 15000)

    def _ilk(self):
        if not self.ayarlar.tamam and not BaglantiPenceresi(self.ayarlar, self).exec():
            self.durum("Integrator bilgileri girilmedi. Ayarlar menüsünden girebilirsiniz.", hata=True)
            return
        self.basla()

    def _baglanti(self):
        if BaglantiPenceresi(self.ayarlar, self).exec():
            self.servis = TransferServisi(Integrator(self.ayarlar))
            self.basla()

    def _kurulum(self, kurulu: tuple[str, str] | None = None):
        def ac(surum):
            p = KurulumPenceresi(self.servis, surum, self.ayarlar.veritabani, self)
            p.exec()
            if p.kuruldu:
                self.basla()

        if kurulu is not None:
            ac(kurulu if any(kurulu) else None)
        else:
            arkada(self.servis.kurulu_surum, ac, lambda e: ac(None))

    def basla(self):
        self.hazir = False
        a = self.ayarlar
        self.baglanti_etiketi.setText(f"{a.url} · {a.veritabani} · {a.kullanici_grubu}/{a.kullanici}")
        self.durum("Nebim'e bağlanılıyor…")

        def calis():
            self.servis.nebim.baglan()
            surum = self.servis.kurulu_surum()
            if not surum or surum[0] != kurulum.SURUM or surum[1] != kurulum.SURUM:
                return surum, None
            return surum, self.servis.magazalar(yenile=True)

        def tamam(sonuc):
            surum, magazalar = sonuc
            if magazalar is None:
                metin = ("Program sorguları Nebim'de kurulu değil." if not surum else
                         f"Nebim'deki sorgular eski sürüm ({surum}); program {kurulum.SURUM} istiyor.")
                QMessageBox.information(self, "Kurulum gerekli", metin + "\n\nSorgu kurulumu penceresi açılacak.")
                self.durum(metin, hata=True)
                self._kurulum(surum or "")
                return
            self.hazir = True
            self.yeni.magazalari_yukle(magazalar)
            self.gecmis.magazalari_yukle(magazalar)
            self.durum(f"✔ Bağlandı · {len(magazalar)} mağaza")
            self.gecmis.getir()

        arkada(calis, tamam, lambda e: (self.durum(f"✖ {e}", hata=True), hata_goster(self, e, "Bağlantı hatası")))
