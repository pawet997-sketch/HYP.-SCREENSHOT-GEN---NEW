# -*- coding: utf-8 -*-
"""Help content (HTML) for the in-app help dialog."""
from __future__ import annotations

from ..i18n import get_lang

_PL = """
<h2>HyperMesh – zrzuty ekranu i raport jakości siatki</h2>
<h3>Przebieg pracy</h3>
<ol>
<li><b>Ustaw model</b> w oknie graficznym HyperMesh (kamera, sekcje, maskowanie).</li>
<li>Kliknij <b>„Zapamiętaj widok”</b> lub naciśnij <b>1</b> – powstaje kafelek z miniaturą. Powtórz dla kolejnych widoków.</li>
<li>Na każdym kafelku zaznacz <b>rodzaje zrzutów</b>: „Zwykły zrzut” i/lub metryki jakości (Aspect Ratio, Jacobian, Skewness…).
    Dla każdej metryki ustaw <b>wartość graniczną</b>; przełącznik <b>⊘</b> pokazuje wyłącznie elementy poza limitem.</li>
<li>W zakładce <b>Zapis</b> wskaż folder. Zrzuty z metryką trafiają do folderu <code>&lt;Metryka&gt;/</code>
    z prefiksem metryki, np. <code>Aspect_Ratio_REF_Widok_1.jpg</code>; zrzuty bez metryki do folderu <code>&lt;Widok&gt;/</code>.</li>
<li>Kliknij <b>„Generuj zrzuty”</b> (klawisz <b>K</b>). Prezentacja PPTX jest aktualizowana automatycznie.</li>
</ol>
<h3>Tryb porównawczy REF / INF</h3>
<ul>
<li><b>Faza REF</b>: zapamiętaj widoki, wybierz metryki, generuj – zdjęcia trafiają do slotów REF slajdów.</li>
<li>Zapisz sesję (<b>Sesja → Zapisz</b>; działa też autozapis).</li>
<li>Wczytaj model influencyjny (w tym samym HyperMesh lub kiedy indziej), wczytaj sesję, przełącz fazę na <b>INF</b> i generuj.
    Makro odtwarza te same widoki (kamera + nagrany układ) i te same metryki, a zdjęcia INF trafiają do slotów INF <i>tej samej</i> prezentacji.</li>
</ul>
<h3>Prezentacja i układ slajdu</h3>
<ul>
<li>Zakładka <b>Prezentacja</b> zawiera interaktywny podgląd slajdu: sloty można <b>przeciągać</b> i <b>zmieniać ich rozmiar</b>
    (krawędź / róg), nadawać role REF / INF, dodawać i usuwać.</li>
<li>Szybkie układy symetryczne: <b>Lewa / Prawa</b> oraz <b>Góra / Dół</b> (liczba par na slajd do wyboru), <b>Lustro</b> odbija sloty REF na stronę INF.</li>
<li>Podgląd pokazuje rzeczywisty slajd z wykonanymi zrzutami; puste miejsca INF są kreskowane także w pliku PPTX.</li>
<li><b>Zapisz układ… / Wczytaj układ…</b> – układ (JSON) można używać wielokrotnie w kolejnych sesjach.</li>
</ul>
<h3>Metryki (zakładka „Metryki”)</h3>
<ul>
<li>Każda metryka ma <b>szablon komend</b> HyperMesh z symbolem <code>{thr}</code> (wartość graniczna) – używane są natywne komendy
    panelu Check Elements, więc HyperMesh rysuje własne wyróżnienie i legendę.</li>
<li>Jeśli składnia w Twojej wersji HyperMesh jest inna: <b>„Nagraj z HyperMesh…”</b> – wykonaj kontrolę ręcznie, a komendy z
    <code>command.tcl</code> staną się szablonem. Można też edytować je ręcznie i dodawać własne metryki.</li>
<li>Sekcja „tylko elementy poza limitem” maskuje elementy spełniające kryterium; „porządkujące” przywracają widok po zrzucie.</li>
</ul>
<h3>Układ wyświetlania (sekcje, style, maskowanie)</h3>
<p>Kliknij <b>„● Nagrywaj układ”</b>, wykonaj zmiany w HyperMesh, potem „Zapamiętaj widok” – komendy z pliku komend zostaną dołączone do widoku (⚙)
i odtworzone przed zrzutem w kolejnym modelu.</p>
<h3>Skróty</h3>
<p><b>1</b> – zapamiętaj widok, <b>K</b> – generuj, <b>Ctrl+S</b> – zapisz sesję. Kliknięcie miniatury ustawia widok w HyperMesh.</p>
"""

_EN = """
<h2>HyperMesh – screenshots & mesh quality report</h2>
<h3>Workflow</h3>
<ol>
<li><b>Set up the model</b> in the HyperMesh graphics window (camera, sections, masking).</li>
<li>Click <b>“Remember view”</b> or press <b>1</b> – a tile with a thumbnail appears. Repeat for further views.</li>
<li>On each tile tick the <b>shot kinds</b>: “Plain screenshot” and/or quality metrics (Aspect Ratio, Jacobian, Skewness…).
    Set a <b>limit</b> per metric; the <b>⊘</b> toggle shows only the elements outside the limit.</li>
<li>Choose the folder in the <b>Output</b> tab. Metric shots go to <code>&lt;Metric&gt;/</code> with the metric prefix,
    e.g. <code>Aspect_Ratio_REF_View_1.jpg</code>; plain shots go to <code>&lt;View&gt;/</code>.</li>
<li>Click <b>“Generate screenshots”</b> (key <b>K</b>). The PPTX deck is updated automatically.</li>
</ol>
<h3>REF / INF comparison mode</h3>
<ul>
<li><b>REF phase</b>: remember views, pick metrics, generate – pictures land in the REF slots of the slides.</li>
<li>Save the session (<b>Session → Save</b>; autosave is active too).</li>
<li>Load the influence model (same HyperMesh or later), load the session, switch the phase to <b>INF</b> and generate.
    The tool replays the same views (camera + recorded layout) and metrics; INF pictures land in the INF slots of the <i>same</i> deck.</li>
</ul>
<h3>Presentation and slide layout</h3>
<ul>
<li>The <b>Presentation</b> tab holds an interactive slide preview: slots can be <b>dragged</b> and <b>resized</b> (edge / corner),
    given REF / INF roles, added and removed.</li>
<li>Quick symmetric layouts: <b>Left / Right</b> and <b>Top / Bottom</b> (pairs per slide selectable); <b>Mirror</b> copies REF slots to the INF side.</li>
<li>The preview shows the real slide with the taken screenshots; empty INF places are dashed in the PPTX as well.</li>
<li><b>Save layout… / Load layout…</b> – the arrangement (JSON) can be reused in later sessions.</li>
</ul>
<h3>Metrics (“Metrics” tab)</h3>
<ul>
<li>Each metric has a HyperMesh <b>command template</b> with the <code>{thr}</code> symbol (limit value) – the native Check Elements
    commands are used, so HyperMesh draws its own highlighting and legend.</li>
<li>If your HyperMesh release uses a different syntax: <b>“Record from HyperMesh…”</b> – perform the check by hand and the lines from
    <code>command.tcl</code> become the template. Templates can be edited and custom metrics added.</li>
<li>“Only elements outside the limit” masks the passing elements; “cleanup” restores the display after the shot.</li>
</ul>
<h3>Display layout (sections, styles, masking)</h3>
<p>Click <b>“● Record layout”</b>, make the changes in HyperMesh, then “Remember view” – the command-file lines are attached to the view (⚙)
and replayed before the shot in the next model.</p>
<h3>Shortcuts</h3>
<p><b>1</b> – remember view, <b>K</b> – generate, <b>Ctrl+S</b> – save session. Clicking a thumbnail applies the view in HyperMesh.</p>
"""


def html() -> str:
    return _EN if get_lang() == "en" else _PL
