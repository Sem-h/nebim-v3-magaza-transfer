# Mağazalar Arası Transfer — Geliştirici Notları

Nebim V3 Integrator ile çalışan, kendi veritabanı olmayan Windows masaüstü programı (Python 3.13, PySide6).
Kullanıcı kılavuzu: [KULLANIM.md](KULLANIM.md). Lisans: [MIT](LICENSE) — dilediğiniz gibi kullanabilir, değiştirebilir ve dağıtabilirsiniz; lisans metni kopyalarda kalmalıdır.

## Geliştirme ortamı

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Paket (kurulum dosyası + taşınabilir zip + Nebim SQL betikleri) için Inno Setup 6 gerekir:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

Çıktılar `installer\Output\` klasörüne yazılır.

## Yapı

| Dosya | Görev |
|---|---|
| `main.py` | Başlatıcı |
| `magaza_transfer/ayarlar.py` | `config.json` okuma/yazma, şifre için Windows DPAPI |
| `magaza_transfer/integrator.py` | Integrator istemcisi: Connect, RunQuery (ModelType 32), RunProc (ModelType 33); 302 ile düşen oturumu yeniler |
| `magaza_transfer/kurulum.py` | Nebim'e kurulacak SQL nesneleri, kurulum/kaldırma betikleri, SQL hesabıyla kurulum |
| `magaza_transfer/servis.py` | Mağaza/depo, barkod, stok, geçmiş okuma; transfer önizleme ve kayıt |
| `magaza_transfer/ui_*.py` | Arayüz (ana pencere, pencereler, ortak yardımcılar) |
| `magaza_transfer/belgeler.py` | Excel okuma/yazma, yazdırma HTML'i |
| `magaza_transfer/sql/` | Programın Nebim'e kurduğu SQL metinleri |

## Neden yordam (stored procedure)?

Integrator'ın mağaza transferi için hazır modelleri var (18 sipariş, 56 siparişe bağlı sevkiyat, 59 siparişsiz sevkiyat,
83 sevk emri), ancak birçok Nebim kurulumunda mağaza depolarının süreç akış kuralı "Sipariş → Sevk Emri → İrsaliye"dir;
Integrator bu kurala uyduğu için sevkiyatı reddeder. Mağaza kasası ise pratikte sipariş + siparişe bağlı sevkiyat yazar.
`sp_MTR_MagazaTransfer` bu yapıyı, Nebim'de kasayla yapılmış son transferi şablon alarak (alan alan kopya) tek işlemde yazar;
`stOrder` / `stShipment` Nebim'in kendi tetikleyicileriyle güncellenir. Ayrıntı yordamın başındaki açıklamadadır.

Integrator'da bir modelin alanlarını kayıt oluşturmadan öğrenmek için var olmayan bir alanla (`"ZZQQ": "x"`) istek gönderin:
Integrator önce bilinmeyen alanı `"X not found!"` diye reddeder.

## Kurallar

- **Sürüm üç yerde birlikte artırılır:** `kurulum.SURUM`, `sql/GetMTR_SURUM.sql` ve `sql/sp_MTR_MagazaTransfer.sql`
  içindeki `MTR-SURUM` işareti (ayrıca `magaza_transfer/__init__.py`). Program sürüm eşleşmezse kurulum ister.
- RunQuery sorguları Integrator tarafından alt sorgu olarak sarılır: `WITH` (CTE), `ORDER BY` ve `@parametre` kullanmayın;
  süzme Criteria ile yapılır (DevExpress sözdizimi: tarih `#2026-01-31#`, `BETWEEN` yok, `IN (...)` var).
- Criteria ile süzülen sütunlara `RTRIM` gibi işlev uygulamayın; indeks kullanılamaz ve sorgu çok yavaşlar.
- Kurulum yalnız `bsReportQuery` (GetMTR_*) ve tek yordama dokunur; başka nesne eklenecekse kurulum ve kaldırma betiğine de ekleyin.
- Nebim'e yazan her değişikliği önce test veritabanında, önizleme (Kaydet = 0) ve geri alınan işlemle deneyin.
