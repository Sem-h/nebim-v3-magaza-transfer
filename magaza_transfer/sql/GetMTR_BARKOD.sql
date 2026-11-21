-- Barkod -> ürün / renk / beden. Criteria: Barcode = '8680000000000'
SELECT Barcode          = b.Barcode,
       BarcodeTypeCode  = b.BarcodeTypeCode,
       ItemCode         = b.ItemCode,
       ItemDescription  = ISNULL(i.ItemDescription, ''),
       ColorCode        = b.ColorCode,
       ColorDescription = ISNULL(c.ColorDescription, ''),
       ItemDim1Code     = b.ItemDim1Code,
       ItemDim2Code     = b.ItemDim2Code,
       ItemDim3Code     = b.ItemDim3Code,
       BarcodeQty       = CASE WHEN b.Qty > 0 THEN b.Qty ELSE 1 END
FROM prItemBarcode b WITH (NOLOCK)
LEFT JOIN cdItemDesc i WITH (NOLOCK) ON i.ItemTypeCode = b.ItemTypeCode AND i.ItemCode = b.ItemCode AND i.LangCode = 'TR'
LEFT JOIN cdColorDesc c WITH (NOLOCK) ON c.ColorCode = b.ColorCode AND c.LangCode = 'TR'
WHERE b.ItemTypeCode = 1
