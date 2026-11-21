-- Mağazalar ve depoları (cari tipi 5 = mağaza). Satır = mağaza + depo. Kapalı mağaza/depo gelmez.
SELECT StoreCode          = c.CurrAccCode,
       StoreName          = ISNULL(d.CurrAccDescription, ''),
       OfficeCode         = w.OfficeCode,
       CompanyCode        = ISNULL(o.CompanyCode, 1),
       WarehouseCode      = w.WarehouseCode,
       WarehouseName      = ISNULL(wd.WarehouseDescription, ''),
       IsDefaultWarehouse = w.IsDefault
FROM cdCurrAcc c WITH (NOLOCK)
JOIN cdWarehouse w WITH (NOLOCK) ON w.CurrAccTypeCode = 5 AND w.CurrAccCode = c.CurrAccCode AND w.IsBlocked = 0
LEFT JOIN cdCurrAccDesc d WITH (NOLOCK) ON d.CurrAccTypeCode = 5 AND d.CurrAccCode = c.CurrAccCode AND d.LangCode = 'TR'
LEFT JOIN cdWarehouseDesc wd WITH (NOLOCK) ON wd.WarehouseCode = w.WarehouseCode AND wd.LangCode = 'TR'
LEFT JOIN cdOffice o WITH (NOLOCK) ON o.OfficeCode = w.OfficeCode
WHERE c.CurrAccTypeCode = 5 AND c.IsBlocked = 0 AND c.CurrAccCode <> ''
