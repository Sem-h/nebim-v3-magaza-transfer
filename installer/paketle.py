"""Yayın paketinin kurulum dosyası dışındaki parçaları: Nebim SQL betikleri, kaynak kod zip'i, SHA-256 listesi.
Kullanım: python installer\\paketle.py  (build.ps1 çağırır)"""

import hashlib
import sys
import zipfile
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))
from magaza_transfer import __version__  # noqa: E402
from magaza_transfer import kurulum  # noqa: E402

CIKTI = KOK / "installer" / "Output"
CIKTI.mkdir(parents=True, exist_ok=True)
V = __version__
YER = "SIRKET_VERITABANI"
UYARI = (f"/* KULLANMADAN ÖNCE: bu dosyadaki tüm {YER} ifadelerini Nebim şirket veritabanınızın adıyla değiştirin.\n"
         f"   Master veritabanınızın adı NebimV3Master değilse onu da değiştirin. Önce test veritabanında deneyin. */\n\n")

(CIKTI / f"MagazaTransfer_NebimKurulum_{V}.sql").write_text(UYARI + kurulum.kurulum_betigi(YER), encoding="utf-8-sig")
(CIKTI / f"MagazaTransfer_NebimKaldirma_{V}.sql").write_text(UYARI + kurulum.kaldirma_betigi(YER), encoding="utf-8-sig")

# Kaynak kod: yalnız izin verilen dosyalar (ayar dosyası, sanal ortam, derleme çıktıları girmez)
DAHIL = ["main.py", "requirements.txt", "README.md", "KULLANIM.md", "LICENSE", "config.example.json", ".gitignore",
         "assets/app.ico", "assets/app.png", "installer/setup.iss", "installer/build.ps1", "installer/paketle.py"]
DAHIL += [p.relative_to(KOK).as_posix() for p in sorted((KOK / "magaza_transfer").rglob("*"))
          if p.is_file() and "__pycache__" not in p.parts]
kaynak = CIKTI / f"MagazaTransfer_Kaynak_{V}.zip"
with zipfile.ZipFile(kaynak, "w", zipfile.ZIP_DEFLATED) as z:
    for ad in DAHIL:
        z.write(KOK / ad, f"MagazaTransfer-{V}/{ad}")

liste = []
for p in sorted(CIKTI.glob(f"*{V}*")):
    if p.suffix in (".exe", ".zip", ".sql"):
        liste.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
(CIKTI / f"SHA256SUMS_{V}.txt").write_text("\n".join(liste) + "\n", encoding="utf-8", newline="\n")
print("\n".join(liste))
