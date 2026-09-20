import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getMarketplaceCities } from '../../entities/marketplace/api'
import { MarketplaceCatalog } from './MarketplaceCatalog'
import { MarketplaceHome } from './home/MarketplaceHome'

const CITY_STORAGE_KEY = 'waysklad:marketplace-city'

function loadStoredCity(): string | null {
  try {
    return localStorage.getItem(CITY_STORAGE_KEY)
  } catch {
    return null
  }
}

function saveStoredCity(city: string | null) {
  try {
    if (city) localStorage.setItem(CITY_STORAGE_KEY, city)
    else localStorage.removeItem(CITY_STORAGE_KEY)
  } catch {
    /* приватный режим/заблокированное хранилище — город просто не запомнится */
  }
}

/**
 * /marketplace — главная (без параметров) или каталог (есть q/pcat/section/фильтры).
 * Полная спецификация блоков — docs/MARKETPLACE_HOME_PROMPTS.md, M-F2/M-F3/M-F4.
 * Общего CityContext в шапке нет (M-F1 не входит в этот шаг) — город главной хранится
 * в localStorage и выставляется только через чип «Рядом со мной».
 */
export function MarketplacePage() {
  const [searchParams] = useSearchParams()
  const [city, setCity] = useState<string | null>(() => loadStoredCity())

  const isCatalogMode =
    searchParams.has('q') ||
    searchParams.has('pcat') ||
    searchParams.has('category') ||
    searchParams.has('section') ||
    searchParams.has('price_min') ||
    searchParams.has('price_max') ||
    searchParams.has('in_stock_only') ||
    searchParams.has('with_discount') ||
    searchParams.has('min_rating') ||
    searchParams.has('shop_slug') ||
    searchParams.has('sort') ||
    searchParams.has('city')

  function handleNearMe() {
    if (city) return
    getMarketplaceCities()
      .then((data) => {
        // «выставляет город, если он не выбран» (M-F2 §1) — без геолокации на этом шаге,
        // берём первый город из справочника как разумный дефолт вместо гео-запроса браузера
        const first = data.cities[0]?.name
        if (first) setCity(first)
      })
      .catch(() => {})
  }

  useEffect(() => {
    saveStoredCity(city)
  }, [city])

  if (isCatalogMode) return <MarketplaceCatalog />
  return <MarketplaceHome city={city} onNearMe={handleNearMe} />
}
