"""Programın Nebim'e kurduğu SQL nesneleri (metinleri programın içinde, sql/ klasöründe).

1) Okuma sorguları -> NebimV3Master.dbo.bsReportQuery (ReportName = 'V3Integrator', QueryName = 'GetMTR_*').
   Integrator RunQuery yalnız bu tabloda kayıtlı sorguları çalıştırır.
2) Kayıt yordamı  -> şirket veritabanı (Integrator'daki veritabanı adı), dbo.sp_MTR_MagazaTransfer.
   Integrator'ın hazır sevkiyat modelleri mağaza depolarının süreç kuralı (Sipariş → Sevk Emri → İrsaliye) yüzünden
   mağazalar arası transferi yazamadığı için transfer RunProc ile bu yordamla yapılır.

İki kurulum yolu:
  a) Program içinden: SQL Server hesabı bir kez sorulur, KAYDEDİLMEZ.
  b) Betik: aynı işlemi yapan .sql dosyası dışa aktarılır, BT SSMS'te çalıştırır.
"""

from __future__ import annotations

from .ayarlar import kaynak_klasoru

SURUM = "1.1.0"  # GetMTR_SURUM.sql ve sp_MTR_MagazaTransfer.sql (MTR-SURUM) ile aynı olmalı
RAPOR = "V3Integrator"
YORDAM = "sp_MTR_MagazaTransfer"
SORGULAR = [
    ("GetMTR_SURUM", "Kurulu sorgu ve yordam sürümü"),
    ("GetMTR_MAGAZALAR", "Mağazalar ve depoları"),
    ("GetMTR_BARKOD", "Barkoddan ürün / renk / beden"),
    ("GetMTR_STOK", "Depo stoku"),
    ("GetMTR_TRANSFER", "Mağazalar arası transfer fişleri"),
    ("GetMTR_TRANSFERSATIR", "Transfer fişi satırları"),
]


def _oku(ad: str) -> str:
    return (kaynak_klasoru() / "sql" / f"{ad}.sql").read_text(encoding="utf-8")


def sorgu_metni(ad: str) -> str:
    """Yorum satırları atılır: Integrator sorguyu alt sorgu olarak sardığı için sondaki '--' yorumu sorguyu bozar."""
    satirlar = [s.rstrip() for s in _oku(ad).splitlines() if s.strip() and not s.strip().startswith("--")]
    return "\n".join(satirlar)


def yordam_metni() -> str:
    """ALTER PROCEDURE metni (önce boş bir yordam oluşturulur; eski SQL Server sürümleriyle de uyumlu)."""
    return _oku(YORDAM)


def _nmetin(s: str) -> str:
    return "N'" + s.replace("'", "''") + "'"


def sorgu_komutlari() -> list[tuple[str, str]]:
    """(sorgu adı, T-SQL) — her biri bsReportQuery'ye ekler ya da günceller."""
    komutlar = []
    for ad, _ in SORGULAR:
        metin = sorgu_metni(ad)
        komutlar.append((ad, (
            f"IF EXISTS (SELECT 1 FROM dbo.bsReportQuery WHERE ReportName = N'{RAPOR}' AND QueryName = N'{ad}')\n"
            f"    UPDATE dbo.bsReportQuery SET QueryText = {_nmetin(metin)}\n"
            f"    WHERE ReportName = N'{RAPOR}' AND QueryName = N'{ad}';\n"
            f"ELSE\n"
            f"    INSERT INTO dbo.bsReportQuery (ReportName, QueryName, IsDefault, DefaultFilterCols, ParameteredFields,\n"
            f"        NotBeFilteredFields, IsPivotAvailable, CanReportOtherCompanies, QueryText, ReportFileName)\n"
            f"    VALUES (N'{RAPOR}', N'{ad}', 0, N'', N'', N'', 0, 0, {_nmetin(metin)}, N'');\n"
        )))
    return komutlar


YORDAM_KOK = (f"IF OBJECT_ID(N'dbo.{YORDAM}', N'P') IS NULL\n"
              f"    EXEC (N'CREATE PROCEDURE dbo.{YORDAM} AS RETURN 0');")


def kurulum_betigi(sirket_db: str, master_db: str = "NebimV3Master") -> str:
    govde = "\n".join(f"-- {ad}\n{sql}" for ad, sql in sorgu_komutlari())
    return (
        f"/* Mağazalar Arası Transfer — Nebim V3 kurulumu (sürüm {SURUM})\n"
        f"   1) {master_db}.dbo.bsReportQuery: ReportName = '{RAPOR}', QueryName = 'GetMTR_*' okuma sorguları (ekle/güncelle)\n"
        f"   2) {sirket_db}.dbo.{YORDAM}: transfer kayıt yordamı (oluştur/güncelle)\n"
        f"   Tekrar çalıştırılabilir. Kaldırmak için:\n"
        f"   DELETE FROM {master_db}.dbo.bsReportQuery WHERE ReportName = '{RAPOR}' AND QueryName LIKE 'GetMTR[_]%'\n"
        f"   DROP PROCEDURE {sirket_db}.dbo.{YORDAM} */\n"
        f"USE [{master_db}];\nGO\nSET XACT_ABORT ON;\nBEGIN TRANSACTION;\n\n{govde}\nCOMMIT TRANSACTION;\nGO\n\n"
        f"USE [{sirket_db}];\nGO\n{YORDAM_KOK}\nGO\n{yordam_metni()}\nGO\n"
    )


def kaldirma_betigi(sirket_db: str, master_db: str = "NebimV3Master") -> str:
    return (
        f"/* Mağazalar Arası Transfer — Nebim'den kaldırma (sürüm {SURUM}) */\n"
        f"USE [{master_db}];\nGO\nDELETE FROM dbo.bsReportQuery WHERE ReportName = N'{RAPOR}' AND QueryName LIKE N'GetMTR[_]%';\nGO\n"
        f"USE [{sirket_db}];\nGO\nIF OBJECT_ID(N'dbo.{YORDAM}', N'P') IS NOT NULL DROP PROCEDURE dbo.{YORDAM};\nGO\n"
    )


def _surucu() -> str:
    import pyodbc

    var = pyodbc.drivers()
    for ad in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0", "SQL Server"):
        if ad in var:
            return ad
    raise RuntimeError("Bu bilgisayarda SQL Server ODBC sürücüsü bulunamadı. Kurulum betiğini dışa aktarıp SSMS'te çalıştırın.")


def _baglan(sunucu: str, veritabani: str, kullanici: str, sifre: str, windows_kimligi: bool):
    import pyodbc

    surucu = _surucu()
    parca = [f"DRIVER={{{surucu}}}", f"SERVER={sunucu}", f"DATABASE={veritabani}"]
    parca += ["Trusted_Connection=yes"] if windows_kimligi else [f"UID={kullanici}", f"PWD={{{sifre.replace('}', '}}')}}}"]
    if "ODBC Driver" in surucu:
        parca += ["Encrypt=no", "TrustServerCertificate=yes"]
    return pyodbc.connect(";".join(parca), timeout=15, autocommit=False)


def kur(sunucu: str, kullanici: str, sifre: str, windows_kimligi: bool, sirket_db: str,
        master_db: str = "NebimV3Master") -> list[str]:
    """Sorguları ve yordamı kurar. Bağlantı bilgisi hiçbir yere yazılmaz."""
    kayit: list[str] = []
    baglanti = _baglan(sunucu, master_db, kullanici, sifre, windows_kimligi)
    try:
        imlec = baglanti.cursor()
        imlec.execute("SELECT OBJECT_ID('dbo.bsReportQuery')")
        if imlec.fetchone()[0] is None:
            raise RuntimeError(f"{master_db} veritabanında bsReportQuery tablosu yok. Master veritabanı adını kontrol edin.")
        imlec.execute(f"SELECT DB_ID(N'{sirket_db.replace(chr(39), '')}')")
        if imlec.fetchone()[0] is None:
            raise RuntimeError(f"'{sirket_db}' veritabanı bulunamadı.")
        for ad, sql in sorgu_komutlari():
            imlec.execute(sql)
            kayit.append(ad)
        baglanti.commit()
    except Exception:
        baglanti.rollback()
        raise
    finally:
        baglanti.close()

    baglanti = _baglan(sunucu, sirket_db, kullanici, sifre, windows_kimligi)
    try:
        imlec = baglanti.cursor()
        imlec.execute("SELECT OBJECT_ID('dbo.trShipmentHeader')")
        if imlec.fetchone()[0] is None:
            raise RuntimeError(f"'{sirket_db}' bir Nebim V3 şirket veritabanı değil.")
        imlec.execute(YORDAM_KOK)
        imlec.execute(yordam_metni())
        baglanti.commit()
        kayit.append(YORDAM)
    except Exception:
        baglanti.rollback()
        raise
    finally:
        baglanti.close()
    return kayit
