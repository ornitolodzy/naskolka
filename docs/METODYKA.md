# Metodyka

## 1. Założenie

Oszuści rotują domeny, teksty i twarze, ale rzadko wymieniają całe zaplecze naraz. Ten sam piksel Facebooka, konto
w trackerze, szablon linku, plik JavaScript czy grafika przenoszą się między wariantami kampanii. Dlatego materiały
grupujemy nie po podobieństwie „na oko”, tylko po **wspólnych, rzadkich śladach technicznych**. Każdy ślad jest
osobnym dowodem, który da się pokazać analitykowi.

## 2. Ekstrakcja cech

Z każdego incydentu (HAR, HTML, MHTML, zrzuty, wideo, metadane) budujemy profil:

| Kanał | Przykładowe cechy |
| --- | --- |
| infrastruktura | domena docelowa, domeny pomocnicze, IP poza wspólnymi CDN, podsieć /24, nagłówek serwera, TLD, łańcuch przekierowań, opcjonalnie RDAP (rejestrar, NS) |
| śledzenie | Facebook Pixel, GTM, Google Ads, GA4, TikTok Pixel; **szablon linku** (klucze parametrów + kształt wartości, np. `utm_id=Mx20&utm_visit=UUID`); prefiks konta reklamowego, identyfikator landingu, klucz LP; telefon, e-mail; reklamodawca z biblioteki reklam |
| kod strony | SHA1 plików JS, CSS i obrazów (bez publicznych CDN), nazwy skryptów, klasy i identyfikatory szablonu, meta generator i site_name |
| treść | tytuł, nagłówki, tekst strony, tekst z OCR i transkrypt mowy z wideo (TF-IDF) |
| wizualne | SHA1 i hash percepcyjny (pHash) grafik i klatek wideo |
| twarze | embeddingi SFace twarzy wykrytych przez YuNet, dopasowanie do galerii osób publicznych |
| osoby i marki | osoby publiczne (słownik + twarze), marki i podmioty, pod które ktoś się podszywa |
| narracja | kategoria tematu (inwestycje, zdrowie, fałszywy artykuł, hazard, loteria, dopłaty) |

Szablon linku jest szczególnie cenny, bo przetrwa rotację domen: kolejna domena tej samej kampanii zwykle używa
identycznego zestawu parametrów trackera. Identyfikatorów kliknięć nie porównujemy dosłownie (są unikalne), tylko
ich format, który zdradza typ trackera.

**Mowa z wideo**: faster-whisper (model Whisper „small”, CPU int8, automatycznie CUDA float16, jeśli dostępna) daje
transkrypt z wykrytym językiem i znacznikami czasu. Transkrypt zasila kanał treści, wykrywanie deklaracji AI (źródło
`asr:<plik>`), osoby, marki, temat i analizę manipulacji. Wynik jest cache'owany w `data/cache/asr/`.

Dla każdego materiału liczymy też **kompletność danych** (czy jest log sieci, strona, obraz, wideo, metadane
reklamy) i ostrzeżenia. Brak HAR oznacza mniej dowodów i słabsze przypisanie, a nie brak powiązania.

## 3. Podobieństwo par: dowody

Każdy wspólny ślad \(e\) ma prawdopodobieństwo, że oba materiały pochodzą od tego samego operatora:

\[ p_e = \text{base}(\text{typ cechy}) \cdot \text{rarity}(df) \]

- `base` to siła typu cechy, od 0.97 (ta sama domena, ten sam piksel) do 0.02 (ten sam CDN). Pełna tabela jest
  w `backend/app/correlate.py` (`FEATURES`) i opisana po polsku w UI.
- `rarity` obniża wagę wartości częstych w zbiorze:
  \( 1 \) dla \( df \le 2 \), dalej \( (df-1)^{-1/2} \), a dodatkowo \( \times 0.3 \), gdy wartość występuje
  w ponad połowie materiałów. Wspólny adres Cloudflare czy słowo „inwestycja” niczego nie dowodzą.
- Treść: kosinus TF-IDF \(\ge 0.25\). Obrazy: identyczny SHA1 albo pHash o odległości \(\le 8\) bitów.
- Twarze: cosinus SFace \(\ge 0.45\). Jeśli oba materiały wymieniają tę samą osobę publiczną, dopasowanie
  trafia do kanału „osoby i marki”, bo ta sama celebryta to przesłanka tematyczna, a nie techniczna.

Łączenie dowodów:

1. noisy-OR w obrębie kanału: \( P_k = 1 - \prod_e (1 - p_e) \);
2. **limit kanału** (cap): infrastruktura i śledzenie 0.97, kod 0.90, treść i obrazy 0.92, twarze 0.75,
   osoby i marki 0.40, narracja 0.15;
3. noisy-OR między kanałami daje wynik pary \( S \in [0,1] \).

Kanały „miękkie” razem dają najwyżej \( 1 - 0.60 \cdot 0.85 = 0.49 \), czyli poniżej progu kampanii 0.55.
**Ta sama osoba publiczna i ten sam temat nigdy same nie scalą dwóch kampanii**, potrzebny jest co najmniej jeden
twardy ślad techniczny. Chroni to przed sklejaniem niezależnych oszustów, którzy podszywają się pod tę samą
celebrytkę.

Relacja pary: `duplikat` (prawie identyczne), `ta sama kampania` (\(S \ge 0.55\)), `podobna kampania`
(\(S \ge 0.30\)), `brak powiązania`.

## 4. Klastrowanie

- **Kampania**: spójna składowa grafu krawędzi \( S \ge 0.55 \). Składowe większe niż 6 węzłów dzielimy algorytmem
  Louvain (ważonym wynikiem), żeby pojedynczy wspólny zasób nie sklejał całych łańcuchów.
- **Rodzina kampanii**: kampanie połączone krawędzią \( 0.30 \le S < 0.55 \). To ten sam modus operandi albo
  prawdopodobnie ten sam operator przy słabszych dowodach.
- **Sygnatura kampanii**: ślady wspólne dla wielu członków, posortowane według wagi. Dla kampanii jednoelementowych
  pokazujemy ślady charakterystyczne, które pozwolą rozpoznać kolejne warianty.
- **Spójność**: średni wynik par wewnątrz kampanii.

Nowy materiał przechodzi tę samą ekstrakcję i dostaje jedną z decyzji:
`znana kampania` (najlepsze dopasowanie \(\ge 0.55\)), `pokrewna kampania / nowy wariant` (\(\ge 0.30\)) albo
`nowy wzorzec`. Dostaje też listę najbliższych materiałów z dowodami.

## 5. Lampki ryzyka

Lampka odpowiada na pytania z treści zadania: czy materiał wygląda na oszustwo i czy da się go przypisać do
wcześniej rozpoznanej kampanii, czy to nowy wzorzec.

| Poziom | Kolor | Warunek |
| --- | --- | --- |
| 0 | zielona | ryzyko oszustwa < 0.35 i brak powiązań ze zgłoszonymi oszustwami (albo analityk: „to nie oszustwo”) |
| 1 | żółta | **podejrzany**: ryzyko 0.35–0.65 albo techniczne podobieństwo (rodzina) do zgłoszonego oszustwa |
| 2 | pomarańczowa | **wysokie ryzyko, nowy wzorzec**: ryzyko \(\ge 0.65\) (albo analityk: „to oszustwo”), ale bez twardego powiązania ze znaną kampanią |
| 3 | czerwona | **część znanej kampanii oszustw**: ta sama kampania (twarde ślady techniczne) co materiał zgłoszony jako oszustwo, albo duplikat takiego materiału |

„Zgłoszone oszustwa” to materiały ze zbioru referencyjnego NASK oraz materiały potwierdzone przez analityka.
Każde potwierdzenie rozszerza bazę, więc kolejne warianty tej samej kampanii dostają czerwoną lampkę.

Obok lampki zawsze pokazujemy **atrybuty**, które nie zmieniają koloru wprost, tylko wchodzą do oceny ryzyka:
- **AI**: zadeklarowane (podpis, etykieta, C2PA, IPTC, SynthID), wykryte bez deklaracji (wiarygodny detektor,
  analityk, propagacja deklaracji z identycznego obrazu), możliwe (detektor w nauce) albo brak;
- **osoba publiczna**: z twarzy (SFace) lub tylko z nazwiska;
- **manipulacja**: wynik 0–1 z kategoriami i cytatami;
- **kampania** i **duplikaty**.

**Manipulacja**: słownik kategorii (presja czasu, sekret i spisek, nierealne zyski, cudowne leczenie, strach i szok,
fałszywy autorytet, przynęta „rządowej dopłaty”) z cytatami trafień, plus styl (wykrzykniki, wersaliki).

**Lokalny LLM (Bielik 11B v2.3 przez Ollama)** dostaje tekst strony, OCR i transkrypcję i zwraca ustrukturyzowany
JSON: streszczenie, schemat oszustwa z zamkniętej listy (fałszywa platforma inwestycyjna, fałszywy wywiad,
cudowny lek, fałszywa dopłata, loteria, hazard, sklep, phishing), nazwę produktu lub platformy, obietnicę, pod kogo
się podszywa, wezwanie do działania, techniki oraz oceny manipulacji i oszustwa. Wynik jest normalizowany
(wartości spoza listy, puste lub opisowe nazwy produktów są odrzucane) i cache'owany. Nazwa produktu staje się
cechą korelacji (kanał treści, 0.60), schemat cechą narracji (0.15), ocena oszustwa \(\ge 0.6\) czynnikiem ryzyka
(\(0.35 \cdot p\)), a ocena manipulacji jest mieszana z wynikiem słownikowym. Bez LLM wszystko działa na
słownikach i regułach.

**Kontekst manipulacji**: poza słownikiem liczą się dwa wzorce złożone. *Fałszywa rekomendacja*: twarz osoby
publicznej na obrazie (albo nazwa pliku) w materiale o inwestycjach, zdrowiu, hazardzie, loterii lub dopłatach.
*Podszywanie się pod medium*: marka redakcji (money.pl, Onet, TVN24…) w takim samym kontekście. Samo nazwisko
w tekście nie wystarcza, żeby zwykły news o biznesie nie był oznaczany. Kategorie łączymy noisy-OR z wagami
(np. nierealne zyski 0.35, fałszywa rekomendacja 0.45), a każde dodatkowe trafienie w kategorii podnosi jej wagę
o 15%.

**Ryzyko oszustwa** łączy wyjaśnialne czynniki metodą noisy-OR:

| Czynnik | Waga |
| --- | --- |
| wizerunek osoby publicznej (twarz) w reklamie finansowej lub zdrowotnej | 0.55 (samo nazwisko: 0.15–0.30) |
| obietnica łatwych pieniędzy | 0.30 + 0.07 za każde kolejne trafienie |
| podszywanie się pod medium | 0.30 |
| inne kategorie manipulacji | 0.6 × waga kategorii |
| adres strony podany w treści reklamy (np. napis na grafice) | 0.20 |
| ta sama kampania co zgłoszone oszustwa (twarde ślady) | 0.55 |
| techniczne podobieństwo do zgłoszonych oszustw | 0.30 |
| syntetyczny wizerunek osoby publicznej (AI + twarz) | 0.45 |
| treść AI bez deklaracji | 0.30 |
| ocena oszustwa przez LLM \(p \ge 0.6\) | \(0.35 \cdot p\) |
| materiał ze zbioru zgłoszonych oszustw | 0.40 |

Poziomy: wysokie \(\ge 0.65\), podwyższone \(\ge 0.35\), niskie poniżej. Każdy czynnik jest pokazany w UI
z cytatem lub dowodem.

**Domeny z treści**: domeny wypisane na grafikach (OCR), w tekście i w mowie stają się cechą korelacji. Ta sama
domena w dwóch reklamach albo domena z grafiki jednej reklamy będąca domeną strony innego materiału to silny dowód
(0.90). Pomijamy znane serwisy (media, platformy społecznościowe), a serwisy fact-checkingowe i archiwa (Demagog,
Konkret24, archive.org) nie są w ogóle traktowane jako infrastruktura, bo tylko hostują zrzut oszustwa.

**Duplikaty**: ponowne zgłoszenie tego samego adresu albo identycznych plików jest oznaczane jako duplikat,
a nie jako „kampania” złożona z kopii jednego materiału.

## 6. Samouczący się detektor AI

Idea: materiały, które **same deklarują AI**, są darmowymi przykładami pozytywnymi. Model uczy się z nich, jak
wyglądają treści AI w tym strumieniu, i wskazuje podobne materiały bez deklaracji.

- **Cechy obrazu**: embedding CLIP ViT-L/14 (768 wymiarów, ONNX, lokalnie) oraz 23 cechy widmowe: 16-przedziałowy
  radialny profil widma Fouriera, udział wysokich częstotliwości, odchylenie i kurtoza rezyduum szumu, wariancja
  laplasjanu, średnia i rozrzut nasycenia oraz jasności. Przed liczeniem cech maskujemy ramki OCR z tekstem
  deklaracji, żeby model nie nauczył się czytać podpisu „wygenerowano przez AI”.
- **Normalizacja „jak w sieci”**: każdy obraz (korpus i zbiór) jest skalowany do maks. 1024 px i przepuszczany przez
  JPEG q85. Bez tego model uczy się skrótu „PNG z generatora vs JPEG z aparatu”, a nie cech generowania.
- **Korpus startowy**: OpenFake (CC-BY-NC-4.0) – obrazy z ponad 50 generatorów (pozytywy, źródło `seed:ai/<generator>`)
  i zdjęcia prawdziwe (negatywy). Pobierany na żądanie do `data/ai_seed/`.
- **Etykiety na poziomie obrazu**: pozytywny jest obraz, którego dotyczy deklaracja (metadane lub OCR tego pliku).
  Deklaracja tekstowa na stronie oznacza wszystkie obrazy materiału. Analityk może oznaczyć materiał jako AI albo
  nie AI.
- **Tryb uczenia**: przy co najmniej 20 negatywach (korpus albo oceny „to nie AI”) regresja logistyczna uczy się
  nadzorowanie AI vs nie-AI, a materiały nieoznaczone służą tylko do kontroli. Bez negatywów działa uczenie PU
  (positive-unlabeled, Elkan i Noto 2008): brak deklaracji to „nieoznaczone”, a wynik kalibruje
  \( c = P(s{=}1 \mid y{=}1) \).
- **Uczciwa walidacja**: AUC liczone w GroupKFold, gdzie pozytywy są grupowane po źródle (generatorze albo
  materiale). Model ocenia więc generatory, których nie widział w treningu.
- **Bramka wiarygodności**: wynik detektora podnosi lampkę dopiero, gdy jednocześnie: co najmniej 20 pozytywów
  z co najmniej 3 źródeł, AUC na niewidzianych źródłach \(\ge 0.80\) oraz najwyżej 35% obrazów zbioru z wynikiem
  \(\ge 0.60\). Ostatni warunek wykrywa przesunięcie domeny: model, który oznacza większość zbioru jako AI, nie
  rozróżnia AI od zrzutów ekranu, tylko „korpus” od „zbioru”. Wcześniej wynik jest tylko informacyjny.
- **Stan na zbiorze demonstracyjnym**: 370 pozytywów (53 generatory), 424 negatywy, AUC 0,85 na niewidzianych
  generatorach, ale 73% obrazów zbioru oflagowanych (zrzuty ekranu, klatki wideo, grafiki stron to inna domena
  niż zdjęcia z korpusu). Bramka słusznie blokuje lampki. Lekarstwem są negatywy z domeny: oceny analityka „to nie
  AI” na kilku materiałach albo legalne zrzuty reklam i stron dodane do korpusu.
- **Propagacja deklaracji**: jeśli obraz jest percepcyjnie identyczny (pHash \(\le 6\) bitów) z obrazem
  zadeklarowanym jako AI w innym materiale, a tu deklaracji brak, to ktoś ją usunął. Lampka czerwona z dowodem
  wskazującym źródło.

Detektor douczamy przyciskiem na stronie System albo `POST /api/v1/ai/train`. Model zapisuje się w
`data/models/ai_head.json`.

## 7. Twarze

YuNet wykrywa twarze na zrzutach, grafikach strony i klatkach wideo (12 klatek z nagrania). SFace liczy embeddingi.
Galerię osób publicznych budujemy z dwóch źródeł:
- zdjęć wzorcowych w `backend/reference/faces/<slug>/`;
- automatycznie z grafik w zbiorze, których nazwa pliku wskazuje osobę (np. `brzoska-avatar.jpg`).

Dopasowanie wymaga kosinusa \(\ge 0.40\), czyli nieco ostrzej niż zalecane przez OpenCV 0.363, żeby unikać fałszywych
tożsamości.

## 8. Ograniczenia i dalszy rozwój

- Detektor AI wymaga negatywów z domeny (zrzuty reklam i stron bez AI), żeby przejść bramkę na realnym strumieniu.
  Kolejnym krokiem może być detekcja wideo deepfake (twarz, synchronizacja ust z transkryptem).
- ASR na CPU przetwarza ok. 3 minuty nagrania w kilkadziesiąt sekund. Na GPU NVIDIA warto ustawić
  `FK_ASR_MODEL=large-v3`.
- RDAP, DNS i pasywne DNS wymagają dostępu do sieci (`FK_ENABLE_ONLINE=1`). Offline korzystamy z tego, co zapisano
  w HAR.
- Progi (0.55 i 0.30) dobrano na zbiorze demonstracyjnym i warto je skalibrować na większym zbiorze z etykietami
  kampanii od analityków.
