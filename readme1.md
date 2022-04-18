# Implementační dokumentace k 1. úloze do IPP 2021/2022  
Jméno a příjmení: Matej Matuška  
Login: xmatus36

## Parse.php
Skript sa náchadza v jednom súbore, pretože jeho rozdelenie do viacerých súborov by viedlo k zbytočnej zložitosti. Kód je štrukturovaný do logických celkov s využitím procedurálneho programovania, teda bez použitia tried. Okrem tejto dokumentácie je každá funkcia v zdrojovom kóde zdokumentovaná.

### Princíp fungovania
Po spracovaní argumentov programu sa vstup spracováva postupne riadok po riadku, pričom komentáre a prázdne riadky sú ignorované. Riadok je rozdelený na tokeny. Na základe inštrukcie sú lexikálne a syntakticky kontrolované jej prípadné argumenty - počet argumentov a ich typy. Pokiaľ sú inštrukcia a jej argumenty lexikálne i syntakticky správne je vygerenovaný príslušný `<instruction>` element a jeho `<argX>` podelementy vo výstupnom XML.

Vzhľadom na relatívnu jednoduchosť jazyka IPPcode22 je samotná lexikálna analýza implementovaná z veľkej časti pomocou regulárnych výrazov. Často používanou funkciou je `preg_match`. 

Implementácia syntaktickej analýzy bola intuitívna. Pozostáva v podstate z kontroly typov (premenná, literál,...) argumentov jednotlivých inštrukcií. Používaný je pojem `symbol`, ktorý označuje typ premenná alebo typ literál.

### Generovanie výstupného XML dokumentu
Generovanie výstupného XML sa vykonáva pomocou knižnice `SimpleXMLElement`, v ktorej avšak nie je možné nastaviť `encoding` (kódovanie) a preto je v konštruktore napevno zadané. Ďalším nedostatkom knižnice je to, že nie je môžné výsledné XML naformátovať. Tento problém rieši knižnica `DOM`, ktorá výsledné XML pred vypísaním naformátuje.  
V reťazcoch a menách premenných zo vstupného programu sú pred generovaním príslušného XML elementu problematické znaky prevedené na ich XML reprezentáciu (napr. `&` na `&amp;`).


