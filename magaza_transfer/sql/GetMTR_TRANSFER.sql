-- Mağazalar arası transfer fişleri (Mağazaya Transfer sevkiyatı, kaynak bir mağaza).
-- Criteria: OperationDate >= #2026-11-01# [AND SourceStore = 'M01'] [AND IsTransferApproved = False]
SELECT ShipmentHeaderID   = h.ShipmentHeaderID,
       ShippingNumber     = h.ShippingNumber,
       OperationDate      = h.OperationDate,
       OperationTime      = CONVERT(char(5), h.OperationTime, 108),
       SourceStore        = h.StoreCode,
       SourceStoreName    = ISNULL(sd.CurrAccDescription, ''),
       SourceWarehouse    = h.WarehouseCode,
       TargetStore        = h.CurrAccCode,
       TargetStoreName    = ISNULL(td.CurrAccDescription, ''),
       TargetWarehouse    = h.ToWarehouseCode,
       TotalQty           = ISNULL((SELECT SUM(l.Qty1) FROM trShipmentLine l WITH (NOLOCK) WHERE l.ShipmentHeaderID = h.ShipmentHeaderID), 0),
       LineCount          = (SELECT COUNT(*) FROM trShipmentLine l WITH (NOLOCK) WHERE l.ShipmentHeaderID = h.ShipmentHeaderID),
       IsTransferApproved = h.IsTransferApproved,
       TransferApprovedDate = CASE WHEN h.IsTransferApproved = 1 THEN h.TransferApprovedDate END,
       EShipmentNumber    = h.Series + CASE WHEN h.SeriesNumber > 0 THEN CAST(h.SeriesNumber AS varchar(20)) ELSE '' END,
       Description        = ISNULL(h.Description, ''),
       CreatedUserName    = h.CreatedUserName,
       CreatedDate        = h.CreatedDate
FROM trShipmentHeader h WITH (NOLOCK)
LEFT JOIN cdCurrAccDesc sd WITH (NOLOCK) ON sd.CurrAccTypeCode = 5 AND sd.CurrAccCode = h.StoreCode AND sd.LangCode = 'TR'
LEFT JOIN cdCurrAccDesc td WITH (NOLOCK) ON td.CurrAccTypeCode = 5 AND td.CurrAccCode = h.CurrAccCode AND td.LangCode = 'TR'
WHERE h.ProcessCode = 'S' AND h.IsReturn = 0 AND h.StoreTypeCode = 5 AND h.StoreCode <> '' AND h.CurrAccTypeCode = 5
