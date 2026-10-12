#=====================================================================
#  HM SHOTS - zrzuty ekranu z AKTUALNIE OTWARTEGO modelu HyperMesh
#  -------------------------------------------------------------------
#  - Zapamietujesz dowolna liczbe widokow (kamera: orientacja + zoom + pan).
#  - Przy KAZDYM zapamietanym widoku powstaje MINIATURA (maly zrzut robiony
#    w momencie zapamietania), zeby od razu bylo widac, co dany widok pokazuje.
#  - Przy kazdym widoku jest CHECKBOX - zaznaczasz, ktore widoki maja trafic
#    do eksportu (mozna zaznaczyc/odznaczyc wszystkie jednym przyciskiem).
#  - Przy zapamietaniu widoku zapisywana jest tez PELNA KLATKA - dokladnie to,
#    co widac na ekranie w tej chwili (WYSIWYG).
#  - "Generuj zrzuty" iteruje TYLKO po zaznaczonych widokach i DOMYSLNIE
#    eksportuje wlasnie te zapisane klatki do wybranego folderu (numeracja
#    sekwencyjna, bez nadpisywania). Dzieki temu pozniejsze zmiany wygladu
#    modelu (np. przelaczenie na widok bezbarwny) NIE zmieniaja juz widokow
#    zapamietanych wczesniej. Gdy widok nie ma zapisanej klatki (np. po
#    "Wczytaj sesje" w innym modelu) albo opcja WYSIWYG jest odznaczona,
#    widok jest renderowany na nowo, jak w starym trybie: uklad + kamera.
#
#  Widok pobierany/ustawiany NATYWNYMI komendami okna modelowania HM:
#     hm_winfo viewmatrix   -> zwraca wartosci uzywane przez *viewset
#     *viewset <20 liczb>   -> ustawia widok (macierz 4x4 + minx miny maxx maxy)
#  Zrzut: *jpegfilenamed (natywny); BMP przez konwersje czystym Tcl
#         (HyperMesh classic - wymaga PELNEJ sciezki pliku).
#  Miniatury: najpierw proba PNG (Tk 8.6); gdy Tk nie czyta PNG, robiony jest
#  zrzut BMP i wczytywany wlasnym parserem w czystym Tcl (dziala tez na Tk 8.5).
#  Gdy oba zawioda -> pokazywana jest szara zaslepka, a reszta dziala normalnie.
#
#  Uruchomienie: w HyperMesh  ->  File/Tools  ->  Run Tcl/Tk Script
#=====================================================================

namespace eval ::hmShot {
    variable views      {}        ;# lista rekordow (dict): id name view thumb
    variable nextId     1         ;# licznik unikalnych ID widokow
    variable selArr               ;# selArr(id) = 0/1  (stan checkboxa)
    variable listCanvas ""        ;# canvas z lista widokow
    variable listInner  ""        ;# ramka wewnatrz canvas (wiersze/karty)
    variable countLbl   ""        ;# etykieta "Zaznaczono: X / Y"
    variable shotDir    ""        ;# folder na zrzuty (eksport)
    variable shotPrefix "shot"    ;# prefiks nazw plikow
    variable shotExt    "jpg"     ;# format eksportu: jpg (natywny) / bmp (konwersja czystym Tcl)
    variable saveToModelDir 0     ;# zapisz zrzuty do folderu otwartego modelu .hm
    variable makeSubfolder  0     ;# utworz podfolder o nazwie prefiksu i zapisuj tam
    variable prefixEntry    ""    ;# sciezka widgetu pola prefiksu (do blokowania)
    variable prefixLabel    ""    ;# sciezka etykiety prefiksu
    variable nmRefAR    0         ;# nazwy automatyczne (REF/INF x AR/Jacobian/Skewness)
    variable nmRefJac   0
    variable nmRefSkew  0
    variable nmInfAR    0
    variable nmInfJac   0
    variable nmInfSkew  0
    variable wantReport 1         ;# czy przy eksporcie zapisac raport widokow (.txt + .xls)
    variable hiQuality  1         ;# czy poprawiac jakosc zrzutu (antyaliasing + maks. JPEG)
    variable bgMode     "bez zmian" ;# tlo na czas eksportu
    variable statusTxt  ""
    variable statusLbl  ""
    variable vcOk       0
    variable thumbW     320       ;# maks. szerokosc miniatury (px)
    variable thumbH     200       ;# maks. wysokosc miniatury (px)
    variable imgOk      0         ;# czy Tk potrafi wczytac PNG (miniatury)
    variable phImg      ""        ;# obraz-zaslepka (gdy brak miniatury)
    variable lastThumbLog ""      ;# log ostatniej proby zrzutu miniatury
    variable thumbFmt   ""        ;# zapamietany dzialajacy format zrzutu (np. jpg)
    variable lastExportFmt ""     ;# faktyczny format ostatniego eksportu (gdy podmieniony)
    variable capBgMethod ""       ;# tlo ZRZUTU: "" nieznane, "scene" tlo sceny wystarcza, "hwi" alternatywna metoda zrzutu, "none" brak metody, inaczej szablon komendy
    variable capBgLogPath ""      ;# sciezka logu diagnostycznego tla zrzutu (gdy "none")
    variable captureMethod "panel" ;# metoda zrzutu: "panel" (*jpegfilenamed itd.) lub "hwi" (HWD CaptureScreen/CaptureActiveWindow)
    variable hwiForm ""           ;# zapamietany dzialajacy szablon zrzutu hwi (%H uchwyt, %E format, %P plik)
    variable hwiJpegTok "jpeg"    ;# pisownia tokenu formatu w dzialajacym szablonie (jpeg/JPEG)
    variable hvGetForm ""         ;# HyperView: zapamietany skrypt pobierania macierzy widoku
    variable hvSetForm ""         ;# HyperView: zapamietany szablon ustawiania (z %N = liczby)
    variable hvProbed 0           ;# HyperView: czy kalibracja juz sie odbyla
    variable hvDiagPath ""        ;# HyperView: sciezka logu kalibracji widoku (gdy porazka)
    variable hvMode ""            ;# HyperView: "matrix" (para macierzowa) / "comp" (kompozyt) / ""
    variable hvProps {}           ;# HyperView: zweryfikowane wlasciwosci kompozytu {tgt Name}
    variable hvRep ""             ;# HyperView: pelny log kalibracji (do pliku diagnostycznego)
    variable hvZoomForm ""        ;# HyperView: zapamietany szablon WZGLEDNEGO zoomu (%F = wspolczynnik)
    variable hvZoomInv 0          ;# HyperView: 1 gdy czasownik zoomu dziala odwrotnie (f -> 1/f)
    variable hvPanForm ""         ;# HyperView: szablon pan (%DX %DY) lub "none"
    variable hvPanGX 1.0          ;# HyperView: wzmocnienie osi X (ulamek ekranu / jednostke)
    variable hvPanGY 1.0          ;# HyperView: wzmocnienie osi Y
    variable vcErr ""             ;# ostatni blad lancucha uchwytow hwi
    variable appMode ""           ;# rozstrzygniety tryb aplikacji: "hm" / "hv" ("" = jeszcze nie)
    variable lastBgLog  ""        ;# log ostatniej proby zmiany tla
    variable lastQualityLog ""    ;# log ostatniej proby poprawy jakosci
    # -- nagrywanie UKLADU WYSWIETLANIA (sekcje, style FE/Geometry, maskowanie itd.) --
    variable recOn      0         ;# czy nagrywanie komend ukladu jest wlaczone
    variable recFile    ""        ;# sciezka pliku komend HM (command.tcl / command.cmf)
    variable recOfs     0         ;# offset w pliku komend, od ktorego czytamy nowe wpisy
    variable recBtn     ""        ;# sciezka przycisku nagrywania (do zmiany etykiety)
    variable dispApplied 0        ;# ile snippetow ukladu odtworzono juz w TEJ sesji HM
    variable useStored  1         ;# eksport: 1 = uzyj klatek zapisanych przy "Zapamietaj widok" (WYSIWYG)
    variable edDisp     ""        ;# bufor pola ukladu w oknie Edytuj
    # zmienne pomocnicze okien dialogowych
    variable edId       0
    variable edName     ""
    variable edTxt      ""
    variable addTxt     ""
    variable lang       "pl"      ;# jezyk interfejsu: pl / en
    variable MSG                  ;# katalog tlumaczen (wypelniany ponizej)
}

# Prosty wybor jezyka: zwraca PL lub EN wg ::hmShot::lang.
proc ::hmShot::T {pl en} {
    return [expr {$::hmShot::lang eq "en" ? $en : $pl}]
}
# Przelaczenie jezyka i przebudowa okna (lista widokow przetrwa - jest w namespace).
proc ::hmShot::setLang {l} {
    if {$l ne "pl" && $l ne "en"} { return }
    set ::hmShot::lang $l
    ::hmShot::gui
}

#---------------------------------------------------------------------
#  Tlo okna graficznego (kolor)
#---------------------------------------------------------------------
# Kolor tla (hex) dla trybu; "" = nie zmieniaj.
# Token tla niezalezny od jezyka: none/black/graphite/navy/white.
proc ::hmShot::bgToken {label} {
    switch -- $label {
        "czarne" - "black"        { return black }
        "grafit" - "graphite"     { return graphite }
        "granat" - "navy"         { return navy }
        "biale"  - "white"        { return white }
        default                   { return none }
    }
}
# Etykieta tla w danym jezyku dla tokenu.
proc ::hmShot::bgLabel {token lang} {
    if {$lang eq "en"} {
        switch -- $token { black {return black} graphite {return graphite} navy {return navy} white {return white} default {return "no change"} }
    }
    switch -- $token { black {return czarne} graphite {return grafit} navy {return granat} white {return biale} default {return "bez zmian"} }
}
# Lista etykiet tla (kolejnosc menu) w danym jezyku.
proc ::hmShot::bgLabels {lang} {
    set out {}
    foreach t {none black graphite navy white} { lappend out [::hmShot::bgLabel $t $lang] }
    return $out
}
# Etykieta tla (PL lub EN) -> "#rrggbb" (lub "" dla "bez zmian"/"no change").
proc ::hmShot::bgHex {mode} {
    switch -- [::hmShot::bgToken $mode] {
        black    { return "#000000" }
        graphite { return "#1f1f1f" }
        navy     { return "#10243b" }
        white    { return "#ffffff" }
        default  { return "" }
    }
}
# "#rrggbb" -> lista {r g b} (0-255) lub "" gdy bledne.
proc ::hmShot::bgRGB255 {hex} {
    set h [string trimleft [string trim $hex] #]
    if {![regexp {^[0-9a-fA-F]{6}$} $h]} { return "" }
    scan $h "%2x%2x%2x" r g b
    return [list $r $g $b]
}
# Czy komenda (globalna lub z przestrzeni nazw) istnieje.
proc ::hmShot::cmdExists {name} {
    expr {[llength [uplevel #0 [list info commands ::$name]]] || [llength [uplevel #0 [list info commands $name]]]}
}
# Odczyt stanu gradientu tla (0/1) lub "" gdy nieznany.
proc ::hmShot::getBgGradient {} {
    if {![::hmShot::cmdExists hm_getbackgroundgradient]} { return "" }
    set r ""
    if {[catch {set r [uplevel #0 hm_getbackgroundgradient]}]} { return "" }
    set r [string trim $r]
    if {[string is integer -strict $r]} { return $r }
    if {[string match -nocase on* $r]}  { return 1 }
    if {[string match -nocase off* $r]} { return 0 }
    return ""
}
# Wlacza/wylacza gradient tla (1/0). Zwraca 1, gdy komenda istnieje i wykonana.
proc ::hmShot::setBgGradient {on logVar} {
    upvar 1 $logVar log
    if {![::hmShot::cmdExists *setbackgroundgradient]} { append log "  *setbackgroundgradient: brak komendy\n" ; return 0 }
    if {[catch {uplevel #0 [list *setbackgroundgradient $on]} e]} { append log "  *setbackgroundgradient $on -> BLAD: $e\n" ; return 0 }
    append log "  *setbackgroundgradient $on -> wykonano\n" ; return 1
}
# Ustawia kolor tla. GLOWNA metoda (potwierdzona w tym buildzie):
#   hwf::setbackgroundcolor #rrggbb
# Gdyby jej nie bylo - fallback na *setbackgroundcolor / *setbackgroundcolors /
# gradient i kandydatow tla zrzutu. Zwraca 1, gdy cokolwiek wykonano.
proc ::hmShot::applyBg {hex logVar} {
    upvar 1 $logVar log
    set rgb [::hmShot::bgRGB255 $hex]
    if {$rgb eq ""} { return 0 }
    lassign $rgb r g b
    set rf [format %.4f [expr {$r/255.0}]]
    set gf [format %.4f [expr {$g/255.0}]]
    set bf [format %.4f [expr {$b/255.0}]]
    set okAny 0
    # (0) GLOWNA metoda: hwf::setbackgroundcolor #rrggbb (ustawia tlo SCENY - dziala)
    if {[::hmShot::cmdExists hwf::setbackgroundcolor]} {
        set sceneOk 0
        if {[catch {uplevel #0 [list hwf::setbackgroundcolor $hex]} e]} {
            append log "  \[hwf::setbackgroundcolor $hex\] -> BLAD: $e\n"
        } else {
            append log "  \[hwf::setbackgroundcolor $hex\] -> wykonano\n" ; set sceneOk 1
        }
        # tlo ZRZUTU jest osobne od sceny (HM renderuje obraz z wlasnym tlem) - probujemy
        # prawdopodobnych komend hwf:: tla zrzutu/hardcopy (odpala sie tylko, jesli istnieje).
        foreach a [list \
                [list hwf::sethardcopybackgroundcolor $hex] \
                [list hwf::setcapturebackgroundcolor $hex] \
                [list hwf::setimagebackgroundcolor $hex] \
                [list hwf::sethardcopybackground $hex] \
                [list hwf::setprintbackgroundcolor $hex] \
                [list hwf::sethardcopywhitebackground 0] \
                [list hwf::setwhitebackground 0]] {
            if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
            if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] -> BLAD: $e\n" ; continue }
            append log "  \[$a\] -> wykonano\n"
        }
        if {$sceneOk} { catch {hm_redraw} ; return 1 }
    }
    # (a) wylacz gradient (rozne mozliwe wartosci)
    foreach gc [list [list *setbackgroundgradient 0] [list *setbackgroundgradient off]] {
        if {![::hmShot::cmdExists [lindex $gc 0]]} { continue }
        if {[catch {uplevel #0 $gc} e]} { append log "  \[$gc\] -> BLAD: $e\n" ; continue }
        append log "  \[$gc\] -> wykonano\n" ; set okAny 1 ; break
    }
    # (b) jednolity kolor tla (float 0-1, potem int 0-255, potem hex)
    foreach a [list \
            [list *setbackgroundcolor $rf $gf $bf] \
            [list *setbackgroundcolor $r $g $b] \
            [list *setbackgroundcolor $hex]] {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] -> BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set okAny 1 ; break
    }
    # (c) OBIE barwy gradientu = ten sam kolor (gdyby gradient pozostal wlaczony)
    foreach a [list \
            [list *setbackgroundcolors $rf $gf $bf $rf $gf $bf] \
            [list *setbackgroundcolors $r $g $b $r $g $b]] {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] -> BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set okAny 1 ; break
    }
    # (d) tlo ZRZUTU/hardcopy: HM czesto wymusza biale tlo na eksporcie niezaleznie od
    #     ekranu. Probujemy wylaczyc "biale tlo" i/lub ustawic kolor tla zrzutu.
    foreach a [list \
            [list *hardcopywhitebackground 0] [list *setwhitebackground 0] \
            [list *whitebackground 0] [list *setcapturewhitebackground 0] \
            [list *setimagewhitebackground 0] [list *usewhitebackground 0]] {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] -> BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set okAny 1
    }
    foreach a [list \
            [list *sethardcopybackgroundcolor $r $g $b] [list *setcapturebackgroundcolor $r $g $b] \
            [list *setimagebackgroundcolor $r $g $b] [list *sethardcopybackgroundcolor $rf $gf $bf]] {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] -> BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set okAny 1
    }
    catch {hm_redraw}
    return $okAny
}
#---------------------------------------------------------------------
#  TLO ZRZUTU (osobne od tla sceny!)
#  HM potrafi renderowac zapisywany obraz z WLASNYM (bialym) tlem, niezaleznie od
#  tla widocznego na ekranie. Ponizsze procedury robia PROBNY zrzut, sprawdzaja
#  kolor naroznikow i - gdy nie pasuje - probuja znanych przelacznikow tla zrzutu,
#  weryfikujac kazdy kolejnym probnym zrzutem. Dzialajaca metode zapamietuja.
#---------------------------------------------------------------------
# Probny zrzut JPG -> lista kolorow naroznikow {{r g b} ...} lub "" gdy weryfikacja
# niemozliwa (brak Tk / brak komendy zrzutu / pusty obraz).
proc ::hmShot::captureCorners {} {
    set log ""
    set p [::hmShot::captureTo jpg log]
    if {$p eq ""} { return "" }
    set out [::hmShot::cornersOfFile $p]
    catch {file delete -force $p}
    return $out
}
# Kolory naroznikow istniejacego pliku obrazu (przez image -file). "" gdy sie nie da.
proc ::hmShot::cornersOfFile {p} {
    if {[uplevel #0 {info commands image}] eq "" && [uplevel #0 {info commands ::image}] eq ""} { return "" }
    if {$p eq "" || ![file isfile $p]} { return "" }
    set img ""
    catch {set img [image create photo -file $p]}
    if {$img eq ""} { return "" }
    set out [::hmShot::photoCorners $img]
    catch {image delete $img}
    return $out
}
# Kolory naroznikow zaladowanego photo. "" gdy sie nie da.
proc ::hmShot::photoCorners {img} {
    if {$img eq ""} { return "" }
    set w 0 ; set h 0
    catch {set w [image width $img]} ; catch {set h [image height $img]}
    if {$w < 10 || $h < 10} { return "" }
    set out {}
    foreach xy [list [list 4 4] [list [expr {$w-5}] 4] [list 4 [expr {$h-5}]] [list [expr {$w-5}] [expr {$h-5}]]] {
        lassign $xy x y
        if {![catch {$img get $x $y} rgb] && [llength $rgb] == 3} { lappend out $rgb }
    }
    return $out
}
#-- GWARANTOWANA metoda tla: przebarwienie pikseli w samym obrazie (odwrocenie
#-- "reverse video" zrzutu). Bialawe piksele (tlo) -> zadany kolor; przy CIEMNYM
#-- tle dodatkowo czarnawe piksele (tekst legendy/opisow) -> biale, zeby pozostaly
#-- czytelne. Kolorowe elementy siatki/konturow pozostaja nietkniete.
# Przetwarza photo w miejscu. Zwraca 1/0.
proc ::hmShot::recolorPhoto {img hex} {
    set rgb [::hmShot::bgRGB255 $hex]
    if {$img eq "" || $rgb eq ""} { return 0 }
    lassign $rgb R G B
    set dark [expr {(0.299*$R + 0.587*$G + 0.114*$B) < 128.0}]
    set rows {}
    if {[catch {set rows [$img data]}] || ![llength $rows]} { return 0 }
    if {![regexp {^#[0-9a-fA-F]{6}$} [lindex [lindex $rows 0] 0]]} { return 0 }
    set y 0
    foreach row $rows {
        set s [join $row ""]
        # tlo (bialawe: wszystkie kanaly >= 0xE0) -> zadany kolor
        regsub -all {#[eEfF][0-9a-fA-F][eEfF][0-9a-fA-F][eEfF][0-9a-fA-F]} $s $hex s
        if {$dark} {
            # tekst (czarnawe: wszystkie kanaly <= 0x2F) -> bialy, by byl czytelny
            regsub -all {#[0-2][0-9a-fA-F][0-2][0-9a-fA-F][0-2][0-9a-fA-F]} $s "#ffffff" s
        }
        set lst [regexp -all -inline {#[0-9a-fA-F]{6}} $s]
        if {[catch {$img put [list $lst] -to 0 $y}]} { return 0 }
        incr y
    }
    return 1
}
# Przebarwia gotowy plik zrzutu. Zapis: JPEG jesli ten Tk potrafi, inaczej BMP
# (czysty Tcl) - wtedy zwraca nowa sciezke. Wynik: {ok sciezka}.
proc ::hmShot::recolorFileInPlace {path hex} {
    if {[uplevel #0 {info commands image}] eq "" && [uplevel #0 {info commands ::image}] eq ""} { return [list 0 $path] }
    set img ""
    catch {set img [image create photo -file $path]}
    if {$img eq ""} { return [list 0 $path] }
    if {![::hmShot::recolorPhoto $img $hex]} { catch {image delete $img} ; return [list 0 $path] }
    set ext [string tolower [string trimleft [file extension $path] .]]
    if {$ext in {jpg jpeg}} {
        set ow "" ; set oh ""
        catch {set ow [image width $img]} ; catch {set oh [image height $img]}
        # sprobuj nadpisac JPEG-iem (niektore buildy Tk maja zapis jpeg)
        if {![catch {$img write $path -format jpeg}] && [file isfile $path] && [file size $path] > 0} {
            set chk [::hmShot::cornersOfFile $path]
            set d [::hmShot::imageDims $path]
            set dimsOk 1
            if {$d ne "" && $ow ne ""} { lassign $d nw nh ; set dimsOk [expr {$nw == $ow && $nh == $oh}] }
            if {$dimsOk && $chk ne "" && [::hmShot::cornersMatch $chk $hex]} {
                catch {image delete $img}
                return [list 1 $path]
            }
        }
        # fallback: BMP obok (zmiana rozszerzenia)
        set np "[file rootname $path].bmp"
        if {[::hmShot::writeBmpFromPhoto $img $np]} {
            catch {image delete $img}
            catch {file delete -force $path}
            return [list 1 $np]
        }
        catch {image delete $img}
        return [list 0 $path]
    }
    if {$ext eq "bmp"} {
        set ok [::hmShot::writeBmpFromPhoto $img $path]
        catch {image delete $img}
        return [list $ok $path]
    }
    catch {image delete $img}
    return [list 0 $path]
}
#-- Alternatywna METODA ZRZUTU: HyperWorks Desktop API (hwi). Zwykle zapisuje obraz
#-- taki, jaki widac na ekranie (wraz z tlem sceny) - obchodzi biale tlo zrzutu panelu.
# Szablony do wyprobowania: %H = uchwyt sesji, %E = token formatu, %P = plik.
proc ::hmShot::hwiForms {} {
    return {
        {{%H CaptureActiveWindow %E %P} jpeg}
        {{%H CaptureActiveWindow %E %P} JPEG}
        {{%H CaptureActiveWindow %E %P} jpg}
        {{%H CaptureScreen %E %P} jpeg}
        {{%H CaptureScreen %E %P} JPEG}
        {{%H CaptureScreen %E %P} jpg}
        {{%H CaptureScreenToFile %E %P} jpeg}
        {{%H CaptureScreenToFile %E %P} JPEG}
        {{%H CaptureActiveWindowToFile %E %P} jpeg}
    }
}
# Token formatu dla hwi: dla jpg DOKLADNIE ta pisownia, ktora zadzialala w sondzie
# (jpeg/JPEG/jpg); dla innych rozszerzen ta sama wielkosc liter.
proc ::hmShot::hwiFmtToken {ext} {
    set e [string tolower $ext]
    set tok $::hmShot::hwiJpegTok
    if {$e in {jpg jpeg}} { return $tok }
    if {$tok eq [string toupper $tok]} { return [string toupper $e] }
    return $e
}
# Wymiary obrazu z pliku (przez Tk). Zwraca {w h} lub "" gdy nie da sie ustalic.
proc ::hmShot::imageDims {path} {
    if {[uplevel #0 {info commands image}] eq "" && [uplevel #0 {info commands ::image}] eq ""} { return "" }
    if {$path eq "" || ![file isfile $path]} { return "" }
    set img "" ; catch {set img [image create photo -file $path]}
    if {$img eq ""} { return "" }
    set w "" ; set h ""
    catch {set w [image width $img]} ; catch {set h [image height $img]}
    catch {image delete $img}
    if {$w eq "" || $h eq ""} { return "" }
    return [list $w $h]
}
# Wykonuje szablon hwi. WAZNE: (a) argumenty budowane jako LISTA, wiec sciezka ze
# spacjami/znakami PL pozostaje JEDNYM argumentem; (b) zrzut idzie najpierw do
# bezpiecznego pliku tymczasowego (silnik HV widzi tylko prosta sciezke TEMP),
# a potem jest kopiowany do celu. Zwraca 1 gdy plik docelowy powstal i jest niepusty.
proc ::hmShot::runHwiForm {tpl ext path} {
    if {![::hmShot::cmdExists hwi]} { return 0 }
    set tok [::hmShot::hwiFmtToken $ext]
    set h "hmShotSess[clock clicks]"
    set tmp [file join [::hmShot::pickTmpBase] "hwic_[clock clicks].$ext"]
    # zbuduj komende jako liste: kazde slowo szablonu mapowane osobno
    set cmd {}
    foreach w $tpl {
        switch -- $w {
            %H { lappend cmd $h }
            %E { lappend cmd $tok }
            %P { lappend cmd $tmp }
            default { lappend cmd $w }
        }
    }
    set ran 0
    catch {uplevel #0 {hwi OpenStack}}
    if {![catch {uplevel #0 [list hwi GetSessionHandle $h]}]} {
        if {![catch {uplevel #0 $cmd}]} { set ran 1 }
    }
    catch {uplevel #0 {hwi CloseStack}}
    if {!$ran} { catch {file delete -force $tmp} ; return 0 }
    set got 0
    for {set i 0} {$i < 10} {incr i} {
        if {[file isfile $tmp] && [file size $tmp] > 0} { set got 1 ; break }
        catch {after 100}
    }
    if {!$got} { catch {file delete -force $tmp} ; return 0 }
    if {$tmp ne $path} {
        if {[catch {file copy -force $tmp $path}]} {
            if {[catch {file rename -force $tmp $path}]} { catch {file delete -force $tmp} ; return 0 }
        }
        catch {file delete -force $tmp}
    }
    return [expr {[file isfile $path] && [file size $path] > 0}]
}
# Kalibracja metody hwi: dla kazdego szablonu robi probny zrzut i sprawdza narozniki.
# Gdy ktorys oddaje obraz z zadanym tlem - zapamietuje go. Zwraca 1/0.
proc ::hmShot::probeHwiCapture {hex} {
    if {![::hmShot::cmdExists hwi]} { return 0 }
    catch {uplevel #0 [list hwf::setbackgroundcolor $hex]}
    catch {hm_redraw}
    foreach ft [::hmShot::hwiForms] {
        lassign $ft tpl tok
        set ::hmShot::hwiJpegTok $tok
        set p [file join [::hmShot::pickTmpBase] "hwiprobe_[clock clicks].jpg"]
        if {![::hmShot::runHwiForm $tpl jpg $p]} { catch {file delete -force $p} ; continue }
        set corners [::hmShot::cornersOfFile $p]
        catch {file delete -force $p}
        if {$corners ne "" && [::hmShot::cornersMatch $corners $hex]} {
            set ::hmShot::hwiForm $tpl
            return 1
        }
    }
    set ::hmShot::hwiForm ""
    return 0
}
# Czy wiekszosc naroznikow (>=3 z 4) ma zadany kolor? Tolerancja na kompresje JPEG.
proc ::hmShot::cornersMatch {corners hex {tol 26}} {
    set t [::hmShot::bgRGB255 $hex]
    if {$t eq "" || ![llength $corners]} { return 0 }
    lassign $t tr tg tb
    set okc 0
    foreach c $corners {
        lassign $c r g b
        if {[catch {expr {abs($r-$tr)<=$tol && abs($g-$tg)<=$tol && abs($b-$tb)<=$tol}} m]} { continue }
        if {$m} { incr okc }
    }
    return [expr {$okc >= ([llength $corners] >= 4 ? 3 : [llength $corners])}]
}
# Kandydaci na przelacznik tla ZRZUTU. Podstawienia: %H=#rrggbb, %R/%G/%B=0-255,
# %r/%g/%b=0.0-1.0. Komendy "reverse video" wylaczaja klasyczne biale tlo hardcopy.
proc ::hmShot::capBgCandidates {} {
    return {
        {hwf::sethardcopybackgroundcolor %H}
        {hwf::setcapturebackgroundcolor %H}
        {hwf::setimagebackgroundcolor %H}
        {hwf::setprintbackgroundcolor %H}
        {hwf::setsnapshotbackgroundcolor %H}
        {hwf::setreversevideo 0}
        {hwf::reversevideo 0}
        {*reversevideo 0}
        {*setreversevideo 0}
        {*hardcopyreversevideo 0}
        {*hardcopywhitebackground 0}
        {*setwhitebackground 0}
        {*whitebackground 0}
        {*setcapturewhitebackground 0}
        {*setimagewhitebackground 0}
        {*usewhitebackground 0}
        {*sethardcopybackgroundcolor %R %G %B}
        {*setcapturebackgroundcolor %R %G %B}
        {*setimagebackgroundcolor %R %G %B}
        {*sethardcopybackgroundcolor %r %g %b}
        {*setoption reverse_video 0}
        {*setoption hardcopy_reverse_video 0}
    }
}
# Wykonuje szablon kandydata z podstawionym kolorem. Zwraca 1 gdy komenda istnieje
# i wykonala sie bez bledu.
proc ::hmShot::capBgRun {tpl hex} {
    set rgb [::hmShot::bgRGB255 $hex]
    if {$rgb eq ""} { return 0 }
    lassign $rgb R G B
    set map [list %H $hex %R $R %G $G %B $B \
        %r [format %.4f [expr {$R/255.0}]] %g [format %.4f [expr {$G/255.0}]] %b [format %.4f [expr {$B/255.0}]]]
    set cmd [string map $map $tpl]
    if {![::hmShot::cmdExists [lindex $cmd 0]]} { return 0 }
    if {[catch {uplevel #0 $cmd}]} { return 0 }
    return 1
}
# Zapewnia zadane tlo TAKZE NA ZRZUCIE. Kalibruje raz (weryfikacja pikselami),
# potem uzywa zapamietanej metody. Zwraca 1 gdy tlo zrzutu zgodne/zastosowane,
# 0 gdy zaden przelacznik nie dziala (wtedy zapisuje log do pliku).
proc ::hmShot::ensureCaptureBg {hex} {
    variable capBgMethod
    if {$hex eq ""} { return 1 }
    if {$capBgMethod eq "scene"}   { return 1 }
    if {$capBgMethod eq "hwi"}     { return 1 }   ;# zrzuty ida przez hwi (captureMethod)
    if {$capBgMethod eq "recolor"} { return 1 }   ;# tlo poprawiane w pikselach obrazu
    if {$capBgMethod eq "none"}    { return 0 }
    if {$capBgMethod ne ""} { ::hmShot::capBgRun $capBgMethod $hex ; return 1 }
    # kalibracja: czy tlo sceny wystarcza?
    set corners [::hmShot::captureCorners]
    if {$corners eq ""} { set capBgMethod "scene" ; return 1 }   ;# nie da sie zweryfikowac
    if {[::hmShot::cornersMatch $corners $hex]} { set capBgMethod "scene" ; return 1 }
    # nie wystarcza -> probuj przelacznikow tla zrzutu i weryfikuj kazdy
    foreach tpl [::hmShot::capBgCandidates] {
        if {![::hmShot::capBgRun $tpl $hex]} { continue }
        catch {uplevel #0 [list hwf::setbackgroundcolor $hex]}   ;# odswiez tlo sceny
        catch {hm_redraw}
        set corners [::hmShot::captureCorners]
        if {$corners ne "" && [::hmShot::cornersMatch $corners $hex]} {
            set capBgMethod $tpl
            return 1
        }
    }
    # ostatnia szansa: ZMIEN METODE ZRZUTU na hwi (HWD API zapisuje obraz z ekranu)
    if {[::hmShot::probeHwiCapture $hex]} {
        set capBgMethod "hwi"
        set ::hmShot::captureMethod "hwi"
        return 1
    }
    # GWARANTOWANY fallback: przebarwienie tla w pikselach kazdego zrzutu.
    # Wymaga tylko dzialajacego Tk image (skoro miniatury powstaja - dziala).
    if {[uplevel #0 {info commands image}] ne "" || [uplevel #0 {info commands ::image}] ne ""} {
        set capBgMethod "recolor"
        return 1
    }
    set capBgMethod "none"
    ::hmShot::dumpCapBgLog $hex
    return 0
}
# Zapisuje log diagnostyczny tla zrzutu (lista komend hwf::* i pokrewnych) do pliku.
proc ::hmShot::dumpCapBgLog {hex} {
    set rep "TLO ZRZUTU: zaden znany przelacznik nie zadzialal (docelowy kolor: $hex).\n"
    append rep "Ekran przyjmuje kolor (hwf::setbackgroundcolor), ale zapisywany obraz ma inne tlo.\n\n"
    append rep "Lista komend hwf::* (przyslij autorowi makra):\n"
    set l {} ; catch {set l [lsort -unique [uplevel #0 {info commands ::hwf::*}]]}
    append rep "  [join $l "\n  "]\n"
    append rep "\nKomendy hwi* (API HyperWorks Desktop):\n"
    set l {} ; catch {set l [lsort -unique [concat [uplevel #0 {info commands hwi*}] [uplevel #0 {info commands ::hwi*}]]]}
    append rep "  [expr {[llength $l] ? [join $l "\n  "] : {(brak)}}]\n"
    append rep "(Probowano rowniez zrzutu przez hwi GetSessionHandle + CaptureActiveWindow/\n CaptureScreen/CaptureScreenToFile - zaden nie odda\u0142 obrazu z zadanym t\u0142em.)\n"
    append rep "\nInne potencjalnie zwiazane komendy:\n"
    foreach pat {*hardcopy* *white* *reverse* *option* *capture* *snapshot*} {
        set l {} ; catch {set l [lsort -unique [uplevel #0 [list info commands $pat]]]}
        if {[llength $l]} { append rep "  $pat : [join $l { }]\n" }
    }
    set lp ""
    catch {
        set lp [file join [::hmShot::logDir] "diag_tlo_zrzutu.txt"]
        set fh [open $lp w] ; puts $fh $rep ; close $fh
    }
    set ::hmShot::capBgLogPath $lp
    set ::hmShot::lastBgLog $rep
    return $lp
}
# Test na zywo: ustawia kolor wybrany w GUI, by od razu zobaczyc efekt na ekranie.
proc ::hmShot::testBg {} {
    set mode $::hmShot::bgMode
    set hex [::hmShot::bgHex $mode]
    if {$hex eq ""} {
        ::hmShot::setStatus [::hmShot::T "Wybrano \u201ebez zmian\u201d \u2013 t\u0142o nie b\u0119dzie zmieniane. Wybierz kolor, by przetestowa\u0107." "\u201eNo change\u201d selected \u2013 background won't be changed. Pick a color to test."] ; return
    }
    set log ""
    if {[::hmShot::applyBg $hex log]} {
        catch {hm_redraw}
        if {[::hmShot::ensureCaptureBg $hex]} {
            ::hmShot::setStatus [::hmShot::T "Ustawiono t\u0142o sceny i zrzutu: $mode ($hex)." "Scene and capture background set: $mode ($hex)."]
        } else {
            ::hmShot::setStatus [::hmShot::T "T\u0142o sceny OK, ale ZRZUT ma inne t\u0142o (brak prze\u0142\u0105cznika w tym buildzie). Log: $::hmShot::capBgLogPath" "Scene background OK, but the CAPTURE uses a different background (no switch in this build). Log: $::hmShot::capBgLogPath"] "#b35a00"
        }
    } else {
        set ::hmShot::lastBgLog $log
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 zmieni\u0107 t\u0142a \u2013 otwieram diagnostyk\u0119." "Could not change the background \u2013 opening diagnostics."] red
        ::hmShot::diagBackground
    }
}
# Diagnostyka tla: lista dostepnych komend + proba ustawienia na czarno.
proc ::hmShot::diagBackground {} {
    set rep "DIAGNOSTYKA T\u0141A (kolor okna graficznego oraz tlo ZRZUTU)\n\n"
    append rep "Komendy zwi\u0105zane z t\u0142em / kolorem / zrzutem / hardcopy:\n"
    foreach pat {*ackground* *bground* *bgcolor* *hardcopy* *whitebg* *white*back* *capture* *jpeg* *image* *print* *snapshot*} {
        set lst {}
        catch {set lst [lsort -unique [concat [uplevel #0 [list info commands $pat]] [uplevel #0 [list info commands ::$pat]]]]}
        if {[llength $lst]} { append rep "  $pat :\n    [join $lst "\n    "]\n" }
    }
    append rep "\nKomendy w przestrzeniach hwf:: / hwi:: (tam dziala hwf::setbackgroundcolor):\n"
    foreach pat {::hwf::*background* ::hwf::*color* ::hwf::*capture* ::hwf::*hardcopy* ::hwf::*image* ::hwf::*print* ::hwf::*screen* ::hwf::*snapshot* ::hwi::*background* ::hwi::*capture* ::hwi::*hardcopy* ::hwi::*image*} {
        set lst {}
        catch {set lst [lsort -unique [uplevel #0 [list info commands $pat]]]}
        if {[llength $lst]} { append rep "  $pat :\n    [join $lst "\n    "]\n" }
    }
    append rep "\nPELNA lista hwf:: (przyslij ja autorowi, jesli powyzej nic nie pasuje):\n"
    set allhwf {}
    catch {set allhwf [lsort -unique [uplevel #0 [list info commands ::hwf::*]]]}
    if {[llength $allhwf]} {
        append rep "    [join $allhwf "\n    "]\n"
    } else {
        append rep "    (brak / nieznane)\n"
    }
    append rep "\nhm_getbackgroundgradient: [expr {[::hmShot::getBgGradient] ne {} ? [::hmShot::getBgGradient] : {brak/nieznane}}]\n"
    # treść błędów kilku kandydatów (ujawnia poprawna skladnie/argumenty)
    append rep "\nProby pojedynczych komend (na czarno) z pelnym komunikatem:\n"
    foreach probe [list \
            {*setbackgroundcolor 0 0 0} {*setbackgroundcolor 0.0 0.0 0.0} \
            {*setbackgroundcolors 0 0 0 0 0 0} {*setbackgroundgradient 0} \
            {*hardcopywhitebackground 0} {*sethardcopybackgroundcolor 0 0 0}] {
        if {![::hmShot::cmdExists [lindex $probe 0]]} { append rep "  \[brak\] $probe\n" ; continue }
        set msg "wykonano" ; if {[catch {uplevel #0 $probe} e]} { set msg "BLAD: $e" }
        set msg [string map {\n " | "} [string trim $msg]]
        if {[string length $msg] > 200} { set msg "[string range $msg 0 199]..." }
        append rep "  \[OK?\] $probe -> $msg\n"
    }
    set log ""
    set ok [::hmShot::applyBg "#000000" log]
    append rep "\nPe\u0142na pr\u00f3ba applyBg na czarne (#000000):\n$log"
    append rep "Wynik: [expr {$ok ? {jaka\u015b metoda wykonana} : {brak dzia\u0142aj\u0105cej metody}}]\n"
    append rep "\n(WA\u017bNE: je\u015bli ekran jest czarny, a ZRZUT bia\u0142y \u2013 HM renderuje obraz z bia\u0142ym\n t\u0142em. Przy\u015blij autorowi list\u0119 komend powy\u017cej \u2013 z niej wybierze on komend\u0119\n steruj\u0105c\u0105 t\u0142em zrzutu/hardcopy.)\n"
    set lp ""
    catch {
        set lp [file join [::hmShot::pickTmpBase] "diag_tlo.txt"]
        set fh [open $lp w] ; puts $fh $rep ; close $fh
    }
    if {$lp ne ""} { append rep "\nZapisano log do: $lp\n" }
    catch {tk_messageBox -type ok -icon info -title [::hmShot::T "Diagnostyka t\u0142a" "Background diagnostics"] -message $rep}
    ::hmShot::setStatus [::hmShot::T "Diagnostyka t\u0142a zako\u0144czona \u2013 wklej log autorowi." "Background diagnostics finished \u2013 paste the log to the author."]
}

#---------------------------------------------------------------------
#  Pasek stanu
#---------------------------------------------------------------------
proc ::hmShot::setStatus {msg {color "#1a7a1a"}} {
    set ::hmShot::statusTxt $msg
    if {$::hmShot::statusLbl ne "" && [winfo exists $::hmShot::statusLbl]} {
        $::hmShot::statusLbl configure -text $msg -fg $color
    }
}

#---------------------------------------------------------------------
#  Widok (kamera)
#---------------------------------------------------------------------
# Pobiera pelny widok HM: macierz 4x4 (a00..a33) + minx miny maxx maxy.
# Rodzaj aplikacji: hm (HyperMesh) / hv (HyperView). W HyperWorks Desktop
# istnieja OBA swiaty naraz (komendy hm_* i hwi), a hm_winfo potrafi zwracac
# macierz UKRYTEGO klienta HM - dlatego przy konflikcie rozstrzygamy
# EMPIRYCZNIE: czy widoczny EKRAN podaza za komendami hm (mutacja macierzy ->
# porownanie sygnatur pikselowych zrzutu -> przywrocenie stanu).
proc ::hmShot::appKind {} {
    if {$::hmShot::appMode ne ""} { return $::hmShot::appMode }
    set hasHM  [expr {[::hmShot::cmdExists hm_winfo] || [::hmShot::cmdExists hm_info]}]
    set hasHWI [::hmShot::cmdExists hwi]
    if {$hasHM && !$hasHWI} { set ::hmShot::appMode hm ; return hm }
    if {!$hasHM && $hasHWI} { set ::hmShot::appMode hv ; return hv }
    if {!$hasHM && !$hasHWI} { return unknown }
    # OBA: test zywotnosci sciezki hm
    set m0 "" ; catch {set m0 [hm_winfo viewmatrix]}
    set m0 [::hmShot::cleanNums $m0]
    if {[llength $m0] < 16} { set ::hmShot::appMode hv ; return hv }
    set s0 [::hmShot::screenSig]
    if {$s0 eq ""} { set ::hmShot::appMode hm ; return hm }   ;# brak zrzutu - zachowaj HM
    set m1 [::hmShot::hvMutate $m0]
    set applied 0
    if {[::hmShot::doViewset $m1]} { set applied 1 } elseif {![catch {eval [linsert $m1 0 hm_setviewmatrix]}]} { set applied 1 }
    if {!$applied} { set ::hmShot::appMode hv ; return hv }
    catch {hm_redraw} ; catch {update idletasks} ; catch {after 150}
    set s1 [::hmShot::screenSig]
    # przywroc stan hm niezaleznie od wyniku
    if {![::hmShot::doViewset $m0]} { catch {eval [linsert $m0 0 hm_setviewmatrix]} }
    catch {hm_redraw}
    if {$s1 ne "" && [::hmShot::sigDiff $s0 $s1] > 0.05} {
        set ::hmShot::appMode hm
        return hm
    }
    set ::hmShot::appMode hv
    return hv
}
# Sygnatura pikselowa ekranu: probny zrzut -> siatka 16x12 skwantowanych kolorow.
proc ::hmShot::screenSig {} {
    set log ""
    set p [::hmShot::captureTo jpg log]
    if {$p eq ""} { return "" }
    set img "" ; catch {set img [image create photo -file $p]}
    catch {file delete -force $p}
    if {$img eq ""} { return "" }
    set w 0 ; set h 0
    catch {set w [image width $img]} ; catch {set h [image height $img]}
    if {$w < 20 || $h < 16} { catch {image delete $img} ; return "" }
    set sig {}
    for {set gy 0} {$gy < 12} {incr gy} {
        set y [expr {2 + ($h-5)*$gy/11}]
        for {set gx 0} {$gx < 16} {incr gx} {
            set x [expr {2 + ($w-5)*$gx/15}]
            if {[catch {$img get $x $y} rgb] || [llength $rgb] != 3} { lappend sig "?" ; continue }
            lassign $rgb r g b
            lappend sig "[expr {$r/32}].[expr {$g/32}].[expr {$b/32}]"
        }
    }
    catch {image delete $img}
    return $sig
}
# Ulamek roznic miedzy sygnaturami (0..1).
proc ::hmShot::sigDiff {a b} {
    set n [llength $a]
    if {$n == 0 || $n != [llength $b]} { return 1.0 }
    set d 0
    foreach x $a y $b { if {$x ne $y} { incr d } }
    return [expr {double($d)/$n}]
}
# Czysci tekst do samych liczb rozdzielonych pojedynczymi spacjami.
proc ::hmShot::cleanNums {s} {
    regsub -all {[^-0-9.eE+ ]} [string trim $s] " " s
    regsub -all {\s+} [string trim $s] " " s
    return $s
}
proc ::hmShot::getView {} {
    if {[::hmShot::appKind] eq "hv"} { return [::hmShot::hvGetView] }
    set vm ""
    catch {set vm [hm_winfo viewmatrix]}
    set vm [::hmShot::cleanNums $vm]
    if {[llength $vm] >= 16} { return $vm }
    return [::hmShot::hvGetView]
}
# Wykonuje skrypt w lancuchu uchwytow hwi (sesja->projekt->strona->okno->ViewControl).
# Okno: najpierw aktywne, potem kolejne 1..8 - szukamy okna z ViewControl (w HV
# aktywne moze byc np. okno wykresu). W skrypcie: %VC = ViewControl, %W = okno.
proc ::hmShot::vcScript {script} {
    set ::hmShot::vcOk 0
    set r ""
    if {[catch {
        hwi OpenStack
        hwi GetSessionHandle hmShot_s
        hmShot_s GetProjectHandle hmShot_p
        hmShot_p GetPageHandle hmShot_pg [hmShot_p GetActivePage]
        set tryList {}
        catch {lappend tryList [hmShot_pg GetActiveWindow]}
        for {set i 1} {$i <= 8} {incr i} {
            if {[lsearch -exact $tryList $i] < 0} { lappend tryList $i }
        }
        set found 0 ; set werr ""
        foreach wi $tryList {
            catch {hmShot_vc ReleaseHandle}
            catch {hmShot_w ReleaseHandle}
            if {[catch {
                hmShot_pg GetWindowHandle hmShot_w $wi
                hmShot_w GetViewControlHandle hmShot_vc
            } e]} { set werr $e ; continue }
            set found 1 ; break
        }
        if {!$found} { error "brak okna z ViewControl ($werr)" }
        set r [uplevel #0 [string map [list %VC hmShot_vc %W hmShot_w] $script]]
        hwi CloseStack
        set ::hmShot::vcOk 1
    } cerr]} {
        catch {hwi CloseStack}
        set ::hmShot::vcOk 0
        set ::hmShot::vcErr $cerr
        return ""
    }
    set ::hmShot::vcErr ""
    return $r
}
# Dwustopniowe pobranie macierzy: getter zwraca UCHWYT macierzy, z ktorego
# czytamy wartosci jedna z typowych metod. Zwraca surowy wynik lub "".
proc ::hmShot::hvMatrixVia {vcH getter} {
    set r ""
    if {[catch {$vcH $getter hmShot_m}]} { return "" }
    foreach mm {GetMatrix GetElements GetValues GetViewMatrix} {
        set r ""
        if {![catch {set r [hmShot_m $mm]}] && [llength [::hmShot::cleanNums $r]] >= 16} { break }
        set r ""
    }
    catch {hmShot_m ReleaseHandle}
    return $r
}
# USTAWIENIE macierzy przez uchwyt: pobiera uchwyt getterem, wola na nim setter
# najpierw z 16 slowami, potem z JEDNA lista. Zwraca 1/0.
proc ::hmShot::hvMatrixSetVia {vcH getter setter nums} {
    if {[catch {$vcH $getter hmShot_m}]} { return 0 }
    set ok 0
    if {![catch {eval [linsert $nums 0 hmShot_m $setter]}]} { set ok 1 }
    if {!$ok && ![catch {hmShot_m $setter $nums}]} { set ok 1 }
    catch {hmShot_m ReleaseHandle}
    return $ok
}
# Porownanie list liczb DOWOLNEJ dlugosci (tolerancja wzgledna).
proc ::hmShot::closeVals {a b} {
    if {![llength $a] || [llength $a] != [llength $b]} { return 0 }
    foreach x $a y $b {
        if {[catch {expr {abs($x-$y)}} d]} { return 0 }
        set m 1.0 ; catch {set m [expr {abs($y) > 1.0 ? abs($y) : 1.0}]}
        if {$d > 0.001*$m} { return 0 }
    }
    return 1
}
#---------------------------------------------------------------------
#  SYLWETKA MODELU (do dostrajania zoomu w HyperView po PIKSELACH)
#  Mierzymy, jaka czesc kadru zajmuje model: siatka probek 24x16, tlo = srednia
#  naroznikow; punkt "modelowy", gdy rozni sie od tla. Wynik: {fw fh n} -
#  ulamek szerokosci/wysokosci zajety przez model i liczba probek modelu.
#---------------------------------------------------------------------
proc ::hmShot::photoSilhouette {img} {
    if {$img eq ""} { return "" }
    set w 0 ; set h 0
    catch {set w [image width $img]} ; catch {set h [image height $img]}
    if {$w < 20 || $h < 16} { return "" }
    set GX 32 ; set GY 24
    set minx -1 ; set maxx -1 ; set miny -1 ; set maxy -1 ; set cnt 0
    for {set gy 0} {$gy < $GY} {incr gy} {
        set y [expr {2 + ($h-5)*$gy/($GY-1)}]
        # wiersz probek
        set row {}
        for {set gx 0} {$gx < $GX} {incr gx} {
            set x [expr {2 + ($w-5)*$gx/($GX-1)}]
            if {[catch {$img get $x $y} rgb] || [llength $rgb] != 3} { lappend row "" ; continue }
            lappend row $rgb
        }
        # TLO LICZONE PER-WIERSZ (odporne na gradient): srednia z 2 probek
        # z lewej i 2 z prawej krawedzi tego wiersza
        set br 0 ; set bg 0 ; set bb 0 ; set bn 0
        foreach i [list 0 1 [expr {$GX-2}] [expr {$GX-1}]] {
            set c [lindex $row $i]
            if {$c eq ""} { continue }
            lassign $c r g b
            incr br $r ; incr bg $g ; incr bb $b ; incr bn
        }
        if {$bn == 0} { continue }
        set br [expr {$br/$bn}] ; set bg [expr {$bg/$bn}] ; set bb [expr {$bb/$bn}]
        for {set gx 0} {$gx < $GX} {incr gx} {
            set c [lindex $row $gx]
            if {$c eq ""} { continue }
            lassign $c r g b
            set d [expr {abs($r-$br) + abs($g-$bg) + abs($b-$bb)}]
            if {$d <= 60} { continue }
            incr cnt
            if {$minx < 0 || $gx < $minx} { set minx $gx }
            if {$gx > $maxx} { set maxx $gx }
            if {$miny < 0 || $gy < $miny} { set miny $gy }
            if {$gy > $maxy} { set maxy $gy }
        }
    }
    if {$cnt < 4} { return "" }
    set fw [expr {double($maxx-$minx+1)/$GX}]
    set fh [expr {double($maxy-$miny+1)/$GY}]
    set cx [expr {double($minx+$maxx)/2.0/($GX-1)}]
    set cy [expr {double($miny+$maxy)/2.0/($GY-1)}]
    return [list [format %.4f $fw] [format %.4f $fh] [format %.4f $cx] [format %.4f $cy] $cnt]
}
# Sylwetka z pliku obrazu (przez image -file). "" gdy sie nie da.
proc ::hmShot::fileSilhouette {path} {
    if {[uplevel #0 {info commands image}] eq "" && [uplevel #0 {info commands ::image}] eq ""} { return "" }
    if {$path eq "" || ![file isfile $path]} { return "" }
    set img "" ; catch {set img [image create photo -file $path]}
    if {$img eq ""} { return "" }
    set out [::hmShot::photoSilhouette $img]
    catch {image delete $img}
    return $out
}
# Probny zrzut -> sylwetka (do petli dostrajania zoomu).
proc ::hmShot::captureSilhouette {} {
    set log ""
    set p [::hmShot::captureTo jpg log]
    if {$p eq ""} { return "" }
    set out [::hmShot::fileSilhouette $p]
    catch {file delete -force $p}
    return $out
}
# HyperView: pobiera macierz widoku (po skalibrowaniu pary get/set). "" gdy brak.
# HyperView: pobiera zapis widoku. Tryb "matrix": 16+ liczb macierzy; tryb "comp":
# kompozyt "HV1: ..." (rotacja/centrum/zoom itd.). "" gdy kalibracja niemozliwa.
proc ::hmShot::hvGetView {} {
    if {![::hmShot::cmdExists hwi]} { return "" }
    if {$::hmShot::hvMode eq ""} { ::hmShot::hvCalibrate }
    switch -- $::hmShot::hvMode {
        matrix {
            set m [::hmShot::cleanNums [::hmShot::vcScript $::hmShot::hvGetForm]]
            if {$m eq ""} { return "" }
            # rekord hybrydowy: macierz + zweryfikowane wlasciwosci (np. Zoom),
            # ktore w HV bywaja POZA macierza
            set parts [list "M=$m"]
            foreach p $::hmShot::hvProps {
                lassign $p tag name shp
                set tgt [expr {$tag eq "W" ? "%W" : "%VC"}]
                set v [::hmShot::cleanNums [::hmShot::vcScript "$tgt Get$name"]]
                if {$v ne ""} { lappend parts "$tag.$name=$v" }
            }
            return "HV1: [join $parts |]"
        }
        comp   { return [::hmShot::hvGetComposite] }
    }
    return ""
}
# HyperView: ustawia widok z 16+ liczb (tryb macierzowy). Zwraca 1/0.
proc ::hmShot::hvApplyView {nums} {
    if {[llength $nums] < 16 || ![::hmShot::cmdExists hwi]} { return 0 }
    if {$::hmShot::hvMode eq ""} { ::hmShot::hvCalibrate }
    if {$::hmShot::hvMode ne "matrix" || $::hmShot::hvSetForm eq ""} { return 0 }
    ::hmShot::vcScript "[string map [list %N [join $nums { }]] $::hmShot::hvSetForm] ; catch {%W Draw}"
    return $::hmShot::vcOk
}
# Mutacja macierzy do testu pary: obrot o 90 stopni (zamiana dwoch pierwszych
# kolumn ze zmiana znaku) - wynik na pewno ROZNY od wejscia i nadal poprawny.
proc ::hmShot::hvMutate {m} {
    set n $m
    foreach {a b} {0 1 4 5 8 9} {
        set oa [lindex $m $a] ; set ob [lindex $m $b]
        set n [lreplace $n $a $a $ob]
        set n [lreplace $n $b $b [expr {-1.0*$oa}]]
    }
    return $n
}
# Nazwy metod potencjalnie niebezpiecznych - nigdy ich nie wolamy na slepo.
proc ::hmShot::hvNameBlocked {m} {
    foreach bad {delete release remove close clear save export capture print file quit new open import add create} {
        if {[string match -nocase "*$bad*" $m]} { return 1 }
    }
    return 0
}
# Sortuje kandydatow: najpierw nazwy z view/matrix/orient/camera/transform/rotation.
proc ::hmShot::hvRank {m} {
    set l [string tolower $m]
    if {[string match *viewmatrix* $l]} { return 0 }
    if {[string match *matrix* $l]}     { return 1 }
    foreach k {view orient camera transform rotation rotate} {
        if {[string match *$k* $l]} { return 2 }
    }
    return 3
}
# ===================== KALIBRACJA WIDOKU HYPERVIEW =====================
# Krok 1 (tryb "matrix"): para get/set macierzy z DOWODEM EMPIRYCZNYM.
#   - GET: metody bezposrednie oraz PRZEZ UCHWYT macierzy (kanoniczny wzorzec HV:
#     GetViewMatrixHandle -> GetMatrix).
#   - SET: szablony z %N w DWOCH kszta\u0142tach argumentow (16 slow ORAZ jedna
#     lista) + ustawianie PRZEZ UCHWYT (GetViewMatrixHandle -> SetMatrix) + Draw.
#   - Protokol: migawki wszystkich getterow -> set(mutacja) -> ktory getter
#     przyjal NOWA wartosc, ten tworzy pare; kazda zmiana przywracana z migawki.
# Krok 2 (tryb "comp"): gdy macierz niedostepna - kompozyt zweryfikowanych par
#   GetX/SetX (rotacja, centrum, zoom, ...) zapisywany jako "HV1: ...".
proc ::hmShot::hvCalibrate {} {
    if {$::hmShot::hvProbed} { return [expr {$::hmShot::hvMode ne ""}] }
    set ::hmShot::hvProbed 1
    if {![::hmShot::cmdExists hwi]} { return 0 }
    # zdrowie lancucha uchwytow
    set lm ""
    catch {set lm [::hmShot::vcScript {%VC ListMethods}]}
    if {$lm eq "" && $::hmShot::vcErr ne ""} {
        set ::hmShot::hvRep "LANCUCH UCHWYTOW: BLAD: $::hmShot::vcErr\n(Sprawdz, czy strona ma okno animacji HyperView.)\n"
        ::hmShot::hvFail
        return 0
    }
    set lmw ""
    catch {set lmw [::hmShot::vcScript {%W ListMethods}]}
    set rep "KALIBRACJA WIDOKU HyperView\nLancuch uchwytow: OK\n\nListMethods(ViewControl):\n  [join [lsort $lm] {, }]\n\nListMethods(Window):\n  [join [lsort $lmw] {, }]\n\n"
    # 1) WLASCIWOSCI POMOCNICZE (zoom/centrum...) wykrywamy PRZED sonda macierzy,
    #    bo proby SetMatrix moga je resetowac. Robimy tez ich migawki.
    append rep "POMOCNICZE (poza macierza):\n"
    set ::hmShot::hvProps {}
    catch {::hmShot::hvProbeComposite $lm $lmw rep 9 1}
    set auxProps $::hmShot::hvProps
    array set auxSnap {}
    foreach p $auxProps {
        lassign $p tag name shp
        set tgt [expr {$tag eq "W" ? "%W" : "%VC"}]
        set auxSnap($tag.$name) [::hmShot::cleanNums [::hmShot::vcScript "$tgt Get$name"]]
    }
    # 2) sonda pary macierzowej (moze naruszyc zoom - przywrocimy go ponizej)
    set okM [::hmShot::hvProbeMatrix $lm $lmw rep]
    # 3) przywroc wlasciwosci pomocnicze z migawek
    foreach p $auxProps {
        lassign $p tag name shp
        set v $auxSnap($tag.$name)
        if {$v eq ""} { continue }
        ::hmShot::vcScript "[string map [list %N [join $v { }]] $shp] ; catch {%W Draw}"
    }
    if {$okM} {
        set ::hmShot::hvMode "matrix"
        set ::hmShot::hvProps $auxProps
        set ::hmShot::hvRep $rep
        ::hmShot::hvWriteRep
        return 1
    }
    set ::hmShot::hvProps {}
    if {[::hmShot::hvProbeComposite $lm $lmw rep]} {
        set ::hmShot::hvMode "comp"
        set ::hmShot::hvRep $rep
        ::hmShot::hvWriteRep
        return 1
    }
    set ::hmShot::hvRep $rep
    ::hmShot::hvFail
    return 0
}
# Folder na pliki diagnostyczne: wybrany folder zrzutow (jesli zapisywalny),
# w przeciwnym razie folder tymczasowy.
proc ::hmShot::logDir {} {
    set d [string trim $::hmShot::shotDir]
    if {$d ne "" && [file isdirectory $d]} {
        set t [file join $d ".hmshot_wtest_[pid]"]
        if {![catch {set fh [open $t w] ; close $fh}]} {
            catch {file delete -force $t}
            return $d
        }
    }
    return [::hmShot::pickTmpBase]
}
# Zapisuje log kalibracji do pliku (takze przy SUKCESIE - do wgladu/wsparcia).
proc ::hmShot::hvWriteRep {} {
    catch {
        set lp [file join [::hmShot::logDir] "hv_kalibracja.txt"]
        set fh [open $lp w] ; puts $fh $::hmShot::hvRep ; close $fh
        set ::hmShot::hvDiagPath $lp
    }
}
# Zapisuje log kalibracji i pokazuje okno z jego poczatkiem.
proc ::hmShot::hvFail {} {
    set lp ""
    catch {
        set lp [file join [::hmShot::logDir] "hv_diag_widok.txt"]
        set fh [open $lp w] ; puts $fh $::hmShot::hvRep ; close $fh
    }
    set ::hmShot::hvDiagPath $lp
    set head [string range $::hmShot::hvRep 0 1400]
    catch {tk_messageBox -type ok -icon warning \
        -title [::hmShot::T "Kalibracja widoku HV" "HV view calibration"] \
        -message [::hmShot::T "Nie uda\u0142o si\u0119 skalibrowa\u0107 widoku HyperView.\nPe\u0142ny log: $lp\n\n$head" "Could not calibrate the HyperView view.\nFull log: $lp\n\n$head"]}
}
# --- tryb macierzowy ---
proc ::hmShot::hvProbeMatrix {lm lmw repVar} {
    upvar 1 $repVar rep
    # kandydaci GET (kanoniczny uchwyt macierzy NAJPIERW)
    set gets {} ; array set seenG {}
    foreach f [list "::hmShot::hvMatrixVia %VC GetViewMatrixHandle" "%VC GetViewMatrix" "%VC GetMatrix"] {
        set seenG($f) 1 ; lappend gets [list 0 $f]
    }
    foreach {src tgt} [list $lm %VC $lmw %W] {
        foreach m $src {
            if {![string match -nocase "get*" $m]} { continue }
            if {[::hmShot::hvNameBlocked $m]} { continue }
            set l [string tolower $m]
            if {[string match -nocase "*handle*" $m]} {
                if {[string match *matrix* $l] || [string match *view* $l] || [string match *camera* $l] || [string match *transform* $l]} {
                    set f "::hmShot::hvMatrixVia $tgt $m"
                    if {![info exists seenG($f)]} { set seenG($f) 1 ; lappend gets [list [::hmShot::hvRank $m] $f] }
                }
            } else {
                set f "$tgt $m"
                if {![info exists seenG($f)]} { set seenG($f) 1 ; lappend gets [list [::hmShot::hvRank $m] $f] }
            }
        }
    }
    set gets [lsort -integer -index 0 $gets]
    # kandydaci SET: szablony z %N; kazdy w kszta\u0142cie SLOWA i LISTA;
    # najpierw kanoniczne ustawianie przez uchwyt macierzy
    set sets {} ; array set seenS {}
    foreach hg {GetViewMatrixHandle GetMatrixHandle} {
        foreach is {SetMatrix SetElements SetValues} {
            set f "::hmShot::hvMatrixSetVia %VC $hg $is {%N}"
            set seenS($f) 1 ; lappend sets [list 0 $f]
        }
    }
    foreach {src tgt} [list $lm %VC $lmw %W] {
        foreach m $src {
            if {[::hmShot::hvNameBlocked $m]} { continue }
            set l [string tolower $m]
            if {[string match -nocase "get*handle" $m] && ([string match *matrix* $l] || [string match *view* $l] || [string match *camera* $l] || [string match *transform* $l])} {
                foreach is {SetMatrix SetElements SetValues} {
                    set f "::hmShot::hvMatrixSetVia $tgt $m $is {%N}"
                    if {![info exists seenS($f)]} { set seenS($f) 1 ; lappend sets [list [::hmShot::hvRank $m] $f] }
                }
                continue
            }
            if {![string match -nocase "set*" $m]} { continue }
            if {[string match -nocase "*handle*" $m]} { continue }
            foreach f [list "$tgt $m %N" "$tgt $m {%N}"] {
                if {![info exists seenS($f)]} { set seenS($f) 1 ; lappend sets [list [::hmShot::hvRank $m] $f] }
            }
        }
    }
    foreach m {SetViewMatrix SetMatrix} {
        foreach f [list "%VC $m %N" "%VC $m {%N}"] {
            if {![info exists seenS($f)]} { set seenS($f) 1 ; lappend sets [list 0 $f] }
        }
    }
    set sets [lsort -integer -index 0 $sets]
    append rep "MACIERZ: kandydaci GET: [llength $gets], SET: [llength $sets]\n"
    # gettery zwracajace >=16 liczb
    set viable {}
    foreach g $gets {
        set gf [lindex $g 1]
        set v [::hmShot::cleanNums [::hmShot::vcScript $gf]]
        if {[llength $v] >= 16} {
            lappend viable $gf
            append rep "GET \[$gf\] -> [llength $v] liczb\n"
        }
    }
    if {![llength $viable]} {
        append rep "Brak gettera zwracajacego >=16 liczb.\n\n"
        return 0
    }
    set trials 0
    foreach s $sets {
        if {$trials >= 40} { break }
        set sf [lindex $s 1]
        array unset snap
        foreach gf $viable { set snap($gf) [::hmShot::cleanNums [::hmShot::vcScript $gf]] }
        set m1 [::hmShot::hvMutate $snap([lindex $viable 0])]
        incr trials
        ::hmShot::vcScript "[string map [list %N [join $m1 { }]] $sf] ; catch {%W Draw}"
        if {!$::hmShot::vcOk} { append rep "SET \[$sf\] -> blad wywolania\n" ; continue }
        set foundG ""
        foreach gf $viable {
            set now [::hmShot::cleanNums [::hmShot::vcScript $gf]]
            if {[::hmShot::numsClose $now $snap($gf)]} { continue }
            if {[::hmShot::numsClose $now $m1]} { set foundG $gf }
            ::hmShot::vcScript "[string map [list %N [join $snap($gf) { }]] $sf] ; catch {%W Draw}"
        }
        if {$foundG ne ""} {
            append rep "SET \[$sf\] -> PARA z \[$foundG\]\n\n"
            set ::hmShot::hvGetForm $foundG
            set ::hmShot::hvSetForm $sf
            return 1
        }
        append rep "SET \[$sf\] -> zaden getter nie przyjal nowej wartosci\n"
    }
    append rep "\n"
    return 0
}
# --- tryb kompozytowy: pary GetX/SetX o "widokowych" nazwach, 1..16 liczb ---
proc ::hmShot::hvCompKeyword {m} {
    set l [string tolower $m]
    foreach k {rotation orient angle camera view center zoom scale pan position target eye distance fov perspect} {
        if {[string match *$k* $l]} { return 1 }
    }
    return 0
}
proc ::hmShot::hvProbeComposite {lm lmw repVar {maxN 20} {skipMatrix 0}} {
    upvar 1 $repVar rep
    append rep "KOMPOZYT: szukam par GetX/SetX (1..$maxN liczb, DOWOLNE nazwy)\n"
    set props {}
    set trials 0
    foreach {src tgt tag} [list $lm %VC V $lmw %W W] {
        foreach m $src {
            if {$trials >= 40} { break }
            if {![string match -nocase "get*" $m]} { continue }
            if {[string match -nocase "*handle*" $m]} { continue }
            if {[::hmShot::hvNameBlocked $m]} { continue }
            if {$skipMatrix && [string match -nocase "*matrix*" $m]} { continue }
            set name [string range $m 3 end]
            if {[lsearch -exact $src "Set$name"] < 0} { continue }
            set v0 [::hmShot::cleanNums [::hmShot::vcScript "$tgt Get$name"]]
            set n [llength $v0]
            if {$n < 1 || $n > $maxN} { continue }
            # mutacja: pierwszy element + wyrazna delta
            set d 0.11 ; catch {set d [expr {abs([lindex $v0 0])*0.1 + 0.11}]}
            set v1 [lreplace $v0 0 0 [expr {[lindex $v0 0] + $d}]]
            incr trials
            set okShape ""
            foreach shp [list "$tgt Set$name %N" "$tgt Set$name {%N}"] {
                ::hmShot::vcScript "[string map [list %N [join $v1 { }]] $shp] ; catch {%W Draw}"
                if {!$::hmShot::vcOk} { continue }
                set v2 [::hmShot::cleanNums [::hmShot::vcScript "$tgt Get$name"]]
                if {[::hmShot::closeVals $v2 $v1]} { set okShape $shp }
                # przywroc stan
                ::hmShot::vcScript "[string map [list %N [join $v0 { }]] $shp] ; catch {%W Draw}"
                if {$okShape ne ""} { break }
            }
            if {$okShape ne ""} {
                append rep "  PARA: ${tag}.Get$name/Set$name ([llength $v0] liczb)\n"
                lappend props [list $tag $name $okShape]
            }
        }
    }
    if {![llength $props]} { append rep "  brak zweryfikowanych par\n" ; return 0 }
    set ::hmShot::hvProps $props
    append rep "\n"
    return 1
}
# Zapis widoku w trybie kompozytowym: "HV1: V.Name=liczby|W.Name=liczby|..."
proc ::hmShot::hvGetComposite {} {
    set parts {}
    foreach p $::hmShot::hvProps {
        lassign $p tag name shp
        set tgt [expr {$tag eq "W" ? "%W" : "%VC"}]
        set v [::hmShot::cleanNums [::hmShot::vcScript "$tgt Get$name"]]
        if {$v eq ""} { continue }
        lappend parts "$tag.$name=$v"
    }
    if {![llength $parts]} { return "" }
    return "HV1: [join $parts |]"
}
# Odtworzenie widoku z zapisu "HV1: ..." (dwa ksztalty argumentow, best-effort).
proc ::hmShot::hvApplyComposite {line} {
    if {![::hmShot::cmdExists hwi]} { return 0 }
    if {$::hmShot::hvMode eq ""} { ::hmShot::hvCalibrate }
    set body [string trim [string range [string trim $line] 4 end]]
    set okAny 0
    foreach part [split $body |] {
        set eq [string first = $part]
        if {$eq < 1} { continue }
        set key [string trim [string range $part 0 [expr {$eq-1}]]]
        set vals [::hmShot::cleanNums [string range $part [expr {$eq+1}] end]]
        if {$vals eq ""} { continue }
        # czesc M = macierz widoku (ustawiana skalibrowana para)
        if {[string toupper $key] eq "M"} {
            if {[llength $vals] >= 16 && $::hmShot::hvSetForm ne ""} {
                ::hmShot::vcScript "[string map [list %N [join $vals { }]] $::hmShot::hvSetForm] ; catch {%W Draw}"
                if {$::hmShot::vcOk} { set okAny 1 }
            }
            continue
        }
        set dot [string first . $key]
        if {$dot < 1} { continue }
        set tag [string range $key 0 [expr {$dot-1}]]
        set name [string range $key [expr {$dot+1}] end]
        set tgt [expr {$tag eq "W" ? "%W" : "%VC"}]
        set done 0
        foreach shp [list "$tgt Set$name %N" "$tgt Set$name {%N}"] {
            ::hmShot::vcScript "[string map [list %N [join $vals { }]] $shp] ; catch {%W Draw}"
            if {$::hmShot::vcOk} { set done 1 ; break }
        }
        if {$done} { set okAny 1 }
    }
    return $okAny
}
#---------------------------------------------------------------------
#  DOSTRAJANIE ZOOMU PO PIKSELACH (HyperView)
#  Gdy zoom nie ma pary Get/Set (w HV bywa tylko WZGLEDNY czasownik "Zoom f"),
#  rekord widoku niesie sylwetke wzorcowa (|ZM=fw fh). Po ustawieniu widoku
#  robimy probny zrzut, porownujemy sylwetki i korygujemy zoom w petli
#  sprzezenia zwrotnego (z automatycznym wykryciem kierunku dzialania).
#---------------------------------------------------------------------
# Kandydaci wzglednego zoomu z ListMethods (+statyczni). Szablon z %F.
proc ::hmShot::hvZoomCandidates {} {
    set out {}
    set lm "" ; catch {set lm [::hmShot::vcScript {%VC ListMethods}]}
    set lmw "" ; catch {set lmw [::hmShot::vcScript {%W ListMethods}]}
    foreach {src tgt} [list $lm %VC $lmw %W] {
        foreach m $src {
            if {[string match -nocase "get*" $m] || [string match -nocase "set*" $m]} { continue }
            if {[::hmShot::hvNameBlocked $m]} { continue }
            if {![string match -nocase "*zoom*" $m] && ![string match -nocase "*scale*" $m]} { continue }
            lappend out "$tgt $m %F"
        }
    }
    foreach m {Zoom GeometricZoom ArithmeticZoom ZoomModel} {
        set f "%VC $m %F"
        if {[lsearch -exact $out $f] < 0} { lappend out $f }
    }
    return $out
}
# Wyciaga sylwetke wzorcowa "|ZM=fw fh" z rekordu widoku (lub "").
proc ::hmShot::viewZM {view} {
    if {[regexp {ZM=([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)} $view -> a b c d]} { return [list $a $b $c $d] }
    if {[regexp {ZM=([0-9.]+) ([0-9.]+)} $view -> a b]} { return [list $a $b] }
    return ""
}
# Dostraja biezacy widok do wzorca z rekordu (|ZM=fw fh ?cx cy?):
# FAZA 1: zoom (rozmiar sylwetki), FAZA 2: pan (centroid sylwetki).
# Zwraca {status iteracje}: status 1 = zgodne/nie dotyczy, 0 = nie udalo sie.
proc ::hmShot::hvViewFineTune {view} {
    if {[::hmShot::appKind] ne "hv"} { return [list 1 0] }
    set zm [::hmShot::viewZM $view]
    if {$zm eq ""} { return [list 1 0] }
    set refW [lindex $zm 0] ; set refH [lindex $zm 1]
    set refCx "" ; set refCy ""
    if {[llength $zm] >= 4} { set refCx [lindex $zm 2] ; set refCy [lindex $zm 3] }
    set ref [expr {$refW > $refH ? $refW : $refH}]
    if {$ref <= 0.02} { return [list 1 0 ""] }
    set tol 0.05
    set iters 0
    set info ""
    set prevF "" ; set prevApplied ""
    # --- FAZA 1: zoom ---
    set zoomOk 0
    for {set it 1} {$it <= 5} {incr it} {
        set sil [::hmShot::captureSilhouette]
        if {$sil eq ""} { return [list 1 $iters [::hmShot::T "pomiar sylwetki niemo\u017cliwy" "silhouette not measurable"]] }
        lassign $sil cw ch ccx ccy cn
        set cur [expr {$cw > $ch ? $cw : $ch}]
        set info "wz [format %.2f $ref] -> [format %.2f $cur]"
        if {$cur <= 0.001} { return [list 0 $iters $info] }
        if {$prevF ne "" && $prevApplied ne ""} {
            if {($prevApplied > 1.001 && $cur < $prevF*0.97) || ($prevApplied < 0.999 && $cur > $prevF*1.03)} {
                set ::hmShot::hvZoomInv [expr {!$::hmShot::hvZoomInv}]
            }
        }
        set ratio [expr {$ref/$cur}]
        if {abs($ratio - 1.0) <= $tol} { set zoomOk 1 ; break }
        if {$ratio > 6.0} { set ratio 6.0 }
        if {$ratio < 0.17} { set ratio 0.17 }
        set f $ratio
        if {$::hmShot::hvZoomInv} { set f [expr {1.0/$ratio}] }
        if {![::hmShot::hvZoomBy $f]} { return [list 0 $iters "$info; brak czasownika zoom"] }
        incr iters
        set prevF $cur ; set prevApplied $ratio
    }
    if {!$zoomOk} {
        set sil [::hmShot::captureSilhouette]
        if {$sil ne ""} {
            lassign $sil cw ch ccx ccy cn
            set cur [expr {$cw > $ch ? $cw : $ch}]
            if {$cur > 0 && abs($ref/$cur - 1.0) <= $tol} { set zoomOk 1 }
        }
        if {!$zoomOk} { return [list 0 $iters $info] }
    }
    # --- FAZA 2: pan (tylko gdy wzorzec ma centroid) ---
    if {$refCx eq ""} { return [list 1 $iters $info] }
    for {set it 1} {$it <= 3} {incr it} {
        set sil [::hmShot::captureSilhouette]
        if {$sil eq ""} { return [list 1 $iters $info] }
        lassign $sil cw ch ccx ccy cn
        set dx [expr {$refCx - $ccx}] ; set dy [expr {$refCy - $ccy}]
        append info "; \u0394c=[format %.2f $dx],[format %.2f $dy]"
        if {abs($dx) <= 0.04 && abs($dy) <= 0.04} { return [list 1 $iters $info] }
        if {![::hmShot::hvPanByFrac $dx $dy]} {
            append info "; brak czasownika pan"
            return [list 1 $iters $info]
        }
        incr iters
    }
    set sil [::hmShot::captureSilhouette]
    if {$sil ne ""} {
        lassign $sil cw ch ccx ccy cn
        if {abs($refCx-$ccx) <= 0.05 && abs($refCy-$ccy) <= 0.05} { return [list 1 $iters $info] }
    }
    return [list 0 $iters $info]
}
# Kandydaci wzglednego przesuniecia widoku (dwa argumenty liczbowe).
proc ::hmShot::hvPanCandidates {} {
    set out {}
    set lm "" ; catch {set lm [::hmShot::vcScript {%VC ListMethods}]}
    set lmw "" ; catch {set lmw [::hmShot::vcScript {%W ListMethods}]}
    foreach {src tgt} [list $lm %VC $lmw %W] {
        foreach m $src {
            if {[string match -nocase "get*" $m] || [string match -nocase "set*" $m]} { continue }
            if {[::hmShot::hvNameBlocked $m]} { continue }
            if {![string match -nocase "*pan*" $m] && ![string match -nocase "*translate*" $m]} { continue }
            lappend out "$tgt $m %DX %DY"
        }
    }
    foreach m {Pan Translate PanView} {
        set f "%VC $m %DX %DY"
        if {[lsearch -exact $out $f] < 0} { lappend out $f }
    }
    return $out
}
# Kalibruje pan: znajduje forme + WZMOCNIENIE i ZNAK obu osi (sonda po ekranie).
# Zapisuje: hvPanForm, hvPanGX/hvPanGY (ulamek-ekranu na jednostke argumentu).
proc ::hmShot::hvPanCalibrate {} {
    if {$::hmShot::hvPanForm ne ""} { return 1 }
    if {$::hmShot::hvPanForm eq "none"} { return 0 }
    set base [::hmShot::captureSilhouette]
    if {$base eq ""} { return 0 }
    lassign $base bw bh bcx bcy bn
    foreach cand [::hmShot::hvPanCandidates] {
        foreach T {10.0 0.1 100.0} {
            # sonda osi X
            ::hmShot::vcScript "[string map [list %DX $T %DY 0] $cand] ; catch {%W Draw}"
            if {!$::hmShot::vcOk} { break }
            set s1 [::hmShot::captureSilhouette]
            if {$s1 eq ""} { break }
            lassign $s1 w1 h1 cx1 cy1 n1
            set gx [expr {($cx1 - $bcx)/$T}]
            # powrot X i sonda osi Y
            ::hmShot::vcScript "[string map [list %DX -$T %DY 0] $cand] ; catch {%W Draw}"
            ::hmShot::vcScript "[string map [list %DX 0 %DY $T] $cand] ; catch {%W Draw}"
            set s2 [::hmShot::captureSilhouette]
            if {$s2 eq ""} { break }
            lassign $s2 w2 h2 cx2 cy2 n2
            set gy [expr {($cy2 - $bcy)/$T}]
            ::hmShot::vcScript "[string map [list %DX 0 %DY -$T] $cand] ; catch {%W Draw}"
            if {abs($gx) > 1e-6 && abs($gy) > 1e-6} {
                set ::hmShot::hvPanForm $cand
                set ::hmShot::hvPanGX $gx
                set ::hmShot::hvPanGY $gy
                return 1
            }
        }
    }
    set ::hmShot::hvPanForm "none"
    return 0
}
# Przesuwa widok o zadany ulamek ekranu (dx,dy w ulamkach kadru). Zwraca 1/0.
proc ::hmShot::hvPanByFrac {dx dy} {
    if {![::hmShot::hvPanCalibrate]} { return 0 }
    set ax [expr {$dx / $::hmShot::hvPanGX}]
    set ay [expr {$dy / $::hmShot::hvPanGY}]
    ::hmShot::vcScript "[string map [list %DX $ax %DY $ay] $::hmShot::hvPanForm] ; catch {%W Draw}"
    return $::hmShot::vcOk
}
# Wykonuje wzgledny zoom o wspolczynnik f: zapamietanym szablonem albo pierwszym
# kandydatem, ktory realnie ZMIENIA sylwetke. Zwraca 1/0.
proc ::hmShot::hvZoomBy {f} {
    if {$::hmShot::hvZoomForm ne ""} {
        ::hmShot::vcScript "[string map [list %F $f] $::hmShot::hvZoomForm] ; catch {%W Draw}"
        return $::hmShot::vcOk
    }
    set before [::hmShot::captureSilhouette]
    set b 0
    if {$before ne ""} { lassign $before bw bh bcx bcy bn ; set b [expr {$bw > $bh ? $bw : $bh}] }
    foreach cand [::hmShot::hvZoomCandidates] {
        ::hmShot::vcScript "[string map [list %F $f] $cand] ; catch {%W Draw}"
        if {!$::hmShot::vcOk} { continue }
        if {$b <= 0} { set ::hmShot::hvZoomForm $cand ; return 1 }
        set after [::hmShot::captureSilhouette]
        if {$after eq ""} { set ::hmShot::hvZoomForm $cand ; return 1 }
        lassign $after aw ah acx acy an
        set a [expr {$aw > $ah ? $aw : $ah}]
        if {abs($a-$b) > 0.02} { set ::hmShot::hvZoomForm $cand ; return 1 }
    }
    return 0
}

proc ::hmShot::numsClose {a b} {
    if {[llength $a] < 16 || [llength $b] < 16} { return 0 }
    for {set i 0} {$i < 16} {incr i} {
        set x [lindex $a $i] ; set y [lindex $b $i]
        if {[catch {expr {abs($x-$y)}} d]} { return 0 }
        set m 1.0 ; catch {set m [expr {abs($y) > 1.0 ? abs($y) : 1.0}]}
        if {$d > 0.001*$m} { return 0 }
    }
    return 1
}
# Ustawia widok przez *viewset (>=16 liczb). Zwraca 1/0.
proc ::hmShot::doViewset {nums} {
    if {[llength $nums] < 16} { return 0 }
    if {![catch {*viewset {*}$nums}]} { return 1 }
    return 0
}
# Fallback przez API uchwytow hwi (gdy *viewset niedostepne w danym buildzie).
# Wyciaga liczby zapisane po znaczniku TAG: (do '|' albo konca linii).
proc ::hmShot::extractTag {line tag} {
    set up [string toupper $line]
    set pos [string first "${tag}:" $up]
    if {$pos < 0} { return "" }
    set rest [string range $line [expr {$pos + [string length $tag] + 1}] end]
    set bar [string first "|" $rest]
    if {$bar >= 0} { set rest [string range $rest 0 [expr {$bar-1}]] }
    regsub -all {[^-0-9.eE+ ]} $rest " " rest
    regsub -all {\s+} [string trim $rest] " " rest
    return $rest
}
# Odtwarza widok z linii: VS: -> *viewset (glowne); inaczej surowe liczby.
proc ::hmShot::applyView {line} {
    if {[string match -nocase "HV1:*" [string trim $line]]} {
        return [::hmShot::hvApplyComposite $line]
    }
    set vs [::hmShot::extractTag $line VS]
    if {$vs ne "" && [::hmShot::doViewset $vs]} { return 1 }
    set mtx [::hmShot::extractTag $line MTX]
    if {$mtx eq ""} {
        regsub -all {[^-0-9.eE+ ]} $line " " mtx
        regsub -all {\s+} [string trim $mtx] " " mtx
    }
    if {[llength $mtx] >= 16} {
        if {[::hmShot::appKind] eq "hv"} {
            return [::hmShot::hvApplyView $mtx]
        }
        if {[::hmShot::doViewset $mtx]} { return 1 }
        if {[::hmShot::hvApplyView $mtx]} { return 1 }
        catch {eval [linsert $mtx 0 hm_setviewmatrix]}
    }
    return 0
}
# Normalizuje pojedyncza linie do postaci "VS: <liczby>" (lub "" gdy niepoprawna).
proc ::hmShot::normalizeViewLine {s} {
    set s [string trim $s]
    if {$s eq "" || [string match "#*" $s]} { return "" }
    set up [string toupper $s]
    if {[string match "HV1:*" $up]} { return $s }
    if {[string match "*VS:*" $up] || [string match "*MTX:*" $up]} { return $s }
    regsub -all {[^-0-9.eE+ ]} $s " " nums
    regsub -all {\s+} [string trim $nums] " " nums
    if {[llength $nums] >= 16} { return "VS: $nums" }
    return ""
}
# Krotki, czytelny opis widoku (do etykiety obok miniatury).
proc ::hmShot::viewSummary {view} {
    regsub -all {[^-0-9.eE+ ]} $view " " nums
    regsub -all {\s+} [string trim $nums] " " nums
    set n [llength $nums]
    set head ""
    if {$n >= 3} { set head [join [lrange $nums 0 2] "  "] }
    return "kamera: $n warto\u015bci   \[$head \u2026\]"
}

#---------------------------------------------------------------------
#  Zrzut pelnowymiarowy (eksport)
#---------------------------------------------------------------------
# Stara sie poprawic jakosc zrzutu: antyaliasing ON + maks. jakosc JPEG +
# (jesli dostepne) wyzsza rozdzielczosc przechwytywania. Best-effort:
# uruchamia tylko komendy, ktore faktycznie istnieja w tym buildzie HM.
# Zwraca 1, gdy cokolwiek udalo sie ustawic.
proc ::hmShot::applyQuality {logVar} {
    upvar 1 $logVar log
    set any 0
    # antyaliasing ON (rozne mozliwe nazwy komend w roznych buildach)
    foreach a {
        {*setantialiasingmode 1} {*setantialiasmode 1} {*setantialiasing 1}
        {hm_setantialiasing 1} {*graphicantialias 1}
    } {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set any 1 ; break
    }
    # maksymalna jakosc kompresji JPEG
    foreach a {
        {*setjpegquality 100} {*setimagequality 100} {*jpegquality 100}
    } {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set any 1 ; break
    }
    # wyzsza rozdzielczosc zrzutu (supersampling), jesli dostepna (x2)
    foreach a {
        {*setcaptureresolution 2} {*setimageresolution 2} {*setscreencaptureresolution 2}
    } {
        if {![::hmShot::cmdExists [lindex $a 0]]} { continue }
        if {[catch {uplevel #0 $a} e]} { append log "  \[$a\] BLAD: $e\n" ; continue }
        append log "  \[$a\] -> wykonano\n" ; set any 1 ; break
    }
    catch {hm_redraw}
    return $any
}
# Zrzut do podanej sciezki. Najpierw wybrany format; jesli nie dziala w tym
# buildzie - przechodzi na format, ktory dziala (zapamietany/wykryty) i zapisuje
# plik z odpowiednim rozszerzeniem. Zwraca 1/0.
# Zrzut + SAMOKONTROLA tla: po zapisie sprawdza narozniki pliku i w razie
# niezgodnosci z wybranym tlem przebarwia je w pikselach (gwarantowany efekt,
# niezalezny od komend HM). Lapie tez falszywe sukcesy kalibracji.
proc ::hmShot::captureScreen {path} {
    set ok [::hmShot::captureScreenRaw $path]
    if {!$ok} { return 0 }
    set ext [string tolower [string trimleft [file extension $path] .]]
    set aext [expr {$::hmShot::lastExportFmt ne "" && $::hmShot::lastExportFmt ne $ext ? $::hmShot::lastExportFmt : $ext}]
    set actual "[file rootname $path].$aext"
    # SANITY: odrzuc zdegenerowany zrzut (np. 100x10 z blednej formy/sciezki) -
    # lepiej zglosic blad niz zapisac smiec.
    if {$aext in {jpg jpeg}} {
        set d [::hmShot::imageDims $actual]
        if {$d ne ""} {
            lassign $d iw ih
            if {$iw < 64 || $ih < 64} {
                catch {file delete -force $actual}
                return 0
            }
        }
    }
    set hex [::hmShot::bgHex $::hmShot::bgMode]
    if {$hex eq ""} { return 1 }
    if {$aext ni {jpg jpeg}} { return 1 }   ;# BMP przebarwiany u zrodla (jpgToBmp)
    set c [::hmShot::cornersOfFile $actual]
    if {$c eq "" || [::hmShot::cornersMatch $c $hex]} { return 1 }
    # tlo w pliku inne niz zadane -> samonaprawa
    set ::hmShot::capBgMethod "recolor"
    lassign [::hmShot::recolorFileInPlace $actual $hex] rok np
    if {$rok && $np ne $actual} {
        set ::hmShot::lastExportFmt [string tolower [string trimleft [file extension $np] .]]
    }
    return 1
}
proc ::hmShot::captureScreenRaw {path} {
    set ext [string tolower [string trimleft [file extension $path] .]]
    if {$ext eq ""} { set ext jpg }
    set log ""
    if {[::hmShot::captureFileTo $ext $path log]} { return 1 }
    # BMP: gdy natywne *bmpfilenamed nie tworzy pliku - konwersja z JPG czystym Tcl
    if {$ext eq "bmp" && [::hmShot::jpgToBmp $path]} { return 1 }
    # format wybrany nie zadzialal -> uzyj dzialajacego
    set wf $::hmShot::thumbFmt
    if {$wf eq ""} {
        foreach e {jpg png bmp tif} {
            set tmp [file join [file dirname $path] ".captest_[clock clicks].$e"]
            if {[::hmShot::captureFileTo $e $tmp log]} { catch {file delete -force $tmp} ; set wf $e ; break }
            catch {file delete -force $tmp}
        }
    }
    if {$wf ne "" && $wf ne $ext} {
        set np "[file rootname $path].$wf"
        if {[::hmShot::captureFileTo $wf $np log]} { set ::hmShot::lastExportFmt $wf ; return 1 }
    } elseif {$wf ne "" && $wf eq $ext} {
        if {[::hmShot::captureFileTo $wf $path log]} { return 1 }
    }
    return 0
}

#---------------------------------------------------------------------
#  Miniatury
#---------------------------------------------------------------------
# Wybiera ZAPISYWALNY folder na surowe zrzuty miniatur (sprawdza kilka lokalizacji).
proc ::hmShot::pickTmpBase {} {
    set cands {}
    foreach v {TEMP TMP TMPDIR} {
        if {[info exists ::env($v)] && $::env($v) ne ""} { lappend cands $::env($v) }
    }
    if {$::hmShot::shotDir ne ""} { lappend cands $::hmShot::shotDir }
    lappend cands [pwd]
    lappend cands "C:/Temp"
    lappend cands "/tmp"
    foreach b $cands {
        if {$b eq ""} { continue }
        set d [file join $b "hmShot_thumbs"]
        if {[catch {file mkdir $d}]} { continue }
        set tf [file join $d ".wtest"]
        if {![catch {set fh [open $tf w] ; close $fh ; file delete -force $tf}]} {
            return $d
        }
    }
    return [pwd]
}
# Mapuje rozszerzenie pliku na trzon nazwy komendy HM (*<trzon>filenamed).
# UWAGA: komendy to *jpegfilenamed i *tifffilenamed (nie *jpg/*tif).
proc ::hmShot::cmdStem {ext} {
    switch -- [string tolower $ext] {
        jpg - jpeg { return jpeg }
        tif - tiff { return tiff }
        default    { return [string tolower $ext] }
    }
}
# Normalizuje wybrany format eksportu do obslugiwanego: jpg (natywny *jpegfilenamed)
# lub bmp (konwersja czystym Tcl). Inne/nieznane -> jpg.
proc ::hmShot::exportExt {} {
    set e [string tolower [string trim $::hmShot::shotExt]]
    if {$e in {jpg jpeg}} { return jpg }
    if {$e eq "bmp"}      { return bmp }
    return jpg
}
# Robi zrzut ekranu BEZPOSREDNIO do podanej sciezki docelowej. Zwraca 1/0.
# Probuje *<stem>filenamed (poprawny trzon nazwy), forme natywna i alternatywy;
# czeka na plik; jesli HM zapisze plik gdzie indziej / pod inna nazwa - przenosi
# go do celu. Do 'logVar' dopisuje przebieg.
proc ::hmShot::captureFileTo {ext targetPath logVar} {
    upvar 1 $logVar log
    # Skalibrowana metoda hwi (HWD API) - probowana jako pierwsza; przy niepowodzeniu
    # przechodzimy do klasycznych komend panelowych.
    if {$::hmShot::captureMethod eq "hwi" && $::hmShot::hwiForm ne ""} {
        if {[::hmShot::runHwiForm $::hmShot::hwiForm $ext $targetPath]} {
            append log "  \[hwi\] -> OK ($targetPath)\n"
            return 1
        }
        append log "  \[hwi\] -> niepowodzenie dla .$ext, probuje komend panelowych\n"
    }
    set stem [::hmShot::cmdStem $ext]
    set tgt  $targetPath
    set ntgt [file nativename $tgt]
    set tdir [file dirname $tgt]
    set cwd  [pwd]
    set watch [list $tdir]
    if {[lsearch -exact $watch $cwd] < 0} { lappend watch $cwd }
    array set before {}
    foreach d $watch { catch {set before($d) [glob -nocomplain -directory $d *]} }
    append log "  cel: $tgt\n"
    set forms [list \
        [list *${stem}filenamed $tgt] \
        [list *${stem}filenamed $ntgt]]
    foreach alt [list [list hm_capturescreentofile $tgt] [list hm_capturescreentofile $ntgt]] {
        set nm [lindex $alt 0]
        if {[llength [uplevel #0 [list info commands ::$nm]]] || [llength [uplevel #0 [list info commands $nm]]]} {
            lappend forms $alt
        }
    }
    foreach c $forms {
        set err ""
        if {[catch {uplevel #0 $c} err]} { append log "    \[$c\] -> BLAD: $err\n" ; continue }
        append log "    \[$c\] -> wykonano\n"
        catch {update}
        for {set i 0} {$i < 12} {incr i} {
            if {[file exists $tgt] && [file size $tgt] > 0} { append log "    -> OK ([file size $tgt] B)\n" ; return 1 }
            # HM zapisal plik gdzie indziej lub pod inna nazwa?
            foreach d $watch {
                if {![info exists before($d)]} continue
                foreach f [glob -nocomplain -directory $d *] {
                    if {[lsearch -exact $before($d) $f] < 0 && ![string match "*.wtest" $f] \
                            && [file isfile $f] && [file size $f] > 0} {
                        if {$f ne $tgt} { catch {file rename -force $f $tgt} }
                        if {[file exists $tgt] && [file size $tgt] > 0} { append log "    -> OK (z $f)\n" ; return 1 }
                    }
                }
            }
            catch {after 100}
        }
    }
    # Ostatnia szansa (m.in. HyperView): sonduj formy zrzutu przez API hwi.
    # Dzialajaca forma zostaje zapamietana i uzywana od razu.
    if {$::hmShot::hwiForm eq "" && [::hmShot::probeHwiFile]} {
        set ::hmShot::captureMethod "hwi"
        if {[::hmShot::runHwiForm $::hmShot::hwiForm $ext $targetPath]} {
            append log "  \[hwi:auto\] -> OK ($targetPath)\n"
            return 1
        }
    }
    append log "    -> brak pliku\n"
    return 0
}
# Sonduje formy zrzutu hwi wylacznie pod katem POWSTANIA pliku (bez oceny tla).
# Uzywane, gdy komendy panelowe (*jpegfilenamed itd.) nie istnieja - np. HyperView.
proc ::hmShot::probeHwiFile {} {
    if {$::hmShot::hwiForm ne ""} { return 1 }
    if {![::hmShot::cmdExists hwi]} { return 0 }
    foreach ft [::hmShot::hwiForms] {
        lassign $ft tpl tok
        set ::hmShot::hwiJpegTok $tok
        set p [file join [::hmShot::pickTmpBase] "hwif_[clock clicks].jpg"]
        if {[::hmShot::runHwiForm $tpl jpg $p]} {
            # odrzuc formy oddajace zdegenerowany obrazek (np. 100x10)
            set d [::hmShot::imageDims $p]
            catch {file delete -force $p}
            if {$d ne ""} {
                lassign $d iw ih
                if {$iw < 64 || $ih < 64} { continue }
            }
            set ::hmShot::hwiForm $tpl
            return 1
        }
        catch {file delete -force $p}
    }
    return 0
}
# Robi zrzut do pliku tymczasowego o danym rozszerzeniu. Zwraca sciezke lub "".
proc ::hmShot::captureTo {ext logVar} {
    upvar 1 $logVar log
    set tdir [::hmShot::pickTmpBase]
    set path [file join $tdir "cap_[clock clicks].$ext"]
    append log "  Folder tymczasowy: $tdir\n"
    if {[::hmShot::captureFileTo $ext $path log]} { return $path }
    return ""
}
# Sprawdza, czy Tk potrafi wczytac obrazy (PNG natywnie w Tk 8.6; ew. pakiet Img).
proc ::hmShot::checkImgSupport {} {
    set ok 0
    catch { if {[package vsatisfies [package require Tk] 8.6-]} { set ok 1 } }
    catch { package require Img ; set ok 1 }
    set ::hmShot::imgOk $ok
    ::hmShot::buildPlaceholder
}
# Buduje szara zaslepke (gdy brak miniatury) - jednolite pole o rozmiarze miniatury.
proc ::hmShot::buildPlaceholder {} {
    set W $::hmShot::thumbW ; set H $::hmShot::thumbH
    if {[catch {set img [image create photo -width $W -height $H]}]} { return }
    catch {
        $img put "#dadada" -to 0 0 $W $H
        $img put "#9e9e9e" -to 0 0 $W 1
        $img put "#9e9e9e" -to 0 [expr {$H-1}] $W $H
        $img put "#9e9e9e" -to 0 0 1 $H
        $img put "#9e9e9e" -to [expr {$W-1}] 0 $W $H
    }
    set ::hmShot::phImg $img
}
proc ::hmShot::placeholderPhoto {} {
    if {$::hmShot::phImg eq "" || [lsearch -exact [image names] $::hmShot::phImg] < 0} {
        ::hmShot::buildPlaceholder
    }
    return $::hmShot::phImg
}
# Dekoduje BMP (24/32 bpp, nieskompresowany) z pomniejszeniem (najblizszy sasiad).
# Zwraca {ow oh wiersze}, gdzie kazdy wiersz to lista #RRGGBB (od gory do dolu).
# Przy bledzie/nieobslugiwanym formacie zwraca {}.  Czysty Tcl - bez Tk i pakietow.
proc ::hmShot::bmpDecodeSampled {raw} {
    if {[string length $raw] < 54} { return {} }
    if {[string range $raw 0 1] ne "BM"} { return {} }
    # offset danych pikseli (z naglowka pliku) dziala dla naglowkow v3/v4/v5,
    # bo pola width/height/bpp/compression sa zawsze w tych samych miejscach.
    if {[binary scan $raw "@10 iu @18 i @22 i @28 su @30 iu" off w h bpp comp] != 5} { return {} }
    if {$w <= 0 || $h == 0} { return {} }
    if {$comp != 0} { return {} }                 ;# tylko nieskompresowane (BI_RGB)
    if {$bpp != 24 && $bpp != 32} { return {} }
    set topdown 0
    if {$h < 0} { set topdown 1 ; set h [expr {-$h}] }
    set bpB     [expr {$bpp/8}]
    set rowSize [expr {(($bpp*$w + 31)/32)*4}]     ;# wiersz wyrownany do 4 bajtow
    set tw $::hmShot::thumbW ; set th $::hmShot::thumbH
    set sx [expr {$w/$tw}] ; if {$sx < 1} {set sx 1}
    set sy [expr {$h/$th}] ; if {$sy < 1} {set sy 1}
    set step [expr {$sx > $sy ? $sx : $sy}] ; if {$step < 1} {set step 1}
    set ow [expr {$w/$step}] ; if {$ow < 1} {set ow 1}
    set oh [expr {$h/$step}] ; if {$oh < 1} {set oh 1}
    set rows {}
    for {set oy 0} {$oy < $oh} {incr oy} {
        set iy [expr {$oy*$step}] ; if {$iy >= $h} {set iy [expr {$h-1}]}
        if {$topdown} { set fr $iy } else { set fr [expr {$h-1-$iy}] }   ;# BMP zwykle bottom-up
        set base [expr {$off + $fr*$rowSize}]
        set rb   [string range $raw $base [expr {$base + $rowSize - 1}]]
        set cols {}
        for {set ox 0} {$ox < $ow} {incr ox} {
            set p [expr {$ox*$step*$bpB}]
            if {[binary scan [string range $rb $p [expr {$p+2}]] cucucu b g r] != 3} {
                lappend cols "#000000"
            } else {
                lappend cols [format "#%02x%02x%02x" $r $g $b]   ;# BMP trzyma BGR
            }
        }
        lappend rows $cols
    }
    return [list $ow $oh $rows]
}
# Wczytuje plik BMP i buduje pomniejszony obraz Tk. Zwraca uchwyt lub "".
proc ::hmShot::bmpToThumb {path} {
    if {![file exists $path]} { return "" }
    set raw ""
    if {[catch {set fh [open $path rb] ; fconfigure $fh -translation binary ; set raw [read $fh] ; close $fh}]} { return "" }
    set dec [::hmShot::bmpDecodeSampled $raw]
    if {![llength $dec]} { return "" }
    lassign $dec ow oh rows
    if {$ow < 1 || $oh < 1} { return "" }
    set img ""
    if {[catch {set img [image create photo -width $ow -height $oh]}]} { return "" }
    set oy 0
    foreach r $rows {
        if {[catch {$img put [list $r] -to 0 $oy}]} { catch {image delete $img} ; return "" }
        incr oy
    }
    return $img
}
# Zapis photo -> BMP 24-bit (BI_RGB), czysty Tcl (rdzen Tk 8.5 nie zapisuje BMP).
# Szybko: wiersz kolorow "#rrggbb..." -> regsub przestawia na "bbggrr" -> jeden
# 'binary format H*' na wiersz. Wiersze od dolu, kazdy dopelniony do 4 bajtow.
proc ::hmShot::writeBmpFromPhoto {photo path} {
    set rows {}
    if {[catch {set rows [$photo data]}] || ![llength $rows]} { return 0 }
    set w [llength [lindex $rows 0]] ; set h [llength $rows]
    if {$w < 1 || $h < 1} { return 0 }
    if {![regexp {^#[0-9a-fA-F]{6}$} [lindex [lindex $rows 0] 0]]} { return 0 }
    set rowBytes [expr {$w*3}]
    set pad [expr {(4 - ($rowBytes % 4)) % 4}]
    set imgSize [expr {($rowBytes + $pad) * $h}]
    set fileSize [expr {54 + $imgSize}]
    if {[catch {set fh [open $path wb]}]} { return 0 }
    puts -nonewline $fh [binary format a2issi "BM" $fileSize 0 0 54]
    puts -nonewline $fh [binary format iiissiiiiii 40 $w $h 1 24 0 $imgSize 2835 2835 0 0]
    set padB "" ; if {$pad} { set padB [binary format a$pad ""] }
    for {set y [expr {$h-1}]} {$y >= 0} {incr y -1} {
        set hexrow [join [lindex $rows $y] ""]
        regsub -all {#(..)(..)(..)} $hexrow {\3\2\1} hexrow
        if {[catch {puts -nonewline $fh [binary format H* $hexrow]}]} { catch {close $fh} ; catch {file delete -force $path} ; return 0 }
        if {$pad} { puts -nonewline $fh $padB }
    }
    close $fh
    return 1
}
# Zrzut do BMP przez konwersje: *jpegfilenamed (jedyny pewny) -> image -file ->
# zapis BMP czystym Tcl. Zwraca 1/0.
proc ::hmShot::jpgToBmp {bmpPath} {
    if {[uplevel #0 {info commands image}] eq "" && [uplevel #0 {info commands ::image}] eq ""} { return 0 }
    set log ""
    set jp [::hmShot::captureTo jpg log]
    if {$jp eq ""} { return 0 }
    set img ""
    catch {set img [image create photo -file $jp]}
    catch {file delete -force $jp}
    if {$img eq ""} { return 0 }
    set ok [::hmShot::writeBmpFromPhoto $img $bmpPath]
    catch {image delete $img}
    return [expr {$ok && [file isfile $bmpPath] && [file size $bmpPath] > 0}]
}
# Wczytuje plik zrzutu do miniatury wg formatu: BMP -> wlasny parser,
# pozostale (jpg/png/tif) -> image -file (jesli Tk czyta dany format).
proc ::hmShot::loadThumbFile {f ext} {
    if {[string tolower $ext] eq "bmp"} { return [::hmShot::bmpToThumb $f] }
    return [::hmShot::makeThumbPhoto $f]
}
# Probuje jednego formatu: zrzut -> wczytanie -> miniatura. Zwraca uchwyt lub "".
# Gdy podano fullVar, PELNY plik zrzutu nie jest kasowany, tylko przekazywany
# wolajacemu (przejmuje go na wlasnosc) - z niego powstala miniatura, wiec
# klatka i podglad to DOKLADNIE ta sama chwila.
proc ::hmShot::grabThumbFmt {ext {fullVar ""}} {
    set log "format $ext:\n"
    set f [::hmShot::captureTo $ext log]
    set ::hmShot::lastThumbLog $log
    if {$f eq ""} { return "" }
    set t [::hmShot::loadThumbFile $f $ext]
    if {$fullVar ne "" && $t ne ""} {
        upvar 1 $fullVar fullOut
        set fullOut $f
    } else {
        catch {file delete -force $f}
    }
    return $t
}
# Robi zrzut AKTUALNEGO ekranu i zwraca GOTOWY uchwyt miniatury (photo) lub "".
# Najpierw probuje zapamietany dzialajacy format; inaczej przechodzi po liscie
# (jpg/png/bmp/tif) i zapamietuje pierwszy, ktory daje czytelny obraz.
proc ::hmShot::grabThumb {{fullVar ""}} {
    set fv ""
    if {$fullVar ne ""} { upvar 1 $fullVar fullOut ; set fullOut "" ; set fv fullOut }
    # Jesli wybrano kolor tla, ustaw go przed zrzutem miniatury, aby podglad
    # odpowiadal temu, co bedzie na eksporcie (HM potrafi renderowac zrzut z innym tlem).
    set bg [::hmShot::bgHex $::hmShot::bgMode]
    if {$bg ne ""} { set blog "" ; ::hmShot::applyBg $bg blog ; ::hmShot::ensureCaptureBg $bg }
    catch {hm_redraw}
    update idletasks ; catch {after 120}
    # 1) zapamietany dzialajacy format (szybka sciezka)
    if {$::hmShot::thumbFmt ne ""} {
        set t [::hmShot::grabThumbFmt $::hmShot::thumbFmt $fv]
        if {$t ne ""} { return $t }
        set ::hmShot::thumbFmt ""
    }
    # 2) kolejnosc prob: na buildach z PNG zaczynamy od PNG (lossless), inaczej od JPG
    if {$::hmShot::imgOk} {
        set order {png jpg bmp tif}
    } else {
        set order {jpg png bmp tif}
    }
    foreach ext $order {
        set t [::hmShot::grabThumbFmt $ext $fv]
        if {$t ne ""} { set ::hmShot::thumbFmt $ext ; return $t }
    }
    return ""
}
# Wylistowuje dostepne w tym buildzie komendy potencjalnie sluzace do zrzutu.
proc ::hmShot::probeCommands {} {
    set out "Dost\u0119pne komendy zrzutu (info commands):\n"
    foreach pat {*filenamed *jpeg* *png* *bmp* *tif* *capture* *hardcopy* *screen* *snapshot* *grab* *image*to* *plot*file* *antialias* *quality* *resolution* *supersample*} {
        set lst {}
        catch {set lst [lsort -unique [concat [uplevel #0 [list info commands ::$pat]] [uplevel #0 [list info commands $pat]]]]}
        if {[llength $lst] > 30} { set lst [concat [lrange $lst 0 29] ...] }
        append out "  $pat : $lst\n"
    }
    catch { append out "  hwi istnieje: [expr {[llength [uplevel #0 {info commands ::hwi}]] ? {TAK} : {NIE}}]\n" }
    return $out
}
# Diagnostyka: listuje dostepne komendy, probuje wszystkich formatow i raportuje,
# co powstalo i czy da sie to wczytac. Wynik -> okienko + plik log (do wklejenia).
proc ::hmShot::diagThumb {} {
    catch {hm_redraw} ; update idletasks ; catch {after 150}
    set rep "DIAGNOSTYKA ZRZUTU MINIATURY\n"
    append rep "Tcl: [info patchlevel]"
    catch {append rep "    Tk: [package require Tk]"}
    append rep "\nimgOk (PNG czytany przez Tk): $::hmShot::imgOk\n"
    append rep "pwd: [pwd]\n"
    append rep "TEMP: [expr {[info exists ::env(TEMP)] ? $::env(TEMP) : {-}}]\n\n"
    append rep [::hmShot::probeCommands]
    append rep "\n"
    set anyFile 0
    foreach ext {jpg png bmp tif} {
        append rep "== format: $ext ==\n"
        set cmd "*[::hmShot::cmdStem $ext]filenamed"
        set exists [expr {[llength [uplevel #0 [list info commands ::$cmd]]] || [llength [uplevel #0 [list info commands $cmd]]]}]
        append rep "  komenda $cmd istnieje: [expr {$exists ? {TAK} : {NIE}}]\n"
        set log ""
        set f [::hmShot::captureTo $ext log]
        append rep $log
        if {$f ne ""} {
            set anyFile 1
            if {$ext eq "bmp"} {
                set t [::hmShot::bmpToThumb $f]
                append rep "  parser BMP: [expr {$t ne {} ? {OK - czytelny} : {odrzucony}}]\n"
                if {$t ne ""} { catch {image delete $t} }
            } else {
                set t "" ; catch {set t [image create photo -file $f]}
                append rep "  Tk (image -file): [expr {$t ne {} ? {OK - czytelny} : {nieczytelny}}]\n"
                if {$t ne ""} { catch {image delete $t} }
            }
            catch {file delete -force $f}
        }
        append rep "\n"
    }
    if {!$anyFile} {
        append rep "WNIOSEK: \u017cadna komenda *...filenamed nie utworzy\u0142a pliku.\n"
        append rep "Zerknij na list\u0119 \u201eDost\u0119pne komendy zrzutu\u201d powy\u017cej \u2013 wska\u017ce,\n"
        append rep "jaki mechanizm zrzutu jest w tym buildzie HM. Wklej autorowi\n"
        append rep "ten raport (lub plik diag_miniatury.txt), a podepn\u0119 w\u0142a\u015bciw\u0105 komend\u0119.\n"
    }
    # --- wykrywanie sciezki otwartego modelu .hm (tylko nieinteraktywnie) ---
    append rep "\n== \u015acie\u017cka modelu (.hm) \u2013 nieinteraktywnie ==\n"
    append rep "  hm_info istnieje: [expr {[::hmShot::cmdExists hm_info] ? {TAK} : {NIE}}]\n"
    if {[::hmShot::cmdExists hm_info]} {
        # Komunikaty bledow zwykle wypisuja liste dozwolonych opcji/kluczy -> pokazujemy je.
        append rep "\n  -- pelne komunikaty (ujawniaja dozwolone opcje) --\n"
        foreach probe {
            {hm_info}
            {hm_info ZZBADSUBCMD}
            {hm_info -appinfo ZZBADKEY}
            {hm_info -appinfo CURRENTMODEL}
        } {
            set msg "" ; set tag "OK"
            if {[catch {set msg [uplevel #0 $probe]} e]} { set msg $e ; set tag "BLAD" }
            set msg [string map {\n " | "} [string trim $msg]]
            if {[string length $msg] > 300} { set msg "[string range $msg 0 299]..." }
            append rep "  \[$tag\] $probe -> $msg\n"
        }
        # Formy bez -appinfo (rozne buildy maja rozna skladnie).
        append rep "\n  -- formy zapytania o plik/sciezke --\n"
        foreach probe {
            {hm_info hmfilename} {hm_info filename} {hm_info currentfile}
            {hm_info modelname} {hm_info model} {hm_info file} {hm_info path}
            {hm_info -appinfo CURRENTDIRECTORY} {hm_info -appinfo STARTDIRECTORY}
            {hm_info -appinfo WORKINGDIRECTORY}
        } {
            set msg "" ; set tag "OK"
            if {[catch {set msg [uplevel #0 $probe]} e]} { set msg $e ; set tag "BLAD" }
            set msg [string map {\n " | "} [string trim $msg]]
            if {[string length $msg] > 200} { set msg "[string range $msg 0 199]..." }
            append rep "  \[$tag\] $probe -> $msg\n"
        }
    }
    append rep "\n  wykryty folder modelu: [expr {[::hmShot::getModelDir] ne {} ? [::hmShot::getModelDir] : {-}}]\n"
    append rep "(Przy\u015blij autorowi linie powy\u017cej \u2013 z komunikat\u00f3w wida\u0107 dozwolone opcje hm_info,\n"
    append rep " a z nich wybierze on komend\u0119 zwracaj\u0105c\u0105 \u015bcie\u017ck\u0119 .hm. Wtedy auto-wykrywanie zadzia\u0142a.)\n"
    set lp ""
    catch {
        set lp [file join [::hmShot::pickTmpBase] "diag_miniatury.txt"]
        set fh [open $lp w] ; puts $fh $rep ; close $fh
    }
    if {$lp ne ""} { append rep "\nZapisano log do: $lp\n" }
    catch {tk_messageBox -type ok -icon info -title [::hmShot::T "Diagnostyka miniatur" "Thumbnail diagnostics"] -message $rep}
    ::hmShot::setStatus [::hmShot::T "Diagnostyka zako\u0144czona \u2013 wklej raport autorowi." "Diagnostics finished \u2013 paste the report to the author."]
    return $rep
}
# Wczytuje PNG i skaluje w dol do <= thumbW x thumbH. Zwraca uchwyt obrazu lub "".
proc ::hmShot::makeThumbPhoto {png} {
    if {![file exists $png]} { return "" }
    set full ""
    if {[catch {set full [image create photo -file $png]}]} { return "" }
    set w [image width $full] ; set h [image height $full]
    if {$w <= 0 || $h <= 0} { catch {image delete $full} ; return "" }
    set fx [expr {int(ceil(double($w)/$::hmShot::thumbW))}]
    set fy [expr {int(ceil(double($h)/$::hmShot::thumbH))}]
    set f [expr {$fx > $fy ? $fx : $fy}] ; if {$f < 1} { set f 1 }
    set thumb [image create photo]
    if {[catch {$thumb copy $full -subsample $f $f}]} {
        catch {image delete $full} ; catch {image delete $thumb} ; return ""
    }
    catch {image delete $full}
    return $thumb
}

#---------------------------------------------------------------------
#  Model danych - operacje na liscie widokow
#---------------------------------------------------------------------
proc ::hmShot::recIndex {id} {
    set i 0
    foreach rec $::hmShot::views {
        if {[dict get $rec id] == $id} { return $i }
        incr i
    }
    return -1
}
# Lista zaznaczonych widokow (stringi VS:/MTX:) - do eksportu.
proc ::hmShot::selectedViews {} {
    set out {}
    foreach rec $::hmShot::views {
        set id [dict get $rec id]
        if {[info exists ::hmShot::selArr($id)] && $::hmShot::selArr($id)} {
            lappend out [dict get $rec view]
        }
    }
    return $out
}
# Pelne rekordy zaznaczonych widokow (do raportu - z nazwami).
proc ::hmShot::selectedRecords {} {
    set out {}
    foreach rec $::hmShot::views {
        set id [dict get $rec id]
        if {[info exists ::hmShot::selArr($id)] && $::hmShot::selArr($id)} { lappend out $rec }
    }
    return $out
}
# Liczby (skladowe macierzy/VS) z linii widoku.
proc ::hmShot::viewVals {view} {
    regsub -all {[^-0-9.eE+ ]} $view " " nums
    regsub -all {\s+} [string trim $nums] " " nums
    return $nums
}
proc ::hmShot::xmlEsc {s} { return [string map {& &amp; < &lt; > &gt; \" &quot;} $s] }
proc ::hmShot::isPlainNum {v} { return [regexp {^-?[0-9]+(\.[0-9]+)?$} $v] }
# Raport tekstowy: czytelna lista (nr, nazwa, plik, pelny VS).
proc ::hmShot::writeTxtReport {path rows} {
    set fh [open $path w]
    catch {fconfigure $fh -encoding utf-8}
    puts $fh "RAPORT WIDOK\u00d3W (HyperMesh)"
    puts $fh "Wygenerowano: [clock format [clock seconds] -format {%Y-%m-%d %H:%M}]"
    puts $fh "Liczba widok\u00f3w: [llength $rows]"
    puts $fh [string repeat = 64]
    foreach r $rows {
        set line "\[[dict get $r nr]\] [dict get $r name]"
        set fl [dict get $r file]
        if {$fl ne ""} { append line "   (plik: $fl)" }
        puts $fh ""
        puts $fh $line
        puts $fh [dict get $r view]
    }
    # Podsumowanie: wszystkie VS, kazdy w osobnej linii (do skopiowania naraz).
    puts $fh ""
    puts $fh [string repeat = 64]
    puts $fh "WSZYSTKIE WIDOKI (VS) \u2013 do skopiowania:"
    puts $fh ""
    foreach r $rows { puts $fh [dict get $r view] }
    close $fh
}
# Komorka SpreadsheetML.
proc ::hmShot::xlsCell {styleId type val} {
    set st "" ; if {$styleId ne ""} { set st " ss:StyleID=\"$styleId\"" }
    if {$type eq "Number" && ![::hmShot::isPlainNum $val]} { set type String }
    return "<Cell$st><Data ss:Type=\"$type\">[::hmShot::xmlEsc $val]</Data></Cell>"
}
# Raport w formacie SpreadsheetML (.xls) - otwiera sie wprost w Excelu, kazda
# skladowa VS w osobnej kolumnie (v1..vN) + pelny VS i nazwa/plik.
proc ::hmShot::writeXlsReport {path rows} {
    set maxN 0
    foreach r $rows {
        set n [llength [::hmShot::viewVals [dict get $r view]]]
        if {$n > $maxN} { set maxN $n }
    }
    set fh [open $path w]
    catch {fconfigure $fh -encoding utf-8}
    puts $fh {<?xml version="1.0" encoding="UTF-8"?>}
    puts $fh {<?mso-application progid="Excel.Sheet"?>}
    puts $fh {<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">}
    puts $fh { <Styles>}
    puts $fh {  <Style ss:ID="hdr"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#1C5A96" ss:Pattern="Solid"/></Style>}
    puts $fh {  <Style ss:ID="mono"><Font ss:FontName="Consolas"/></Style>}
    puts $fh { </Styles>}
    puts $fh { <Worksheet ss:Name="Widoki">}
    puts $fh {  <Table>}
    set hdr "   <Row>"
    append hdr [::hmShot::xlsCell hdr String "Nr"]
    append hdr [::hmShot::xlsCell hdr String "Nazwa"]
    append hdr [::hmShot::xlsCell hdr String "Plik"]
    append hdr [::hmShot::xlsCell hdr String "VS (pe\u0142ny)"]
    for {set i 1} {$i <= $maxN} {incr i} { append hdr [::hmShot::xlsCell hdr String "v$i"] }
    append hdr "</Row>"
    puts $fh $hdr
    foreach r $rows {
        set vals [::hmShot::viewVals [dict get $r view]]
        set row "   <Row>"
        append row [::hmShot::xlsCell "" Number [dict get $r nr]]
        append row [::hmShot::xlsCell "" String [dict get $r name]]
        append row [::hmShot::xlsCell "" String [dict get $r file]]
        append row [::hmShot::xlsCell mono String [dict get $r view]]
        foreach v $vals { append row [::hmShot::xlsCell "" Number $v] }
        append row "</Row>"
        puts $fh $row
    }
    # Podsumowanie: wszystkie VS, kazdy w osobnym wierszu (kolumna A) do skopiowania.
    puts $fh {   <Row></Row>}
    puts $fh "   <Row>[::hmShot::xlsCell hdr String "WSZYSTKIE WIDOKI (VS) \u2013 do skopiowania:"]</Row>"
    foreach r $rows {
        puts $fh "   <Row>[::hmShot::xlsCell mono String [dict get $r view]]</Row>"
    }
    puts $fh {  </Table>}
    puts $fh { </Worksheet>}
    puts $fh {</Workbook>}
    close $fh
}
# Zapisuje miniature (photo) do pliku obrazu (PNG/GIF) - best-effort. Zwraca sciezke lub "".
proc ::hmShot::writeThumbFile {photo base} {
    if {$photo eq "" || [lsearch -exact [image names] $photo] < 0} { return "" }
    foreach {fmt ext} {png .png gif .gif} {
        set p "$base$ext"
        if {![catch {$photo write $p -format $fmt}]} { return $p }
    }
    return ""
}
# Szybki koder base64 (Tcl 8.5 nie ma 'binary encode base64'). 'binary scan B*' ->
# string map (6-bitowe ciagi -> znaki) -> dopelnienie '='. Operacje C-level.
proc ::hmShot::b64enc {bytes} {
    binary scan $bytes B* bits
    if {![info exists bits] || $bits eq ""} { return "" }
    variable b64fwd
    if {![info exists b64fwd]} {
        set chars "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        set b64fwd {}
        for {set i 0} {$i < 64} {incr i} {
            set bb ""
            for {set b 5} {$b >= 0} {incr b -1} { append bb [expr {($i >> $b) & 1}] }
            lappend b64fwd $bb [string index $chars $i]
        }
    }
    set len [string length $bits]
    set pad [expr {(6 - ($len % 6)) % 6}]
    if {$pad} { append bits [string repeat 0 $pad] }
    set b64 [string map $b64fwd $bits]
    if {$pad} { append b64 [string repeat = [expr {$pad/2}]] }
    return $b64
}
# Szybki dekoder base64 (Tcl 8.5 nie ma 'binary decode base64'). Zamiast petli po
# bajtach: mapuje znaki -> 6-bitowe ciagi (string map, C-level), a potem jeden
# 'binary format B*'. Buduje tabele raz. NIE uzywa 'format %b' (brak w Tcl 8.5).
proc ::hmShot::b64dec {s} {
    variable b64bits
    if {![info exists b64bits]} {
        set chars "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        set b64bits {}
        for {set i 0} {$i < 64} {incr i} {
            set bb ""
            for {set b 5} {$b >= 0} {incr b -1} { append bb [expr {($i >> $b) & 1}] }
            lappend b64bits [string index $chars $i] $bb
        }
    }
    regsub -all {[^A-Za-z0-9+/]} $s "" s
    if {$s eq ""} { return "" }
    set bits [string map $b64bits $s]
    set n [expr {[string length $bits] & ~7}]   ;# przytnij do wielokrotnosci 8 bitow
    if {$n <= 0} { return "" }
    return [binary format B* [string range $bits 0 [expr {$n-1}]]]
}
# Escapowanie/odsescapowanie pol sesji (jeden rekord = jedna linia, pola \t-rozdzielane).
proc ::hmShot::sesEsc {s} {
    return [string map [list "\\" "\\\\" "\t" "\\t" "\n" "\\n" "\r" "\\r"] $s]
}
proc ::hmShot::sesUnesc {s} {
    return [string map [list "\\\\" "\\" "\\t" "\t" "\\n" "\n" "\\r" "\r"] $s]
}
# Zamienia miniature (photo) na {fmt b64}. 'order' = kolejnosc prob formatow.
# Dla przegladarki: png/jpeg/gif (gif=256 kol.). Dla ponownego wczytania do makra
# lepszy jest PPM (pelny kolor, bezstratny) zamiast GIF. Weryfikuje odczyt.
proc ::hmShot::thumbToDataUri {photo {order {png jpeg gif ppm}}} {
    if {$photo eq "" || [lsearch -exact [image names] $photo] < 0} { return {} }
    set tmp [file join [::hmShot::pickTmpBase] "hmses_[clock clicks].img"]
    foreach fmt $order {
        if {[catch {$photo write $tmp -format $fmt}]} { continue }
        set bytes ""
        if {[catch {
            set fh [open $tmp rb] ; set bytes [read $fh] ; close $fh
        }]} { catch {file delete -force $tmp} ; continue }
        catch {file delete -force $tmp}
        if {$bytes eq ""} { continue }
        set b64 [::hmShot::b64enc $bytes]
        # weryfikacja: czy makro odczyta to z powrotem?
        set test ""
        if {[catch {set test [image create photo -data $b64]}]} { continue }
        catch {image delete $test}
        return [list $fmt $b64]
    }
    catch {file delete -force $tmp}
    return {}
}
# Osadza GOTOWY plik obrazu (np. pelny zrzut .jpg) jako {mime b64} bez udzialu Tk
# (pelna rozdzielczosc i pelny kolor). Zwraca {} gdy pliku nie ma / format nie do podgladu.
proc ::hmShot::fileToDataUri {path} {
    if {$path eq "" || ![file isfile $path]} { return {} }
    set ext [string tolower [string trimleft [file extension $path] .]]
    switch -- $ext {
        jpg - jpeg { set mime jpeg }
        png        { set mime png }
        gif        { set mime gif }
        bmp        { set mime bmp }
        default    { return {} }
    }
    set bytes ""
    if {[catch {set fh [open $path rb] ; set bytes [read $fh] ; close $fh}]} { return {} }
    if {$bytes eq ""} { return {} }
    return [list $mime [::hmShot::b64enc $bytes]]
}
# Pomniejsza photo do rozmiaru miniatury (<= thumbW x thumbH), zwraca nowy uchwyt
# i kasuje oryginal. Gdy obraz juz maly - zwraca go bez zmian.
proc ::hmShot::scalePhotoToThumb {full} {
    if {$full eq "" || [lsearch -exact [image names] $full] < 0} { return $full }
    set w 0 ; set h 0
    catch {set w [image width $full]} ; catch {set h [image height $full]}
    if {$w <= 0 || $h <= 0} { return $full }
    if {$w <= $::hmShot::thumbW && $h <= $::hmShot::thumbH} { return $full }
    set fx [expr {int(ceil(double($w)/$::hmShot::thumbW))}]
    set fy [expr {int(ceil(double($h)/$::hmShot::thumbH))}]
    set f [expr {$fx > $fy ? $fx : $fy}] ; if {$f < 1} { set f 1 }
    set thumb [image create photo]
    if {[catch {$thumb copy $full -subsample $f $f}]} { catch {image delete $thumb} ; return $full }
    catch {image delete $full}
    return $thumb
}
# Koduje miniature do bloku sesji jako PPM (pelny kolor, bezstratny). Odczyt nastepuje
# przez plik tymczasowy + image -file (ten build NIE czyta PPM/JPEG przez -data), wiec
# tu NIE weryfikujemy przez -data. Zwraca {ppm b64} lub {}.
proc ::hmShot::thumbToSession {photo} {
    if {$photo eq "" || [lsearch -exact [image names] $photo] < 0} { return {} }
    set tmp [file join [::hmShot::pickTmpBase] "hmses_[clock clicks].ppm"]
    if {[catch {$photo write $tmp -format ppm}]} { catch {file delete -force $tmp} ; return {} }
    set bytes ""
    if {[catch {set fh [open $tmp rb] ; set bytes [read $fh] ; close $fh}]} { catch {file delete -force $tmp} ; return {} }
    catch {file delete -force $tmp}
    if {$bytes eq ""} { return {} }
    return [list ppm [::hmShot::b64enc $bytes]]
}
# Raport HTML SAMODZIELNY: miniatury osadzone (data-URI), otwiera sie w przegladarce,
# a makro potrafi go ponownie wczytac (ukryty blok HMSESSION z danymi widokow).
# rows: slowniki z polami nr, name, view, thumb (uchwyt photo lub ""), opcj. file.
proc ::hmShot::writeHtmlReport {path rows} {
    set maxN 0
    foreach r $rows {
        set n [llength [::hmShot::viewVals [dict get $r view]]]
        if {$n > $maxN} { set maxN $n }
    }
    # Blok sesji (odczyt do makra przez plik tymczasowy + image -file): miniatura PPM
    # (pelny kolor). Widoczna tabela: pelny plik zrzutu (ostry, pelny kolor), a gdy
    # go brak - miniatura w formacie dla przegladarki.
    set sess {} ; set vis {}
    foreach r $rows {
        set t "" ; if {[dict exists $r thumb]} { set t [dict get $r thumb] }
        lappend sess [::hmShot::thumbToSession $t]
        set p "" ; if {[dict exists $r path]} { set p [dict get $r path] }
        set full [::hmShot::fileToDataUri $p]
        if {[llength $full]} {
            lappend vis $full
        } else {
            lappend vis [::hmShot::thumbToDataUri $t {png jpeg gif ppm}]
        }
    }
    set fh [open $path w]
    catch {fconfigure $fh -encoding utf-8}
    puts $fh {<!DOCTYPE html><html><head><meta charset="utf-8"><title>Raport widokow</title><style>}
    puts $fh {body{font-family:Arial,sans-serif;font-size:12px;color:#222}}
    puts $fh {table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:4px 6px;vertical-align:top}}
    puts $fh {th{background:#1c5a96;color:#fff}img{display:block;border:1px solid #ccc}}
    puts $fh {code{font-family:Consolas,monospace;font-size:11px;white-space:nowrap}td.n{font-weight:bold}}
    puts $fh {</style></head><body>}
    puts $fh "<h2>Raport widok\u00f3w (HyperMesh)</h2>"
    puts $fh "<p>Wygenerowano: [clock format [clock seconds] -format {%Y-%m-%d %H:%M}] &middot; widok\u00f3w: [llength $rows]</p>"
    puts $fh "<p style=\"font-size:11px;color:#777\">Ten plik mo\u017cna wczyta\u0107 z powrotem do makra (\u201eWczytaj sesj\u0119\u2026\u201d), aby odtworzy\u0107 list\u0119 widok\u00f3w z podgl\u0105dami.</p>"
    # --- ukryty blok danych dla makra (niewidoczny w przegladarce) ---
    puts $fh "<!--HMSESSION v2"
    puts $fh [llength $rows]
    set k 0
    foreach r $rows {
        set fmt [lindex [lindex $sess $k] 0] ; set b64 [lindex [lindex $sess $k] 1]
        set dsp "" ; if {[dict exists $r disp]} { set dsp [dict get $r disp] }
        puts $fh "R\t[::hmShot::sesEsc [dict get $r name]]\t[::hmShot::sesEsc [dict get $r view]]\t$fmt\t$b64\t[::hmShot::sesEsc $dsp]"
        incr k
    }
    puts $fh "HMSESSION-->"
    # --- widoczna tabela ---
    puts -nonewline $fh {<table><tr><th>Nr</th><th>Podgl&#261;d</th><th>Nazwa</th><th>VS (pe&#322;ny)</th>}
    for {set i 1} {$i <= $maxN} {incr i} { puts -nonewline $fh "<th>v$i</th>" }
    puts $fh {</tr>}
    set k 0
    foreach r $rows {
        set fmt [lindex [lindex $vis $k] 0] ; set b64 [lindex [lindex $vis $k] 1]
        set vals [::hmShot::viewVals [dict get $r view]]
        puts -nonewline $fh "<tr><td>[dict get $r nr]</td>"
        if {$fmt ne "" && $b64 ne ""} {
            puts -nonewline $fh "<td><img src=\"data:image/$fmt;base64,$b64\" style=\"max-width:360px;max-height:240px\"></td>"
        } else {
            puts -nonewline $fh "<td><i>(brak podgl\u0105du)</i></td>"
        }
        set nm [::hmShot::xmlEsc [dict get $r name]]
        if {[dict exists $r disp] && [dict get $r disp] ne ""} { append nm " &#9881;" }
        puts -nonewline $fh "<td class=\"n\">$nm</td>"
        puts -nonewline $fh "<td><code>[::hmShot::xmlEsc [dict get $r view]]</code></td>"
        foreach v $vals { puts -nonewline $fh "<td>[::hmShot::xmlEsc $v]</td>" }
        puts $fh "</tr>"
        incr k
    }
    puts $fh {</table>}
    # Podsumowanie: wszystkie VS w polu tekstowym (klik -> Ctrl+A -> Ctrl+C).
    set nrows [llength $rows] ; if {$nrows < 3} { set nrows 3 } ; if {$nrows > 20} { set nrows 20 }
    puts $fh "<h3>Wszystkie widoki (VS) \u2013 do skopiowania</h3>"
    puts $fh "<p style=\"font-size:11px;color:#555\">Kliknij w pole, zaznacz wszystko (Ctrl+A) i skopiuj (Ctrl+C).</p>"
    puts -nonewline $fh "<textarea readonly rows=\"$nrows\" style=\"width:100%;font-family:Consolas,monospace;font-size:11px\">"
    foreach r $rows { puts -nonewline $fh "[::hmShot::xmlEsc [dict get $r view]]\n" }
    puts $fh {</textarea>}
    puts $fh {</body></html>}
    close $fh
}
# Zapisuje raport HTML (samodzielny: miniatury osadzone, mozliwy ponowny odczyt
# przez makro). Zwraca liste zapisanych sciezek (jeden plik .html).
proc ::hmShot::writeViewsReport {dir prefix rows} {
    set pfx [string trim $prefix] ; if {$pfx eq ""} { set pfx "shot" }
    set html [file join $dir "${pfx}_widoki.html"]
    set done {}
    if {![catch {::hmShot::writeHtmlReport $html $rows}]} { lappend done $html }
    return $done
}
# Buduje wiersze raportu z zaznaczonych widokow (miniatury osadzane w HTML).
proc ::hmShot::buildReportRows {{files {}} {imgs {}}} {
    set rows {} ; set nr 1
    foreach rec [::hmShot::selectedRecords] {
        set fl "" ; if {[llength $files] >= $nr} { set fl [lindex $files [expr {$nr-1}]] }
        lappend rows [dict create nr $nr name [dict get $rec name] file $fl \
            thumb [dict get $rec thumb] view [dict get $rec view] disp [::hmShot::viewDisp $rec]]
        incr nr
    }
    return $rows
}
# Standalone: zapisuje raport zaznaczonych widokow (bez robienia zrzutow).
# Miniatury zapamietanych widokow trafiaja do raportu HTML jako obrazki.
proc ::hmShot::saveReportNow {} {
    set recs [::hmShot::selectedRecords]
    if {![llength $recs]} { ::hmShot::setStatus [::hmShot::T "Zaznacz przynajmniej jeden widok (checkbox)." "Select at least one view (checkbox)."] red ; return }
    set dir [string trim $::hmShot::shotDir]
    if {$dir eq ""} { catch {set dir [tk_chooseDirectory -title [::hmShot::T "Wybierz folder na raport widok\u00f3w" "Choose a folder for the views report"]]} }
    if {$dir eq ""} { ::hmShot::setStatus [::hmShot::T "Nie wskazano folderu na raport." "No folder chosen for the report."] red ; return }
    if {[catch {file mkdir $dir} e]} { ::hmShot::setStatus [::hmShot::T "Nie mo\u017cna utworzy\u0107 folderu: $e" "Cannot create folder: $e"] red ; return }
    set pfx [string trim $::hmShot::shotPrefix] ; if {$pfx eq ""} { set pfx "shot" }
    ::hmShot::setStatus [::hmShot::T "Zapisywanie raportu HTML (osadzam podgl\u0105dy)\u2026" "Saving HTML report (embedding previews)\u2026"] ; update idletasks
    set rows [::hmShot::buildReportRows]
    set done [::hmShot::writeViewsReport $dir $pfx $rows]
    if {[llength $done]} {
        ::hmShot::setStatus [::hmShot::T "Zapisano raport: [file tail [lindex $done 0]]  (w: $dir). Mo\u017cna go p\u00f3\u017aniej wczyta\u0107 (\u201eWczytaj sesj\u0119\u2026\u201d)." "Report saved: [file tail [lindex $done 0]]  (in: $dir). It can be loaded later (\u201eLoad session\u2026\u201d)."]
    } else {
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 zapisa\u0107 raportu." "Could not save the report."] red
    }
}
# Odtwarza obraz z base64: najpierw plik tymczasowy + image -file (ten build czyta
# PPM/JPEG/GIF przez -file), w razie niepowodzenia fallback na -data. Pomniejsza do
# rozmiaru miniatury. Zwraca uchwyt photo lub "".
proc ::hmShot::imageFromB64 {fmt b64} {
    if {$b64 eq ""} { return "" }
    set img ""
    set bytes ""
    catch {set bytes [::hmShot::b64dec $b64]}
    if {$bytes ne ""} {
        set ext [expr {$fmt eq "jpeg" ? "jpg" : ($fmt eq "" ? "img" : $fmt)}]
        set tmp [file join [::hmShot::pickTmpBase] "hmload_[clock clicks].$ext"]
        if {![catch {set fh [open $tmp wb] ; puts -nonewline $fh $bytes ; close $fh}]} {
            catch {set img [image create photo -file $tmp]}
        }
        catch {file delete -force $tmp}
    }
    if {$img eq "" || [lsearch -exact [image names] $img] < 0} {
        set img "" ; catch {set img [image create photo -data $b64]}
    }
    if {$img ne "" && [lsearch -exact [image names] $img] >= 0} {
        return [::hmShot::scalePhotoToThumb $img]
    }
    return ""
}
# Wczytuje sesje z pliku HTML zapisanego przez makro (blok HMSESSION): odtwarza
# liste widokow wraz z miniaturami (osadzonymi jako data-URI).
proc ::hmShot::loadSession {} {
    set path ""
    catch {set path [tk_getOpenFile -title [::hmShot::T "Wczytaj sesj\u0119 (HTML)" "Load session (HTML)"] \
        -filetypes {{HTML {.html .htm}} {All *}}]}
    if {$path eq "" || ![file exists $path]} { return }
    set data ""
    if {[catch {set fh [open $path r] ; catch {fconfigure $fh -encoding utf-8} ; set data [read $fh] ; close $fh} e]} {
        ::hmShot::setStatus [::hmShot::T "Nie mo\u017cna otworzy\u0107 pliku: $e" "Cannot open the file: $e"] red ; return
    }
    set s [string first "<!--HMSESSION" $data]
    set e [string first "HMSESSION-->" $data]
    if {$s < 0 || $e < 0 || $e < $s} {
        ::hmShot::setStatus [::hmShot::T "To nie jest plik sesji makra (brak bloku HMSESSION)." "This is not a macro session file (no HMSESSION block)."] red ; return
    }
    set block [string range $data $s [expr {$e-1}]]
    set loaded {}
    foreach ln [split $block "\n"] {
        if {![string match "R\t*" $ln]} { continue }
        set parts [split $ln "\t"]
        if {[llength $parts] < 5} { continue }
        set name [::hmShot::sesUnesc [lindex $parts 1]]
        set vw   [::hmShot::sesUnesc [lindex $parts 2]]
        set fmt  [lindex $parts 3]
        set b64  [lindex $parts 4]
        set disp ""
        if {[llength $parts] >= 6} { set disp [::hmShot::sesUnesc [lindex $parts 5]] }
        set thumb [::hmShot::imageFromB64 $fmt $b64]
        lappend loaded [list $name $vw $thumb $disp]
    }
    if {![llength $loaded]} { ::hmShot::setStatus [::hmShot::T "Nie znaleziono widok\u00f3w w pliku sesji." "No views found in the session file."] red ; return }
    if {[llength $::hmShot::views] > 0} {
        set ans yes
        catch {set ans [tk_messageBox -type yesno -icon question -title [::hmShot::T "Wczytaj sesj\u0119" "Load session"] \
            -message [::hmShot::T "Wczytanie zast\u0105pi obecn\u0105 list\u0119 ([llength $::hmShot::views]) now\u0105 ([llength $loaded]). Kontynuowa\u0107?" "Loading will replace the current list ([llength $::hmShot::views]) with a new one ([llength $loaded]). Continue?"]]}
        if {$ans ne "yes"} { ::hmShot::setStatus [::hmShot::T "Anulowano wczytywanie sesji." "Session loading cancelled."] ; return }
    }
    foreach rec $::hmShot::views {
        set t [dict get $rec thumb]
        if {$t ne "" && [lsearch -exact [image names] $t] >= 0} { catch {image delete $t} }
        ::hmShot::dropShotFile $rec
    }
    set ::hmShot::views {} ; array unset ::hmShot::selArr
    set nd 0
    foreach item $loaded {
        set id $::hmShot::nextId ; incr ::hmShot::nextId
        set dsp [lindex $item 3]
        if {$dsp ne ""} { incr nd }
        lappend ::hmShot::views [dict create id $id name [lindex $item 0] view [lindex $item 1] thumb [lindex $item 2] disp $dsp]
        set ::hmShot::selArr($id) 1
    }
    # nowa sesja = uklady jeszcze nieodtworzone w biezacym modelu
    set ::hmShot::dispApplied 0
    ::hmShot::redrawList
    set dn [expr {$nd > 0 ? [::hmShot::T " (w tym $nd z uk\u0142adem wy\u015bwietlania \u2013 odtworzy si\u0119 przy Testuj/Generuj)" " (incl. $nd with display layout \u2013 replayed on Test/Generate)"] : ""}]
    ::hmShot::setStatus [::hmShot::T "Wczytano sesj\u0119: [llength $loaded] widok\u00f3w z [file tail $path].$dn" "Session loaded: [llength $loaded] views from [file tail $path].$dn"]
}
# Zapamietuje biezacy widok + robi miniature.
#---------------------------------------------------------------------
#  UKLAD WYSWIETLANIA (sekcje, style FE/Geometry, maskowanie, widocznosc...)
#  HyperMesh loguje kazda akcje uzytkownika do pliku komend (command.tcl /
#  command.cmf). Nagrywamy ogon tego pliku miedzy startem nagrywania a
#  "Zapamietaj widok", zapisujemy z widokiem w sesji i ODTWARZAMY przed
#  zrzutem w kolejnym modelu - dzieki temu screenshoty wygladaja identycznie.
#---------------------------------------------------------------------
# Szuka pliku komend HM: command.tcl / command.cmf w biezacym katalogu procesu,
# w razie braku najnowszy command*.tcl|cmf. Zwraca sciezke lub "".
proc ::hmShot::findCommandFile {} {
    set base [pwd]
    foreach n {command.tcl command.cmf} {
        set p [file join $base $n]
        if {[file isfile $p]} { return $p }
    }
    set best "" ; set bt -1
    foreach p [concat [glob -nocomplain -directory $base command*.tcl] \
                      [glob -nocomplain -directory $base command*.cmf]] {
        if {![file isfile $p]} { continue }
        set t 0 ; catch {set t [file mtime $p]}
        if {$t > $bt} { set bt $t ; set best $p }
    }
    return $best
}
# Wlacza/wylacza nagrywanie ukladu. Przy starcie zapamietuje biezacy rozmiar pliku
# komend (offset) - czytamy tylko to, co uzytkownik zrobi OD TERAZ.
proc ::hmShot::recToggle {} {
    if {$::hmShot::recOn} {
        set ::hmShot::recOn 0
        ::hmShot::recBtnSync
        ::hmShot::setStatus [::hmShot::T "Nagrywanie uk\u0142adu zako\u0144czone." "Layout recording stopped."]
        return
    }
    set f $::hmShot::recFile
    if {$f eq "" || ![file isfile $f]} { set f [::hmShot::findCommandFile] }
    if {$f eq ""} {
        # ostatnia deska ratunku: wskaz plik recznie (standardowy dialog Tk)
        catch {set f [tk_getOpenFile -title [::hmShot::T "Wska\u017c plik komend HM (command.tcl)" "Locate the HM command file (command.tcl)"] \
            -filetypes {{{command file} {.tcl .cmf}} {{wszystkie} {*}}}]}
        if {$f eq "" || ![file isfile $f]} {
            ::hmShot::setStatus [::hmShot::T "Nie znaleziono pliku komend (command.tcl). Uk\u0142ad mo\u017cesz wklei\u0107 r\u0119cznie w \u201eEdytuj\u201d." "Command file (command.tcl) not found. You can paste the layout manually in \u201eEdit\u201d."] red
            return
        }
    }
    set ::hmShot::recFile $f
    set ::hmShot::recOfs [file size $f]
    set ::hmShot::recOn 1
    ::hmShot::recBtnSync
    ::hmShot::setStatus [::hmShot::T "NAGRYWAM uk\u0142ad: wykonaj sekcje / style / maskowanie, potem \u201eZapami\u0119taj widok (1)\u201d." "RECORDING layout: set up sections / styles / masking, then \u201eRemember view (1)\u201d."] "#b00020"
}
# Synchronizuje etykiete/kolor przycisku nagrywania ze stanem.
proc ::hmShot::recBtnSync {} {
    set b $::hmShot::recBtn
    if {$b eq "" || ![winfo exists $b]} { return }
    if {$::hmShot::recOn} {
        $b configure -text [::hmShot::T "\u25a0 Zako\u0144cz nagryw." "\u25a0 Stop recording"] -bg "#b00020" -fg white -activebackground "#8f001a" -activeforeground white
    } else {
        $b configure -text [::hmShot::T "\u25cf Nagrywaj uk\u0142ad" "\u25cf Record layout"] -bg "#e0e0e0" -fg black -activebackground "#d0d0d0" -activeforeground black
    }
}
# Czyta NOWE linie pliku komend (od zapamietanego offsetu), przesuwa offset.
# Filtruje szum makra (zrzuty, kamera, tlo) - zostaja komendy ukladu.
proc ::hmShot::captureDispTail {} {
    set f $::hmShot::recFile
    if {$f eq "" || ![file isfile $f]} { return "" }
    set sz [file size $f]
    if {$sz <= $::hmShot::recOfs} { return "" }
    set data ""
    if {[catch {
        set fh [open $f r]
        seek $fh $::hmShot::recOfs
        set data [read $fh]
        close $fh
    }]} { return "" }
    set ::hmShot::recOfs $sz
    set keep {}
    foreach ln [split $data "\n"] {
        set t [string trim $ln]
        if {$t eq ""} { continue }
        set skip 0
        foreach pat [list "*viewset*" "*jpegfilenamed*" "*pngfilenamed*" "*bmpfilenamed*" "*tifffilenamed*" \
                     "*setbackground*" "*sethardcopy*" "*hardcopy*" "*screencapture*" "*quitapplication*"] {
            if {[string match $pat $t]} { set skip 1 ; break }
        }
        if {!$skip} { lappend keep $ln }
    }
    return [join $keep "\n"]
}
# Uklad danego rekordu widoku ("" gdy brak).
proc ::hmShot::viewDisp {rec} {
    if {[dict exists $rec disp]} { return [dict get $rec disp] }
    return ""
}
# Odtwarza snippety ukladu od pozycji juz-wykonanej do widoku idx (wlacznie).
# Snippety sa PRZYROSTOWE, wiec wykonujemy kazdy dokladnie raz, po kolei.
# Zwraca {wykonanychSnippetow bledow zaLancuchem} - zaLancuchem=1 gdy stan sesji
# jest juz DALEJ niz ten widok (nie da sie cofnac bez ponownego wczytania modelu).
proc ::hmShot::applyDispUpTo {idx} {
    set ran 0 ; set fails 0
    set target 0
    for {set i 0} {$i <= $idx && $i < [llength $::hmShot::views]} {incr i} {
        if {[::hmShot::viewDisp [lindex $::hmShot::views $i]] ne ""} { incr target }
    }
    if {$target == 0} { return [list 0 0 0] }
    if {$::hmShot::dispApplied > $target} { return [list 0 0 1] }
    set ci 0
    for {set i 0} {$i <= $idx && $i < [llength $::hmShot::views]} {incr i} {
        set d [::hmShot::viewDisp [lindex $::hmShot::views $i]]
        if {$d eq ""} { continue }
        incr ci
        if {$ci <= $::hmShot::dispApplied} { continue }
        foreach ln [split $d "\n"] {
            set t [string trim $ln]
            if {$t eq ""} { continue }
            if {[catch {uplevel #0 $t}]} { incr fails }
        }
        incr ran
        set ::hmShot::dispApplied $ci
    }
    catch {hm_redraw}
    return [list $ran $fails 0]
}
#---------------------------------------------------------------------
#  ZAPISANA KLATKA (WYSIWYG): przy "Zapamietaj widok" pelny zrzut ekranu
#  zostaje na dysku i to on jest domyslnie eksportowany. Dzieki temu widok
#  wyglada DOKLADNIE tak jak w chwili zapamietania - pozniejsze zmiany
#  wygladu modelu (np. przelaczenie na widok bezbarwny) nie zmieniaja
#  wczesniej zapamietanych widokow.
#---------------------------------------------------------------------
# Sciezka zapisanej pelnej klatki rekordu ("" gdy brak).
proc ::hmShot::viewShot {rec} {
    if {[dict exists $rec shot]} { return [dict get $rec shot] }
    return ""
}
# Czy rekord ma uzyteczna zapisana klatke (plik istnieje i nie jest pusty).
proc ::hmShot::storedShotUsable {rec} {
    set p [::hmShot::viewShot $rec]
    return [expr {$p ne "" && [file isfile $p] && [file size $p] > 0}]
}
# Usuwa plik zapisanej klatki rekordu (sprzatanie po Usun/Wyczysc itd.).
proc ::hmShot::dropShotFile {rec} {
    set p [::hmShot::viewShot $rec]
    if {$p ne ""} { catch {file delete -force $p} }
}
# Przenosi tymczasowy plik pelnej klatki pod stabilna nazwe (w tym samym,
# sprawdzonym folderze tymczasowym). Zwraca docelowa sciezke lub "".
proc ::hmShot::keepFullShot {tmpPath id} {
    if {$tmpPath eq ""} { return "" }
    if {![file isfile $tmpPath] || [file size $tmpPath] == 0} {
        catch {file delete -force $tmpPath}
        return ""
    }
    set dst [file join [file dirname $tmpPath] "shotfull_${id}_[clock clicks][file extension $tmpPath]"]
    if {[catch {file rename -force $tmpPath $dst}]} {
        if {[catch {file copy -force $tmpPath $dst}]} { return "" }
        catch {file delete -force $tmpPath}
    }
    return $dst
}
proc ::hmShot::rememberView {} {
    set vm [::hmShot::getView]
    if {[llength $vm] < 16 && ![string match -nocase "HV1:*" [string trim $vm]]} {
        set ::hmShot::hvProbed 0   ;# pozwol na ponowna kalibracje przy nastepnej probie
        set ::hmShot::appMode ""
        set hvd [expr {$::hmShot::hvDiagPath ne "" ? " Log: $::hmShot::hvDiagPath" : ""}]
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 pobra\u0107 widoku (HyperMesh: hm_winfo; HyperView: API hwi). Czy okno graficzne jest aktywne?$hvd" "Could not read the view (HyperMesh: hm_winfo; HyperView: hwi API). Is the graphics window active?$hvd"] red
        return
    }
    if {[string match -nocase "HV1:*" [string trim $vm]]} {
        set view [string trim $vm]
    } else {
        set view "VS: $vm"
    }
    set id $::hmShot::nextId ; incr ::hmShot::nextId
    # uklad wyswietlania: przy wlaczonym nagrywaniu dolacz komendy od ostatniego punktu
    set disp ""
    if {$::hmShot::recOn} { set disp [::hmShot::captureDispTail] }
    # miniatura + PELNA KLATKA z biezacego (wlasnie ustawionego) widoku.
    # Klatka zostaje na dysku i to ONA jest domyslnie eksportowana (WYSIWYG) -
    # pozniejsze zmiany wygladu modelu nie dotkna juz tego widoku.
    set fullTmp ""
    set thumb [::hmShot::grabThumb fullTmp]
    set shot  [::hmShot::keepFullShot $fullTmp $id]
    # HyperView: dolacz sylwetke wzorcowa (|ZM=...) do dostrajania zoomu po pikselach
    if {[string match -nocase "HV1:*" $view] && $thumb ne ""} {
        set sil [::hmShot::photoSilhouette $thumb]
        if {$sil ne ""} {
            lassign $sil fw fh cx cy cnt
            append view "|ZM=$fw $fh $cx $cy"
        }
    }
    lappend ::hmShot::views [dict create id $id name [::hmShot::T "Widok $id" "View $id"] view $view thumb $thumb disp $disp shot $shot]
    if {$disp ne ""} {
        # stan ukladu tego widoku wlasnie obowiazuje na ekranie (wykonal go uzytkownik)
        set t 0
        foreach r $::hmShot::views { if {[::hmShot::viewDisp $r] ne ""} { incr t } }
        set ::hmShot::dispApplied $t
    }
    set ::hmShot::selArr($id) 1
    ::hmShot::redrawList
    ::hmShot::scrollEnd
    set mi [expr {$thumb ne "" ? [::hmShot::T "tak" "yes"] : [::hmShot::T "nie (zrzut miniatury si\u0119 nie powi\u00f3d\u0142)" "no (thumbnail capture failed)"]}]
    set dn [expr {$disp ne "" ? [::hmShot::T " + uk\u0142ad ([llength [split $disp \n]] kom.)" " + layout ([llength [split $disp \n]] cmds)"] : ""}]
    set fz [expr {$shot ne "" ? "" : [::hmShot::T " (bez zapisanej klatki \u2013 eksport wyrenderuje ten widok na nowo)" " (no stored frame \u2013 export will re-render this view)"]}]
    if {$::hmShot::capBgMethod eq "none" && [::hmShot::bgHex $::hmShot::bgMode] ne ""} {
        ::hmShot::setStatus [::hmShot::T "Zapami\u0119tano widok, ALE zrzuty maj\u0105 inne t\u0142o ni\u017c ekran (brak prze\u0142\u0105cznika w tym buildzie). Log: $::hmShot::capBgLogPath" "View remembered, BUT captures use a different background than the screen (no switch in this build). Log: $::hmShot::capBgLogPath"] "#b35a00"
        return
    }
    ::hmShot::setStatus [::hmShot::T "Zapami\u0119tano widok$dn$fz. Miniatura: $mi. Widok\u00f3w: [llength $::hmShot::views]." "View remembered$dn$fz. Thumbnail: $mi. Views: [llength $::hmShot::views]."]
}
# Kopiuje dane (VS) danego widoku do schowka systemowego.
proc ::hmShot::copyView {id} {
    set idx [::hmShot::recIndex $id] ; if {$idx < 0} { return }
    set v [dict get [lindex $::hmShot::views $idx] view]
    if {[catch {clipboard clear ; clipboard append $v}]} {
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 skopiowa\u0107 do schowka." "Could not copy to the clipboard."] red ; return
    }
    ::hmShot::setStatus [::hmShot::T "Skopiowano dane widoku (VS) do schowka." "View data (VS) copied to the clipboard."]
}
proc ::hmShot::deleteRecord {id} {
    set idx [::hmShot::recIndex $id] ; if {$idx < 0} { return }
    set rec [lindex $::hmShot::views $idx]
    set t [dict get $rec thumb]
    if {$t ne "" && [lsearch -exact [image names] $t] >= 0} { catch {image delete $t} }
    ::hmShot::dropShotFile $rec
    set ::hmShot::views [lreplace $::hmShot::views $idx $idx]
    catch {unset ::hmShot::selArr($id)}
    ::hmShot::redrawList
    ::hmShot::setStatus [::hmShot::T "Usuni\u0119to widok. Pozosta\u0142o: [llength $::hmShot::views]." "View deleted. Remaining: [llength $::hmShot::views]."]
}
proc ::hmShot::clearViews {} {
    foreach rec $::hmShot::views {
        set t [dict get $rec thumb]
        if {$t ne "" && [lsearch -exact [image names] $t] >= 0} { catch {image delete $t} }
        ::hmShot::dropShotFile $rec
    }
    set ::hmShot::views {}
    array unset ::hmShot::selArr
    set ::hmShot::dispApplied 0
    ::hmShot::redrawList
    ::hmShot::setStatus [::hmShot::T "Wyczyszczono zapisane widoki." "Cleared the remembered views."]
}
proc ::hmShot::setAllSel {val} {
    foreach rec $::hmShot::views { set ::hmShot::selArr([dict get $rec id]) $val }
    ::hmShot::updateCount
}
# Testuje widok z danego rekordu na biezacym modelu (najpierw uklad, potem kamera).
proc ::hmShot::testRecord {id} {
    set idx [::hmShot::recIndex $id] ; if {$idx < 0} { return }
    lassign [::hmShot::applyDispUpTo $idx] dR dF dB
    set view [dict get [lindex $::hmShot::views $idx] view]
    set ok [::hmShot::applyView $view]
    catch {hm_redraw} ; ::hmShot::applyView $view
    lassign [::hmShot::hvViewFineTune $view] tuneOk tuneIt tuneInfo
    set dn ""
    if {$tuneIt > 0 && $tuneOk} { append dn [::hmShot::T " Zoom/pan dostrojony ($tuneIt iter.)." " Zoom/pan fine-tuned ($tuneIt iter.)."] }
    if {!$tuneOk} { append dn [::hmShot::T " UWAGA: nie uda\u0142o si\u0119 dostroi\u0107 kadru." " WARNING: could not tune the frame."] }
    if {$tuneInfo ne ""} { append dn " \[$tuneInfo\]" }
    if {$dR > 0}  { append dn [::hmShot::T " Odtworzono uk\u0142ad ($dR sn.)." " Layout replayed ($dR sn.)."] }
    if {$dF > 0}  { append dn [::hmShot::T " Uwaga: $dF komend uk\u0142adu nie wykona\u0142o si\u0119." " Warning: $dF layout commands failed."] }
    if {$dB}      { append dn [::hmShot::T " Uwaga: stan uk\u0142adu sesji jest ju\u017c dalej ni\u017c ten widok (wczytaj model ponownie)." " Warning: session layout state is already past this view (reload the model)."] }
    if {$ok} {
        ::hmShot::setStatus [::hmShot::T "Zastosowano widok do bie\u017c\u0105cego modelu \u2013 sprawd\u017a ekran.$dn" "Applied the view to the current model \u2013 check the screen.$dn"]
    } else {
        set hvd [expr {$::hmShot::hvDiagPath ne "" ? " Log: $::hmShot::hvDiagPath" : ""}]
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 zastosowa\u0107 widoku (komenda widoku niedost\u0119pna).$dn$hvd" "Could not apply the view (view command unavailable).$dn$hvd"] red
    }
}
# Odswieza miniature: zapisuje biezacy widok, ustawia widok rekordu, robi
# zrzut, po czym PRZYWRACA poprzedni widok.
proc ::hmShot::refreshThumb {id} {
    set idx [::hmShot::recIndex $id] ; if {$idx < 0} { return }
    set rec  [lindex $::hmShot::views $idx]
    set view [dict get $rec view]
    set cur  [::hmShot::getView]
    ::hmShot::applyView $view
    catch {hm_redraw} ; ::hmShot::applyView $view
    update idletasks ; catch {after 150}
    set newFull ""
    set newt [::hmShot::grabThumb newFull]
    if {[llength $cur] >= 16} { ::hmShot::applyView "VS: $cur" ; catch {hm_redraw} }
    if {$newt ne ""} {
        set old [dict get $rec thumb]
        if {$old ne "" && [lsearch -exact [image names] $old] >= 0} { catch {image delete $old} }
        dict set rec thumb $newt
        # nowa klatka zastepuje stara (podglad i eksport = ta sama chwila)
        ::hmShot::dropShotFile $rec
        dict set rec shot [::hmShot::keepFullShot $newFull $id]
        set ::hmShot::views [lreplace $::hmShot::views $idx $idx $rec]
        ::hmShot::redrawList
        ::hmShot::setStatus [::hmShot::T "Od\u015bwie\u017cono miniatur\u0119 i zapisan\u0105 klatk\u0119 widoku." "View thumbnail and stored frame refreshed."]
    } else {
        ::hmShot::setStatus [::hmShot::T "Nie uda\u0142o si\u0119 zrobi\u0107 miniatury (sprawd\u017a okno graficzne / format)." "Could not create the thumbnail (check the graphics window / format)."] red
    }
}

#---------------------------------------------------------------------
#  Okno: edycja pojedynczego widoku (nazwa + surowe dane)
#---------------------------------------------------------------------
proc ::hmShot::editRecord {id} {
    set idx [::hmShot::recIndex $id] ; if {$idx < 0} { return }
    set rec [lindex $::hmShot::views $idx]
    set ::hmShot::edId   $id
    set ::hmShot::edName [dict get $rec name]
    set w .hmshot_edit
    catch {destroy $w}
    toplevel $w
    wm title $w [::hmShot::T "Edytuj widok" "Edit view"]
    catch {wm transient $w .hmshot}
    frame $w.f -padx 12 -pady 10
    pack $w.f -fill both -expand 1
    label $w.f.ln -text [::hmShot::T "Nazwa:" "Name:"] -anchor w
    entry $w.f.en -textvariable ::hmShot::edName -width 36
    label $w.f.lv -text [::hmShot::T "Dane widoku (VS:/MTX: lub \u226516 liczb):" "View data (VS:/MTX: or \u226516 numbers):"] -anchor w
    set t [text $w.f.tv -height 4 -width 50 -wrap word -font {Courier 8}]
    $t insert 1.0 [dict get $rec view]
    set ::hmShot::edTxt $t
    label $w.f.ld -text [::hmShot::T "Uk\u0142ad wy\u015bwietlania \u2013 komendy HM odtwarzane przed zrzutem (sekcje, style, maskowanie; mo\u017cna wklei\u0107 z command.tcl):" "Display layout \u2013 HM commands replayed before the shot (sections, styles, masking; may be pasted from command.tcl):"] -anchor w -wraplength 380 -justify left
    set td [text $w.f.td -height 6 -width 50 -wrap none -font {Courier 8}]
    $td insert 1.0 [::hmShot::viewDisp $rec]
    set ::hmShot::edDisp $td
    grid $w.f.ln -row 0 -column 0 -sticky w -pady {0 2}
    grid $w.f.en -row 1 -column 0 -sticky we -pady {0 8}
    grid $w.f.lv -row 2 -column 0 -sticky w -pady {0 2}
    grid $w.f.tv -row 3 -column 0 -sticky we
    grid $w.f.ld -row 4 -column 0 -sticky w -pady {8 2}
    grid $w.f.td -row 5 -column 0 -sticky we
    grid columnconfigure $w.f 0 -weight 1
    set bb [frame $w.f.bb]
    grid $bb -row 6 -column 0 -sticky e -pady {10 0}
    button $bb.ok -text [::hmShot::T "Zapisz" "Save"] -command [list ::hmShot::editApply $w] \
        -bg "#1c5a96" -fg white -activebackground "#16487a" -activeforeground white -font {Arial 9 bold}
    button $bb.no -text [::hmShot::T "Anuluj" "Cancel"] -command [list destroy $w]
    pack $bb.no -side right
    pack $bb.ok -side right -padx {0 6}
}
proc ::hmShot::editApply {w} {
    set id $::hmShot::edId
    set idx [::hmShot::recIndex $id]
    if {$idx < 0} { catch {destroy $w} ; return }
    set nm [string trim $::hmShot::edName] ; if {$nm eq ""} { set nm [::hmShot::T "Widok $id" "View $id"] }
    set raw ""
    if {$::hmShot::edTxt ne "" && [winfo exists $::hmShot::edTxt]} {
        set raw [$::hmShot::edTxt get 1.0 end]
    }
    set norm [::hmShot::normalizeViewLine $raw]
    if {$norm eq ""} {
        ::hmShot::setStatus [::hmShot::T "Niepoprawne dane widoku (potrzeba VS:/MTX: lub \u226516 liczb)." "Invalid view data (need VS:/MTX: or \u226516 numbers)."] red
        catch {destroy $w} ; return
    }
    set rec [lindex $::hmShot::views $idx]
    set oldView [dict get $rec view]
    dict set rec name $nm
    dict set rec view $norm
    set dsp ""
    if {$::hmShot::edDisp ne "" && [winfo exists $::hmShot::edDisp]} {
        set dsp [string trim [$::hmShot::edDisp get 1.0 end] "\n"]
        set dsp [string trim $dsp]
    }
    dict set rec disp $dsp
    if {$norm ne $oldView} {
        # zmieniono dane widoku -> zapisana klatka juz mu nie odpowiada;
        # eksport wyrenderuje ten widok na nowo (mozna tez uzyc "Miniatura")
        ::hmShot::dropShotFile $rec
        dict set rec shot ""
    }
    set ::hmShot::views [lreplace $::hmShot::views $idx $idx $rec]
    catch {destroy $w}
    ::hmShot::redrawList
    ::hmShot::setStatus [::hmShot::T "Zaktualizowano \u201e$nm\u201d. (W razie potrzeby u\u017cyj \u201eMiniatura\u201d, by od\u015bwie\u017cy\u0107 podgl\u0105d.)" "Updated \u201e$nm\u201d. (If needed, use \u201eThumbnail\u201d to refresh the preview.)"]
}

#---------------------------------------------------------------------
#  Okno: dodaj widok(i) z tekstu (wklejone surowe macierze)
#---------------------------------------------------------------------
proc ::hmShot::addFromText {} {
    set w .hmshot_add
    catch {destroy $w}
    toplevel $w
    wm title $w [::hmShot::T "Dodaj widok z tekstu" "Add view from text"]
    catch {wm transient $w .hmshot}
    frame $w.f -padx 12 -pady 10
    pack $w.f -fill both -expand 1
    label $w.f.l -text [::hmShot::T "Wklej dane widoku/widok\u00f3w (1 linia = 1 widok).\nDopuszczalne: VS:/MTX: lub \u226516 liczb. Bez miniatury \u2013 mo\u017cesz j\u0105 p\u00f3\u017aniej od\u015bwie\u017cy\u0107." "Paste view data (1 line = 1 view).\nAllowed: VS:/MTX: or \u226516 numbers. No thumbnail \u2013 you can refresh it later."] \
        -justify left -anchor w -font {Arial 8} -fg "#444"
    set t [text $w.f.t -height 7 -width 56 -wrap none -font {Courier 8}]
    set ::hmShot::addTxt $t
    grid $w.f.l -row 0 -column 0 -sticky w -pady {0 4}
    grid $w.f.t -row 1 -column 0 -sticky we
    grid columnconfigure $w.f 0 -weight 1
    set bb [frame $w.f.bb]
    grid $bb -row 2 -column 0 -sticky e -pady {10 0}
    button $bb.ok -text [::hmShot::T "Dodaj" "Add"] -command [list ::hmShot::addApply $w] \
        -bg "#1c5a96" -fg white -activebackground "#16487a" -activeforeground white -font {Arial 9 bold}
    button $bb.no -text [::hmShot::T "Anuluj" "Cancel"] -command [list destroy $w]
    pack $bb.no -side right
    pack $bb.ok -side right -padx {0 6}
}
proc ::hmShot::addApply {w} {
    set raw ""
    if {$::hmShot::addTxt ne "" && [winfo exists $::hmShot::addTxt]} {
        set raw [$::hmShot::addTxt get 1.0 end]
    }
    set added 0
    foreach line [split $raw "\n"] {
        set norm [::hmShot::normalizeViewLine $line]
        if {$norm eq ""} { continue }
        set id $::hmShot::nextId ; incr ::hmShot::nextId
        lappend ::hmShot::views [dict create id $id name [::hmShot::T "Widok $id" "View $id"] view $norm thumb ""]
        set ::hmShot::selArr($id) 1
        incr added
    }
    catch {destroy $w}
    ::hmShot::redrawList
    if {$added > 0} {
        ::hmShot::setStatus [::hmShot::T "Dodano widok\u00f3w: $added. (Miniatury mo\u017cna od\u015bwie\u017cy\u0107 przyciskiem \u201eMiniatura\u201d.)" "Views added: $added. (You can refresh thumbnails with \u201eThumbnail\u201d.)"]
    } else {
        ::hmShot::setStatus [::hmShot::T "Nie dodano nic \u2013 brak poprawnych linii (VS:/MTX: lub \u226516 liczb)." "Nothing added \u2013 no valid lines (VS:/MTX: or \u226516 numbers)."] red
    }
}

#---------------------------------------------------------------------
#  Rysowanie listy widokow (karty: checkbox + miniatura + nazwa + przyciski)
#---------------------------------------------------------------------
proc ::hmShot::wheel {d} {
    set c $::hmShot::listCanvas
    if {[winfo exists $c]} { $c yview scroll [expr {$d > 0 ? -1 : 1}] units }
}
proc ::hmShot::bindWheelTree {w} {
    bind $w <MouseWheel> {::hmShot::wheel %D}
    bind $w <Button-4>   {::hmShot::wheel 120}
    bind $w <Button-5>   {::hmShot::wheel -120}
    foreach c [winfo children $w] { ::hmShot::bindWheelTree $c }
}
# Focus podazajacy za myszem: gdy kursor jest nad oknem makra, okno przejmuje
# focus klawiatury (dzieki temu dziala skrot D bez klikania). Pola tekstowe
# przejmuja focus na siebie, zeby mozna bylo w nich normalnie pisac.
proc ::hmShot::bindFocusTree {w top} {
    set cls ""
    catch {set cls [winfo class $w]}
    if {$cls in {Entry TEntry Text Spinbox TCombobox}} {
        bind $w <Enter> [list focus $w]
    } else {
        bind $w <Enter> [list focus $top]
    }
    foreach c [winfo children $w] { ::hmShot::bindFocusTree $c $top }
}
proc ::hmShot::onInnerConfigure {iw} {
    set c $::hmShot::listCanvas
    if {[winfo exists $c]} { catch {$c configure -scrollregion [$c bbox all]} }
}
proc ::hmShot::scrollEnd {} {
    set c $::hmShot::listCanvas
    if {[winfo exists $c]} { update idletasks ; catch {$c yview moveto 1.0} }
}
proc ::hmShot::updateCount {args} {
    set total [llength $::hmShot::views]
    set sel 0
    foreach rec $::hmShot::views {
        set id [dict get $rec id]
        if {[info exists ::hmShot::selArr($id)] && $::hmShot::selArr($id)} { incr sel }
    }
    if {$::hmShot::countLbl ne "" && [winfo exists $::hmShot::countLbl]} {
        $::hmShot::countLbl configure -text [::hmShot::T "Zaznaczono: $sel / $total" "Selected: $sel / $total"]
    }
}
proc ::hmShot::redrawList {} {
    set f $::hmShot::listInner
    if {$f eq "" || ![winfo exists $f]} { return }
    foreach c [winfo children $f] { destroy $c }
    grid columnconfigure $f 0 -weight 1

    if {![llength $::hmShot::views]} {
        label $f.empty -text [::hmShot::T "(brak widok\u00f3w \u2013 ustaw model w oknie graficznym i kliknij \u201eZapami\u0119taj widok\u201d)" "(no views \u2013 set up the model in the graphics window and click \u201eRemember view\u201d)"] \
            -fg "#777" -font {Arial 9} -bg "#f0f0f0" -anchor w -pady 14 -padx 8
        grid $f.empty -row 0 -column 0 -sticky we
        ::hmShot::updateCount
        ::hmShot::onInnerConfigure $f
        return
    }

    set r 0
    foreach rec $::hmShot::views {
        set id    [dict get $rec id]
        set name  [dict get $rec name]
        set view  [dict get $rec view]
        set thumb [dict get $rec thumb]
        if {![info exists ::hmShot::selArr($id)]} { set ::hmShot::selArr($id) 1 }

        set row [frame $f.row$id -bd 1 -relief solid -bg white]
        grid $row -row $r -column 0 -sticky we -padx 4 -pady 3

        # checkbox
        checkbutton $row.cb -variable ::hmShot::selArr($id) -bg white -activebackground white \
            -takefocus 1
        # miniatura (lub zaslepka)
        if {$thumb ne "" && [lsearch -exact [image names] $thumb] >= 0} {
            label $row.img -image $thumb -bd 1 -relief groove -bg white
        } else {
            label $row.img -image [::hmShot::placeholderPhoto] -bd 1 -relief groove -bg white
        }
        # info: nazwa + dane VS (na wierzchu, zaznaczalne do kopiowania)
        set info [frame $row.inf -bg white]
        set nlab $name
        if {[::hmShot::viewDisp $rec] ne ""} { append nlab "  \u2699" }
        if {[::hmShot::storedShotUsable $rec]} { append nlab "  \u25c9" }
        label $info.n -text $nlab -font {Arial 9 bold} -bg white -anchor w
        entry $info.e -font {Courier 8} -fg "#222" -bg white -readonlybackground white \
            -relief solid -bd 1 -highlightthickness 0
        $info.e insert 0 $view
        $info.e configure -state readonly
        pack $info.n -fill x -anchor w
        pack $info.e -fill x -anchor w -pady {2 0}
        # przyciski (pionowo, waska kolumna)
        set b [frame $row.b -bg white]
        button $b.c -text [::hmShot::T "Kopiuj" "Copy"]    -width 11 -font {Arial 8} -command [list ::hmShot::copyView    $id]
        button $b.t -text [::hmShot::T "Testuj" "Test"]    -width 11 -font {Arial 8} -command [list ::hmShot::testRecord  $id]
        button $b.m -text [::hmShot::T "Miniatura" "Thumbnail"] -width 11 -font {Arial 8} -command [list ::hmShot::refreshThumb $id]
        button $b.e -text [::hmShot::T "Edytuj" "Edit"]    -width 11 -font {Arial 8} -command [list ::hmShot::editRecord   $id]
        button $b.x -text [::hmShot::T "Usu\u0144" "Delete"]  -width 11 -font {Arial 8} -command [list ::hmShot::deleteRecord $id]
        pack $b.c -fill x
        pack $b.t -fill x -pady {2 0}
        pack $b.m -fill x -pady {2 0}
        pack $b.e -fill x -pady {2 0}
        pack $b.x -fill x -pady {2 0}

        grid $row.cb  -row 0 -column 0 -sticky n -padx {4 2} -pady 6
        grid $row.img -row 0 -column 1 -sticky n -padx {0 8} -pady 4
        grid $info    -row 0 -column 2 -sticky we -pady 6
        grid $b       -row 0 -column 3 -sticky n -padx {8 6} -pady 4
        grid columnconfigure $row 2 -weight 1

        ::hmShot::bindWheelTree $row
        ::hmShot::bindFocusTree $row .hmshot
        incr r
    }
    ::hmShot::updateCount
    ::hmShot::onInnerConfigure $f
}

#---------------------------------------------------------------------
#  Folder / numeracja / eksport
#---------------------------------------------------------------------
proc ::hmShot::pickDir {} {
    set d ""
    catch {set d [tk_chooseDirectory -title [::hmShot::T "Wybierz folder na zrzuty" "Choose a folder for screenshots"]]}
    if {$d ne ""} { set ::hmShot::shotDir $d }
}
# Sciezka aktualnie otwartego pliku .hm. UWAGA: uzywamy tylko NIEINTERAKTYWNYCH
# komend (hm_getfilename otwiera okno dialogowe, wiec go NIE uzywamy). "" gdy brak.
# Probujemy kilku skladni (rozne buildy HM) i akceptujemy tylko wynik, ktory
# wyglada jak istniejacy plik lub sciezka *.hm.
proc ::hmShot::getModelFile {} {
    if {![::hmShot::cmdExists hm_info]} { return "" }
    foreach cmd {
        {hm_info hmfilename} {hm_info filename} {hm_info currentfile}
        {hm_info modelname} {hm_info model} {hm_info file}
        {hm_info -appinfo CURRENTMODEL} {hm_info -appinfo CURRENTFILE}
        {hm_info -appinfo MODELFILE} {hm_info -appinfo HMFILE} {hm_info -appinfo HMFILENAME}
        {hm_info -appinfo CURRENTHMFILE} {hm_info -appinfo MODELNAME} {hm_info -appinfo FILENAME}
        {hm_info -appinfo MODELPATH} {hm_info -appinfo CURRENTMODELFILE}
    } {
        set r ""
        if {[catch {set r [uplevel #0 $cmd]}]} { continue }
        set r [string trim $r]
        if {$r eq ""} { continue }
        if {[file isfile $r]} { return $r }
        if {[string match -nocase *.hm $r] && [file isdirectory [file dirname $r]]} { return $r }
    }
    return ""
}
# Folder otwartego modelu .hm (lub "").
proc ::hmShot::getModelDir {} {
    set f [::hmShot::getModelFile]
    if {$f eq ""} { return "" }
    set d [file dirname $f]
    if {[file isdirectory $d]} { return $d }
    return ""
}
# Natychmiastowa informacja po zaznaczeniu opcji "folder modelu".
proc ::hmShot::onModelDirToggle {} {
    if {!$::hmShot::saveToModelDir} {
        ::hmShot::setStatus [::hmShot::T "Zrzuty trafi\u0105 do wskazanego folderu." "Screenshots will go to the chosen folder."] ; return
    }
    set d [::hmShot::getModelDir]
    if {$d ne ""} {
        ::hmShot::setStatus [::hmShot::T "Wykryto folder modelu: $d" "Detected model folder: $d"]
    } else {
        ::hmShot::setStatus [::hmShot::T "Nie wykryto folderu modelu automatycznie \u2013 zostanie u\u017cyty wskazany folder." "Model folder not detected automatically \u2013 the chosen folder will be used."] "#b35a00"
    }
}
# Lista zaznaczonych nazw-presetow w ustalonej kolejnosci (REF: AR/Jac/Skew, INF: AR/Jac/Skew).
proc ::hmShot::presetNames {} {
    set out {}
    foreach {var name} {
        nmRefAR  REF_Aspect_Ratio
        nmRefJac REF_Jacobian
        nmRefSkew REF_Skewness
        nmInfAR  INF_Aspect_Ratio
        nmInfJac INF_Jacobian
        nmInfSkew INF_Skewness
    } {
        if {[set ::hmShot::$var]} { lappend out $name }
    }
    return $out
}
# Blokuje (wyszarza) pole prefiksu, gdy zaznaczono jakakolwiek nazwe automatyczna.
proc ::hmShot::updateNameUi {} {
    set on [expr {[llength [::hmShot::presetNames]] > 0}]
    if {$::hmShot::prefixEntry ne "" && [winfo exists $::hmShot::prefixEntry]} {
        catch {$::hmShot::prefixEntry configure -state [expr {$on ? "disabled" : "normal"}]}
    }
    if {$::hmShot::prefixLabel ne "" && [winfo exists $::hmShot::prefixLabel]} {
        catch {$::hmShot::prefixLabel configure -foreground [expr {$on ? "#999999" : "black"}]}
    }
}
# Zamienia znaki niedozwolone w nazwie folderu/pliku na "_".
proc ::hmShot::sanitizeName {s} {
    set s [string trim $s]
    regsub -all {[\\/:*?\"<>|]} $s "_" s
    if {$s eq ""} { set s "shot" }
    return $s
}
# Nastepny wolny numer (na podstawie istniejacych plikow w folderze).
proc ::hmShot::nextIndex {dir} {
    set mx 0
    foreach f [glob -nocomplain -directory $dir *] {
        set t [file rootname [file tail $f]]
        if {[regexp {([0-9]+)$} $t -> num]} {
            scan $num %d num
            if {$num > $mx} { set mx $num }
        }
    }
    return [expr {$mx + 1}]
}
# Iteruje po ZAZNACZONYCH widokach i robi pelnowymiarowe zrzuty do folderu.
# Po zrzutach (jesli wlaczone) zapisuje raport widokow (.txt + .xls).
# Eksportuje ZAPISANA KLATKE rekordu (WYSIWYG) do folderu docelowego, nie
# ruszajac biezacego stanu sesji HM. base = nazwa bez rozszerzenia, reqExt =
# zadany format (jpg/bmp), bg = docelowy hex tla ("" = bez zmiany).
#  - klatka JPG/PNG przy zadanym BMP: konwersja przez Tk photo (gdy sie da),
#  - gdy konwersja niemozliwa: kopia w formacie zrodlowym (uczciwa nazwa pliku),
#  - tlo: gdy narozniki KOPII nie zgadzaja sie z zadanym kolorem - przebarwienie
#    kopii (oryginal klatki zostaje nietkniety).
# Zwraca nazwe zapisanego pliku (tail) lub "" przy niepowodzeniu.
proc ::hmShot::exportStoredShot {rec base dir reqExt bg} {
    set src [::hmShot::viewShot $rec]
    if {$src eq "" || ![file isfile $src] || [file size $src] == 0} { return "" }
    set sExt [string tolower [string trimleft [file extension $src] .]]
    if {$sExt eq "jpeg"} { set sExt jpg }
    set outExt $sExt
    set target [file join $dir "$base.$outExt"]
    if {$reqExt eq "bmp" && $sExt ne "bmp"} {
        # konwersja do BMP przez Tk photo (o ile ten build czyta format zrodla)
        set img ""
        catch {set img [image create photo -file $src]}
        if {$img ne ""} {
            set tbmp [file join $dir "$base.bmp"]
            set okc [::hmShot::writeBmpFromPhoto $img $tbmp]
            catch {image delete $img}
            if {$okc && [file isfile $tbmp] && [file size $tbmp] > 0} {
                set target $tbmp ; set outExt bmp
            } else {
                catch {file delete -force $tbmp}
                if {[catch {file copy -force $src $target}]} { return "" }
            }
        } else {
            if {[catch {file copy -force $src $target}]} { return "" }
        }
    } else {
        if {[catch {file copy -force $src $target}]} { return "" }
    }
    # tlo: samokontrola narozniki -> przebarwienie kopii (jak w captureScreen)
    if {$bg ne ""} {
        set c [::hmShot::cornersOfFile $target]
        if {$c ne "" && ![::hmShot::cornersMatch $c $bg]} {
            lassign [::hmShot::recolorFileInPlace $target $bg] rok np
            if {$rok && $np ne $target} { set target $np }
        }
    }
    if {![file isfile $target] || [file size $target] == 0} { return "" }
    return [file tail $target]
}
proc ::hmShot::generate {} {
    set recs [::hmShot::selectedRecords]
    if {![llength $recs]} {
        ::hmShot::setStatus [::hmShot::T "Zaznacz przynajmniej jeden widok (checkbox po lewej)." "Select at least one view (checkbox on the left)."] red ; return
    }
    set dir [string trim $::hmShot::shotDir]
    set dirNote ""
    # Opcja: zapisz do folderu otwartego modelu .hm (nadpisuje wskazany folder).
    if {$::hmShot::saveToModelDir} {
        set md [::hmShot::getModelDir]
        if {$md ne ""} {
            set dir $md ; set dirNote [::hmShot::T " (folder modelu)" " (model folder)"]
        } else {
            set dirNote [::hmShot::T " (nie wykryto folderu modelu \u2013 u\u017cyto wskazanego)" " (model folder not detected \u2013 using the chosen one)"]
        }
    }
    if {$dir eq ""} { ::hmShot::setStatus [::hmShot::T "Wska\u017c folder zrzut\u00f3w (\u201eWybierz\u2026\u201d) lub zaznacz \u201efolder modelu\u201d." "Choose a screenshot folder (\u201eBrowse\u2026\u201d) or tick \u201emodel folder\u201d."] red ; return }
    set pfx [string trim $::hmShot::shotPrefix] ; if {$pfx eq ""} { set pfx "shot" }
    set ext [::hmShot::exportExt]
    set presets [::hmShot::presetNames]
    # Opcja: utworz podfolder i zapisuj zrzuty wlasnie tam. Nazwa podfolderu:
    #  - gdy pole prefiksu aktywne (brak nazw automatycznych) -> prefiks,
    #  - gdy pole prefiksu zablokowane (sa nazwy automatyczne) -> pierwsza zaznaczona nazwa.
    set subNote ""
    if {$::hmShot::makeSubfolder} {
        if {[llength $presets] > 0} {
            set sub [::hmShot::sanitizeName [lindex $presets 0]]
        } else {
            set sub [::hmShot::sanitizeName $pfx]
        }
        set dir [file join $dir $sub]
        set subNote [::hmShot::T " (podfolder: $sub)" " (subfolder: $sub)"]
    }
    if {[catch {file mkdir $dir} e]} { ::hmShot::setStatus [::hmShot::T "Nie mo\u017cna utworzy\u0107 folderu: $e" "Cannot create folder: $e"] red ; return }
    set start [::hmShot::nextIndex $dir]
    set nV [llength $recs] ; set ok 0 ; set fail 0
    set ::hmShot::lastExportFmt ""

    # Nazwy bazowe plikow: najpierw zaznaczone presety (po kolei). Gdy uzyto presetow,
    # prefiks NIE nazywa plikow (jest zablokowany) - ewentualne nadmiarowe widoki dostaja
    # neutralne "shot_NNN". Bez presetow: wszystkie pliki to "prefiks_NNN".
    set fbBase [expr {[llength $presets] > 0 ? "shot" : $pfx}]
    set baseNames {} ; set numIdx 0
    for {set i 0} {$i < $nV} {incr i} {
        if {$i < [llength $presets]} {
            lappend baseNames [lindex $presets $i]
        } else {
            lappend baseNames [format "%s_%03d" $fbBase [expr {$start + $numIdx}]] ; incr numIdx
        }
    }
    set nameNote ""
    if {[llength $presets] > 0 && [llength $presets] != $nV} {
        set nameNote [::hmShot::T " (nazw: [llength $presets], widok\u00f3w: $nV)" " (names: [llength $presets], views: $nV)"]
    }

    # Zrodlo eksportu: DOMYSLNIE zapisane klatki z chwili "Zapamietaj widok"
    # (WYSIWYG). Renderowanie na zywo tylko dla widokow bez klatki albo gdy
    # opcja WYSIWYG jest odznaczona. Przygotowanie sesji do zrzutow na zywo
    # (jakosc + tlo sceny) wykonywane LENIWIE, przy pierwszym takim widoku -
    # eksport samych zapisanych klatek NIE rusza stanu sesji uzytkownika.
    set bg [::hmShot::bgHex $::hmShot::bgMode]
    set qNote "" ; set bgNote "" ; set blog "" ; set gPrev ""
    set livePrepped 0

    set dispFails 0 ; set dispBehind 0 ; set viewFails 0 ; set zoomTuned 0 ; set zoomFails 0
    set okStored 0 ; set okLive 0
    set outNames {} ; set liveIdx {}
    for {set i 0} {$i < $nV} {incr i} {
        set rec  [lindex $recs $i]
        set base [lindex $baseNames $i]
        # 1) WYSIWYG: eksport klatki zapisanej przy "Zapamietaj widok" - widok
        #    wychodzi DOKLADNIE taki, jaki byl w chwili zapamietania; pozniejsze
        #    zmiany wygladu modelu (np. widok bezbarwny) NIE wplywaja na zrzut.
        if {$::hmShot::useStored && [::hmShot::storedShotUsable $rec]} {
            set fn [::hmShot::exportStoredShot $rec $base $dir $ext $bg]
            if {$fn ne ""} {
                incr ok ; incr okStored
                lappend outNames $fn
                ::hmShot::setStatus [::hmShot::T "Zrzut [expr {$i+1}] / $nV (zapisana klatka)\u2026" "Shot [expr {$i+1}] / $nV (stored frame)\u2026"] ; update idletasks
                continue
            }
            # klatki nie dalo sie uzyc -> renderowanie na zywo (jak dawniej)
        }
        # 2) Renderowanie na zywo: uklad + kamera + zrzut z biezacej sesji.
        if {!$livePrepped} {
            set livePrepped 1
            # Poprawa jakosci (jesli wlaczona): antyaliasing + maks. JPEG (+ rozdzielczosc).
            if {$::hmShot::hiQuality} {
                set qlog ""
                if {![::hmShot::applyQuality qlog]} {
                    set ::hmShot::lastQualityLog $qlog
                    set qNote [::hmShot::T " (brak komend jako\u015bci w tym HM)" " (no quality commands in this HM)"]
                }
            }
            # Tlo na czas zrzutu (jesli wybrano kolor): scena + weryfikacja tla ZRZUTU.
            if {$bg ne ""} {
                set gPrev [::hmShot::getBgGradient]
                if {![::hmShot::applyBg $bg blog]} {
                    set ::hmShot::lastBgLog $blog
                    set bgNote [::hmShot::T " (t\u0142a nie zmieniono \u2013 sprawd\u017a \u201eTestuj t\u0142o\u201d)" " (background unchanged \u2013 try \u201eTest background\u201d)"]
                } elseif {![::hmShot::ensureCaptureBg $bg]} {
                    set bgNote [::hmShot::T " (UWAGA: zrzut mo\u017ce mie\u0107 inne t\u0142o \u2013 log: $::hmShot::capBgLogPath)" " (WARNING: capture may use a different background \u2013 log: $::hmShot::capBgLogPath)"]
                }
                catch {hm_redraw} ; update idletasks
            }
        }
        set vw [dict get $rec view]
        # Najpierw UKLAD wyswietlania (sekcje/style/maskowanie) zarejestrowany z widokiem
        lassign [::hmShot::applyDispUpTo [::hmShot::recIndex [dict get $rec id]]] dR dF dB
        incr dispFails $dF
        if {$dB} { set dispBehind 1 }
        # Widok ustawiamy JAKO OSTATNI przed zrzutem (po przerysowaniu ponawiamy
        # *viewset, gdyby cokolwiek go cofnelo). Bez *plot (potrafil cofac widok).
        if {![::hmShot::applyView $vw]} { incr viewFails }
        catch {hm_redraw} ; ::hmShot::applyView $vw
        # HyperView: dostrojenie zoomu po pikselach do sylwetki wzorcowej (|ZM=)
        lassign [::hmShot::hvViewFineTune $vw] tuneOk tuneIt
        if {!$tuneOk} { incr zoomFails } elseif {$tuneIt > 0} { incr zoomTuned }
        catch {hm_redraw} ; ::hmShot::applyView $vw
        update idletasks ; catch {after 250}
        if {$bg ne ""} { ::hmShot::ensureCaptureBg $bg }
        set p [file join $dir "$base.${ext}"]
        if {[::hmShot::captureScreen $p]} { incr ok ; incr okLive } else { incr fail }
        lappend outNames "$base.${ext}"
        lappend liveIdx $i
        ::hmShot::setStatus [::hmShot::T "Zrzut [expr {$i+1}] / $nV\u2026" "Shot [expr {$i+1}] / $nV\u2026"] ; update idletasks
    }

    # Przywroc poprzedni stan gradientu tla (tylko gdy byly zrzuty na zywo).
    if {$livePrepped && $bg ne "" && $gPrev ne ""} { ::hmShot::setBgGradient $gPrev blog ; catch {hm_redraw} }

    # Faktyczne rozszerzenie plikow renderowanych na zywo (gdy wybrany format byl
    # podmieniony na dzialajacy). Zapisane klatki maja juz wlasciwe nazwy.
    set aext [expr {$::hmShot::lastExportFmt ne "" ? $::hmShot::lastExportFmt : $ext}]
    if {$aext ne $ext} {
        foreach li $liveIdx {
            set fn [lindex $outNames $li]
            lset outNames $li "[file rootname $fn].$aext"
        }
    }
    set repRows {}
    for {set i 0} {$i < $nV} {incr i} {
        set rec [lindex $recs $i]
        set fname [lindex $outNames $i]
        lappend repRows [dict create nr [expr {$i+1}] name [dict get $rec name] \
            file $fname path [file join $dir $fname] thumb [dict get $rec thumb] view [dict get $rec view] disp [::hmShot::viewDisp $rec]]
    }

    if {$::hmShot::hvRep ne ""} { ::hmShot::hvWriteRep }   ;# log kalibracji do folderu zrzutow
    set dispNote ""
    if {$viewFails > 0} {
        set hvd [expr {$::hmShot::hvDiagPath ne "" ? " (log: $::hmShot::hvDiagPath)" : ""}]
        append dispNote [::hmShot::T " (UWAGA: $viewFails widok\u00f3w nie uda\u0142o si\u0119 ustawi\u0107 \u2013 zrzuty mog\u0105 by\u0107 identyczne$hvd)" " (WARNING: $viewFails views could not be applied \u2013 shots may be identical$hvd)"]
    }
    if {$dispFails > 0} { append dispNote [::hmShot::T " (uk\u0142ad: $dispFails komend nie wykona\u0142o si\u0119)" " (layout: $dispFails commands failed)"] }
    if {$zoomTuned > 0} { append dispNote [::hmShot::T " (zoom dostrojony: $zoomTuned widok\u00f3w)" " (zoom fine-tuned: $zoomTuned views)"] }
    if {$zoomFails > 0} { append dispNote [::hmShot::T " (UWAGA: zoom niedostrojony dla $zoomFails widok\u00f3w)" " (WARNING: zoom not tuned for $zoomFails views)"] }
    if {$dispBehind}    { append dispNote [::hmShot::T " (uk\u0142ad: stan sesji jest dalej ni\u017c cz\u0119\u015b\u0107 widok\u00f3w \u2013 wczytaj model ponownie, aby odtworzy\u0107 wcze\u015bniejsze)" " (layout: session state is past some views \u2013 reload the model to reproduce earlier ones)"] }

    # Raport HTML (samodzielny, z osadzonymi podgladami) - jesli wlaczone.
    set repNote ""
    if {$::hmShot::wantReport && [llength $repRows]} {
        set done [::hmShot::writeViewsReport $dir $pfx $repRows]
        if {[llength $done]} {
            set names {} ; foreach f $done { lappend names [file tail $f] }
            set repNote [::hmShot::T " + raport ([join $names {, }])" " + report ([join $names {, }])"]
        } else {
            set repNote [::hmShot::T " (nie uda\u0142o si\u0119 zapisa\u0107 raportu)" " (could not save the report)"]
        }
    }

    set fmtNote ""
    if {$::hmShot::lastExportFmt ne "" && $::hmShot::lastExportFmt ne $ext} {
        set fmtNote [::hmShot::T " (format $ext niedost\u0119pny w tym HM \u2013 zapisano jako $::hmShot::lastExportFmt)" " (format $ext unavailable in this HM \u2013 saved as $::hmShot::lastExportFmt)"]
    }
    set srcNote ""
    if {$okStored > 0 && $okLive > 0} {
        set srcNote [::hmShot::T " (zapisane klatki: $okStored, renderowane na nowo: $okLive)" " (stored frames: $okStored, re-rendered: $okLive)"]
    } elseif {$okStored > 0} {
        set srcNote [::hmShot::T " (z zapisanych klatek \u2013 WYSIWYG)" " (from stored frames \u2013 WYSIWYG)"]
    } elseif {$::hmShot::useStored && $okLive > 0} {
        set srcNote [::hmShot::T " (renderowane na nowo \u2013 te widoki nie mia\u0142y zapisanych klatek)" " (re-rendered \u2013 these views had no stored frames)"]
    }
    if {$fail > 0} {
        ::hmShot::setStatus [::hmShot::T "Gotowe. Zapisano $ok (nie zapisano $fail \u2013 sprawd\u017a format/sciezke). Folder: $dir$dirNote$subNote$nameNote$fmtNote$srcNote$repNote$dispNote$bgNote$qNote" "Done. Saved $ok (failed $fail \u2013 check format/path). Folder: $dir$dirNote$subNote$nameNote$fmtNote$srcNote$repNote$dispNote$bgNote$qNote"] "#b35a00"
    } else {
        ::hmShot::setStatus [::hmShot::T "Gotowe. Zapisano $ok zrzut\u00f3w w: $dir$dirNote$subNote$nameNote$fmtNote$srcNote$repNote$dispNote$bgNote$qNote" "Done. Saved $ok screenshots in: $dir$dirNote$subNote$nameNote$fmtNote$srcNote$repNote$dispNote$bgNote$qNote"]
    }
}

proc ::hmShot::help {} {
    if {$::hmShot::lang eq "en"} {
        set t "SCREENSHOTS OF THE OPEN MODEL\n\n"
        append t "1. Set up the model in the graphics window the way you want it in the image.\n"
        append t "2. Click \u201eRemember view (1)\u201d or press the 1 key while the macro\n"
        append t "   window is active. A tile with a THUMBNAIL (preview) is created.\n"
        append t "   Repeat for the next views.\n"
        append t "3. Tick the CHECKBOXES for the views you want to export\n"
        append t "   (or use \u201eSelect/Deselect all\u201d).\n"
        append t "4. Each tile shows the VS data (you can select and copy it),\n"
        append t "   and the buttons are:\n"
        append t "     \u2022 Copy      \u2013 copies the VS data to the clipboard,\n"
        append t "     \u2022 Test      \u2013 sets this view on screen (to verify it),\n"
        append t "     \u2022 Thumbnail \u2013 refreshes the preview (sets the view, takes a shot,\n"
        append t "                   then restores the previous view),\n"
        append t "     \u2022 Edit      \u2013 changes the name and raw view data,\n"
        append t "     \u2022 Delete    \u2013 removes the tile.\n"
        append t "5. Choose the \u201eScreenshot folder\u201d (or tick \u201eSave to the open model's folder\u201d),\n"
        append t "   set the prefix, format and optionally the background (\u201eTest background\u201d checks it now).\n"
        append t "   \u201eCreate subfolder named after the prefix\u201d \u2013 shots go into a subfolder = prefix.\n"
        append t "   Automatic names: tick REF_/INF_ (Aspect_Ratio/Jacobian/Skewness), and the\n"
        append t "   selected views get these names in order. Once ticked, the prefix field is\n"
        append t "   locked (it then serves as the subfolder name).\n"
        append t "6. Click \u201eGenerate screenshots (K)\u201d or press the K key \u2013 files are created\n"
        append t "   ONLY for the ticked views: prefix_001.ext, prefix_002.ext\u2026\n"
        append t "   (numbering continues, so existing files are not overwritten).\n\n"
        append t "WYSIWYG \u2013 stored frames (\u25c9, option ticked by default):\n"
        append t " \u2022 At \u201eRemember view\u201d the macro also saves the FULL frame exactly as\n"
        append t "   shown on screen, and \u201eGenerate\u201d exports those frames. Later changes\n"
        append t "   of the model's appearance (e.g. switching to an uncolored view) no\n"
        append t "   longer affect views remembered EARLIER \u2013 each shot looks like the\n"
        append t "   screen did at its own moment.\n"
        append t " \u2022 Views without a stored frame (added from text, loaded from a session)\n"
        append t "   are re-rendered on the current model, as before. Untick the option to\n"
        append t "   force re-rendering for all views (e.g. after \u201eLoad session\u2026\u201d in a new\n"
        append t "   model). \u201eThumbnail\u201d refreshes both the preview and the stored frame.\n\n"
        append t "HTML REPORT / SESSION (when ticked) \u2013 created next to the screenshots:\n"
        append t "   prefix_widoki.html \u2013 ONE standalone file: a table with previews of\n"
        append t "                         each view (images embedded in the file), full VS,\n"
        append t "                         and a box with all VS to copy.\n"
        append t " \u2022 \u201eSave report\u2026\u201d writes this file without taking screenshots.\n"
        append t " \u2022 \u201eLoad session\u2026\u201d loads such a file back \u2013 it restores the list of\n"
        append t "   views together with previews, so after closing the macro you return\n"
        append t "   to the same window.\n\n"
        append t "DISPLAY LAYOUT (sections, FE/Geometry styles, masking\u2026) \u2013 \u2699:\n"
        append t " \u2022 Click \u201e\u25cf Record layout\u201d, perform sections / style changes / masking\n"
        append t "   in HM, then \u201eRemember view (1)\u201d \u2013 the commands from command.tcl are\n"
        append t "   attached to that view (\u2699 marker).\n"
        append t " \u2022 You can continue: further changes + further views; finally\n"
        append t "   \u201e\u25a0 Stop recording\u201d and \u201eSave report\u2026\u201d.\n"
        append t " \u2022 In a NEW model: \u201eLoad session\u2026\u201d \u2192 \u201eGenerate\u201d \u2013 before each shot the\n"
        append t "   macro replays the recorded commands (in order, each once) and then\n"
        append t "   sets the camera \u2013 screenshots look like in the reference model.\n"
        append t " \u2022 The layout can also be pasted/edited manually in \u201eEdit\u201d.\n"
        append t " \u2022 Notes: commands refer to IDs/names \u2013 the models must have matching\n"
        append t "   components; within one HM session the layout cannot be \u201erewound\u201d to\n"
        append t "   an earlier view (reload the model).\n\n"
        append t "Notes:\n"
        append t " \u2022 High quality: enables anti-aliasing and max JPEG quality (if HM exposes\n"
        append t "   such commands).\n"
        append t " \u2022 Screenshots concern the CURRENTLY open model \u2013 the macro loads nothing.\n"
        append t " \u2022 Also works in HyperView: the view and captures go through the hwi API\n"
        append t "   (the macro detects the application and picks the methods itself).\n"
        append t " \u2022 The 1 shortcut works when the cursor is over the macro window (not while typing).\n"
        append t " \u2022 Thumbnails: PNG/JPG/BMP attempted \u2013 the first working format is used.\n"
        append t "   If none works, a grey placeholder is shown instead of a preview."
    } else {
        set t "ZRZUTY EKRANU Z OTWARTEGO MODELU\n\n"
        append t "1. Ustaw model w oknie graficznym tak, jak chcesz na zdjeciu.\n"
        append t "2. Kliknij \u201eZapami\u0119taj widok (1)\u201d lub naci\u015bnij klawisz 1, gdy okno\n"
        append t "   makra jest aktywne. Powstanie kafelek z MINIATUR\u0104 (podgl\u0105dem uj\u0119cia).\n"
        append t "   Powt\u00f3rz dla kolejnych widok\u00f3w.\n"
        append t "3. Zaznacz CHECKBOXy przy widokach, kt\u00f3re chcesz wyeksportowa\u0107\n"
        append t "   (lub u\u017cyj \u201eZaznacz/Odznacz wszystkie\u201d).\n"
        append t "4. Na kafelku widoczne s\u0105 dane VS (mo\u017cna zaznaczy\u0107 i skopiowa\u0107),\n"
        append t "   a przyciski to:\n"
        append t "     \u2022 Kopiuj    \u2013 kopiuje dane VS do schowka,\n"
        append t "     \u2022 Testuj    \u2013 ustawia ten widok na ekranie (do sprawdzenia),\n"
        append t "     \u2022 Miniatura \u2013 od\u015bwie\u017ca podgl\u0105d (ustawia widok, robi zdj\u0119cie,\n"
        append t "                   po czym przywraca poprzedni widok),\n"
        append t "     \u2022 Edytuj    \u2013 zmienia nazw\u0119 i surowe dane widoku,\n"
        append t "     \u2022 Usu\u0144      \u2013 kasuje kafelek.\n"
        append t "5. Wska\u017c \u201eFolder zrzut\u00f3w\u201d (albo zaznacz \u201eZapisz do folderu modelu .hm\u201d),\n"
        append t "   ustaw prefiks, format i opcjonalnie t\u0142o (\u201eTestuj t\u0142o\u201d sprawdza od razu).\n"
        append t "   \u201eUtw\u00f3rz podfolder o nazwie prefiksu\u201d \u2013 zrzuty trafi\u0105 do podfolderu = prefiks.\n"
        append t "   Automatyczne nazwy: zaznacz REF_/INF_ (Aspect_Ratio/Jacobian/Skewness),\n"
        append t "   a kolejne zaznaczone widoki dostan\u0105 te nazwy po kolei. Po ich zaznaczeniu\n"
        append t "   pole prefiksu jest blokowane (s\u0142u\u017cy wtedy jako nazwa podfolderu).\n"
        append t "6. Kliknij \u201eGeneruj zrzuty (K)\u201d lub naci\u015bnij klawisz K \u2013 powstan\u0105 pliki\n"
        append t "   TYLKO dla zaznaczonych widok\u00f3w: prefiks_001.ext, prefiks_002.ext\u2026\n"
        append t "   (numeracja ci\u0105gnie si\u0119 dalej, wi\u0119c istniej\u0105ce pliki nie s\u0105 nadpisywane).\n\n"
        append t "WYSIWYG \u2013 zapisane klatki (\u25c9, opcja domy\u015blnie w\u0142\u0105czona):\n"
        append t " \u2022 Przy \u201eZapami\u0119taj widok\u201d makro zapisuje te\u017c PE\u0141N\u0104 klatk\u0119 \u2013 dok\u0142adnie\n"
        append t "   to, co wida\u0107 na ekranie \u2013 a \u201eGeneruj\u201d eksportuje w\u0142a\u015bnie te klatki.\n"
        append t "   P\u00f3\u017aniejsze zmiany wygl\u0105du modelu (np. prze\u0142\u0105czenie na widok\n"
        append t "   bezbarwny) NIE zmieniaj\u0105 ju\u017c widok\u00f3w zapami\u0119tanych WCZE\u015aNIEJ \u2013\n"
        append t "   ka\u017cdy zrzut wygl\u0105da tak, jak ekran w swojej chwili.\n"
        append t " \u2022 Widoki bez zapisanej klatki (dodane z tekstu, wczytane z sesji) s\u0105\n"
        append t "   renderowane na nowo na bie\u017c\u0105cym modelu, jak dawniej. Odznacz opcj\u0119,\n"
        append t "   aby wymusi\u0107 renderowanie wszystkich widok\u00f3w (np. po \u201eWczytaj sesj\u0119\u2026\u201d\n"
        append t "   w nowym modelu). \u201eMiniatura\u201d od\u015bwie\u017ca podgl\u0105d razem z klatk\u0105.\n\n"
        append t "RAPORT / SESJA HTML (gdy zaznaczony) \u2013 powstaje obok zrzut\u00f3w:\n"
        append t "   prefiks_widoki.html \u2013 JEDEN samodzielny plik: tabela z podgl\u0105dami\n"
        append t "                         ka\u017cdego widoku (obrazki osadzone w pliku),\n"
        append t "                         pe\u0142ne VS oraz pole z wszystkimi VS do kopiowania.\n"
        append t " \u2022 \u201eZapisz raport\u2026\u201d zapisuje ten plik bez robienia zrzut\u00f3w.\n"
        append t " \u2022 \u201eWczytaj sesj\u0119\u2026\u201d wczytuje taki plik z powrotem \u2013 odtwarza list\u0119\n"
        append t "   widok\u00f3w wraz z podgl\u0105dami, wi\u0119c po zamkni\u0119ciu makra wracasz\n"
        append t "   do tego samego okienka.\n\n"
        append t "UK\u0141AD WY\u015aWIETLANIA (sekcje, style FE/Geometry, maskowanie\u2026) \u2013 \u2699:\n"
        append t " \u2022 Kliknij \u201e\u25cf Nagrywaj uk\u0142ad\u201d, wykonaj w HM sekcje / zmiany styl\u00f3w /\n"
        append t "   maskowanie itd., potem \u201eZapami\u0119taj widok (1)\u201d \u2013 komendy z pliku\n"
        append t "   command.tcl zostan\u0105 do\u0142\u0105czone do tego widoku (znacznik \u2699).\n"
        append t " \u2022 Mo\u017cesz kontynuowa\u0107: kolejne zmiany + kolejne widoki; na koniec\n"
        append t "   \u201e\u25a0 Zako\u0144cz nagryw.\u201d i \u201eZapisz raport\u2026\u201d.\n"
        append t " \u2022 W NOWYM modelu: \u201eWczytaj sesj\u0119\u2026\u201d \u2192 \u201eGeneruj\u201d \u2013 przed ka\u017cdym zrzutem\n"
        append t "   makro odtworzy nagrane komendy (po kolei, ka\u017cd\u0105 raz), a potem ustawi\n"
        append t "   kamer\u0119 \u2013 zrzuty wygl\u0105daj\u0105 jak w modelu wzorcowym.\n"
        append t " \u2022 Uk\u0142ad mo\u017cna te\u017c wklei\u0107/poprawi\u0107 r\u0119cznie w \u201eEdytuj\u201d (pole \u201eUk\u0142ad\u201d).\n"
        append t " \u2022 Uwagi: komendy odwo\u0142uj\u0105 si\u0119 do ID/nazw \u2013 modele musz\u0105 mie\u0107 zgodne\n"
        append t "   komponenty; w jednej sesji HM nie da si\u0119 \u201ecofn\u0105\u0107\u201d uk\u0142adu do\n"
        append t "   wcze\u015bniejszego widoku (wczytaj model ponownie).\n\n"
        append t "Uwagi:\n"
        append t " \u2022 Wysoka jako\u015b\u0107: w\u0142\u0105cza antyaliasing i maks. jako\u015b\u0107 JPEG (je\u015bli HM\n"
        append t "   udost\u0119pnia takie komendy).\n"
        append t " \u2022 Zrzuty dotycz\u0105 AKTUALNIE otwartego modelu \u2013 makro niczego nie wczytuje.\n"
        append t " \u2022 Dzia\u0142a te\u017c w HyperView: widok i zrzuty id\u0105 przez API hwi\n"
        append t "   (makro samo wykrywa aplikacj\u0119 i dobiera metody).\n"
        append t " \u2022 Skr\u00f3t 1 dzia\u0142a, gdy kursor jest nad oknem makra (nie podczas pisania w polach).\n"
        append t " \u2022 Miniatury: pr\u00f3ba PNG/JPG/BMP \u2013 u\u017cywany jest pierwszy dzia\u0142aj\u0105cy format.\n"
        append t "   Gdy \u017caden nie zadzia\u0142a, zamiast podgl\u0105du wida\u0107 szar\u0105 zaslepk\u0119."
    }
    catch {tk_messageBox -type ok -icon info -title [::hmShot::T "Pomoc" "Help"] -message $t}
}

#---------------------------------------------------------------------
#  Skrot klawiszowy
#---------------------------------------------------------------------
# Czy fokus jest w polu tekstowym (zeby skrot D nie przeszkadzal w pisaniu).
proc ::hmShot::inTextEntry {} {
    set f [focus]
    if {$f eq "" || ![winfo exists $f]} { return 0 }
    return [expr {[winfo class $f] in {Entry TEntry Text Spinbox TCombobox}}]
}
# Obsluga klawisza D: zapamietaj widok (chyba ze wlasnie piszemy w polu).
proc ::hmShot::hotkeyRemember {} {
    if {[::hmShot::inTextEntry]} { return }
    ::hmShot::rememberView
}
# Obsluga klawisza K: zrob zrzuty (jak przycisk "Generuj zrzuty"), chyba ze piszemy.
proc ::hmShot::hotkeyCapture {} {
    if {[::hmShot::inTextEntry]} { return }
    ::hmShot::generate
}

#---------------------------------------------------------------------
#  GUI
#---------------------------------------------------------------------
proc ::hmShot::gui {} {
    catch {package require Tk}
    ::hmShot::checkImgSupport

    set w .hmshot
    catch {destroy $w}
    toplevel $w
    wm title $w [::hmShot::T "Zrzuty ekranu HyperMesh" "HyperMesh Screenshots"]
    wm resizable $w 0 1
    catch {wm minsize $w 640 480}

    set hdr [frame $w.hdr -bg "#1c5a96"]
    pack $hdr -fill x -side top
    # przelacznik jezyka (prawy gorny rog)
    set lng [frame $hdr.lng -bg "#1c5a96"]
    pack $lng -side right -padx 10 -pady 8 -anchor ne
    radiobutton $lng.pl -text "PL" -value pl -variable ::hmShot::lang \
        -command {::hmShot::setLang pl} -bg "#1c5a96" -fg white -selectcolor "#16487a" \
        -activebackground "#1c5a96" -activeforeground white -font {Arial 8 bold} -indicatoron 0 -width 3
    radiobutton $lng.en -text "EN" -value en -variable ::hmShot::lang \
        -command {::hmShot::setLang en} -bg "#1c5a96" -fg white -selectcolor "#16487a" \
        -activebackground "#1c5a96" -activeforeground white -font {Arial 8 bold} -indicatoron 0 -width 3
    pack $lng.pl $lng.en -side left -padx 1
    label $hdr.t -text [::hmShot::T "Zrzuty ekranu z otwartego modelu" "Screenshots of the open model"] -bg "#1c5a96" -fg white -font {Arial 14 bold} -anchor w
    label $hdr.s -text [::hmShot::T "Zapami\u0119taj widoki (z miniatur\u0105) \u2013 zaznacz \u2013 wygeneruj zdj\u0119cia" "Remember views (with thumbnail) \u2013 select \u2013 generate images"] -bg "#1c5a96" -fg "#cfe0f5" -font {Arial 9} -anchor w
    pack $hdr.t -fill x -padx 12 -pady {8 0}
    pack $hdr.s -fill x -padx 12 -pady {0 8}

    set body [frame $w.body]
    pack $body -fill both -expand 1 -padx 12 -pady 10

    # --- widoki (lista kafelkow) ---
    set lf [labelframe $body.lf -text [::hmShot::T " Zapami\u0119tane widoki " " Remembered views "] -font {Arial 9 bold} -padx 8 -pady 8]
    pack $lf -fill both -expand 1 -pady {0 8}

    # pasek narzedzi (dwa rzedy)
    set tb [frame $lf.tb]
    pack $tb -fill x -pady {0 4}
    button $tb.cap -text [::hmShot::T "Zapami\u0119taj widok (1)" "Remember view (1)"] -command ::hmShot::rememberView \
        -bg "#1c5a96" -fg white -activebackground "#16487a" -activeforeground white -font {Arial 9 bold}
    button $tb.all -text [::hmShot::T "Zaznacz wszystkie" "Select all"]  -command {::hmShot::setAllSel 1} -font {Arial 8}
    button $tb.non -text [::hmShot::T "Odznacz wszystkie" "Deselect all"]  -command {::hmShot::setAllSel 0} -font {Arial 8}
    pack $tb.cap -side left
    pack $tb.all -side left -padx {8 0}
    pack $tb.non -side left -padx {4 0}
    set ::hmShot::countLbl [label $tb.cnt -text [::hmShot::T "Zaznaczono: 0 / 0" "Selected: 0 / 0"] -font {Arial 8} -fg "#333"]
    pack $tb.cnt -side right

    set tb2 [frame $lf.tb2]
    pack $tb2 -fill x -pady {0 6}
    button $tb2.add  -text [::hmShot::T "Dodaj z tekstu\u2026" "Add from text\u2026"]   -command ::hmShot::addFromText  -font {Arial 8}
    button $tb2.rep  -text [::hmShot::T "Zapisz raport\u2026" "Save report\u2026"]    -command ::hmShot::saveReportNow -font {Arial 8}
    button $tb2.load -text [::hmShot::T "Wczytaj sesj\u0119\u2026" "Load session\u2026"] -command ::hmShot::loadSession   -font {Arial 8}
    button $tb2.rec  -text [::hmShot::T "\u25cf Nagrywaj uk\u0142ad" "\u25cf Record layout"] -command ::hmShot::recToggle -font {Arial 8}
    set ::hmShot::recBtn $tb2.rec
    ::hmShot::recBtnSync
    button $tb2.clr  -text [::hmShot::T "Wyczy\u015b\u0107" "Clear"]        -command ::hmShot::clearViews    -font {Arial 8}
    pack $tb2.add  -side left
    pack $tb2.rep  -side left -padx {8 0}
    pack $tb2.load -side left -padx {4 0}
    pack $tb2.rec  -side left -padx {12 0}
    pack $tb2.clr  -side left -padx {12 0}

    # canvas + scrollbar (przewijalna lista)
    set lc [frame $lf.lc]
    pack $lc -fill both -expand 1
    set cv [canvas $lc.cv -bg "#f0f0f0" -highlightthickness 0 -height 280 \
        -yscrollcommand [list $lc.sb set]]
    scrollbar $lc.sb -orient vertical -command [list $cv yview]
    pack $lc.sb -side right -fill y
    pack $cv -side left -fill both -expand 1
    set inner [frame $cv.inner -bg "#f0f0f0"]
    $cv create window 0 0 -anchor nw -window $inner -tags innerwin
    bind $cv <Configure> { %W itemconfigure innerwin -width %w }
    bind $inner <Configure> [list ::hmShot::onInnerConfigure %W]
    bind $cv <MouseWheel> {::hmShot::wheel %D}
    bind $cv <Button-4>   {::hmShot::wheel 120}
    bind $cv <Button-5>   {::hmShot::wheel -120}
    set ::hmShot::listCanvas $cv
    set ::hmShot::listInner  $inner

    label $lf.h -text [::hmShot::T "Ka\u017cdy kafelek = jeden widok. Zaznacz checkboxy, kt\u00f3re maj\u0105 trafi\u0107 do eksportu." "Each tile = one view. Tick the checkboxes you want to export."] \
        -font {Arial 8} -fg "#444444" -anchor w
    pack $lf.h -fill x -pady {6 0}

    # --- folder / format ---
    set of [labelframe $body.of -text [::hmShot::T " Zapis " " Output "] -font {Arial 9 bold} -padx 8 -pady 8]
    pack $of -fill x -pady {0 8}
    label $of.ld -text [::hmShot::T "Folder zrzut\u00f3w:" "Screenshot folder:"] -anchor w
    entry $of.ed -textvariable ::hmShot::shotDir -width 34
    button $of.bd -text [::hmShot::T "Wybierz\u2026" "Browse\u2026"] -command ::hmShot::pickDir
    label $of.lp -text [::hmShot::T "Prefiks plik\u00f3w:" "File prefix:"] -anchor w
    entry $of.ep -textvariable ::hmShot::shotPrefix -width 12
    set ::hmShot::prefixEntry $of.ep
    set ::hmShot::prefixLabel $of.lp
    checkbutton $of.sub -text [::hmShot::T "Utw\u00f3rz podfolder o nazwie prefiksu" "Create subfolder named after the prefix"] \
        -variable ::hmShot::makeSubfolder -anchor w
    label $of.lf -text [::hmShot::T "Format:" "Format:"] -anchor w
    set fmtm [tk_optionMenu $of.fmt ::hmShot::shotExt jpg bmp]
    checkbutton $of.md -text [::hmShot::T "Zapisz do folderu otwartego modelu (.hm)" "Save to the open model's folder (.hm)"] \
        -variable ::hmShot::saveToModelDir -anchor w -command ::hmShot::onModelDirToggle
    checkbutton $of.hq -text [::hmShot::T "Wysoka jako\u015b\u0107 (antyaliasing + maks. JPEG)" "High quality (anti-aliasing + max JPEG)"] \
        -variable ::hmShot::hiQuality -anchor w
    label $of.lb -text [::hmShot::T "T\u0142o zrzutu:" "Screenshot background:"] -anchor w
    # tlo: wartosc bgMode niezalezna od jezyka (lokalizujemy etykiete)
    set ::hmShot::bgMode [::hmShot::bgLabel [::hmShot::bgToken $::hmShot::bgMode] $::hmShot::lang]
    set bgm [tk_optionMenu $of.bg ::hmShot::bgMode {*}[::hmShot::bgLabels $::hmShot::lang]]
    button $of.bgtest -text [::hmShot::T "Testuj t\u0142o" "Test background"] -command ::hmShot::testBg -font {Arial 8}
    checkbutton $of.rep -text [::hmShot::T "Raport HTML (samodzielny, z osadzonymi podgl\u0105dami)" "HTML report (standalone, with embedded previews)"] \
        -variable ::hmShot::wantReport -anchor w
    checkbutton $of.ws -text [::hmShot::T "Eksportuj klatki zapisane przy \u201eZapami\u0119taj widok\u201d (WYSIWYG)" "Export the frames saved at \u201eRemember view\u201d (WYSIWYG)"] \
        -variable ::hmShot::useStored -anchor w
    grid $of.ld  -row 0 -column 0 -sticky w -padx {0 6} -pady 3
    grid $of.ed  -row 0 -column 1 -sticky we -pady 3
    grid $of.bd  -row 0 -column 2 -sticky w -padx {6 0} -pady 3
    grid $of.md  -row 1 -column 0 -columnspan 3 -sticky w
    grid $of.lp  -row 2 -column 0 -sticky w -padx {0 6} -pady 3
    grid $of.ep  -row 2 -column 1 -sticky w -pady 3
    grid $of.sub -row 2 -column 2 -sticky w -padx {6 0} -pady 3
    grid $of.lf  -row 3 -column 0 -sticky w -padx {0 6} -pady 3
    grid $of.fmt -row 3 -column 1 -sticky w -pady 3
    grid $of.hq  -row 3 -column 2 -sticky w -padx {6 0} -pady 3
    grid $of.lb  -row 4 -column 0 -sticky w -padx {0 6} -pady 3
    grid $of.bg  -row 4 -column 1 -sticky w -pady 3
    grid $of.bgtest -row 4 -column 2 -sticky w -padx {6 0} -pady 3
    grid $of.ws  -row 5 -column 0 -columnspan 3 -sticky w -pady {4 0}
    grid $of.rep -row 6 -column 0 -columnspan 3 -sticky w
    grid columnconfigure $of 1 -weight 1
    label $of.wsh -text [::hmShot::T "WYSIWYG: widok wychodzi dok\u0142adnie tak, jak wygl\u0105da\u0142 przy zapami\u0119taniu (\u25c9 na kafelku) \u2013 p\u00f3\u017aniejsze zmiany wygl\u0105du modelu nie psuj\u0105 wcze\u015bniejszych widok\u00f3w. Odznacz, aby renderowa\u0107 na nowo na bie\u017c\u0105cym modelu (np. po \u201eWczytaj sesj\u0119\u2026\u201d)." "WYSIWYG: a view is exported exactly as it looked when remembered (\u25c9 on the tile) \u2013 later changes of the model's appearance do not break earlier views. Untick to re-render on the current model (e.g. after \u201eLoad session\u2026\u201d)."] \
        -font {Arial 8} -fg "#444444" -anchor w -justify left -wraplength 560
    grid $of.wsh -row 7 -column 0 -columnspan 3 -sticky w -pady {2 0}
    label $of.bgh -text [::hmShot::T "Raport: prefiks_widoki.html \u2013 jeden samodzielny plik z podgl\u0105dami; mo\u017cna go p\u00f3\u017aniej wczyta\u0107 (\u201eWczytaj sesj\u0119\u2026\u201d)." "Report: prefix_widoki.html \u2013 one standalone file with previews; can be loaded later (\u201eLoad session\u2026\u201d)."] \
        -font {Arial 8} -fg "#444444" -anchor w
    grid $of.bgh -row 8 -column 0 -columnspan 3 -sticky w -pady {2 0}

    # --- automatyczne nazwy plikow ---
    set nf [labelframe $body.nf -text [::hmShot::T " Automatyczne nazwy plik\u00f3w " " Automatic file names "] -font {Arial 9 bold} -padx 8 -pady 6]
    pack $nf -fill x -pady {0 8}
    checkbutton $nf.r1 -text "REF_Aspect_Ratio" -variable ::hmShot::nmRefAR  -anchor w -command ::hmShot::updateNameUi
    checkbutton $nf.r2 -text "REF_Jacobian"     -variable ::hmShot::nmRefJac -anchor w -command ::hmShot::updateNameUi
    checkbutton $nf.r3 -text "REF_Skewness"     -variable ::hmShot::nmRefSkew -anchor w -command ::hmShot::updateNameUi
    checkbutton $nf.i1 -text "INF_Aspect_Ratio" -variable ::hmShot::nmInfAR  -anchor w -command ::hmShot::updateNameUi
    checkbutton $nf.i2 -text "INF_Jacobian"     -variable ::hmShot::nmInfJac -anchor w -command ::hmShot::updateNameUi
    checkbutton $nf.i3 -text "INF_Skewness"     -variable ::hmShot::nmInfSkew -anchor w -command ::hmShot::updateNameUi
    grid $nf.r1 -row 0 -column 0 -sticky w -padx {0 18}
    grid $nf.i1 -row 0 -column 1 -sticky w
    grid $nf.r2 -row 1 -column 0 -sticky w -padx {0 18}
    grid $nf.i2 -row 1 -column 1 -sticky w
    grid $nf.r3 -row 2 -column 0 -sticky w -padx {0 18}
    grid $nf.i3 -row 2 -column 1 -sticky w
    label $nf.h -text [::hmShot::T "Zaznaczone nazwy trafiaj\u0105 do kolejnych zaznaczonych widok\u00f3w (po kolei: REF AR/Jac/Skew, potem INF). Gdy zaznaczysz nazwy, pole prefiksu jest blokowane; podfolder (je\u015bli w\u0142\u0105czony) dostaje wtedy nazw\u0119 pierwszej zaznaczonej nazwy." "Ticked names are assigned to the selected views in order (REF AR/Jac/Skew, then INF). When names are ticked, the prefix field is locked; the subfolder (if enabled) then takes the first ticked name."] \
        -font {Arial 8} -fg "#444444" -anchor w -justify left -wraplength 560
    grid $nf.h -row 3 -column 0 -columnspan 2 -sticky w -pady {4 0}

    button $body.go -text [::hmShot::T "Generuj zrzuty (K)" "Generate screenshots (K)"] -command ::hmShot::generate \
        -bg "#5BA314" -fg white -activebackground "#4a8810" -activeforeground white \
        -font {Arial 11 bold} -relief raised -bd 2 -padx 10 -pady 6
    pack $body.go -fill x -pady {0 8}

    set bb [frame $body.bb]
    pack $bb -fill x
    button $bb.help -text [::hmShot::T "? Pomoc" "? Help"] -command ::hmShot::help
    button $bb.close -text [::hmShot::T "Zamknij" "Close"] -command {destroy .hmshot}
    pack $bb.help -side left
    pack $bb.close -side right

    set sb [frame $w.sb -relief sunken -bd 1]
    pack $sb -fill x -side bottom
    set ::hmShot::statusLbl [label $sb.l -text "" -anchor w -font {Arial 8} -fg "#1a7a1a"]
    pack $sb.l -fill x -padx 6 -pady 2

    # licznik zaznaczonych aktualizowany na biezaco wraz z checkboxami
    catch {trace remove variable ::hmShot::selArr write ::hmShot::updateCount}
    trace add variable ::hmShot::selArr write ::hmShot::updateCount

    # Skrot klawiszowy: 1 zapamietuje widok, K robi zrzuty (gdy okno makra aktywne).
    bind $w <Key-1>  {::hmShot::hotkeyRemember}
    bind $w <KP_1>   {::hmShot::hotkeyRemember}
    bind $w <Key-k> {::hmShot::hotkeyCapture}
    bind $w <Key-K> {::hmShot::hotkeyCapture}
    catch {focus -force $w}
    # Focus podazajacy za myszem -> D dziala, gdy kursor jest nad oknem makra.
    ::hmShot::bindFocusTree $w $w
    ::hmShot::updateNameUi

    ::hmShot::redrawList
    ::hmShot::setStatus [::hmShot::T "Ustaw widok i naci\u015bnij 1 (zapami\u0119taj). Zrzuty: klawisz K lub \u201eGeneruj zrzuty\u201d." "Set the view and press 1 (remember). Screenshots: press K or \u201eGenerate screenshots\u201d."]
}

::hmShot::gui
