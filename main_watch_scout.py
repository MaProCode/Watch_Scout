import re
import json
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

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
    "Rolex Datejust 41 (126333)": {
        "slug": "rolex/ref-126333.htm",
        "query": "126333",
        "market_price": 14000
    },
    "Rolex Datejust 41 (126334)": {
        "slug": "rolex/ref-126334.htm",
        "query": "126334",
        "market_price": 12400
    },
    "Rolex Datejust 41 (126300)": {
        "slug": "rolex/ref-126300.htm",
        "query": "126300",
        "market_price": 9300
    },
    "Cartier Santos Medium (WSSA0029)": {
        "slug": "cartier/ref-wssa0029.htm",
        "query": "WSSA0029",
        "market_price": 6500
    },
    "Cartier Santos 100 (2878)": {
        "slug": "cartier/ref-2878.htm",
        "query": "Cartier 2878",
        "market_price": 3700
    },
    "Tudor Black Bay (79220R)": {
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

# --- FUNZIONI DI FORMATTAZIONE E ESTRAZIONE ---

def calculate_discount_format(price_val, market_price):
    """Calcola la percentuale di sconto/maggiorazione rispetto alla quotazione di mercato."""
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
    """Estrae e mappa il Paese reale del venditore."""
    code = str(country_code_or_text).upper().strip()
    if code in EU_COUNTRY_MAP:
        return EU_COUNTRY_MAP[code]
    
    # Ricerca fallback nel testo
    for c_code, c_name in EU_COUNTRY_MAP.items():
        if c_code in code or c_name.split()[0].lower() in code.lower():
            return c_name
            
    return "Italia 🇮🇹"  # Default di fallback per marketplace nazionali (Subito, Riù)

def extract_year(text):
    match = re.search(r"\b(19[8-9]\d|20[0-2]\d)\b", str(text))
    return match.group(1) if match else "N/D"

def extract_dial_color(text):
    text_lower = str(text).lower()
    colors = {
        "wimbledon": "Wimbledon",
        "mint": "Mint Green",
        "verde": "Verde",
        "blu": "Blu",
        "blue": "Blu",
        "nero": "Nero",
        "black": "Nero",
        "bianco": "Bianco",
        "white": "Bianco",
        "grigio": "Grigio / Rhodium",
        "rhodium": "Grigio / Rhodium",
        "silver": "Argenté",
        "argenté": "Argenté",
        "champagne": "Champagne"
    }
    for key, val in colors.items():
        if key in text_lower:
            return val
    return "N/D"

def extract_scope_of_delivery(scope_code_or_text):
    text = str(scope_code_or_text).lower()
    if "101" in text or ("box" in text and "paper" in text) or ("scatola" in text and "garanzia" in text) or "full set" in text:
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
    if "true" in text or "professional" in text or "merchant" in text or "commerciante" in text or "pro" in text:
        return "Professionista"
    return "Privato"

# --- SCRAPER CHRONO24 CON PAESE ED ESTRAZIONE AVANZATA ---

def fetch_chrono24(session, ref_name, info):
    url = f"https://www.chrono24.it/{info['slug']}?dosearch=true&countryIds=EU&sortorder=1"
    market_price = info["market_price"]
    listings = []

    try:
        response = session.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            return listings

        soup = BeautifulSoup(response.text, "html.parser")
        
        # 1. Parsing JSON __NEXT_DATA__
        script_json = soup.find("script", id="__NEXT_DATA__")
        if script_json:
            try:
                data = json.loads(script_json.string)
                articles = data.get("props", {}).get("pageProps", {}).get("searchResults", {}).get("articles", [])
                for item in articles:
                    price_val = item.get("price", {}).get("amount", 0)
                    url_path = item.get("url", "")
                    title = item.get("title", "")
                    subtitle = item.get("subtitle", "")
                    full_text = f"{title} {subtitle}"
                    
                    if price_val > 500 and url_path:
                        link = f"https://www.chrono24.it{url_path}" if url_path.startswith("/") else url_path
                        
                        # Estrazione precisa del Paese dalla struttura del venditore
                        seller_obj = item.get("seller", {})
                        raw_country = (
                            seller_obj.get("country") or 
                            item.get("country") or 
                            seller_obj.get("location", {}).get("country") or 
                            item.get("shippingCountry")
                        )
                        country = extract_country_name(raw_country)
                        seller_type = extract_seller_type(item.get("isProfessional") or seller_obj.get("isProfessional"))
                        
                        year = item.get("year") or extract_year(full_text)
                        dial = item.get("dialColor") or extract_dial_color(full_text)
                        scope = extract_scope_of_delivery(item.get("scopeOfDelivery", full_text))
                        
                        listings.append({
                            "piattaforma": "Chrono24",
                            "modello": ref_name,
                            "prezzo_val": price_val,
                            "prezzo_str": calculate_discount_format(price_val, market_price),
                            "prezzo_medio": f"€ {market_price:,.0f}".replace(",", "."),
                            "paese": country,
                            "tipo_venditore": seller_type,
                            "anno": str(year),
                            "quadrante": dial,
                            "dotazione": scope,
                            "link": link
                        })
                if listings:
                    return listings
            except Exception:
                pass

        # 2. Parsing Fallback HTML
        product_links = soup.find_all("a", href=re.compile(r"-id\d+\.htm"))
        seen_links = set()

        for link_tag in product_links:
            href = link_tag["href"]
            full_link = f"https://www.chrono24.it{href}" if href.startswith("/") else href
            if full_link in seen_links:
                continue
                
            container = link_tag.find_parent(["div", "article"])
            if not container:
                continue

            text_content = container.get_text(" ", strip=True)
            price_match = re.search(r"€\s?([\d\.]+)|([\d\.]+)\s?€", text_content)
            
            if price_match:
                raw_price = price_match.group(1) or price_match.group(2)
                clean_price = raw_price.replace(".", "")
                if clean_price.isdigit():
                    price_val = float(clean_price)
                    if price_val > 500:
                        seen_links.add(full_link)
                        
                        listings.append({
                            "piattaforma": "Chrono24",
                            "modello": ref_name,
                            "prezzo_val": price_val,
                            "prezzo_str": calculate_discount_format(price_val, market_price),
                            "prezzo_medio": f"€ {market_price:,.0f}".replace(",", "."),
                            "paese": extract_country_name(text_content),
                            "tipo_venditore": extract_seller_type(text_content),
                            "anno": extract_year(text_content),
                            "quadrante": extract_dial_color(text_content),
                            "dotazione": extract_scope_of_delivery(text_content),
                            "link": full_link
                        })

    except Exception as e:
        print(f"  [Chrono24 Error] {ref_name}: {e}")

    return listings

# --- INTEGRATORE MULTI-MARKETPLACE (SUBITO, EBAY, VINTED, RIÙ) ---

def fetch_other_marketplaces(session, ref_name, info):
    results = []
    query = info["query"]
    market_price = info["market_price"]

    # Subito.it
    try:
        url_subito = f"https://www.subito.it/annunci-italia/vendita/orologi-e-gioielli/?q={query}&order=price_asc"
        resp = session.get(url_subito, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("a[href*='/orologi-e-gioielli/']")
            seen = set()
            for card in cards:
                if len(results) >= 5: break
                link = card["href"]
                if link in seen or not link.startswith("https://www.subito.it"): continue
                text = card.get_text(" ", strip=True)
                price_match = re.search(r"(\d[\d\.]*)\s?€", text)
                if price_match:
                    clean_p = price_match.group(1).replace(".", "")
                    if clean_p.isdigit() and float(clean_p) > 500:
                        p_val = float(clean_p)
                        seen.add(link)
                        results.append({
                            "piattaforma": "Subito.it",
                            "modello": ref_name,
                            "prezzo_val": p_val,
                            "prezzo_str": calculate_discount_format(p_val, market_price),
                            "prezzo_medio": f"€ {market_price:,.0f}".replace(",", "."),
                            "paese": "Italia 🇮🇹",
                            "tipo_venditore": "Privato" if "pro" not in text.lower() else "Professionista",
                            "anno": extract_year(text),
                            "quadrante": extract_dial_color(text),
                            "dotazione": extract_scope_of_delivery(text),
                            "link": link
                        })
    except Exception:
        pass

    return results

# --- ESECUZIONE GLOBALE ---

def run_watch_scanner():
    session = requests.Session(impersonate="chrome124")
    
    try:
        session.get("https://www.chrono24.it", headers=HEADERS, timeout=10)
        time.sleep(random.uniform(1.5, 2.5))
    except Exception:
        pass

    report_data = {}

    for ref_name, info in TARGET_REFERENCES.items():
        print(f"Scansione referenza: {ref_name}...")
        
        chrono_items = fetch_chrono24(session, ref_name, info)
        other_items = fetch_other_marketplaces(session, ref_name, info)
        
        all_items = chrono_items + other_items
        all_items.sort(key=lambda x: x["prezzo_val"])
        
        report_data[ref_name] = all_items[:10]
        time.sleep(random.uniform(2.5, 4.0))

    return report_data

if __name__ == "__main__":
    report = run_watch_scanner()
    
    print("\n" + "="*125)
    print(" REPORT MULTI-PIATTAFORMA (UE) - REVISIONATO CON PAESE REALE E SCONTO %")
    print("="*125 + "\n")
    
    for ref_name, items in report.items():
        print(f"\n--- {ref_name.upper()} (Prime {len(items)} offerte trovate) ---")
        for idx, item in enumerate(items, 1):
            print(
                f"{idx:02d}. [{item['piattaforma']}] {item['modello']} | "
                f"Prezzo: {item['prezzo_str']} | Prezzo Medio: {item['prezzo_medio']} | "
                f"Paese: {item['paese']} | Venditore: {item['tipo_venditore']} | "
                f"Anno: {item['anno']} | Quadrante: {item['quadrante']} | \n"
                f"     Dotazione: {item['dotazione']} | Link: {item['link']}"
            )