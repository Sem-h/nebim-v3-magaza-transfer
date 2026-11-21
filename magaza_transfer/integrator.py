"""Nebim V3 Integrator istemcisi (Connect / RunQuery / Post).

- Connect şifresiz de oturum verir; kullanıcı bilgisinin doğruluğu ilk sorguda anlaşılır.
- Integrator ara sıra 302 ile oturumu düşürür: yeniden bağlanıp tekrar denenir.
- Post (kayıt) yalnız oturum düşmüşse (istek işlenmemişse) tekrarlanır; zaman aşımında tekrar EDİLMEZ.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import threading
from typing import Any
from urllib.parse import quote

import httpx

from .ayarlar import Ayarlar


class IntegratorHatasi(Exception):
    pass


class SorguYokHatasi(IntegratorHatasi):
    """Sorgu NebimV3Master.bsReportQuery'de kayıtlı değil (kurulum gerekli)."""


class KayitBelirsizHatasi(IntegratorHatasi):
    """Kayıt isteği gönderildi ama yanıt alınamadı; Nebim'de oluşmuş olabilir."""


def okunur_hata(metin: str) -> str:
    metin = (metin or "").strip()
    m = re.search(r"Error Desc\s*:\s*(.+?)(?:\r?\n|$)", metin)
    if m:
        return m.group(1).strip()
    if '"Message"' in metin:  # {"Message":..,"ItemInfo":..}&&{...}
        parcalar = []
        for parca in metin.split("&&"):
            try:
                obj = json.loads(parca)
            except ValueError:
                continue
            msg = str(obj.get("Message") or "").strip()
            bilgi = obj.get("ItemInfo")
            try:
                bilgi = json.loads(bilgi) if isinstance(bilgi, str) else (bilgi or {})
            except ValueError:
                bilgi = {}
            ek = " ".join(str(bilgi.get(k) or "") for k in ("ItemCode", "ColorCode", "ItemDim1Code")).strip()
            satir = f"{msg} ({ek})" if ek else msg
            if satir and satir not in parcalar:
                parcalar.append(satir)
        if parcalar:
            return " | ".join(parcalar)
    return metin.replace("\r\n", " · ").replace("\n", " · ")


def nebim_tarihi(deger: Any) -> dt.date | None:
    """'/Date(ms)/' (UTC) -> Türkiye günü."""
    if deger is None or deger == "":
        return None
    if isinstance(deger, dt.datetime):
        return deger.date()
    if isinstance(deger, dt.date):
        return deger
    m = re.search(r"/Date\((-?\d+)", str(deger))
    if m:
        return (dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=int(m.group(1)) + 3 * 3600 * 1000)).date()
    try:
        return dt.date.fromisoformat(str(deger)[:10])
    except ValueError:
        return None


def nebim_zamani(deger: Any) -> dt.datetime | None:
    m = re.search(r"/Date\((-?\d+)", str(deger or ""))
    if not m:
        return None
    return dt.datetime(1970, 1, 1) + dt.timedelta(milliseconds=int(m.group(1)) + 3 * 3600 * 1000)


def gun_degeri(gun: dt.date) -> str:
    """Yalnız gün gönderilir (saatli değer UTC sayıldığı için gece belgeler ertesi güne kayabiliyor)."""
    ms = int((dt.datetime(gun.year, gun.month, gun.day) - dt.datetime(1970, 1, 1)).total_seconds() * 1000)
    return f"/Date({ms})/"


def kriter_metni(deger: str) -> str:
    return "'" + str(deger).replace("'", "''") + "'"


class Integrator:
    def __init__(self, ayarlar: Ayarlar):
        self.ayarlar = ayarlar
        self._oturum = ""
        self._kilit = threading.Lock()

    # ------------------------------------------------------------ temel
    def _taban(self) -> str:
        adres = self.ayarlar.url.strip().rstrip("/")
        if not adres.lower().startswith(("http://", "https://")):
            adres = "http://" + adres
        return adres

    def baglan(self) -> str:
        a = self.ayarlar
        if not a.tamam:
            raise IntegratorHatasi("Integrator bilgileri eksik (adres, veritabanı, kullanıcı grubu, kullanıcı).")
        url = (f"{self._taban()}/IntegratorService/Connect?DatabaseName={quote(a.veritabani)}"
               f"&UserGroupCode={quote(a.kullanici_grubu)}&UserName={quote(a.kullanici)}")
        if a.sifre:
            url += f"&Password={quote(a.sifre)}"
        son = ""
        for _ in range(4):
            try:
                with httpx.Client(timeout=30, verify=False, follow_redirects=True) as c:
                    r = c.post(url)
                veri = r.json()
            except httpx.HTTPError as exc:
                son = f"Sunucuya ulaşılamadı: {exc}"
                continue
            except ValueError:
                son = f"Integrator yanıtı okunamadı (HTTP {r.status_code})."
                continue
            oturum = veri.get("SessionID") or veri.get("sessionID") or ""
            if oturum:
                self._oturum = oturum
                return oturum
            son = okunur_hata(str(veri.get("ExceptionMessage") or veri.get("Message") or veri))
        raise IntegratorHatasi(f"Nebim Integrator'a bağlanılamadı. {son}")

    def kapat(self) -> None:
        self._oturum = ""

    def _cagir(self, komut: str, yuk: dict, kayit: bool = False) -> Any:
        with self._kilit:
            son = ""
            for deneme in range(3):
                if not self._oturum:
                    self.baglan()
                url = f"{self._taban()}/(S({self._oturum}))/IntegratorService/{komut}?"
                try:
                    with httpx.Client(timeout=self.ayarlar.zaman_asimi, verify=False, follow_redirects=False) as c:
                        r = c.post(url, json=yuk)
                except httpx.ConnectError as exc:  # istek sunucuya hiç ulaşmadı
                    self._oturum, son = "", f"Sunucuya ulaşılamadı: {exc}"
                    continue
                except httpx.HTTPError as exc:
                    if kayit:
                        raise KayitBelirsizHatasi(
                            "Nebim'den yanıt alınamadı; kayıt oluşmuş olabilir. Transfer Geçmişi'nden kontrol edin. "
                            f"({exc})") from exc
                    self._oturum, son = "", str(exc)
                    continue
                if r.status_code in (301, 302):  # oturum düştü, istek işlenmedi
                    self._oturum, son = "", "oturum düştü"
                    continue
                try:
                    veri = r.json()
                except ValueError:
                    self._oturum, son = "", f"HTTP {r.status_code}: {r.text[:200]}"
                    continue
                if isinstance(veri, list):
                    return veri
                mesaj = str(veri.get("ExceptionMessage") or "")
                if mesaj:
                    if "bsReportQuery" in mesaj:
                        raise SorguYokHatasi(f"Sorgu Nebim'de kurulu değil: {yuk.get('QueryName', '')}")
                    if ("deserialize an empty stream" in mesaj or "Session" in mesaj) and deneme < 2:
                        self._oturum, son = "", mesaj
                        continue
                    raise IntegratorHatasi(okunur_hata(mesaj))
                return veri
            raise IntegratorHatasi(f"Integrator isteği tamamlanamadı: {son}")

    # ------------------------------------------------------------ işlemler
    def sorgu(self, ad: str, kriter: str = "") -> list[dict]:
        sonuc = self._cagir("RunQuery", {"ModelType": 32, "QueryName": ad, "Criteria": kriter, "Skip": 0, "Take": 0})
        return sonuc if isinstance(sonuc, list) else []

    def yordam(self, ad: str, parametreler: list[tuple[str, str]], kayit: bool = False) -> list[dict]:
        """RunProc (ModelType 33): parametreler metin gider; ilk sonuç kümesi döner. THROW -> IntegratorHatasi."""
        yuk = {"ModelType": 33, "ProcName": ad, "Parameters": [{"Name": n, "Value": "" if v is None else str(v)} for n, v in parametreler]}
        sonuc = self._cagir("RunProc", yuk, kayit=kayit)
        return sonuc if isinstance(sonuc, list) else []

    def gonder(self, yuk: dict) -> dict:
        sonuc = self._cagir("Post", yuk, kayit=True)
        return sonuc if isinstance(sonuc, dict) else {"Sonuc": sonuc}
