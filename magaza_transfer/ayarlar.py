"""Program ayarları: yerel config.json (veritabanı yok).

Konum: program klasörü yazılabiliyorsa orada (taşınabilir kullanım), değilse %APPDATA%\\MagazaTransfer.
Integrator şifresi girilirse dosyaya Windows DPAPI ile şifrelenmiş yazılır (yalnız aynı Windows kullanıcısı çözebilir).
"""

from __future__ import annotations

import base64
import ctypes
import json
import os
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

UYGULAMA = "MagazaTransfer"


def program_klasoru() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def kaynak_klasoru() -> Path:
    """Paketle gelen dosyalar (sql/) — PyInstaller'da _MEIPASS altında."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "magaza_transfer" if base else Path(__file__).resolve().parent


def _yazilabilir(klasor: Path) -> bool:
    try:
        deneme = klasor / ".yazma_denemesi"
        deneme.write_text("x", encoding="utf-8")
        deneme.unlink()
        return True
    except OSError:
        return False


def _appdata() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / UYGULAMA


def ayar_dosyasi() -> Path:
    yerel = program_klasoru()
    return yerel / "config.json" if _yazilabilir(yerel) else _appdata() / "config.json"


# ---------------------------------------------------------------- DPAPI
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(veri: bytes, sifrele: bool) -> bytes:
    tampon = ctypes.create_string_buffer(veri, len(veri))
    giris = _BLOB(len(veri), ctypes.cast(tampon, ctypes.POINTER(ctypes.c_char)))
    cikis = _BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if sifrele else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(giris), None, None, None, None, 0x1, ctypes.byref(cikis)):
        raise OSError("DPAPI işlemi başarısız")
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(cikis.pbData, ctypes.c_void_p))


def sifre_sakla(metin: str) -> str:
    if not metin:
        return ""
    return "dpapi:" + base64.b64encode(_dpapi(metin.encode("utf-8"), True)).decode("ascii")


def sifre_coz(saklanan: str) -> str:
    if not saklanan:
        return ""
    if not saklanan.startswith("dpapi:"):
        return saklanan  # elle düz yazılmışsa
    try:
        return _dpapi(base64.b64decode(saklanan[6:]), False).decode("utf-8")
    except Exception:
        return ""  # başka bilgisayar/kullanıcıda şifrelenmiş: yeniden girilmeli


# ---------------------------------------------------------------- ayarlar
@dataclass
class Ayarlar:
    url: str = ""
    veritabani: str = ""
    kullanici_grubu: str = ""
    kullanici: str = ""
    sifre: str = ""
    zaman_asimi: int = 180
    kabul_beklensin: bool = True      # transfer hedef mağazanın kabulüne düşsün
    son_kaynak: str = ""
    son_hedef: str = ""

    @property
    def nebim_kullanici(self) -> str:
        """Nebim'in CreatedUserName biçimi: 5 karakterlik grup + kullanıcı (ör. 'ADM  kullanici')."""
        return (f"{self.kullanici_grubu[:5]:<5}" + self.kullanici)[:20]

    @property
    def tamam(self) -> bool:
        return bool(self.url and self.veritabani and self.kullanici_grubu and self.kullanici)

    @classmethod
    def yukle(cls) -> "Ayarlar":
        yollar = [ayar_dosyasi(), program_klasoru() / "config.json", _appdata() / "config.json"]
        for yol in yollar:
            if yol.exists():
                try:
                    veri = json.loads(yol.read_text(encoding="utf-8-sig"))
                except (OSError, ValueError):
                    continue
                i = veri.get("integrator") or {}
                t = veri.get("transfer") or {}
                return cls(
                    url=i.get("url", ""), veritabani=i.get("database", ""), kullanici_grubu=i.get("user_group", ""),
                    kullanici=i.get("user", ""), sifre=sifre_coz(i.get("password", "")),
                    zaman_asimi=int(i.get("timeout", 180) or 180),
                    kabul_beklensin=bool(t.get("wait_for_approval", True)),
                    son_kaynak=t.get("last_source", ""), son_hedef=t.get("last_target", ""),
                )
        return cls()

    def kaydet(self) -> Path:
        yol = ayar_dosyasi()
        yol.parent.mkdir(parents=True, exist_ok=True)
        veri = {
            "integrator": {"url": self.url, "database": self.veritabani, "user_group": self.kullanici_grubu,
                           "user": self.kullanici, "password": sifre_sakla(self.sifre), "timeout": self.zaman_asimi},
            "transfer": {"wait_for_approval": self.kabul_beklensin,
                         "last_source": self.son_kaynak, "last_target": self.son_hedef},
        }
        yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
        return yol
