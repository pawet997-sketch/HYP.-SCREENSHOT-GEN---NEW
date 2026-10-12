# HyperMesh Auto-Screenshot & Quality Reporting Tool (Python)

Makro do HyperMesh (Altair HyperWorks 2021+), które:

* zapamiętuje dowolną liczbę **widoków** (kamera + miniatura + opcjonalnie nagrany układ wyświetlania),
* obok każdej miniatury pozwala wybrać **kontrole jakości siatki** (Aspect Ratio, Jacobian, Skewness, Warpage, …)
  z **własną wartością graniczną** dla każdego widoku; HyperMesh pokazuje wtedy swoje natywne wyróżnienie / legendę,
  a opcja **⊘** zostawia na ekranie wyłącznie elementy poza limitem,
* robi zrzuty i **sam segreguje je do folderów**: `<Metryka>/` (pliki z prefiksem metryki, np.
  `Aspect_Ratio_REF_Widok_1.jpg`) albo `<NazwaWidoku>/` dla zrzutów bez metryki,
* buduje **prezentację PowerPoint (.pptx)** z interaktywnym podglądem slajdu w GUI (sloty na zdjęcia można
  przeciągać i skalować; szybkie układy symetryczne *Lewa / Prawa* i *Góra / Dół*; zapis / odczyt układu),
* obsługuje **tryb porównawczy REF vs INF**: faza REF (model referencyjny) i faza INF (model influencyjny)
  trafiają do tej samej prezentacji, w z góry określonych miejscach na slajdach.

Jest to całkowicie przepisana w Pythonie wersja makra Tcl `Hypermesh_screenshots-42_VF.tcl`
(oryginał pozostawiono w `legacy/`).

---

## Wymagania

| Składnik | Uwagi |
|---|---|
| HyperMesh / HyperWorks **2021 lub nowszy** | potrzebny jest wbudowany interpreter Pythona (moduł `hm`) |
| Python 3.8+ | ten, który uruchamia HyperMesh |
| **PySide6 / PySide2** (lub PyQt6 / PyQt5) | GUI; HyperWorks zwykle dostarcza PySide w swoim Pythonie. Jeśli nie: `"<HW>\hw\python\python.exe" -m pip install PySide6` |
| Pillow (opcjonalnie) | lepsze miniatury; bez niego miniatury powstają przez Qt |

Eksport PPTX **nie wymaga** żadnych dodatkowych bibliotek (własny, lekki zapis OOXML).

## Uruchomienie

**W HyperMesh:** `File → Run → Python script…` (lub `Tools → Run Python Script`) i wskaż plik
**`hm_screenshot_tool.py`**. Folder `hm_shots/` musi leżeć obok tego pliku. Okno makra działa równolegle
z oknem HyperMesh (nie blokuje go).

**Poza HyperMesh (tryb offline / demo):**

```bash
python hm_screenshot_tool.py            # offline: edytor układu, sesje, eksport PPTX z istniejących zdjęć
python hm_screenshot_tool.py --demo     # demo: symulowane zrzuty – pełny przebieg bez HyperMesh
python -m hm_shots --lang=en --dark     # opcje: język, ciemny motyw, plik sesji .hmshots.json
```

## Przebieg pracy

1. Ustaw model w oknie graficznym HyperMesh (kamera, sekcje, maskowanie).
2. **„● Zapamiętaj widok”** lub klawisz **1** → kafelek z miniaturą. Powtórz dla kolejnych widoków.
3. Na kafelku zaznacz rodzaje zrzutów: **Zwykły zrzut** i/lub **metryki**; ustaw próg; **⊘** = tylko elementy poza limitem.
4. Zakładka **Zapis**: folder główny, format, wzorce nazw (`{metric}_{phase}_{view}`), tło, jakość.
5. **„▶ Generuj zrzuty”** (klawisz **K**). Zrzuty lądują w folderach wg metryk / widoków, PPTX aktualizuje się automatycznie.

### Tryb porównawczy REF / INF

1. Włącz **„Porównanie REF / INF”** w nagłówku, faza **REF**: widoki + metryki → *Generuj*.
2. **Sesja → Zapisz** (działa też autozapis w `~/.hm_shots/`).
3. Wczytaj model influencyjny (teraz albo kiedy indziej), **Sesja → Wczytaj sesję…**, przełącz fazę na **INF** → *Generuj*.
   Makro odtwarza te same widoki (kamera + nagrany układ) i te same metryki z tymi samymi progami; zdjęcia INF
   trafiają do slotów INF *tej samej* prezentacji. Puste sloty INF są w PPTX kreskowanymi „miejscami docelowymi”.

### Prezentacja i układ slajdu (zakładka *Prezentacja*)

* Interaktywny podgląd: **przeciągnij** slot, chwyć **krawędź / róg**, aby zmienić rozmiar; strzałki – precyzyjne
  przesuwanie, Delete – usuwanie; siatka przyciągania 1 / 2,5 / 5 %.
* Szybkie układy symetryczne: **Lewa / Prawa**, **Góra / Dół** (liczba par na slajd), **Lustro L/P**, **Lustro G/D**,
  zamiana ról, wyrównanie rozmiarów, dodawanie slotów REF / INF / dowolnych.
* Podgląd pokazuje **prawdziwe slajdy** (wykonane zrzuty, tytuły, podpisy); przełączanie slajdów ◀ ▶.
* **Zapisz układ… / Wczytaj układ…** – układ (`*.hmlayout.json`) można używać wielokrotnie.
* Opcje: tytuły slajdów, podpisy REF/INF, slajd tytułowy, format 16:9 / 4:3, tryb dopasowania zdjęcia (dopasuj / wypełnij).

### Metryki (zakładka *Metryki*)

Każda metryka ma **szablon komend HyperMesh** z symbolem `{thr}` (wartość graniczna), np.

```
*createmark elements 1 "displayed"
*elementtestaspect elements 1 {thr} 2 2 0 0 0 0 0
```

Używane są natywne komendy panelu *Check Elements*, więc HyperMesh sam rysuje wyróżnienie i legendę.
Sekcja *„tylko elementy poza limitem”* maskuje elementy spełniające kryterium, sekcja *porządkująca*
przywraca ekran po zrzucie.

> **Ważne:** składnia `*elementtest*` i komend maskowania różni się między wersjami HyperMesh. Jeśli domyślny
> szablon nie działa w Twojej wersji, użyj **„● Nagraj z HyperMesh…”**: wykonaj kontrolę ręcznie
> (np. *Tool → Check Elems → aspect → check / display*), a nowe linie z `command.tcl` staną się szablonem –
> wpisana wartość graniczna zostanie automatycznie zastąpiona przez `{thr}`. Szablony można też edytować
> ręcznie i dodawać własne metryki; wszystko zapisuje się w sesji.

### Układ wyświetlania (sekcje, style, maskowanie)

**„● Nagrywaj układ”** → zmiany w HyperMesh → **„Zapamiętaj widok”**: komendy z pliku komend (`command.tcl`)
zostają dołączone do widoku (znacznik ⚙) i są odtwarzane przed zrzutem w kolejnym modelu (faza INF).

## Struktura plików

```
hm_screenshot_tool.py      – launcher (uruchamiany z HyperMesh)
hm_shots/
  hm_bridge.py             – adapter do HyperMesh (hw.evalTcl / hm.Model, *viewset, *jpegfilenamed, hwi…), tryb offline/demo
  views.py                 – widoki (kamera, miniatura, układ, metryki per widok)
  quality.py               – rejestr metryk, szablony komend, uczenie z command.tcl
  naming.py                – nazwy plików i segregacja do folderów
  layout.py                – układ slajdu (sloty REF/INF, presety, lustro, JSON)
  project.py               – sesja (.hmshots.json), plan slajdów REF/INF
  capture.py               – pipeline generowania zrzutów
  pptx_writer.py           – zapis .pptx bez zależności
  gui/                     – interfejs Qt (PySide6/PySide2): okno główne, kafelki, edytor układu, metryki
  tests/                   – testy (python -m unittest discover -s hm_shots/tests -t .)
legacy/                    – oryginalne makro Tcl
```

## Uwagi

* Widok pobierany jest komendą `hm_winfo viewmatrix`, ustawiany przez `*viewset`; zrzut przez `*jpegfilenamed`
  / `*pngfilenamed` / `*bmpfilenamed` (z fallbackiem `hm_capturescreentofile` i API `hwi` dla HyperWorks Desktop).
  Komendy wykonywane są przez `hw.evalTcl` (lub inny dostępny most Tcl) albo bezpośrednio przez `hm.Model`.
* Sesja zawiera miniatury (base64), więc plik sesji można przenosić między komputerami.
* Testy: `python -m unittest discover -s hm_shots/tests -t .` (test GUI wymaga PySide i działa offscreen).

---

## English summary

Python rewrite of the HyperMesh screenshot macro. Run `hm_screenshot_tool.py` from HyperMesh
(*File → Run → Python script*) or standalone (`--demo` simulates captures). Remember views (key **1**), pick quality
checks with per-view limits on each tile (native HyperMesh highlighting / legend, **⊘** = only elements outside the
limit), generate (key **K**) – files are sorted into `<Metric>/` or `<View>/` folders with metric prefixes and
the PPTX deck is updated. REF / INF comparison: run the REF phase, save the session, load the INF model, load the
session, switch to INF and generate – the same views and metrics land in the INF slots of the same deck. The
*Presentation* tab has an interactive slide editor (drag / resize slots, Left/Right & Top/Bottom presets, mirror,
save / load layouts). Metric command templates (`{thr}` placeholder) are editable and can be learned from
`command.tcl` (*Record from HyperMesh…*) when a HyperMesh release uses a different syntax.
