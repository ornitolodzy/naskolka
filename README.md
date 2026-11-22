# Kolekcjoner fejków: FOLLOW THE FAKE

Narzędzie dla analityka, które grupuje oszukańcze reklamy i strony w **kampanie**: materiały z tymi samymi śladami
technicznymi (domeny, piksele śledzące, szablony linków, pliki strony, grafiki) prawdopodobnie pochodzą od tego samego
operatora. Każde powiązanie jest **wyjaśnione** listą konkretnych wspólnych śladów. Dodatkowo każdy materiał dostaje
**lampkę ryzyka** zależną od użycia AI, wizerunku osób publicznych i manipulacyjnego przekazu.

Wyzwanie NASK „Kolekcjoner fejków”, HackNation 2026. Szczegóły metody: [docs/METODYKA.md](docs/METODYKA.md).

## Co potrafi

- **Import incydentów** w formacie zbioru NASK: HAR, HTML, MHTML, zrzuty ekranu, wideo, `info.json`, `manifest.json`.
  Działa na rozpakowanym katalogu albo przez wgranie archiwum `.zip`.
- **Analiza nowego materiału**: URL, pliki albo archiwum. Wynik to przypisanie do znanej kampanii, oznaczenie jako
  pokrewny wariant albo nowy wzorzec, razem z uzasadnieniem.
- **Ekstrakcja cech** w ośmiu kanałach: infrastruktura, śledzenie i lejek reklamowy, kod strony, treść, obrazy,
  twarze, osoby i marki, narracja. Teksty z grafik i klatek wideo czyta OCR.
- **Kampanie i rodziny kampanii**: sygnatura każdej kampanii, interaktywny graf powiązań, porównanie dowolnej pary
  materiałów z rozbiciem na kanały.
- **Lampki ryzyka**:

  | Kolor | Znaczenie |
  | --- | --- |
  | zielona | brak sygnału AI |
  | żółta | treść zadeklarowana jako AI |
  | czerwona | AI wykryte bez deklaracji |
  | fioletowa | AI + wizerunek osoby publicznej |
  | czarna | AI + osoba publiczna + manipulacyjny przekaz |

- **Samouczący się detektor AI**: uczy się na materiałach, które same deklarują AI (podpis, etykieta platformy,
  metadane C2PA, IPTC lub SynthID), oraz na ocenach analityka.
- **Eksport** wzbogaconego zbioru (cechy, kampanie, powiązania, lampki) do JSON.

## Uruchomienie (Docker)

```bash
cp .env.example .env              # opcjonalnie
docker compose up -d --build
# UI: http://localhost:4300
```

Dane trzymane są w `./data`, który jest montowany do kontenera:

1. Rozpakuj zbiór NASK do `data/raw/` (albo wgraj `.zip` na stronie **System**).
2. Kliknij **Importuj zbiór**. Pierwszy import 10 incydentów trwa około 7 minut na CPU (OCR i wideo), kolejne korzystają
   z cache.

Opcjonalny lokalny LLM do analizy narracji (Bielik przez Ollama):

```bash
docker compose --profile llm up -d
docker compose exec ollama ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
# w .env: FK_OLLAMA_URL=http://ollama:11434, potem: docker compose up -d backend
```

Bez LLM analiza manipulacji działa na słownikach i regułach. Żadne dane nie są wysyłane do zewnętrznych usług.
Wzbogacanie online (RDAP i DNS) jest domyślnie wyłączone (`FK_ENABLE_ONLINE=1`, żeby je włączyć).

## Uruchomienie deweloperskie

```powershell
# backend (Python 3.12+)
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m app.cli models       # pobiera modele twarzy do data/models
.\.venv\Scripts\python -m app.cli import       # import data/raw + raport kampanii w konsoli
.\.venv\Scripts\python -m uvicorn app.main:app --port 8010 --reload
.\.venv\Scripts\python -m pytest

# frontend (Node 22+)
cd frontend
npm install
npx ng serve --port 4300                       # proxy /api -> 127.0.0.1:8010
```

## Architektura

```
frontend (Angular 22, Cytoscape)  ──>  proxy (nginx)  ──>  backend (FastAPI)
                                                             ├─ ingest/    HAR, HTML, MHTML, obrazy, wideo
                                                             ├─ features/  infra, URL, tekst, OCR, twarze, detektor AI
                                                             ├─ correlate  dowody -> powiązania -> kampanie
                                                             ├─ risk       lampki ryzyka
                                                             └─ store      SQLite (data/kolekcjoner.sqlite3)
```

Najważniejsze endpointy (`/api/v1`): `POST /analyze`, `GET /materials/{id}`, `GET /campaigns`, `GET /graph`,
`GET /compare?a=&b=`, `POST /dataset/import`, `POST /ai/train`, `GET /export`. Pełna lista jest w `/docs` (Swagger).

Wiedzę referencyjną można edytować bez zmian w kodzie:
- `backend/reference/persons.yaml`: osoby publiczne;
- `backend/reference/lexicons.yaml`: marki, tematy, kategorie manipulacji, wzorce deklaracji AI;
- `backend/reference/faces/<slug>/*.jpg`: zdjęcia wzorcowe twarzy.

## Dane

Materiały konkursowe **nie mogą być publicznie rozpowszechniane**, dlatego `data/` jest w `.gitignore`.
Repozytorium zawiera wyłącznie kod i wiedzę referencyjną.

## Biblioteki, modele i licencje

| Komponent | Zastosowanie | Licencja |
| --- | --- | --- |
| FastAPI, Starlette, Pydantic, Uvicorn | API | MIT / BSD-3 |
| httpx | pobieranie stron, RDAP | BSD-3 |
| BeautifulSoup4, lxml | parsowanie HTML | MIT / BSD-3 |
| Pillow, ImageHash | obrazy, hashe percepcyjne | MIT-CMU / BSD-2 |
| NumPy, scikit-learn | TF-IDF, regresja logistyczna (detektor AI) | BSD-3 |
| NetworkX | graf, Louvain | BSD-3 |
| tldextract | domeny rejestrowalne | BSD-3 |
| PyYAML | wiedza referencyjna | MIT |
| OpenCV (opencv-python-headless) | wideo, detekcja i rozpoznawanie twarzy | Apache-2.0 |
| YuNet (OpenCV Zoo) | model detekcji twarzy | MIT |
| SFace (OpenCV Zoo) | model embeddingów twarzy | Apache-2.0 |
| RapidOCR + ONNX Runtime (modele PP-OCR) | OCR tekstu z grafik i klatek | Apache-2.0 / MIT |
| Angular, RxJS | interfejs | MIT / Apache-2.0 |
| Cytoscape.js | graf powiązań | MIT |
| nginx | serwowanie i proxy | BSD-2 |
| Ollama, Bielik 11B v2.3 (opcjonalnie) | lokalna analiza narracji | MIT / Apache-2.0 |
