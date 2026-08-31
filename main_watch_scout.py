import re
import json
import time
import random
import urllib.parse
from curl_cffi import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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

TARGET_REFERENCES = {
    "Rolex Datejust 41 (126333) Steel&Gold flutè": {
        "slug": "rolex/ref-126333.htm",
        "query": "126333",
        "market_price": 14000
    },
    "Rolex Datejust 41 (126334) Steel flutè": {
        "slug": "rolex/ref-126334.htm",
        "query": "126334",
        "market_price": 12400
    },
    "Rolex Datejust 41 (126300) Steel smooth": {
        "slug": "rolex/ref-126300.htm",
        "query": "126300",
        "market_price": 9300
    },
    "Cartier Santos Medium (WSSA0029) 35mm": {
        "slug": "cartier/ref-wssa0029.htm",
        "query": "WSSA0029",
        "market_price": 6500
    },
    "Cartier Santos 100 (2878) 33mm": {
        "slug": "cartier/ref-2878.htm",
        "query": "Cartier 2878",
        "market_price": 3700
    },
    "Tudor Black Bay (79220R) Smiley": {
        "slug": "tudor/ref-79220r.htm",
        "query": "79220R",
        "market_price": 3500
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

def calculate_discount_format(price_val, market_price):
    if not price_val or not market_price:
        return f"€ {price_val:,.0f}".replace(",", ".")

    diff_pct = ((market_price - price_val) / market_price) * 100
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


# --- SCRAPER CHRONO24 ---

def fetch_chrono24(session, ref_name, info):
    url = f"https://www.chrono24.it/{info['slug']}?dosearch=true&countryIds=EU&sortorder=1"
    market_price = info["market_price"]
    listings = []

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            print(f"  [Chrono24 Warning] HTTP Status: {response.status_code}")
            return listings, market_price

        soup = BeautifulSoup(response.text, "html.parser")
        extracted_market_price = market_price

        script_json = soup.find("script", id="__NEXT_DATA__")
        if script_json:
            try:
                data = json.loads(script_json.string)
                page_props = data.get("props", {}).get("pageProps", {})
                search_results = page_props.get("searchResults", {})

                dynamic_avg = search_results.get("averagePrice") or page_props.get("marketPrice")
                if dynamic_avg and float(dynamic_avg) > 0:
                    extracted_market_price = float(dynamic_avg)

                articles = search_results.get("articles", [])
                for item in articles:
                    price_val = item.get("price", {}).get("amount", 0)
                    url_path = item.get("url", "")
                    title = item.get("title", "")
                    subtitle = item.get("subtitle", "")
                    full_text = f"{title} {subtitle}"

                    if price_val > 500 and url_path:
                        link = f"https://www.chrono24.it{url_path}" if url_path.startswith("/") else url_path
                        seller_obj = item.get("seller", {})
                        raw_country = seller_obj.get("country") or item.get("country") or item.get("shippingCountry")
                        country = extract_country_name(raw_country)
                        seller_type = extract_seller_type(
                            item.get("isProfessional") or seller_obj.get("isProfessional"))

                        listings.append({
                            "piattaforma": "Chrono24",
                            "modello": ref_name,
                            "prezzo_val": float(price_val),
                            "paese": country,
                            "tipo_venditore": seller_type,
                            "anno": str(item.get("year") or extract_year(full_text)),
                            "quadrante": item.get("dialColor") or extract_dial_color(full_text),
                            "dotazione": extract_scope_of_delivery(item.get("scopeOfDelivery", full_text)),
                            "link": link
                        })
                if listings:
                    return listings, extracted_market_price
            except Exception as e:
                print(f"  [Chrono24 JSON Error]: {e}")

        # Fallback HTML
        product_links = soup.find_all("a", href=re.compile(r"-id\d+\.htm"))
        seen_links = set()

        for link_tag in product_links:
            href = link_tag["href"]
            full_link = f"https://www.chrono24.it{href}" if href.startswith("/") else href
            if full_link in seen_links: continue

            container = link_tag.find_parent(["div", "article"])
            if not container: continue

            text_content = container.get_text(" ", strip=True)
            price_match = re.search(r"€\s?([\d\.]+)|([\d\.]+)\s?€", text_content)

            if price_match:
                raw_price = price_match.group(1) or price_match.group(2)
                clean_price = raw_price.replace(".", "")
                if clean_price.isdigit() and float(clean_price) > 500:
                    seen_links.add(full_link)
                    listings.append({
                        "piattaforma": "Chrono24",
                        "modello": ref_name,
                        "prezzo_val": float(clean_price),
                        "paese": extract_country_name(text_content),
                        "tipo_venditore": extract_seller_type(text_content),
                        "anno": extract_year(text_content),
                        "quadrante": extract_dial_color(text_content),
                        "dotazione": extract_scope_of_delivery(text_content),
                        "link": full_link
                    })

    except Exception as e:
        print(f"  [Chrono24 Error] {ref_name}: {e}")

    return listings, extracted_market_price


# --- SCRAPER SUBITO.IT (Playwright con attesa nodo nascosto) ---

def parse_subito_json_item(item, ref_name):
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
            if p_val > 500:
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


def fetch_subito_playwright(ref_name, info):
    results = []
    query = urllib.parse.quote_plus(info["query"])
    url = f"https://www.subito.it/annunci-italia/vendita/usato/?c=36&q={query}&order=price_asc"

    with sync_playwright() as p:
        # 1. Bypass antidentificazione headless
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

        # Rimuove il flag navigator.webdriver per eludere i controlli anti-bot
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        # 2. Intercettazione diretta delle chiamate di rete JSON
        def handle_response(response):
            if "search/items" in response.url or "hades" in response.url:
                try:
                    data = response.json()
                    items = data.get("list", []) or data.get("items", [])
                    for item in items:
                        parsed = parse_subito_json_item(item, ref_name)
                        if parsed:
                            results.append(parsed)
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Se l'intercettazione di rete non ha ancora catturato i dati, prova a leggere dal tag __NEXT_DATA__
            if not results:
                script_element = page.query_selector("#__NEXT_DATA__")
                if script_element:
                    content = script_element.inner_text()
                    if content:
                        data = json.loads(content)
                        page_props = data.get("props", {}).get("pageProps", {})
                        items = (
                                page_props.get("initialState", {}).get("items", {}).get("list", []) or
                                page_props.get("items", []) or
                                page_props.get("searchResults", {}).get("items", [])
                        )
                        for item in items:
                            parsed = parse_subito_json_item(item, ref_name)
                            if parsed:
                                results.append(parsed)

            # 3. Fallback HTML se il JSON viene bloccato completamente
            if not results:
                cards = page.query_selector_all("div[class*='items__item']")
                for card in cards:
                    link_el = card.query_selector("a[class*='SmallCard-module_link']")
                    price_el = card.query_selector("p[class*='price']")

                    if link_el and price_el:
                        link = link_el.get_attribute("href")
                        price_text = price_el.inner_text()
                        price_match = re.search(r"([\d\.]+)\s?€", price_text)

                        if price_match and link:
                            p_val = float(price_match.group(1).replace(".", ""))
                            if p_val > 500:
                                card_text = card.inner_text()
                                results.append({
                                    "piattaforma": "Subito.it",
                                    "modello": ref_name,
                                    "prezzo_val": p_val,
                                    "paese": "Italia 🇮🇹",
                                    "tipo_venditore": extract_seller_type(card_text),
                                    "anno": extract_year(card_text),
                                    "quadrante": extract_dial_color(card_text),
                                    "dotazione": extract_scope_of_delivery(card_text),
                                    "link": link
                                })

        except Exception as e:
            print(f"  [Subito Playwright Error] Impossibile recuperare {ref_name}: {e}")
        finally:
            browser.close()

    # Rimuove eventuali duplicati per lo stesso link
    unique_results = []
    seen = set()
    for item in results:
        if item["link"] not in seen:
            seen.add(item["link"])
            unique_results.append(item)

    return unique_results



# --- ESECUZIONE GLOBALE ON DEMAND ---

def run_watch_scanner():
    session = requests.Session(impersonate="chrome124")

    # Warm-up della sessione per superare eventuali check TLS base
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

        all_items = chrono_items + subito_items
        all_items.sort(key=lambda x: x["prezzo_val"])

        for item in all_items:
            item["prezzo_str"] = calculate_discount_format(item["prezzo_val"], market_price)

        # Ripristino: estrazione delle prime 10 offerte meno care
        top_10 = all_items[:10]

        report_data[ref_name] = {
            "market_price": market_price,
            "items": top_10
        }

        print(f"  -> Estratti {len(chrono_items)} su Chrono24 e {len(subito_items)} su Subito.it.")
        time.sleep(random.uniform(2.5, 4.0))

    return report_data


if __name__ == "__main__":
    report = run_watch_scanner()

    print("\n" + "=" * 125)
    print(" REPORT MULTI-PIATTAFORMA (UE) - PRIME 10 OFFERTE MENO CARE PER REFERENZA")
    print("=" * 125 + "\n")

    for ref_name, data in report.items():
        items = data["items"]
        avg_price_formatted = f"€ {data['market_price']:,.0f}".replace(",", ".")

        print(
            f"\n--- {ref_name.upper()} (Prime {len(items)} offerte trovate) --- Prezzo medio stimato: {avg_price_formatted}")

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