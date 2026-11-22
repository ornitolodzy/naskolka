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
| treść | tytuł, nagłówki, tekst strony i tekst z OCR (TF-IDF) |
| wizualne | SHA1 i hash percepcyjny (pHash) grafik i klatek wideo |
| twarze | embeddingi SFace twarzy wykrytych przez YuNet, dopasowanie do galerii osób publicznych |
| osoby i marki | osoby publiczne (słownik + twarze), marki i podmioty, pod które ktoś się podszywa |
| narracja | kategoria tematu (inwestycje, zdrowie, fałszywy artykuł, hazard, loteria, dopłaty) |

Szablon linku jest szczególnie cenny, bo przetrwa rotację domen: kolejna domena tej samej kampanii zwykle używa
identycznego zestawu parametrów trackera. Identyfikatorów kliknięć nie porównujemy dosłownie (są unikalne), tylko
ich format, który zdradza typ trackera.

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

Lampki to warstwa niezależna od kampanii: oceniają pojedynczy materiał.

| Poziom | Kolor | Warunek |
| --- | --- | --- |
| 0 | zielona | brak sygnału AI |
| 1 | żółta | **zadeklarowano AI**: podpis lub etykieta w tekście lub OCR, metadane C2PA/JUMBF, IPTC `trainedAlgorithmicMedia`, SynthID, EXIF Software z generatorem |
| 2 | czerwona | **AI wykryte bez deklaracji**: wiarygodny detektor \(\ge 0.60\), ocena analityka albo propagacja deklaracji |
| 3 | fioletowa | poziom 1 lub 2 **i** osoba publiczna (twarz z galerii albo nazwisko w treści) |
| 4 | czarna | poziom 3 **i** manipulacyjny przekaz (wynik \(\ge 0.40\)) |

Poziomy 3 i 4 wymagają sygnału AI, zgodnie z założeniem: wizerunek osoby publicznej w treści syntetycznej to
podszycie. Wskaźniki (osoba publiczna, manipulacja) są raportowane zawsze, także przy niskiej lampce.

**Manipulacja**: słownik kategorii (presja czasu, sekret i spisek, nierealne zyski, cudowne leczenie, strach i szok,
fałszywy autorytet) z cytatami trafień, plus styl (wykrzykniki, wersaliki). Wynik łączy szerokość (ile kategorii),
gęstość i styl. Jeśli skonfigurowano lokalny LLM (Bielik przez Ollama), jego ocena jest mieszana z wynikiem
słownikowym, a uzasadnienie i techniki trafiają do UI.

## 6. Samouczący się detektor AI

Idea: materiały, które **same deklarują AI**, są darmowymi przykładami pozytywnymi. Model uczy się z nich, jak
wyglądają treści AI w tym strumieniu, i wskazuje podobne materiały bez deklaracji.

- **Cechy obrazu** (23 wymiary): 16-przedziałowy radialny profil widma Fouriera, udział wysokich częstotliwości,
  odchylenie i kurtoza rezyduum szumu (obraz minus filtr medianowy), wariancja laplasjanu (ostrość i gładkość),
  średnia i rozrzut nasycenia oraz jasności. Przed liczeniem cech maskujemy
  ramki OCR z tekstem deklaracji, żeby model nie nauczył się czytać podpisu „wygenerowano przez AI”.
- **Etykiety na poziomie obrazu**: pozytywny jest obraz, którego dotyczy deklaracja (metadane lub OCR tego pliku).
  Deklaracja tekstowa na stronie oznacza wszystkie obrazy materiału. Analityk może oznaczyć materiał jako AI albo
  nie AI.
- **Uczenie PU** (positive-unlabeled, Elkan i Noto 2008): brak deklaracji to nie „prawdziwe”, tylko „nieoznaczone”.
  Regresja logistyczna uczy się rozróżniać oznaczone od nieoznaczonych, a wynik jest kalibrowany przez
  \( c = P(s{=}1 \mid y{=}1) \).
- **Bramka wiarygodności**: wynik detektora podnosi lampkę dopiero przy co najmniej 20 pozytywach z co najmniej
  3 różnych materiałów. Wcześniej jest tylko informacyjny („detektor w trakcie nauki”). Zapobiega to sytuacji,
  w której model wytrenowany na jednej kampanii oznacza wszystko na czerwono.
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

- Brak transkrypcji mowy (ASR). Wideo bez tekstu na ekranie wnosi tylko twarze i obrazy. Naturalnym rozszerzeniem
  jest faster-whisper, którego transkrypt trafi do kanału treści i analizy manipulacji.
- Detektor AI na cechach spektralnych to baseline. Przy większej liczbie deklaracji można podmienić głowicę na
  embeddingi CLIP lub DINOv2 bez zmiany procesu etykietowania.
- RDAP, DNS i pasywne DNS wymagają dostępu do sieci (`FK_ENABLE_ONLINE=1`). Offline korzystamy z tego, co zapisano
  w HAR.
- Progi (0.55 i 0.30) dobrano na zbiorze demonstracyjnym i warto je skalibrować na większym zbiorze z etykietami
  kampanii od analityków.
