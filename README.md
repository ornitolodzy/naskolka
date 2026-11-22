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
  twarze, osoby i marki, narracja. Teksty z grafik i klatek wideo czyta OCR, a mowę z wideo transkrybuje lokalnie
  faster-whisper (Whisper „small”, CPU int8, automatycznie CUDA, jeśli jest karta NVIDIA).
- **Kampanie i rodziny kampanii**: sygnatura każdej kampanii, interaktywny graf powiązań, porównanie dowolnej pary
  materiałów z rozbiciem na kanały.
- **Lampki ryzyka** (oszustwo i przypisanie do kampanii):

  | Kolor | Znaczenie |
  | --- | --- |
  | zielona | brak sygnałów oszustwa |
  | żółta | podejrzany: pojedyncze sygnały albo podobieństwo do zgłoszonego oszustwa |
  | pomarańczowa | wysokie ryzyko oszustwa, ale nowy wzorzec (brak twardego powiązania ze znaną kampanią) |
  | czerwona | część znanej kampanii oszustw (twarde ślady wspólne ze zgłoszonym materiałem) |

  Atrybuty pokazywane obok lampki: AI (zadeklarowane / wykryte / możliwe), osoba publiczna (twarz lub nazwisko),
  manipulacja, kampania, duplikaty. Pod lampką jest rozwijana lista czynników ryzyka z wagami i cytatami.
  Analityk może potwierdzić „to oszustwo” albo „to nie oszustwo”.
- **Ryzyko oszustwa**: wyjaśnialna ocena z czynnikami takimi jak twarz osoby publicznej w reklamie finansowej,
  obietnica łatwych pieniędzy, podszywanie się pod medium, adres strony na grafice, ocena Bielika i powiązanie
  ze zgłoszonymi kampaniami. Domeny z grafik i mowy oraz nazwy produktów (z LLM) łączą reklamy w kampanie,
  a ponowne zgłoszenia są oznaczane jako duplikaty.
- **Samouczący się detektor AI**: cechy CLIP ViT-L/14 i widmowe, uczony na korpusie startowym OpenFake (obrazy
  z ponad 50 generatorów i zdjęcia prawdziwe), materiałach, które same deklarują AI (podpis, etykieta platformy,
  metadane C2PA, IPTC lub SynthID), oraz ocenach analityka. Jego wynik liczy się dopiero wtedy, gdy przejdzie
  bramkę jakości: co najmniej 20 przykładów AI z 3 źródeł, AUC ≥ 0,80 na niewidzianych generatorach i najwyżej
  35% oflagowanych materiałów zbioru (ochrona przed przesunięciem domeny).
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

Opcjonalny LLM do analizy narracji (Bielik 11B v2.3 przez Ollama), na jeden z dwóch sposobów:

```bash
# A) Ollama na serwerze z GPU przez tunel SSH (tak działa demo)
ssh -N -L 127.0.0.1:21434:127.0.0.1:11434 <login>@<serwer>
# w .env: FK_OLLAMA_URL=http://host.docker.internal:21434

# B) Ollama lokalnie w kontenerze
docker compose --profile llm up -d
docker compose exec ollama ollama pull SpeakLeash/bielik-11b-v2.3-instruct:Q4_K_M
# w .env: FK_OLLAMA_URL=http://ollama:11434

docker compose up -d backend
```

Na stronie **System** widać, czy LLM jest osiągalny. Wynik każdego materiału jest cache'owany w `data/cache/llm/`.

Bez LLM analiza manipulacji działa na słownikach i regułach. Żadne dane nie są wysyłane do zewnętrznych usług.
Wzbogacanie online (RDAP i DNS) jest domyślnie wyłączone (`FK_ENABLE_ONLINE=1`, żeby je włączyć).

## Uruchomienie deweloperskie

```powershell
# backend (Python 3.12+)
cd backend
python -m venv .venv; .\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m app.cli models       # pobiera modele twarzy, CLIP i Whisper do data/models
.\.venv\Scripts\python -m app.cli import       # import data/raw + raport kampanii w konsoli
.\.venv\Scripts\python -m app.cli seed --shards 10   # korpus startowy OpenFake do data/ai_seed
.\.venv\Scripts\python -m app.cli train        # trening detektora AI + metryki bramki
.\.venv\Scripts\python -m app.cli reprocess    # ponowna ekstrakcja cech wszystkich materiałów
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

Korpus startowy detektora pobierany jest na żądanie (`app.cli seed` albo przycisk na stronie **System**) z
[OpenFake](https://huggingface.co/datasets/ComplexDataLab/OpenFake) (ComplexDataLab, CC-BY-NC-4.0, użycie
niekomercyjne) do `data/ai_seed/` i także nie jest częścią repozytorium.

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
| faster-whisper, CTranslate2, Whisper small | transkrypcja mowy z wideo | MIT / MIT / MIT |
| PyAV | dekodowanie audio | BSD-3 |
| CLIP ViT-L/14 (OpenAI, eksport ONNX Xenova) | cechy obrazu dla detektora AI | MIT |
| huggingface_hub, pyarrow | pobieranie modeli i korpusu startowego | Apache-2.0 |
| OpenFake (korpus startowy) | przykłady obrazów AI i prawdziwych | CC-BY-NC-4.0 |
| Angular, RxJS | interfejs | MIT / Apache-2.0 |
| Cytoscape.js | graf powiązań | MIT |
| nginx | serwowanie i proxy | BSD-2 |
| Ollama, Bielik 11B v2.3 (opcjonalnie) | lokalna analiza narracji | MIT / Apache-2.0 |
