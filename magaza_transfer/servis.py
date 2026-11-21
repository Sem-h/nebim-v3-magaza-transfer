"""Transfer iş kuralları: mağaza/depo listesi, barkod, stok, transfer oluşturma ve geçmiş."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from xml.sax.saxutils import quoteattr

from .integrator import Integrator, SorguYokHatasi, kriter_metni, nebim_tarihi, nebim_zamani
from .kurulum import SURUM, YORDAM


@dataclass
class Depo:
    kod: str
    ad: str
    varsayilan: bool


@dataclass
class Magaza:
    kod: str
    ad: str
    ofis: str
    sirket: int
    depolar: list[Depo] = field(default_factory=list)

    @property
    def etiket(self) -> str:
        return f"{self.kod} — {self.ad}"

    @property
    def varsayilan_depo(self) -> Depo | None:
        return next((d for d in self.depolar if d.varsayilan), self.depolar[0] if self.depolar else None)


@dataclass
class Satir:
    urun: str
    urun_adi: str
    renk: str
    renk_adi: str
    beden: str
    boyut2: str = ""
    boyut3: str = ""
    adet: float = 1
    barkod: str = ""
    stok: float | None = None  # kaynak depoda kullanılabilir stok

    @property
    def anahtar(self) -> tuple:
        return (self.urun, self.renk, self.beden, self.boyut2, self.boyut3)

    @property
    def stok_yetersiz(self) -> bool:
        return self.stok is not None and self.adet > self.stok


@dataclass
class TransferOzet:
    fis_no: str
    tarih: dt.date | None
    saat: str
    kaynak: str
    kaynak_adi: str
    kaynak_depo: str
    hedef: str
    hedef_adi: str
    hedef_depo: str
    adet: float
    satir: int
    kabul: bool
    kabul_tarihi: dt.date | None
    eirsaliye: str
    aciklama: str
    olusturan: str
    olusturma: dt.datetime | None


@dataclass
class TransferSonuc:
    durum: str          # ONIZLEME | KAYDEDILDI
    siparis_no: str
    fis_no: str
    ornek_fis: str
    satir: int
    adet: float


def _s(v) -> str:
    return str(v or "").strip()


def _ozet(r: dict) -> TransferOzet:
    return TransferOzet(
        _s(r.get("ShippingNumber")), nebim_tarihi(r.get("OperationDate")), _s(r.get("OperationTime")),
        _s(r.get("SourceStore")), _s(r.get("SourceStoreName")), _s(r.get("SourceWarehouse")),
        _s(r.get("TargetStore")), _s(r.get("TargetStoreName")), _s(r.get("TargetWarehouse")),
        float(r.get("TotalQty") or 0), int(r.get("LineCount") or 0), bool(r.get("IsTransferApproved")),
        nebim_tarihi(r.get("TransferApprovedDate")), _s(r.get("EShipmentNumber")), _s(r.get("Description")),
        _s(r.get("CreatedUserName")), nebim_zamani(r.get("CreatedDate")))


class TransferServisi:
    def __init__(self, integrator: Integrator):
        self.nebim = integrator
        self._magazalar: list[Magaza] | None = None

    # ------------------------------------------------------------ kurulum
    def kurulu_surum(self) -> tuple[str, str] | None:
        """(sorgu sürümü, yordam sürümü); sorgular kurulu değilse None."""
        try:
            satirlar = self.nebim.sorgu("GetMTR_SURUM")
        except SorguYokHatasi:
            return None
        if not satirlar:
            return None
        return _s(satirlar[0].get("Surum")), _s(satirlar[0].get("YordamSurum")).split()[0] if _s(satirlar[0].get("YordamSurum")) else ""

    @staticmethod
    def program_surumu() -> str:
        return SURUM

    # ------------------------------------------------------------ okuma
    def magazalar(self, yenile: bool = False) -> list[Magaza]:
        if self._magazalar is None or yenile:
            sozluk: dict[str, Magaza] = {}
            for r in self.nebim.sorgu("GetMTR_MAGAZALAR"):
                kod = _s(r.get("StoreCode"))
                m = sozluk.get(kod)
                if not m:
                    m = sozluk[kod] = Magaza(kod, _s(r.get("StoreName")), _s(r.get("OfficeCode")), int(r.get("CompanyCode") or 1))
                m.depolar.append(Depo(_s(r.get("WarehouseCode")), _s(r.get("WarehouseName")), bool(r.get("IsDefaultWarehouse"))))
            self._magazalar = sorted(sozluk.values(), key=lambda m: m.kod)
        return self._magazalar

    def magaza(self, kod: str) -> Magaza | None:
        return next((m for m in self.magazalar() if m.kod == kod), None)

    @staticmethod
    def _satir(r: dict, adet: float = 1) -> Satir:
        return Satir(_s(r.get("ItemCode")), _s(r.get("ItemDescription")), _s(r.get("ColorCode")), _s(r.get("ColorDescription")),
                     _s(r.get("ItemDim1Code")), _s(r.get("ItemDim2Code")), _s(r.get("ItemDim3Code")), adet, _s(r.get("Barcode")))

    def barkodlar(self, barkodlar: list[str]) -> dict[str, Satir]:
        """Barkod -> ürün satırı (100'erli gruplarla tek sorgu)."""
        sonuc: dict[str, Satir] = {}
        temiz = list(dict.fromkeys(b.strip() for b in barkodlar if b and b.strip()))
        for i in range(0, len(temiz), 100):
            grup = temiz[i:i + 100]
            kriter = "Barcode IN (" + ", ".join(kriter_metni(b) for b in grup) + ")"
            for r in self.nebim.sorgu("GetMTR_BARKOD", kriter):
                s = self._satir(r, float(r.get("BarcodeQty") or 1))
                sonuc.setdefault(s.barkod, s)
        return sonuc

    def stoklar(self, depo: str, urunler: list[str]) -> dict[tuple, float]:
        """(ürün, renk, beden, boyut2, boyut3) -> kullanılabilir stok."""
        sonuc: dict[tuple, float] = {}
        temiz = sorted({u for u in urunler if u})
        for i in range(0, len(temiz), 50):
            grup = temiz[i:i + 50]
            kriter = f"WarehouseCode = {kriter_metni(depo)} AND ItemCode IN (" + ", ".join(kriter_metni(u) for u in grup) + ")"
            for r in self.nebim.sorgu("GetMTR_STOK", kriter):
                anahtar = (_s(r.get("ItemCode")), _s(r.get("ColorCode")), _s(r.get("ItemDim1Code")),
                           _s(r.get("ItemDim2Code")), _s(r.get("ItemDim3Code")))
                sonuc[anahtar] = sonuc.get(anahtar, 0) + float(r.get("AvailableQty") or 0)
        return sonuc

    def urun_ara(self, depo: str, metin: str, yalniz_stoklu: bool = True) -> list[Satir]:
        metin = metin.strip()
        if len(metin) < 3:
            raise ValueError("En az 3 karakter yazın.")
        desen = metin.replace("'", "''").replace("*", "%")
        kriter = (f"WarehouseCode = {kriter_metni(depo)} AND "
                  f"(ItemCode LIKE '{desen}%' OR ItemDescription LIKE '%{desen}%')")
        if yalniz_stoklu:
            kriter += " AND AvailableQty > 0"
        satirlar = []
        for r in self.nebim.sorgu("GetMTR_STOK", kriter):
            s = self._satir(r, 0)
            s.stok = float(r.get("AvailableQty") or 0)
            satirlar.append(s)
        satirlar.sort(key=lambda s: s.anahtar)
        return satirlar

    def transferler(self, bas: dt.date, bit: dt.date, magaza: str = "", yalniz_yolda: bool = False) -> list[TransferOzet]:
        kriter = f"OperationDate >= #{bas:%Y-%m-%d}# AND OperationDate <= #{bit:%Y-%m-%d}#"
        if magaza:
            kriter += f" AND (SourceStore = {kriter_metni(magaza)} OR TargetStore = {kriter_metni(magaza)})"
        if yalniz_yolda:
            kriter += " AND IsTransferApproved = False"
        liste = [_ozet(r) for r in self.nebim.sorgu("GetMTR_TRANSFER", kriter)]
        liste.sort(key=lambda t: (t.olusturma or dt.datetime.min), reverse=True)
        return liste

    def transfer(self, fis_no: str) -> TransferOzet | None:
        satirlar = self.nebim.sorgu("GetMTR_TRANSFER", f"ShippingNumber = {kriter_metni(fis_no)}")
        if not satirlar:
            return None
        return _ozet(satirlar[0])

    def transfer_satirlari(self, fis_no: str) -> list[Satir]:
        satirlar = [self._satir(r, float(r.get("Qty1") or 0))
                    for r in self.nebim.sorgu("GetMTR_TRANSFERSATIR", f"ShippingNumber = {kriter_metni(fis_no)}")]
        return satirlar

    # ------------------------------------------------------------ yazma (RunProc sp_MTR_MagazaTransfer)
    @staticmethod
    def satir_xml(satirlar: list[Satir]) -> str:
        parca = []
        for i, s in enumerate(satirlar, 1):
            ozn = {"n": str(i), "i": s.urun, "c": s.renk, "d1": s.beden, "d2": s.boyut2, "d3": s.boyut3,
                   "q": f"{s.adet:g}", "b": s.barkod}
            parca.append("<l " + " ".join(f"{k}={quoteattr(v)}" for k, v in ozn.items()) + "/>")
        return "<s>" + "".join(parca) + "</s>"

    def transfer_calistir(self, kaynak: Magaza, kaynak_depo: str, hedef: Magaza, hedef_depo: str, satirlar: list[Satir],
                          tarih: dt.date, aciklama: str, kabul_edildi: bool, kaydet: bool, nebim_kullanici: str) -> TransferSonuc:
        """Kaydet=False: Nebim'de kontrol + tahmini numaralar (hiçbir şey yazılmaz). Kaydet=True: tek işlemde kayıt."""
        if kaynak.kod == hedef.kod:
            raise ValueError("Gönderen ve alan mağaza aynı olamaz.")
        if not satirlar:
            raise ValueError("Transfer satırı yok.")
        if any(s.adet <= 0 for s in satirlar):
            raise ValueError("Adedi sıfır olan satır var.")
        parametreler = [
            ("KaynakMagaza", kaynak.kod), ("KaynakDepo", kaynak_depo), ("HedefMagaza", hedef.kod), ("HedefDepo", hedef_depo),
            ("Tarih", f"{tarih:%Y-%m-%d}"), ("Aciklama", aciklama[:200]), ("Satirlar", self.satir_xml(satirlar)),
            ("KabulEdildi", "1" if kabul_edildi else "0"), ("Kaydet", "1" if kaydet else "0"), ("Kullanici", nebim_kullanici),
        ]
        satir = self.nebim.yordam(YORDAM, parametreler, kayit=kaydet)
        if not satir:
            raise RuntimeError("Nebim'den sonuç dönmedi.")
        r = satir[0]
        sonuc = TransferSonuc(_s(r.get("Sonuc")), _s(r.get("SiparisNo")), _s(r.get("FisNo")), _s(r.get("OrnekFis")),
                              int(r.get("SatirSayisi") or 0), float(r.get("ToplamAdet") or 0))
        if kaydet and sonuc.durum != "KAYDEDILDI":
            raise RuntimeError(f"Beklenmeyen sonuç: {sonuc.durum}")
        stok = {(_s(x.get("ItemCode")), _s(x.get("ColorCode")), _s(x.get("ItemDim1Code")), _s(x.get("ItemDim2Code")),
                 _s(x.get("ItemDim3Code"))): float(x.get("Stok") or 0) for x in satir}
        for s in satirlar:
            s.stok = stok.get(s.anahtar, s.stok)
        return sonuc
