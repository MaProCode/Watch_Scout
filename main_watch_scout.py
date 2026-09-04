import re
import json
import time
import random
import logging
import urllib.parse
from curl_cffi import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("watch_scout")

# Mappatura completa dei Paesi membri dell'Unione Europea
EU_COUNTRY_MAP = {
    "IT": "Italia 🇮🇹", "DE": "Germania 🇩🇪", "FR": "Francia 🇫🇷",
    "ES": "Spagna 🇪🇸", "NL": "Olanda 🇳🇱", "BE": "Belgio 🇧🇪",
    "AT": "Austria 🇦🇹", "GR": "Grecia 🇬🇷", "PT": "Portogallo 🇵🇹",
    "PL": "Polonia 🇵🇱", "SE": "Svezia 🇸🇪", "DK": "Danimarca 🇩🇰",
    "FI": "Finlandia 🇫🇮", "CZ": "Rep. Ceca 🇨🇿", "HU": "Ungheria 🇭🇺",
    "IE": "Irlanda 🇮🇪", "LU": "Lussemburgo 🇱🇺", "HR": "Croazia 🇭🇷",
    "SI": "Slovenia 🇸🇮", "SK": "Slovacchia 🇸🇰", "RO": "Romania 🇷🇴",
    "BG": "Bulgaria 🇧🇬", "LT": "Lituania 🇱🇹", "LV": "Lettonia 🇱🇻",
    "EE": "Estonia 🇪🇪", "CY": "Cipro 🇨🇾", "MT": "Malta 🇲🇹"
}

#TARGET_REFERENCES = {
#    "Rolex Datejust 41 (126333) Steel&Gold flutè": {
#        "slug": "rolex/ref-126333.htm",
#        "query": "126333",
#        "min_price": 2000
#    },
#    "Rolex Datejust 41 (126334) Steel flutè": {
#        "slug": "rolex/ref-126334.htm",
#        "query": "126334",
#        "min_price": 2000
#    },
#    "Rolex Datejust 41 (126300) Steel smooth": {
#        "slug": "rolex/ref-126300.htm",
#        "query": "126300",
#        "min_price": 2000
#    },
#    "Cartier Santos Medium (WSSA0029) 35mm": {
#        "slug": "cartier/ref-wssa0029.htm",
#        "query": "WSSA0029",
#        "min_price": 2000
#    },
#    "Cartier Santos 100 (2878) 33mm": {
#        "slug": "cartier/ref-2878.htm",
#        "query": "Cartier 2878",
#        "min_price": 1000
#    },
#    "Tudor Black Bay (79220R) Smiley": {
#        "slug": "tudor/ref-79220r.htm",
#        "query": "79220R",
#        "min_price": 1000
#    },
#    "Seiko Cement/Lunar (SRPG63K1)": {
#        "slug": "seiko/ref-srpg63k1.htm",
#        "query": "SRPG63K1",
#        "min_price": 50
#    }
#}

TARGET_REFERENCES = {
    "Rolex Datejust 41 (126333) Steel&Gold flutè": {
        "slug": "rolex/ref-126333.htm",
        "query": "126333",
        "min_price": 2000
    }
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}


# --- FUNZIONI DI FORMATTAZIONE E PARSING METADATI ---

def calculate_discount_format(price_val, average_price):
    if not price_val or not average_price:
        return f"€ {price_val:,.0f}".replace(",", ".")

    diff_pct = ((average_price - price_val) / average_price) * 100
    price_formatted = f"€ {price_val:,.0f}".replace(",", ".")

    if diff_pct > 0:
        return f"{price_formatted} (-{diff_pct:.0f}%)"
    elif diff_pct < 0:
        return f"{price_formatted} (+{abs(diff_pct):.0f}%)"
    else:
        return f"{price_formatted} (0%)"


def extract_country_name(country_code_or_text):
    code = str(country_code_or_text).upper().strip()
    if code in EU_COUNTRY_MAP:
        return EU_COUNTRY_MAP[code]

    for c_code, c_name in EU_COUNTRY_MAP.items():
        if c_code in code or c_name.split()[0].lower() in code.lower():
            return c_name

    return "Italia 🇮🇹"


def extract_year(text):
    match = re.search(r"\b(19[8-9]\d|20[0-2]\d)\b", str(text))
    return match.group(1) if match else "N/D"


def extract_dial_color(text):
    text_lower = str(text).lower()
    colors = {
        "wimbledon": "Wimbledon", "mint": "Mint Green", "verde": "Verde",
        "blu": "Blu", "blue": "Blu", "nero": "Nero", "black": "Nero",
        "bianco": "Bianco", "white": "Bianco", "grigio": "Grigio / Rhodium",
        "rhodium": "Grigio / Rhodium", "silver": "Argenté", "champagne": "Champagne"
    }
    for key, val in colors.items():
        if key in text_lower:
            return val
    return "N/D"


def extract_scope_of_delivery(scope_code_or_text):
    text = str(scope_code_or_text).lower()
    if "101" in text or ("box" in text and "paper" in text) or (
            "scatola" in text and "garanzia" in text) or "full set" in text:
        return "Box + Card"
    elif "102" in text or "box_only" in text or ("scatola" in text and "no garanzia" in text):
        return "Box, No Card"
    elif "103" in text or "papers_only" in text or ("garanzia" in text and "no scatola" in text):
        return "No Box, Card"
    elif "104" in text or "no_box" in text or "solo orologio" in text:
        return "No Box, No Card"
    return "N/D"


def extract_seller_type(seller_info):
    text = str(seller_info).lower()
    if "true" in text or "professional" in text or "merchant" in text or "commerciante" in text or "pro" in text or "company" in text:
        return "Professionista"
    return "Privato"


def parse_eu_price(text):
    """Estrae un prezzo in formato europeo (es. '€ 1.234,56' o '1234 €') da un testo libero."""
    match = re.search(r"€\s?([\d.,]+)|([\d.,]+)\s?€", str(text))
    if not match:
        return None
    raw = match.group(1) or match.group(2)
    # Normalizza: rimuove i punti delle migliaia, converte la virgola decimale in punto
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


def build_marketplace_query(ref_name, info):
    """
    Costruisce una query 'marca + referenza' per i marketplace generalisti
    (Subito, eBay), dove cercare la sola referenza nuda spesso non produce
    risultati perché i privati descrivono l'orologio per marca/modello.
    Chrono24 non usa questa funzione: la sua ricerca è già per slug/referenza.
    """
    brand = ref_name.split()[0]
    ref_code = info["query"]
    if brand.lower() in ref_code.lower():
        return ref_code
    return f"{brand} {ref_code}"


# --- SCRAPER CHRONO24 (INVARIATO) ---

def _extract_chrono24_average_price(search_results, listings):
    """Estrae il prezzo medio dichiarato da Chrono24.
    Se il campo ufficiale non è presente, calcola un fallback sulla stessa
    lista di annunci Chrono24 già estratta; non usa più valori hardcoded.
    """
    dynamic_avg = search_results.get("averagePrice") or search_results.get("marketPrice")
    if isinstance(dynamic_avg, dict):
        dynamic_avg = dynamic_avg.get("amount") or dynamic_avg.get("value")
    try:
        if dynamic_avg is not None and float(dynamic_avg) > 0:
            return float(dynamic_avg)
    except (TypeError, ValueError):
        pass

    prices = [item.get("prezzo_val") for item in listings if item.get("prezzo_val")]
    return sum(prices) / len(prices) if prices else None


def fetch_chrono24(session, ref_name, info):
    url = f"https://www.chrono24.it/{info['slug']}?dosearch=true&countryIds=EU&sortorder=1"
    min_price = info["min_price"]
    listings = []
    average_price = None

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            print(f"  [Chrono24 Warning] HTTP Status: {response.status_code}")
            return listings, average_price

        soup = BeautifulSoup(response.text, "html.parser")
        script_json = soup.find("script", id="__NEXT_DATA__")

        if script_json:
            try:
                data = json.loads(script_json.string or "{}")
                page_props = data.get("props", {}).get("pageProps", {})
                search_results = page_props.get("searchResults", {}) or {}
                articles = search_results.get("articles", []) or []

                for item in articles:
                    price_obj = item.get("price", {})
                    price_val = price_obj.get("amount", 0) if isinstance(price_obj, dict) else price_obj
                    url_path = item.get("url", "")
                    title = item.get("title", "")
                    subtitle = item.get("subtitle", "")
                    full_text = f"{title} {subtitle}"

                    try:
                        price_val = float(price_val)
                    except (TypeError, ValueError):
                        continue

                    if price_val > min_price and url_path:
                        link = f"https://www.chrono24.it{url_path}" if url_path.startswith("/") else url_path
                        seller_obj = item.get("seller", {}) or {}
                        raw_country = seller_obj.get("country") or item.get("country") or item.get("shippingCountry")
                        country = extract_country_name(raw_country)
                        seller_type = extract_seller_type(
                            item.get("isProfessional") or seller_obj.get("isProfessional"))
                        listings.append({
                            "piattaforma": "Chrono24",
                            "modello": ref_name,
                            "prezzo_val": price_val,
                            "paese": country,
                            "tipo_venditore": seller_type,
                            "anno": str(item.get("year") or extract_year(full_text)),
                            "quadrante": item.get("dialColor") or extract_dial_color(full_text),
                            "dotazione": extract_scope_of_delivery(item.get("scopeOfDelivery", full_text)),
                            "link": link
                        })

                # Preferisce il prezzo medio che Chrono24 espone nei propri dati.
                average_price = _extract_chrono24_average_price(search_results, listings)
                if listings:
                    return listings, average_price
            except Exception as e:
                print(f"  [Chrono24 JSON Error]: {e}")

        # Fallback HTML
        product_links = soup.find_all("a", href=re.compile(r"-id\d+\.htm"))
        seen_links = set()

        for link_tag in product_links:
            href = link_tag.get("href", "")
            full_link = f"https://www.chrono24.it{href}" if href.startswith("/") else href
            if full_link in seen_links:
                continue

            container = link_tag.find_parent(["div", "article"])
            if not container:
                continue
            text_content = container.get_text(" ", strip=True)
            price_val = parse_eu_price(text_content)

            if price_val is not None and price_val > min_price:
                seen_links.add(full_link)
                listings.append({
                    "piattaforma": "Chrono24",
                    "modello": ref_name,
                    "prezzo_val": price_val,
                    "paese": extract_country_name(text_content),
                    "tipo_venditore": extract_seller_type(text_content),
                    "anno": extract_year(text_content),
                    "quadrante": extract_dial_color(text_content),
                    "dotazione": extract_scope_of_delivery(text_content),
                    "link": full_link
                })

        if listings:
            average_price = sum(item["prezzo_val"] for item in listings) / len(listings)

    except Exception as e:
        print(f"  [Chrono24 Error] {ref_name}: {e}")

    return listings, average_price


# --- SCRAPER VINTED.IT (Playwright + Network Interception + Fallback HTML) ---

def fetch_vinted(session, ref_name, info):
    results = []
    query = urllib.parse.quote_plus(info["query"])
    # Ordina per prezzo crescente
    url = f"https://www.vinted.it/catalog?search_text={query}&order=price_low_to_high"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT",
            timezone_id="Europe/Rome",
            extra_http_headers={
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )
        page = context.new_page()

        # Elude il rilevamento navigator.webdriver
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        # Intercettazione delle risposte API di Vinted
        def handle_response(response):
            if "api/v2/catalog/items" in response.url:
                try:
                    data = response.json()
                    items = data.get("items", [])
                    for item in items:
                        title = item.get("title", "")
                        price_obj = item.get("price", {})
                        raw_price = price_obj.get("amount") if isinstance(price_obj, dict) else item.get("price")

                        if not raw_price:
                            continue

                        try:
                            p_val = float(raw_price)
                        except (ValueError, TypeError):
                            continue

                        # Filtro di sicurezza per escludere accessori/ricambi
                        if p_val < 500:
                            continue

                        item_url = item.get("url")
                        if not item_url and item.get("id"):
                            item_url = f"https://www.vinted.it/items/{item.get('id')}"

                        if not item_url:
                            continue

                        user_info = item.get("user", {})
                        country_title = user_info.get("country_title") or "Italia"
                        country = extract_country_name(country_title)

                        description = item.get("description", "")
                        full_text = f"{title} {description}"

                        results.append({
                            "piattaforma": "Vinted",
                            "modello": ref_name,
                            "prezzo_val": p_val,
                            "paese": country,
                            "tipo_venditore": "Privato",
                            "anno": extract_year(full_text),
                            "quadrante": extract_dial_color(full_text),
                            "dotazione": extract_scope_of_delivery(full_text),
                            "link": item_url
                        })
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Fallback HTML se l'API non è stata intercettata
            if not results:
                html_content = page.content()
                soup = BeautifulSoup(html_content, "html.parser")
                grid_items = soup.select("[data-testid*='grid-item'], div.feed-grid__item")
                seen_links = set()

                for g_item in grid_items:
                    link_el = g_item.select_one("a[href*='/items/']")
                    if not link_el:
                        continue
                    href = link_el.get("href", "")
                    clean_link = f"https://www.vinted.it{href}" if href.startswith("/") else href

                    if clean_link in seen_links:
                        continue

                    text_content = g_item.get_text(" ", strip=True)
                    price_match = re.search(r"([\d\.\,]+)\s?€|€\s?([\d\.\,]+)", text_content)
                    if price_match:
                        raw_p = price_match.group(1) or price_match.group(2)
                        raw_p = raw_p.replace(".", "").replace(",", ".")
                        try:
                            p_val = float(raw_p)
                        except ValueError:
                            continue

                        if p_val < 500:
                            continue

                        seen_links.add(clean_link)
                        results.append({
                            "piattaforma": "Vinted",
                            "modello": ref_name,
                            "prezzo_val": p_val,
                            "paese": extract_country_name(text_content),
                            "tipo_venditore": "Privato",
                            "anno": extract_year(text_content),
                            "quadrante": extract_dial_color(text_content),
                            "dotazione": extract_scope_of_delivery(text_content),
                            "link": clean_link
                        })

        except Exception as e:
            print(f"  [Vinted Playwright Error] Impossibile recuperare {ref_name}: {e}")
        finally:
            browser.close()

    # Rimuove eventuali duplicati
    unique_results = []
    seen = set()
    for item in results:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique_results.append(item)

    return unique_results



# --- SCRAPER SUBITO.IT (CORRETTO) ---

def parse_subito_json_item(item, ref_name, min_price=500):
    price_val = None
    features = item.get("features", [])

    if isinstance(features, list):
        for feat in features:
            if feat.get("uri") == "/price" or feat.get("name") == "price":
                vals = feat.get("values", [])
                if vals and isinstance(vals, list):
                    price_val = vals[0].get("value")
    elif isinstance(features, dict):
        p_obj = features.get("/price", {})
        vals = p_obj.get("values", [{}])
        if vals:
            price_val = vals[0].get("value")

    if not price_val and item.get("price"):
        price_val = item["price"].get("value") if isinstance(item["price"], dict) else item["price"]

    if price_val:
        try:
            p_val = float(str(price_val).replace(".", "").replace(",", "."))
            if p_val > min_price:
                url_item = item.get("urls", {}).get("default") or item.get("url") or ""
                if not url_item: return None

                full_text = f"{item.get('subject', '')} {item.get('body', '')}"
                seller_type = "Professionista" if item.get("advertiser", {}).get("type") in ["company", "shop",
                                                                                             "pro"] else "Privato"

                return {
                    "piattaforma": "Subito.it",
                    "modello": ref_name,
                    "prezzo_val": p_val,
                    "paese": "Italia 🇮🇹",
                    "tipo_venditore": seller_type,
                    "anno": extract_year(full_text),
                    "quadrante": extract_dial_color(full_text),
                    "dotazione": extract_scope_of_delivery(full_text),
                    "link": url_item
                }
        except ValueError:
            pass
    return None


def parse_subito_html_fallback(page, ref_name, min_price=500):
    """
    Fallback robusto basato su regex sull'URL dell'annuncio, NON su nomi di
    classe CSS (quelli sono class-hash generati da Next.js e cambiano ad ogni
    deploy, causa più comune di 'zero risultati' silenziosi).

    Le pagine annuncio di Subito seguono sempre il pattern:
    https://www.subito.it/<categoria>/<slug-testo>-<ID-numerico>.htm
    """
    results = []
    anchors = page.query_selector_all("a[href*='.htm']")
    id_pattern = re.compile(r"-\d{6,}\.htm/?$")
    seen = set()

    for a in anchors:
        href = a.get_attribute("href") or ""
        if not id_pattern.search(href):
            continue
        full_link = href if href.startswith("http") else f"https://www.subito.it{href}"
        if full_link in seen:
            continue

        # Risale al contenitore della card per leggere prezzo e testo
        container = a
        card_text = ""
        for _ in range(4):
            container = container.evaluate_handle("el => el.closest('article, div')")
            if container is None:
                break
            try:
                card_text = container.as_element().inner_text()
            except Exception:
                card_text = ""
            if "€" in card_text:
                break

        price_val = parse_eu_price(card_text)
        if price_val and price_val > min_price:
            seen.add(full_link)
            results.append({
                "piattaforma": "Subito.it",
                "modello": ref_name,
                "prezzo_val": price_val,
                "paese": "Italia 🇮🇹",
                "tipo_venditore": extract_seller_type(card_text),
                "anno": extract_year(card_text),
                "quadrante": extract_dial_color(card_text),
                "dotazione": extract_scope_of_delivery(card_text),
                "link": full_link
            })

    return results


def fetch_subito_playwright(ref_name, info):
    results = []
    min_price = info["min_price"]
    # FIX 1: query "marca + referenza" invece della sola referenza nuda,
    # che su Subito restituisce quasi sempre 0 risultati specifici.
    search_query = build_marketplace_query(ref_name, info)
    query = urllib.parse.quote_plus(search_query)
    url = f"https://www.subito.it/annunci-italia/vendita/usato/?q={query}&order=price_asc"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="it-IT",
            timezone_id="Europe/Rome"
        )
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # Intercettazione di rete: mantenuta come prima via (best-effort),
        # ma non più l'unica strada, perché i nomi di endpoint non erano verificati.
        def handle_response(response):
            ctype = response.headers.get("content-type", "")
            if "json" not in ctype:
                return
            if "subito.it" not in response.url:
                return
            try:
                data = response.json()
            except Exception:
                return
            # Cerca in modo tollerante una lista di annunci in chiavi comuni
            candidates = []
            if isinstance(data, dict):
                for key in ("list", "items", "ads", "results"):
                    val = data.get(key)
                    if isinstance(val, list) and val:
                        candidates = val
                        break
            for item in candidates:
                if isinstance(item, dict):
                    parsed = parse_subito_json_item(item, ref_name, min_price)
                    if parsed:
                        results.append(parsed)

        page.on("response", handle_response)

        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Prova __NEXT_DATA__ se la rete non ha dato nulla
            if not results:
                script_element = page.query_selector("#__NEXT_DATA__")
                if script_element:
                    content = script_element.inner_text()
                    if content:
                        try:
                            data = json.loads(content)
                            page_props = data.get("props", {}).get("pageProps", {})
                            items = (
                                    page_props.get("initialState", {}).get("items", {}).get("list", []) or
                                    page_props.get("items", []) or
                                    page_props.get("searchResults", {}).get("items", [])
                            )
                            for item in items:
                                parsed = parse_subito_json_item(item, ref_name, min_price)
                                if parsed:
                                    results.append(parsed)
                        except Exception as e:
                            print(f"  [Subito __NEXT_DATA__ Error] {e}")

            # FIX 2: fallback HTML basato su URL-pattern stabile, non su classi CSS
            if not results:
                results = parse_subito_html_fallback(page, ref_name, min_price)

        except Exception as e:
            print(f"  [Subito Playwright Error] Impossibile recuperare {ref_name}: {e}")
        finally:
            browser.close()

    unique_results = []
    seen = set()
    for item in results:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique_results.append(item)

    return unique_results


# --- SCRAPER EBAY.IT (NUOVO) ---

def fetch_ebay(session, ref_name, info):
    """
    Scraper eBay.it.
    Mantiene Playwright, ma non dipende più esclusivamente dal vecchio markup
    .s-item__*. eBay usa attualmente card .s-card / .su-card-container.
    """
    results = []
    min_price = info["min_price"]

    # Per eBay usiamo la stessa logica di query dei marketplace generalisti.
    search_query = build_marketplace_query(ref_name, info)
    query = urllib.parse.quote_plus(search_query)

    # _sop=15: prezzo + spedizione dal più economico.
    # LH_PrefLoc=3: mantiene il filtro UE già adottato dallo scraper originale.
    url = f"https://www.ebay.it/sch/i.html?_nkw={query}&_sop=15&LH_PrefLoc=3"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="it-IT",
            timezone_id="Europe/Rome",
            extra_http_headers={
                "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"'
            }
        )
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        try:
            # Warm-up della sessione: eBay è più permissivo se la navigazione
            # parte dalla home prima della SRP.
            page.goto(
                "https://www.ebay.it/",
                timeout=30000,
                wait_until="domcontentloaded"
            )
            page.wait_for_timeout(1200)

            # Gestione banner cookie, se presente.
            try:
                cookie_selectors = (
                    "#gdpr-banner-accept, "
                    "button[id*='accept'], "
                    "button[aria-label*='Accetta'], "
                    "button:has-text('Accetta')"
                )
                cookie_btn = page.query_selector(cookie_selectors)
                if cookie_btn and cookie_btn.is_visible():
                    cookie_btn.click()
                    page.wait_for_timeout(700)
            except Exception:
                pass

            # Solo dopo il warm-up apriamo la ricerca.
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Se eBay ha restituito un challenge/interstitial, non proviamo
            # a interpretarlo come "0 risultati".
            body_text = (page.locator("body").inner_text(timeout=5000) or "").lower()
            challenge_markers = (
                "pardon our interruption",
                "access denied",
                "verify you're human",
                "verifica che sei umano"
            )
            if any(marker in body_text for marker in challenge_markers):
                print(f"  [eBay Warning] eBay ha restituito una challenge per: {ref_name}")
                return results

            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            seen_links = set()

            # eBay SRP attuale: .s-card / .su-card-container.
            # Manteniamo anche il vecchio .s-item come fallback.
            cards = soup.select("li.s-card, .su-card-container, li.s-item")

            for item in cards:
                # Nuovo markup
                title_el = item.select_one(
                    ".s-card__title, .su-styled-text.s-card__title"
                )
                price_el = item.select_one(
                    ".s-card__price, .su-styled-text.s-card__price"
                )
                link_el = item.select_one(
                    "a.s-card__link[href*='/itm/'], "
                    "a[href*='/itm/']"
                )

                # Vecchio markup come fallback, nel caso eBay serva ancora
                # una variante legacy per quella sessione.
                if title_el is None:
                    title_el = item.select_one(".s-item__title")
                if price_el is None:
                    price_el = item.select_one(".s-item__price")
                if link_el is None:
                    link_el = item.select_one("a.s-item__link[href*='/itm/']")

                if not link_el:
                    continue

                link = link_el.get("href", "").strip()
                if not link or "/itm/" not in link:
                    continue

                # Ricava l'ID pubblico dell'inserzione. Serve anche a eliminare
                # la card fittizia "Shop on eBay".
                item_match = re.search(r"/itm/(?:[^/]+/)?(\d{8,})", link)
                if not item_match:
                    continue
                item_id = item_match.group(1)
                if item_id == "123456":
                    continue

                clean_link = link.split("?")[0]
                if clean_link.startswith("//"):
                    clean_link = f"https:{clean_link}"
                elif clean_link.startswith("/"):
                    clean_link = f"https://www.ebay.it{clean_link}"

                if clean_link in seen_links:
                    continue

                # Titolo: se manca il nodo titolo, prova il testo della card.
                title = title_el.get_text(" ", strip=True) if title_el else ""
                if not title:
                    # Evita di utilizzare il prezzo come titolo.
                    card_copy = item.get_text(" ", strip=True)
                    title = re.sub(r"EUR\s*[\d\.,]+", "", card_copy).strip()

                normalized_title = re.sub(r"\s+", " ", title).strip()
                if not normalized_title:
                    continue

                # Scarta la card placeholder di eBay.
                if normalized_title.lower() in {
                    "shop on ebay",
                    "acquista su ebay"
                }:
                    continue

                if price_el:
                    price_text = price_el.get_text(" ", strip=True)
                else:
                    # Fallback sul testo della card: utile per le card sparse.
                    price_text = item.get_text(" ", strip=True)

                p_val = parse_eu_price(price_text)
                if p_val is None:
                    # Fallback specifico per casi come "EUR 12.406,95".
                    match = re.search(
                        r"(?:EUR|€)\s*([\d\.,]+)",
                        price_text,
                        flags=re.IGNORECASE
                    )
                    if match:
                        raw_price = match.group(1)
                        if "," in raw_price and "." in raw_price:
                            raw_price = raw_price.replace(".", "").replace(",", ".")
                        elif "," in raw_price:
                            raw_price = raw_price.replace(",", ".")
                        else:
                            raw_price = raw_price.replace(".", "")
                        try:
                            p_val = float(raw_price)
                        except ValueError:
                            p_val = None

                if p_val is None:
                    continue

                # Manteniamo il filtro originale dello scraper.
                if p_val <= min_price:
                    continue

                # Località: nuovo markup -> righe attributo/footer;
                # legacy -> selettori .s-item__*.
                loc_el = item.select_one(
                    ".s-card__attribute-row, "
                    ".s-card__footer--row, "
                    ".s-item__location, "
                    ".s-item__itemLocation"
                )
                loc_text = loc_el.get_text(" ", strip=True) if loc_el else ""

                full_text = item.get_text(" ", strip=True)

                # Se la card non espone una località dedicata, preserviamo
                # il comportamento originale: Italia come default.
                if not loc_text:
                    loc_text = "Italia"

                country = extract_country_name(loc_text)

                seller_el = item.select_one(
                    ".s-card__attribute-row, "
                    ".s-card__footer--row, "
                    ".s-item__seller-info"
                )
                seller_text = seller_el.get_text(" ", strip=True) if seller_el else ""
                seller_type = extract_seller_type(seller_text or full_text)

                seen_links.add(clean_link)
                results.append({
                    "piattaforma": "eBay",
                    "modello": ref_name,
                    "prezzo_val": p_val,
                    "paese": country,
                    "tipo_venditore": seller_type,
                    "anno": extract_year(full_text),
                    "quadrante": extract_dial_color(full_text),
                    "dotazione": extract_scope_of_delivery(full_text),
                    "link": clean_link
                })

        except Exception as e:
            print(f"  [eBay Playwright Error] Impossibile recuperare {ref_name}: {e}")
        finally:
            browser.close()

    if not results:
        print(f"  [eBay Warning] Nessuna inserzione parsabile per: {search_query}")

    return results









# --- ESECUZIONE GLOBALE ON DEMAND ---

def run_watch_scanner():
    session = requests.Session(impersonate="chrome124")

    try:
        session.get("https://www.chrono24.it", headers=HEADERS, timeout=10)
        time.sleep(random.uniform(1.0, 1.8))
    except Exception:
        pass

    report_data = {}

    for ref_name, info in TARGET_REFERENCES.items():
        print(f"Scansione in corso per: {ref_name}...")

        chrono_items, market_price = fetch_chrono24(session, ref_name, info)
        subito_items = fetch_subito_playwright(ref_name, info)
        ebay_items = fetch_ebay(session, ref_name, info)
        vinted_items = fetch_vinted(session, ref_name, info)  # Scraper Vinted

        # Unione dei risultati di tutte e 4 le piattaforme
        all_items = chrono_items + subito_items + ebay_items + vinted_items
        all_items.sort(key=lambda x: x["prezzo_val"])

        for item in all_items:
            item["prezzo_str"] = calculate_discount_format(item["prezzo_val"], market_price)

        top_10 = all_items[:10]

        report_data[ref_name] = {
            "market_price": market_price,
            "items": top_10
        }

        print(
            f"  -> Estratti {len(chrono_items)} su Chrono24, "
            f"{len(subito_items)} su Subito.it, "
            f"{len(ebay_items)} su eBay.it e "
            f"{len(vinted_items)} su Vinted."
        )
        time.sleep(random.uniform(2.5, 4.0))

    return report_data







if __name__ == "__main__":
    report = run_watch_scanner()

    print("\n" + "=" * 125)
    print(" REPORT MULTI-PIATTAFORMA (UE) - PRIME 10 OFFERTE MENO CARE PER REFERENZA")
    print("=" * 125 + "\n")

    for ref_name, data in report.items():
        items = data["items"]
        average_price = data["average_price"]
        avg_price_formatted = (
            f"€ {average_price:,.0f}".replace(",", ".") if average_price else "N/D"
        )

        print(
            f"\n--- {ref_name.upper()} (Prime {len(items)} offerte trovate) --- Prezzo medio Chrono24: {avg_price_formatted}")

        if items:
            for idx, item in enumerate(items, 1):
                print(
                    f"{idx:02d}. [{item['piattaforma']}] {item['modello']} | "
                    f"Prezzo: {item['prezzo_str']} | Paese: {item['paese']} | "
                    f"Venditore: {item['tipo_venditore']} | Anno: {item['anno']} | "
                    f"Quadrante: {item['quadrante']} | Dotazione: {item['dotazione']} | \n        Link: {item['link']}"
                )
        else:
            print("Nessuna offerta trovata per questa referenza.")