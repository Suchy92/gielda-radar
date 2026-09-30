"""
radar.py - darmowy radar wiadomości giełdowych po polsku

Co robi (po ludzku):
1. Dla każdej Twojej spółki pyta Google News (po polsku) o najnowsze artykuły.
   Google News zbiera wiadomości z dziesiątek polskich portali naraz.
2. Zapamiętuje, co już widział (plik seen.json), żeby nie powiadamiać 2 razy o tym samym.
3. O KAŻDYM NOWYM artykule wysyła powiadomienie push na Twój telefon (przez ntfy.sh).

Uruchamiany automatycznie co 15 min przez GitHub Actions - za darmo, bez serwera.
"""

import json
import os
import urllib.parse
from pathlib import Path

import feedparser
import requests

KATALOG = Path(__file__).resolve().parent
PLIK_WATCHLISTY = KATALOG / "watchlist.json"
PLIK_SEEN = KATALOG / "seen.json"

# Temat ntfy bierzemy z sekretu GitHuba (bezpiecznie). Zapas: wpisany na sztywno.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "lukasz-gielda-8823xk")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

# Ile artykułów per spółka brać pod uwagę w jednym przebiegu
LIMIT_NA_SPOLKE = 8
# Ile ID pamiętać (żeby plik nie rósł w nieskończoność)
MAX_PAMIEC = 800


def google_news_rss(query: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=pl&gl=PL&ceid=PL:pl"


def wczytaj_json(sciezka, domyslne):
    try:
        with open(sciezka, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return domyslne


def zapisz_json(sciezka, dane):
    with open(sciezka, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)


def wyslij_push(tytul: str, tresc: str, link: str):
    """Wysyła jedno powiadomienie na telefon przez ntfy."""
    try:
        requests.post(
            NTFY_URL,
            data=tresc.encode("utf-8"),
            headers={
                "Title": tytul.encode("utf-8"),
                "Click": link,          # kliknięcie w powiadomienie otwiera artykuł
                "Tags": "chart_with_upwards_trend",
            },
            timeout=15,
        )
    except Exception as e:
        print(f"  ! Nie udało się wysłać push: {e}")


def main():
    watchlist = wczytaj_json(PLIK_WATCHLISTY, {"spolki": []})
    seen = set(wczytaj_json(PLIK_SEEN, []))
    pierwszy_raz = len(seen) == 0

    nowe_ids = []
    liczba_nowych = 0

    for spolka in watchlist.get("spolki", []):
        nazwa = spolka["nazwa"]
        url = google_news_rss(spolka["query"])
        feed = feedparser.parse(url)
        print(f"[{nazwa}] pobrano {len(feed.entries)} artykułów")

        for wpis in feed.entries[:LIMIT_NA_SPOLKE]:
            art_id = wpis.get("id") or wpis.get("link")
            if not art_id or art_id in seen:
                continue
            seen.add(art_id)
            nowe_ids.append(art_id)

            # Przy pierwszym uruchomieniu NIE zalewamy telefonu - tylko zapamiętujemy.
            if pierwszy_raz:
                continue

            tytul = f"📈 {nazwa}"
            tresc = wpis.get("title", "(brak tytułu)")
            link = wpis.get("link", "")
            wyslij_push(tytul, tresc, link)
            liczba_nowych += 1
            print(f"  -> PUSH: {tresc}")

    # Ograniczamy rozmiar pamięci
    seen_lista = (nowe_ids + list(seen))[:MAX_PAMIEC]
    zapisz_json(PLIK_SEEN, seen_lista)

    if pierwszy_raz:
        wyslij_push("✅ Radar giełdowy uruchomiony",
                    "Od teraz dostaniesz push o nowych wiadomościach o Twoich spółkach.",
                    "")
        print("Pierwsze uruchomienie - zapamiętano obecne artykuły, wysłano powitanie.")
    else:
        print(f"Gotowe. Nowych powiadomień: {liczba_nowych}")


if __name__ == "__main__":
    main()
