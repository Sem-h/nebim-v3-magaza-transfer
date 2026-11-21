-- Depo stoku (ürün + renk + beden). Mutlaka süzgeçle çağrılır:
-- Criteria: WarehouseCode = 'D01' AND ItemCode = 'URUN001'   veya   WarehouseCode = 'D01' AND ItemCode LIKE 'URUN%'
SELECT WarehouseCode     = s.WarehouseCode,
       ItemCode          = s.ItemCode,
       ItemDescription   = ISNULL(i.ItemDescription, ''),
       ColorCode         = s.ColorCode,
       ColorDescription  = ISNULL(c.ColorDescription, ''),
       ItemDim1Code      = s.ItemDim1Code,
       ItemDim2Code      = s.ItemDim2Code,
       ItemDim3Code      = s.ItemDim3Code,
       InventoryQty      = s.InventoryQty1,
       AvailableQty      = s.AvailableInventoryQty1
FROM ItemInventory s WITH (NOLOCK)
LEFT JOIN cdItemDesc i WITH (NOLOCK) ON i.ItemTypeCode = s.ItemTypeCode AND i.ItemCode = s.ItemCode AND i.LangCode = 'TR'
LEFT JOIN cdColorDesc c WITH (NOLOCK) ON c.ColorCode = s.ColorCode AND c.LangCode = 'TR'
WHERE s.ItemTypeCode = 1
