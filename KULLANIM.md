# Mağazalar Arası Transfer — Kullanım Kılavuzu

Nebim V3 kullanan perakende firmaları için mağazalar arası transfer programı. **Nebim V3 Integrator** üzerinden çalışır;
programın kendi veritabanı yoktur. Ayarlar program klasöründeki `config.json` dosyasında durur
(klasör yazılamıyorsa `%APPDATA%\MagazaTransfer\config.json`).

## Gereksinimler

- Windows 10 / 11 (64 bit)
- Çalışan bir Nebim V3 Integrator (adres, veritabanı adı, kullanıcı grubu, kullanıcı; gerekiyorsa şifre)
- Bir kerelik Nebim kurulumu için SQL Server'da yetkili bir hesap **ya da** kurulum betiğini çalıştıracak bir BT çalışanı
- Nebim'de mağaza kasasıyla yapılmış **en az bir** siparişe bağlı mağazalar arası transfer (yordam bunu örnek alır)

## Kurulum

- **Kurulum dosyası:** `MagazaTransfer_Setup_x.y.z.exe` çalıştırılır (yönetici yetkisi istemez, kullanıcının kendi klasörüne kurulur).
- **Taşınabilir:** `MagazaTransfer_Tasinabilir_x.y.z.zip` bir klasöre açılır, `MagazaTransfer.exe` çalıştırılır.

İlk açılışta Integrator bilgileri sorulur. Şifre girilirse `config.json`'a Windows'un kendi şifrelemesiyle (DPAPI)
yazılır; yalnız aynı bilgisayardaki aynı Windows kullanıcısı çözebilir. **Bağlantıyı Test Et** ile kontrol edin.

## Nebim'e bir kez yapılacak kurulum

Integrator yalnız Nebim'de kayıtlı sorguları çalıştırabildiği için program ilk bağlantıda kurulumu kontrol eder;
eksikse **Nebim Kurulumu** penceresi açılır. Kurulum yalnız şunları ekler, başka hiçbir tabloya dokunmaz:

| Nerede | Ne |
|---|---|
| `NebimV3Master.dbo.bsReportQuery` (ReportName = `V3Integrator`) | `GetMTR_SURUM`, `GetMTR_MAGAZALAR`, `GetMTR_BARKOD`, `GetMTR_STOK`, `GetMTR_TRANSFER`, `GetMTR_TRANSFERSATIR` okuma sorguları |
| Nebim şirket veritabanı | `dbo.sp_MTR_MagazaTransfer` transfer kayıt yordamı |

İki yol vardır:
1. **Kur:** SQL Server yetkili hesabı bir kez girilir (hiçbir yere kaydedilmez), program kurar.
2. **Kurulum betiği:** `MagazaTransfer_NebimKurulum_x.y.z.sql` dosyasındaki `SIRKET_VERITABANI` ifadesi Nebim şirket
   veritabanı adıyla değiştirilip SSMS'te çalıştırılır (program içinden **Kurulum Betiğini Kaydet** ile de üretilebilir).

Kaldırmak için `MagazaTransfer_NebimKaldirma_x.y.z.sql` kullanılır. Program sürümü değiştiğinde kurulum yeniden istenir.

> **Önce deneme ortamında deneyin.** Yordam Nebim tablolarına doğrudan yazar. Canlıya almadan önce bir test
> veritabanında birkaç transfer yapıp Nebim ekranlarından ve stoklardan kontrol edin.

## Kullanım

**Yeni Transfer**
1. Gönderen ve alan mağazayı (ve depolarını) seçin.
2. Barkod okutun (`3*barkod` = 3 adet), **Ürün Ara** ile ürün koduna/adına göre seçin ya da **Excel'den Yükle**
   (sütunlar: `Barkod` + `Adet`, ya da `Ürün Kodu` + `Renk` + `Beden` + `Adet`; boş şablon için **Şablon**).
3. Tabloda gönderen depodaki kullanılabilir stok görünür; yetmeyen satırlar kırmızıdır.
4. **Transferi Oluştur:** Nebim önce kontrol eder (hiçbir şey yazmaz), önizleme açılır; **Nebim'e Kaydet** ile kayıt yapılır.

Kayıt, mağaza kasasının yaptığıyla aynıdır: transfer siparişi (`…-S-2-…`) + ona bağlı sevkiyat fişi (`…-S-6-…`),
gönderen depodan stok çıkışı. Varsayılan olarak transfer alan mağazanın **kabulüne düşer** (mal yolda görünür);
bağlantı ayarlarında kapatılırsa kabul edilmiş yazılır ve alan depoya hemen girer.

**e-İrsaliye bu programla kesilmez.** Transfer fişi oluştuktan sonra gönderen mağaza e-İrsaliyeyi Nebim'den keser.

**Transfer Geçmişi:** tarih aralığı, mağaza ve "yalnız yoldakiler" süzgeciyle fişler; çift tıklayınca satırlar,
**Fişi Yazdır**, **Excel'e Aktar**.

## Sık karşılaşılanlar

- *"Örnek alınacak mağazalar arası transfer bulunamadı"*: Nebim'de kasayla en az bir siparişe bağlı mağaza transferi yapın.
- *"Gönderen depoda stok yetersiz"*: Nebim kullanılabilir stoku (rezerv ve sevk emirleri düşülmüş) yetmiyor.
- Integrator ara sıra oturumu düşürür; program kendiliğinden yeniden bağlanır. Kayıt sırasında yanıt alınamazsa
  program uyarır: **Transfer Geçmişi**'nden fişin oluşup oluşmadığına bakın.
