/* =====================================================================
   sp_MTR_MagazaTransfer  -  Integrator RunProc (ModelType 33)          MTR-SURUM: 1.1.0
   ---------------------------------------------------------------------
   Mağazalar arası transfer: gönderen mağaza deposundan alan mağazaya "Mağazaya Transfer (S)".
   Mağaza kasasının yazdığı yapının aynısını yazar: S transfer siparişi (talep) + ona bağlı S sevkiyatı.
   Integrator'ın hazır modelleri bu akışı yazamadığı için (depo süreç kuralı 2,4,6) yordamla yapılır.
   "Mağazalar Arası Transfer" programı kurar.

   Kurallar:
   - Kayıtlar, Nebim'de mağaza kasasıyla yapılmış en son mağazalar arası transfer örnek alınarak oluşturulur
     (alan alan kopya, yeni kimlik/numara/tarih/mağaza/ürün): trOrderHeader, trOrderLine, trShipmentHeader,
     tpShipmentHeaderExtension, trShipmentLine, trStock (gönderen depodan çıkış). stOrder / stShipment Nebim
     tetikleyicileriyle güncellenir.
   - KabulEdildi = 0: transfer alan mağazanın kabulüne düşer (mal yolda; giriş kabulde kasa tarafından yazılır).
     KabulEdildi = 1: alan depoya giriş + rpTransferApproved da yazılır (kasanın kabul ettiği gibi).
   - Numaralar Nebim sayacından: sipariş srRefNumberProcessFlow (S, 2), sevkiyat (S, 6).
   - Stok kontrolü: gönderen depoda kullanılabilir stok (ItemInventory) yetmezse kayıt yapılmaz.
   - e-İrsaliye bu yordamla kesilmez (Series/SeriesNumber boş kalır); Nebim'den kesilir.
   - Kaydet = 0: hiçbir şey yazılmaz, kontrol edilir ve tahmini numaralarla satırlar döner.
     Kaydet = 1: tek işlem (transaction); son kontrol tutmazsa hiçbir şey yazılmaz.

   Parametreler (RunProc metin gönderir):
     KaynakMagaza  M01        KaynakDepo  D01
     HedefMagaza   M02        HedefDepo   D02
     Tarih         yyyy-aa-gg (boş = bugün)
     Aciklama      fiş açıklaması
     Satirlar      <s><l n="1" i="ÜRÜN" c="RENK" d1="BEDEN" d2="" d3="" q="1" b="BARKOD"/>...</s>
     KabulEdildi   0 / 1
     Kaydet        0 / 1
     Kullanici     Nebim kullanıcısı (CreatedUserName), ör. 'ADM  kullanici'
   Dönüş: satır başına bir kayıt; Sonuc = ONIZLEME | KAYDEDILDI, SiparisNo, FisNo, toplamlar ve satır bilgisi.
   Hatalar ExceptionMessage içinde "Error Desc:" satırıyla döner.
   ===================================================================== */
ALTER PROCEDURE dbo.sp_MTR_MagazaTransfer
    @KaynakMagaza nvarchar(30),
    @KaynakDepo   nvarchar(10),
    @HedefMagaza  nvarchar(30),
    @HedefDepo    nvarchar(10),
    @Tarih        nvarchar(10),
    @Aciklama     nvarchar(200),
    @Satirlar     nvarchar(max),
    @KabulEdildi  nvarchar(1),
    @Kaydet       nvarchar(1),
    @Kullanici    nvarchar(20)
AS
BEGIN
    -- MTR-SURUM: 1.1.0
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    SET @KaynakMagaza = LTRIM(RTRIM(ISNULL(@KaynakMagaza, '')));
    SET @KaynakDepo   = LTRIM(RTRIM(ISNULL(@KaynakDepo, '')));
    SET @HedefMagaza  = LTRIM(RTRIM(ISNULL(@HedefMagaza, '')));
    SET @HedefDepo    = LTRIM(RTRIM(ISNULL(@HedefDepo, '')));
    SET @Aciklama     = LTRIM(RTRIM(ISNULL(@Aciklama, '')));
    SET @Kullanici    = ISNULL(@Kullanici, '');
    IF ISNULL(@Kaydet, '') NOT IN (N'0', N'1')      THROW 50201, N'Kaydet 0 (önizleme) ya da 1 (kaydet) olmalı.', 1;
    IF ISNULL(@KabulEdildi, '') NOT IN (N'0', N'1') THROW 50202, N'KabulEdildi 0 ya da 1 olmalı.', 1;
    IF @Kaydet = N'1' AND LTRIM(RTRIM(@Kullanici)) = '' THROW 50203, N'Kaydetmek için Kullanici (Nebim kullanıcısı) gerekli.', 1;

    DECLARE @Gun date = CASE WHEN LTRIM(RTRIM(ISNULL(@Tarih, ''))) = '' THEN CAST(GETDATE() AS date) ELSE TRY_CONVERT(date, @Tarih, 23) END;
    IF @Gun IS NULL THROW 50204, N'Tarih yyyy-aa-gg biçiminde olmalı.', 1;
    IF @Gun > CAST(GETDATE() AS date) THROW 50205, N'İleri tarihli transfer yapılamaz.', 1;

    /* ---- mağaza / depo ---- */
    DECLARE @KOfis nvarchar(10), @HOfis nvarchar(10), @Sirket numeric(4, 0), @HSirket numeric(4, 0);
    SELECT @KOfis = w.OfficeCode, @Sirket = o.CompanyCode
    FROM cdWarehouse w JOIN cdCurrAcc c ON c.CurrAccTypeCode = 5 AND c.CurrAccCode = w.CurrAccCode
    JOIN cdOffice o ON o.OfficeCode = w.OfficeCode
    WHERE w.WarehouseCode = @KaynakDepo AND w.CurrAccTypeCode = 5 AND w.CurrAccCode = @KaynakMagaza AND w.IsBlocked = 0 AND c.IsBlocked = 0;
    IF @KOfis IS NULL THROW 50206, N'Gönderen mağaza/depo bulunamadı, kapalı ya da depo bu mağazanın değil.', 1;
    SELECT @HOfis = w.OfficeCode, @HSirket = o.CompanyCode
    FROM cdWarehouse w JOIN cdCurrAcc c ON c.CurrAccTypeCode = 5 AND c.CurrAccCode = w.CurrAccCode
    JOIN cdOffice o ON o.OfficeCode = w.OfficeCode
    WHERE w.WarehouseCode = @HedefDepo AND w.CurrAccTypeCode = 5 AND w.CurrAccCode = @HedefMagaza AND w.IsBlocked = 0 AND c.IsBlocked = 0;
    IF @HOfis IS NULL THROW 50207, N'Alan mağaza/depo bulunamadı, kapalı ya da depo bu mağazanın değil.', 1;
    IF @KaynakMagaza = @HedefMagaza THROW 50208, N'Gönderen ve alan mağaza aynı olamaz.', 1;
    IF @Sirket <> @HSirket THROW 50209, N'Mağazalar farklı şirketlerde; mağazalar arası transfer yapılamaz.', 1;

    /* ---- satırlar ---- */
    DECLARE @x xml = TRY_CONVERT(xml, @Satirlar);
    IF @x IS NULL THROW 50210, N'Satırlar okunamadı.', 1;
    SELECT Sira      = l.value('@n', 'int'),
           ItemCode  = LTRIM(RTRIM(ISNULL(l.value('@i', 'nvarchar(30)'), ''))),
           ColorCode = LTRIM(RTRIM(ISNULL(l.value('@c', 'nvarchar(10)'), ''))),
           Dim1      = LTRIM(RTRIM(ISNULL(l.value('@d1', 'nvarchar(10)'), ''))),
           Dim2      = LTRIM(RTRIM(ISNULL(l.value('@d2', 'nvarchar(10)'), ''))),
           Dim3      = LTRIM(RTRIM(ISNULL(l.value('@d3', 'nvarchar(10)'), ''))),
           Qty       = l.value('@q', 'float'),
           Barkod    = LTRIM(RTRIM(ISNULL(l.value('@b', 'nvarchar(30)'), '')))
    INTO #s
    FROM @x.nodes('/s/l') t(l);
    IF NOT EXISTS (SELECT 1 FROM #s) THROW 50211, N'Transfer satırı yok.', 1;
    IF EXISTS (SELECT 1 FROM #s WHERE Sira IS NULL) OR (SELECT COUNT(DISTINCT Sira) FROM #s) <> (SELECT COUNT(*) FROM #s)
        THROW 50212, N'Satır sıra numaraları eksik ya da tekrarlı.', 1;
    IF EXISTS (SELECT 1 FROM #s WHERE ItemCode = '' OR ISNULL(Qty, 0) <= 0)
        THROW 50213, N'Ürün kodu boş ya da adedi sıfır olan satır var.', 1;

    DECLARE @m nvarchar(2048);
    SELECT @m = STUFF((SELECT TOP 5 N', ' + s.ItemCode + N' ' + s.ColorCode + N' ' + s.Dim1 FROM #s s
                       WHERE NOT EXISTS (SELECT 1 FROM prItemVariant v WHERE v.ItemTypeCode = 1 AND v.ItemCode = s.ItemCode
                                         AND v.ColorCode = s.ColorCode AND v.ItemDim1Code = s.Dim1 AND v.ItemDim2Code = s.Dim2 AND v.ItemDim3Code = s.Dim3)
                       ORDER BY s.Sira FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, '');
    IF @m IS NOT NULL
    BEGIN
        SET @m = N'Nebim''de olmayan ürün/renk/beden: ' + @m;
        THROW 50214, @m, 1;
    END

    /* ---- stok ---- */
    SELECT ItemCode, ColorCode, Dim1, Dim2, Dim3, Istenen = SUM(Qty), Stok = CAST(0 AS float)
    INTO #g FROM #s GROUP BY ItemCode, ColorCode, Dim1, Dim2, Dim3;
    UPDATE g SET Stok = ISNULL((SELECT SUM(i.AvailableInventoryQty1) FROM ItemInventory i
                                WHERE i.WarehouseCode = @KaynakDepo AND i.ItemTypeCode = 1 AND i.ItemCode = g.ItemCode
                                  AND i.ColorCode = g.ColorCode AND i.ItemDim1Code = g.Dim1 AND i.ItemDim2Code = g.Dim2
                                  AND i.ItemDim3Code = g.Dim3), 0)
    FROM #g g;
    SELECT @m = STUFF((SELECT TOP 5 N', ' + ItemCode + N' ' + ColorCode + N' ' + Dim1 + N' (istenen ' + CAST(Istenen AS nvarchar(20))
                              + N', stok ' + CAST(Stok AS nvarchar(20)) + N')'
                       FROM #g WHERE Istenen > Stok ORDER BY ItemCode, ColorCode, Dim1 FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 2, '');
    IF @m IS NOT NULL
    BEGIN
        SET @m = N'Gönderen depoda stok yetersiz: ' + @m;
        THROW 50215, @m, 1;
    END

    /* ---- şablon: kasayla yapılmış en son mağazalar arası transfer (siparişe bağlı) ---- */
    DECLARE @SSev uniqueidentifier, @SSevSatir uniqueidentifier, @SSipSatir uniqueidentifier, @SSip uniqueidentifier, @SNo nvarchar(30);
    SELECT TOP 1 @SSev = h.ShipmentHeaderID, @SSevSatir = l.ShipmentLineID, @SSipSatir = l.OrderLineID, @SSip = ol.OrderHeaderID, @SNo = h.ShippingNumber
    FROM trShipmentHeader h
    JOIN trShipmentLine l ON l.ShipmentHeaderID = h.ShipmentHeaderID
    JOIN trOrderLine ol ON ol.OrderLineID = l.OrderLineID
    JOIN trOrderHeader oh ON oh.OrderHeaderID = ol.OrderHeaderID
    WHERE h.ProcessCode = 'S' AND h.IsReturn = 0 AND h.StoreTypeCode = 5 AND h.StoreCode <> '' AND h.CurrAccTypeCode = 5
      AND h.IsOrderBase = 1 AND h.ApplicationCode = 'Shipm' AND h.OperationDate >= DATEADD(year, -2, @Gun)
      AND oh.ProcessCode = 'S' AND oh.StoreCode = h.StoreCode AND oh.CurrAccCode = h.CurrAccCode
      AND l.ReserveLineID IS NULL AND l.DispOrderLineID IS NULL AND l.PickingLineID IS NULL AND l.Qty1 > 0
      AND h.Description NOT LIKE N'TEST%'
      AND EXISTS (SELECT 1 FROM trStock st WHERE st.ApplicationID = l.ShipmentLineID AND st.Out_Qty1 > 0)
    ORDER BY CASE WHEN h.StoreCode = @KaynakMagaza THEN 0 ELSE 1 END, h.CreatedDate DESC;
    IF @SSev IS NULL
        THROW 50216, N'Örnek alınacak mağazalar arası transfer bulunamadı: Nebim''de mağaza kasasıyla en az bir siparişe bağlı mağaza transferi yapılmış olmalı.', 1;

    DECLARE @Adres uniqueidentifier = (SELECT TOP 1 PostalAddressID FROM prCurrAccDefault WHERE CurrAccTypeCode = 5 AND CurrAccCode = @HedefMagaza);
    IF @Adres IS NULL
        SELECT TOP 1 @Adres = PostalAddressID FROM prCurrAccPostalAddress WHERE CurrAccTypeCode = 5 AND CurrAccCode = @HedefMagaza ORDER BY CreatedDate;

    DECLARE @Kabul bit = CASE WHEN @KabulEdildi = N'1' THEN 1 ELSE 0 END;
    DECLARE @Satir int = (SELECT COUNT(*) FROM #s), @Toplam float = (SELECT SUM(Qty) FROM #s);
    DECLARE @Pfx nvarchar(10) = CAST(CAST(@Sirket AS int) AS nvarchar(10)) + N'-S-';

    /* ---- önizleme: hiçbir şey yazılmaz; numaralar tahmini ---- */
    IF @Kaydet = N'0'
    BEGIN
        SELECT Sonuc = N'ONIZLEME',
               SiparisNo = @Pfx + N'2-' + CAST(ISNULL((SELECT LastNumber FROM srRefNumberProcessFlow WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 2), 0) + 1 AS nvarchar(20)),
               FisNo     = @Pfx + N'6-' + CAST(ISNULL((SELECT LastNumber FROM srRefNumberProcessFlow WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 6), 0) + 1 AS nvarchar(20)),
               KaynakMagaza = @KaynakMagaza, KaynakDepo = @KaynakDepo, HedefMagaza = @HedefMagaza, HedefDepo = @HedefDepo,
               Tarih = @Gun, KabulEdildi = @Kabul, SatirSayisi = @Satir, ToplamAdet = @Toplam, OrnekFis = @SNo,
               s.Sira, s.ItemCode, s.ColorCode, ItemDim1Code = s.Dim1, ItemDim2Code = s.Dim2, ItemDim3Code = s.Dim3, Qty1 = s.Qty,
               Stok = g.Stok, Barkod = s.Barkod
        FROM #s s JOIN #g g ON g.ItemCode = s.ItemCode AND g.ColorCode = s.ColorCode AND g.Dim1 = s.Dim1 AND g.Dim2 = s.Dim2 AND g.Dim3 = s.Dim3
        ORDER BY s.Sira;
        RETURN;
    END

    /* ================================ KAYIT ================================ */
    DECLARE @Now datetime = DATEADD(ms, -DATEPART(ms, GETDATE()), GETDATE());
    DECLARE @NowT time(0) = CAST(@Now AS time(0));
    DECLARE @Bos date = '19000101';

    BEGIN TRANSACTION;

    DECLARE @N numeric(19, 0), @SipNo nvarchar(30), @FisNo nvarchar(30);
    IF NOT EXISTS (SELECT 1 FROM srRefNumberProcessFlow WITH (UPDLOCK, ROWLOCK) WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 2)
        INSERT INTO srRefNumberProcessFlow (CompanyCode, ProcessCode, ProcessFlowCode, LastNumber) VALUES (@Sirket, 'S', 2, 0);
    UPDATE srRefNumberProcessFlow WITH (ROWLOCK) SET @N = LastNumber = LastNumber + 1 WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 2;
    SET @SipNo = @Pfx + N'2-' + CAST(@N AS nvarchar(20));
    IF NOT EXISTS (SELECT 1 FROM srRefNumberProcessFlow WITH (UPDLOCK, ROWLOCK) WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 6)
        INSERT INTO srRefNumberProcessFlow (CompanyCode, ProcessCode, ProcessFlowCode, LastNumber) VALUES (@Sirket, 'S', 6, 0);
    UPDATE srRefNumberProcessFlow WITH (ROWLOCK) SET @N = LastNumber = LastNumber + 1 WHERE CompanyCode = @Sirket AND ProcessCode = 'S' AND ProcessFlowCode = 6;
    SET @FisNo = @Pfx + N'6-' + CAST(@N AS nvarchar(20));
    IF EXISTS (SELECT 1 FROM trOrderHeader WHERE OrderNumber = @SipNo) OR EXISTS (SELECT 1 FROM trShipmentHeader WHERE ShippingNumber = @FisNo)
        THROW 50217, N'Nebim numara sayacı kullanılmış bir numara verdi; işlem yapılmadı.', 1;

    DECLARE @OH uniqueidentifier = NEWID(), @SH uniqueidentifier = NEWID();
    SELECT Sira, OL = NEWID(), SL = NEWID() INTO #id FROM #s;

    /* sipariş başlığı */
    SELECT * INTO #oh FROM trOrderHeader WHERE OrderHeaderID = @SSip;
    UPDATE #oh SET OrderHeaderID = @OH, ApplicationID = @OH, OrderNumber = @SipNo, OrderDate = @Gun, OrderTime = @NowT,
        DocumentNumber = N'', PaymentTerm = 0, AverageDueDate = @Bos, Description = @Aciklama, InternalDescription = N'',
        CurrAccTypeCode = 5, CurrAccCode = @HedefMagaza, SubCurrAccID = NULL, ContactID = NULL,
        ShippingPostalAddressID = @Adres, BillingPostalAddressID = NULL, CompanyCode = @Sirket, OfficeCode = @KOfis,
        StoreTypeCode = 5, StoreCode = @KaynakMagaza, WarehouseCode = @KaynakDepo, ToWarehouseCode = N'',
        OrdererCompanyCode = @Sirket, OrdererOfficeCode = @HOfis, OrdererStoreCode = @HedefMagaza,
        IsCompleted = 1, IsPrinted = 0, IsLocked = 0, IsClosed = 0, IsSuspended = 0, UserLocked = 0, IsCancelOrder = 0,
        CreditableConfirmedUser = @Kullanici, CreditableConfirmedDate = @Gun;

    /* sipariş satırları */
    SELECT i.Sira AS _Sira, t.* INTO #ol FROM trOrderLine t CROSS JOIN #id i WHERE t.OrderLineID = @SSipSatir;
    UPDATE o SET OrderLineID = i.OL, SortOrder = s.Sira, ItemTypeCode = 1, ItemCode = s.ItemCode, ColorCode = s.ColorCode,
        ItemDim1Code = s.Dim1, ItemDim2Code = s.Dim2, ItemDim3Code = s.Dim3, Qty1 = s.Qty, Qty2 = 0, CancelQty1 = 0, CancelQty2 = 0,
        CancelDate = @Bos, OrderCancelReasonCode = N'', ClosedDate = @Bos, DeliveryDate = @Gun, PlannedDateOfLading = @Gun,
        LineDescription = N'', UsedBarcode = s.Barkod, PriceListLineID = NULL, SupportRequestHeaderID = NULL,
        PurchaseRequisitionLineID = NULL, OrderLineLinkedProductID = NULL, OrderHeaderID = @OH
    FROM #ol o JOIN #s s ON s.Sira = o._Sira JOIN #id i ON i.Sira = o._Sira;

    /* sevkiyat başlığı + uzantı */
    SELECT * INTO #sh FROM trShipmentHeader WHERE ShipmentHeaderID = @SSev;
    UPDATE #sh SET ShipmentHeaderID = @SH, ApplicationID = @SH, ShippingNumber = @FisNo, IsReturn = 0,
        ShippingDate = @Gun, ShippingTime = @NowT, OperationDate = @Gun, OperationTime = @NowT, Series = N'', SeriesNumber = 0,
        Description = @Aciklama, InternalDescription = N'', CurrAccTypeCode = 5, CurrAccCode = @HedefMagaza, SubCurrAccID = NULL,
        ContactID = NULL, ShippingPostalAddressID = @Adres, BillingPostalAddressID = NULL, LogisticsCompanyBOL = N'',
        CompanyCode = @Sirket, OfficeCode = @KOfis, StoreTypeCode = 5, StoreCode = @KaynakMagaza, WarehouseCode = @KaynakDepo,
        ToWarehouseCode = @HedefDepo, IsOrderBase = 1, IsCompleted = 1, IsPrinted = 0, IsLocked = 0,
        IsTransferApproved = @Kabul, TransferApprovedDate = CASE WHEN @Kabul = 1 THEN @Gun ELSE @Bos END,
        IsPostingJournal = 0, JournalDate = @Bos, CustomerASNNumber = N'';
    SELECT * INTO #ext FROM tpShipmentHeaderExtension WHERE ShipmentHeaderID = @SSev;
    UPDATE #ext SET ShipmentHeaderID = @SH, EShipmentNumber = N'', MainEShipmentNumber = N'', MainShipmentHeaderID = NULL,
        EShipmentStatusCode = 0, ERAApplicationCode = N'', ERAApplicationID = NULL;

    /* sevkiyat satırları (siparişe bağlı) */
    SELECT i.Sira AS _Sira, t.* INTO #sl FROM trShipmentLine t CROSS JOIN #id i WHERE t.ShipmentLineID = @SSevSatir;
    UPDATE l SET ShipmentLineID = i.SL, SortOrder = s.Sira, ItemTypeCode = 1, ItemCode = s.ItemCode, ColorCode = s.ColorCode,
        ItemDim1Code = s.Dim1, ItemDim2Code = s.Dim2, ItemDim3Code = s.Dim3, Qty1 = s.Qty, Qty2 = 0, LineDescription = N'',
        UsedBarcode = s.Barkod, ReserveLineID = NULL, DispOrderLineID = NULL, PickingLineID = NULL, OrderAsnLineID = NULL,
        OrderLineID = i.OL, PriceListLineID = NULL, IsInvoiced = 0, SupportRequestHeaderID = NULL, ShipmentHeaderID = @SH,
        OrderDeliveryDate = @Bos
    FROM #sl l JOIN #s s ON s.Sira = l._Sira JOIN #id i ON i.Sira = l._Sira;

    /* stok: gönderen depodan çıkış */
    SELECT i.Sira AS _Sira, t.* INTO #so FROM (SELECT TOP 1 * FROM trStock WHERE ApplicationID = @SSevSatir AND Out_Qty1 > 0) t CROSS JOIN #id i;
    UPDATE k SET StockID = NEWID(), TransTypeCode = 2, ProcessCode = 'S', InnerProcessCode = N'', IsReturn = 0,
        DocumentDate = @Gun, DocumentTime = @NowT, DocumentNumber = @FisNo, OperationDate = @Gun, OperationTime = @NowT,
        ItemTypeCode = 1, ItemCode = s.ItemCode, ColorCode = s.ColorCode, ItemDim1Code = s.Dim1, ItemDim2Code = s.Dim2, ItemDim3Code = s.Dim3,
        CurrAccTypeCode = 5, CurrAccCode = @HedefMagaza, SubCurrAccID = NULL, CompanyCode = @Sirket,
        OfficeCode = @KOfis, StoreTypeCode = 5, StoreCode = @KaynakMagaza, WarehouseCode = @KaynakDepo,
        In_Qty1 = 0, In_Qty2 = 0, Out_Qty1 = s.Qty, Out_Qty2 = 0,
        FromOfficeCode = @HOfis, FromStoreTypeCode = 5, FromStoreCode = @HedefMagaza, FromWarehouseCode = @HedefDepo,
        LineDescription = N'', ApplicationCode = 'Shipm', ApplicationID = i.SL
    FROM #so k JOIN #s s ON s.Sira = k._Sira JOIN #id i ON i.Sira = k._Sira;

    /* kabul edildiyse: alan depoya giriş */
    SELECT * INTO #si FROM #so WHERE @Kabul = 1;
    UPDATE #si SET StockID = NEWID(), TransTypeCode = 1, OfficeCode = @HOfis, StoreCode = @HedefMagaza, WarehouseCode = @HedefDepo,
        In_Qty1 = Out_Qty1, Out_Qty1 = 0, FromOfficeCode = @KOfis, FromStoreCode = @KaynakMagaza, FromWarehouseCode = @KaynakDepo;

    /* ortak alanlar: kullanıcı, tarih, yeni RowGuid; sonra gerçek tablolara yaz (sıra önemli: tetikleyiciler) */
    DECLARE @T TABLE (Sira int IDENTITY, Tablo sysname, Gecici sysname);
    INSERT INTO @T (Tablo, Gecici) VALUES ('trOrderHeader', '#oh'), ('trOrderLine', '#ol'), ('trShipmentHeader', '#sh'),
        ('tpShipmentHeaderExtension', '#ext'), ('trShipmentLine', '#sl'), ('trStock', '#so'), ('trStock', '#si');
    DECLARE @i int = 1, @tbl sysname, @tmp sysname, @cols nvarchar(max), @sql nvarchar(max);
    WHILE @i <= (SELECT MAX(Sira) FROM @T)
    BEGIN
        SELECT @tbl = Tablo, @tmp = Gecici FROM @T WHERE Sira = @i;
        SET @sql = N'UPDATE ' + @tmp + N' SET CreatedUserName = @u, CreatedDate = @d, LastUpdatedUserName = @u, LastUpdatedDate = @d'
                 + CASE WHEN COL_LENGTH(@tbl, 'RowGuid') IS NOT NULL THEN N', RowGuid = NEWID()' ELSE N'' END;
        EXEC sp_executesql @sql, N'@u nvarchar(20), @d datetime', @Kullanici, @Now;
        SET @cols = STUFF((SELECT N',' + QUOTENAME(c.name) FROM sys.columns c
                           WHERE c.object_id = OBJECT_ID(@tbl) AND c.is_computed = 0 AND c.is_identity = 0 AND TYPE_NAME(c.system_type_id) <> 'timestamp'
                           ORDER BY c.column_id FOR XML PATH(''), TYPE).value('.', 'nvarchar(max)'), 1, 1, '');
        SET @sql = N'INSERT INTO dbo.' + QUOTENAME(@tbl) + N' (' + @cols + N') SELECT ' + @cols + N' FROM ' + @tmp
                 + CASE WHEN @tmp IN ('#ol', '#sl', '#so', '#si') THEN N' ORDER BY _Sira' ELSE N'' END;
        EXEC sp_executesql @sql;
        SET @i += 1;
    END

    IF @Kabul = 1
        INSERT INTO rpTransferApproved (TransferApprovedID, ApplicationCode, ApplicationID, ApplicationLineID, ProcessCode, InnerProcessCode,
            ItemTypeCode, ItemCode, ColorCode, ItemDim1Code, ItemDim2Code, ItemDim3Code, UsedBarcode, LotBarcode, SerialNumber,
            MissingStock, OverStock, CreatedUserName, CreatedDate, LastUpdatedUserName, LastUpdatedDate, BatchCode, SectionCode)
        SELECT NEWID(), 'Shipm', @SH, i.SL, 'S', N'', 1, s.ItemCode, s.ColorCode, s.Dim1, s.Dim2, s.Dim3, s.Barkod, N'', N'',
               0, 0, @Kullanici, @Now, @Kullanici, @Now, N'', N''
        FROM #s s JOIN #id i ON i.Sira = s.Sira;

    /* son kontrol */
    IF (SELECT COUNT(*) FROM trOrderLine WHERE OrderHeaderID = @OH) <> @Satir
       OR (SELECT COUNT(*) FROM trShipmentLine WHERE ShipmentHeaderID = @SH) <> @Satir
       OR ISNULL((SELECT SUM(st.Out_Qty1) FROM trStock st JOIN #id i ON i.SL = st.ApplicationID), 0) <> @Toplam
       OR (@Kabul = 1 AND ISNULL((SELECT SUM(st.In_Qty1) FROM trStock st JOIN #id i ON i.SL = st.ApplicationID), 0) <> @Toplam)
       OR EXISTS (SELECT 1 FROM stOrder so JOIN #id i ON i.OL = so.OrderLineID WHERE so.Qty1 > 0)
        THROW 50218, N'Son kontrol tutmadı; hiçbir şey yazılmadı.', 1;

    COMMIT TRANSACTION;

    SELECT Sonuc = N'KAYDEDILDI', SiparisNo = @SipNo, FisNo = @FisNo,
           KaynakMagaza = @KaynakMagaza, KaynakDepo = @KaynakDepo, HedefMagaza = @HedefMagaza, HedefDepo = @HedefDepo,
           Tarih = @Gun, KabulEdildi = @Kabul, SatirSayisi = @Satir, ToplamAdet = @Toplam, OrnekFis = @SNo,
           s.Sira, s.ItemCode, s.ColorCode, ItemDim1Code = s.Dim1, ItemDim2Code = s.Dim2, ItemDim3Code = s.Dim3, Qty1 = s.Qty,
           Stok = g.Stok, Barkod = s.Barkod
    FROM #s s JOIN #g g ON g.ItemCode = s.ItemCode AND g.ColorCode = s.ColorCode AND g.Dim1 = s.Dim1 AND g.Dim2 = s.Dim2 AND g.Dim3 = s.Dim3
    ORDER BY s.Sira;
END
