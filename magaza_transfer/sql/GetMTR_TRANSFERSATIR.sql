-- Transfer fişi satırları. Criteria: ShippingNumber = '1-S-6-1001'
SELECT ShippingNumber   = h.ShippingNumber,
       SortOrder        = l.SortOrder,
       Barcode          = l.UsedBarcode,
       ItemCode         = l.ItemCode,
       ItemDescription  = ISNULL(i.ItemDescription, ''),
       ColorCode        = l.ColorCode,
       ColorDescription = ISNULL(c.ColorDescription, ''),
       ItemDim1Code     = l.ItemDim1Code,
       ItemDim2Code     = l.ItemDim2Code,
       ItemDim3Code     = l.ItemDim3Code,
       Qty1             = l.Qty1,
       LineDescription  = ISNULL(l.LineDescription, '')
FROM trShipmentLine l WITH (NOLOCK)
JOIN trShipmentHeader h WITH (NOLOCK) ON h.ShipmentHeaderID = l.ShipmentHeaderID
LEFT JOIN cdItemDesc i WITH (NOLOCK) ON i.ItemTypeCode = l.ItemTypeCode AND i.ItemCode = l.ItemCode AND i.LangCode = 'TR'
LEFT JOIN cdColorDesc c WITH (NOLOCK) ON c.ColorCode = l.ColorCode AND c.LangCode = 'TR'
WHERE h.ProcessCode = 'S'
