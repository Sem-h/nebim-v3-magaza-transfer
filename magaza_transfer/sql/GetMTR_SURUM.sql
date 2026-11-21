-- Kurulu sorgu ve yordam sürümü (program kurulumun güncel olup olmadığını bununla anlar)
SELECT Surum = '1.1.0',
       YordamSurum = ISNULL((SELECT SUBSTRING(d, CHARINDEX('MTR-SURUM: ', d) + 11, 12)
                             FROM (SELECT d = OBJECT_DEFINITION(OBJECT_ID('dbo.sp_MTR_MagazaTransfer'))) x
                             WHERE CHARINDEX('MTR-SURUM: ', d) > 0), ''),
       Program = N'Mağazalar Arası Transfer'
