System Identyfikacji Wizualnej (SIW) — Projekt „Naskółka”

Projekt: Naskółka

Zleceniodawca / Instytucja: NASK (Naukowa i Akademicka Sieć Komputerowa – Państwowy Instytut Badawczy)

Dokument: System Identyfikacji Wizualnej (SIW)

Wersja: 1.0 (Draft)

1. Kontekst projektu i Filozofia wizualna

Dokument definiuje uniwersalne standardy wizualne dla systemu Naskółka, realizowanego dla instytutu NASK. System został zaprojektowany w sposób modułowy — określa fundamenty estetyczne, kolorystykę, typografię oraz geometrię komponentów niezależnie od docelowej architektury informacji i funkcji konkretnego modułu aplikacji.

Kluczowe filary estetyczne

Metafora Naskółki (Hirundo rustica): Nazwa i tożsamość wizualna nawiązują do jaskółki dymówki — symbolu szybkości, precyzji, zwinności i niezawodnej nawigacji w przestrzeni informacyjnej.

Ergonomia i stonowany kontrast: Zamiast agresywnego, niebieskiego światła i jałowej bieli, interfejs wykorzystuje naturalny szlachetny odcień kremowobiały (#F4EBE1) wsparty głębokim granatowoczarnym (#0F1626).

Koncentryczna geometria (Nested Radii): Interfejs rezygnuje ze skrajnych ovali (pill-shapes) na rzecz miękko zaokrąglonych prostokątów. Kluczową zasadą jest spójność promieni zaokrąglenia komponentów zagnieżdżonych względem swoich kontenerów.

Precyzyjny akcent: Akcent w kolorze ceglastoczerwonym (#A33B24) służy wyłącznie do ściśle zdefiniowanych akcji (CTA), stanów aktywnych i kluczowych komunikatów, unikając przebodźcowania użytkownika.

2. Logo i Sygnet

Znak identyfikacyjny projektu Naskółka harmonijnie łączy instytucjonalny profil NASK z motywem zwinnego ptaka.

Logotyp: Zapis nazwy naskółka (małymi literami) w nowoczesnym, geometrycznym kroju bezszeryfowym.

Sygnet: Stylizowany, płaski i dynamiczny motyw skrzydła lub rozwidlonego ogona jaskółki. Posiada możliwość stosowania niezależnie jako favicon, ikona aplikacji mobilnej lub avatar.

Warianty kolorystyczne:

Wariant podstawowy (Jasne tło): Logotyp w kolorze #0F1626 z akcentem w sygnecie #A33B24.

Wariant kontrowy (Ciemne tło): Logotyp w kolorze #F4EBE1 z akcentem #A33B24.

Pole ochronne: Minimalny odstęp wokół znaku odpowiada wysokości litery „a” w logotypie.

3. Paleta Kolorystyczna

Rdzeń palety stanowią cztery główne barwy upierzenia jaskółki dymówki, uzupełnione o funkcjonalne odcienie interfejsu użytkownika (zgodne z WCAG 2.1 AA).

Barwy Podstawowe (Brand Core)

Nazwa barwy

Kod Hex

RGB

Rola w interfejsie

Granatowoczarny

#0F1626

15, 22, 38

Kolor marki, nagłówki, panele nawigacyjne, elementy strukturalne.

Ceglastoczerwony

#A33B24

163, 59, 36

Akcent główny (CTA), aktywne stany, przyciski akcji, powiadomienia.

Kremowobiały

#F4EBE1

244, 235, 225

Główne tło aplikacji (canvas), tekst w kontrze na ciemnych elementach.

Ciemnoszary / Czarny

#252321

37, 35, 33

Podstawowy kolor tekstu (body), ikony, kontrastowe elementy.

Barwy Rozszerzone (UI Tokens)

Nazwa barwy

Kod Hex

RGB

Rola w interfejsie

Jasny krem (Powierzchnia)

#FAF6F0

250, 246, 240

Tło kart, sekcji, pól formularzy, okien dialogowych.

Ciepły popiel

#D8CFC5

216, 207, 197

Subtelne ramki, linie podziału (dividers), stany nieaktywne.

Grafitowy

#5E5A56

94, 90, 86

Tekst pomocniczy, metadane, etykiety formularzy, podpowiedzi.

Ciemna cegła (Hover)

#872F1C

135, 47, 28

Stan najechania / kliknięcia dla głównych przycisków akcji.

Stalowy granat (Hover)

#1D2A44

29, 42, 68

Stan najechania dla ciemnych elementów nawigacyjnych.

4. Geometria i Zasady Ułóżenia UI

Zasada Koncentrycznych Zaokrągleń (Concentric Border Radius)

W projekcie Naskółka rezygnujemy ze sztywnych owali na rzecz harmonijnie dopasowanych zaokrągleń zagnieżdżonych. Aby uniknąć wizualnego zgrzytu („załamania” wizualnego krawędzi), promień zaokrąglenia elementu zewnętrznego ($R_{\text{zewnętrzne}}$) musi być równy sumie promienia elementu wewnętrznego ($R_{\text{wewnętrzne}}$) oraz wewnętrznego odstępu ($\text{Padding}$):

$$R_{\text{zewnętrzne}} = R_{\text{wewnętrzne}} + \text{Padding}$$

Skala Zaokrągleń (Radius Tokens):

XS (6px): Najmniejsze elementy – tagi, znaczniki (badges), checkboxy, wskaźniki.

SM (10px): Przycisk wewnątrz karty, pole do wpisywania tekstu, pojedynczy element listy.

MD (16px): Kontener wewnętrzny, mniejsza karta, popover, notification toast.

LG (22px): Główna karta / moduł z paddingiem 12px zawierająca przyciski 10px ($10\text{px} + 12\text{px} = 22\text{px}$).

XL (28px): Okna dialogowe (modale), główne kontenere sekcji z paddingiem 12px wokół kart 16px ($16\text{px} + 12\text{px} = 28\text{px}$).

5. Typografia

Kroje Pisma (Open Source)

Główny krój interfejsu (UI & Body): Plus Jakarta Sans lub Inter (wysoka czytelność, świetna mikrotypografia i wsparcie dla języka polskiego).

Krój danych technicznych: JetBrains Mono (dane liczbowe, logi, kody, ID transakcji/zgłoszeń).

Hierarchy & Scale

H1 / Tytuł Ekranu: 32px / Bold / line-height: 1.2

H2 / Tytuł Sekcji: 24px / SemiBold / line-height: 1.3

H3 / Tytuł Karty: 18px / SemiBold / line-height: 1.4

Body / Tekst Główny: 15px / Regular / line-height: 1.6

Interaktywne (Przyciski / Tabele): 14px / Medium

Etykiety i Metadane: 12px–13px / Regular / line-height: 1.4

6. Specyfikacja Techniczna (CSS Design Tokens)

/* ==========================================================================
   NASKÓŁKA UI DESIGN TOKENS
   Paleta: Jaskółka Dymówka (Hirundo rustica)
   ========================================================================== */

:root {
  /* --- Brand Core Palette --- */
  --naskolka-navy-black: #0F1626;
  --naskolka-brick-red: #A33B24;
  --naskolka-cream-white: #F4EBE1;
  --naskolka-charcoal: #252321;

  /* --- Functional UI Tokens --- */
  --naskolka-bg-canvas: var(--naskolka-cream-white);
  --naskolka-bg-surface: #FAF6F0;
  --naskolka-border-subtle: #D8CFC5;

  --naskolka-text-primary: var(--naskolka-charcoal);
  --naskolka-text-heading: var(--naskolka-navy-black);
  --naskolka-text-secondary: #5E5A56;
  --naskolka-text-on-dark: var(--naskolka-cream-white);

  --naskolka-accent-primary: var(--naskolka-brick-red);
  --naskolka-accent-primary-hover: #872F1C;
  --naskolka-accent-secondary: var(--naskolka-navy-black);
  --naskolka-accent-secondary-hover: #1D2A44;

  /* --- Geometry & Spacing --- */
  --spacing-inner-card: 12px;
  --spacing-inner-modal: 16px;

  --radius-xs: 6px;
  --radius-sm: 10px;
  --radius-md: 16px;
  
  /* Matematycznie spójne promienie zewnętrzne (Concentric Radii) */
  --radius-lg: calc(var(--radius-sm) + var(--spacing-inner-card)); /* 22px */
  --radius-xl: calc(var(--radius-md) + var(--spacing-inner-modal)); /* 32px */

  /* --- Typography --- */
  --font-sans: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

/* --- Przykłady Dopasowania Komponentów Zagnieżdżonych --- */

/* Karta Zewnętrzna */
.naskolka-card {
  background-color: var(--naskolka-bg-surface);
  border: 1px solid var(--naskolka-border-subtle);
  border-radius: var(--radius-lg); /* 22px */
  padding: var(--spacing-inner-card); /* 12px */
  color: var(--naskolka-text-primary);
  font-family: var(--font-sans);
}

/* Przycisk Wewnątrz Karty */
.naskolka-button-primary {
  background-color: var(--naskolka-accent-primary);
  color: var(--naskolka-text-on-dark);
  border-radius: var(--radius-sm); /* 10px - idealne dopasowanie do promienia 22px z paddingiem 12px */
  border: none;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.1s ease;
}

.naskolka-button-primary:hover {
  background-color: var(--naskolka-accent-primary-hover);
}

/* Pole tekstowe (Input) */
.naskolka-input {
  background-color: var(--naskolka-bg-canvas);
  border: 1px solid var(--naskolka-border-subtle);
  border-radius: var(--radius-sm); /* 10px */
  padding: 10px 14px;
  color: var(--naskolka-text-primary);
  font-family: var(--font-sans);
  font-size: 14px;
  outline: none;
}

.naskolka-input:focus {
  border-color: var(--naskolka-accent-primary);
}
