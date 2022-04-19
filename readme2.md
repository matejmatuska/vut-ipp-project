# Implementační dokumentace k 2. úloze do IPP 2021/2022  
Jméno a příjmení: Matej Matuška  
Login: xmatus36

## interpret.py
Implementácia skriptu je obsiahnutá v jednom súbore. Kód je štrukturovaný do logických celkov s využitím procedurálneho aj objektovo orientovaného programovania. Okrem tejto dokumentácie je každá funkcia a trieda v zdrojovom kóde zdokumentovaná.

### Vnútorná reprezentácia
Vnútorne sú inštrukcie reprezentované objektmi triedy `Instruction`, ktorá obsahuje tzv. opcode, ale aj zoznam argumentov inštrukcie. Trieda `Frames` riadi vytváranie a prístup k rámcom a premenným. Jendotlivé premenné, ale aj symboly a niektoré ďalšie hodnoty sú reprezentované triedou `TypedValue` ktorá okrem samotnej hodnoty drží aj jej typ, ktorý obmedzuje výpočet `Type`. Dátový zásobník a zásobník volania sú implementované pomocou Python zoznamov. Náveštia sú namapované na adresy v Python slovníku. Jednotlivé inštrukcie sú implementované funkciami prípadne lambda funkciami.

### Princíp fungovania
Po spracovaní argumentov programu sa zo vstupného zdrojového súboru (prípadne štandarného vstupu) vytvorí vnútorná XML reprezentácia s použitím knižnice `xml.etree.ElementTree` a z potom nej vnútorná reprezentácia. Pri prvom priechode cez všetky inštrukcie sa uložia do mapy náveští ich adresy. Pri druhom priechode sú postupne v cykle volané (lambda) funkcie implementujúce jednotlivé inštrukcie na základe opcode inštrukcie.

Volanie a návrat z funckií zabezpečuje zásobník volaní tzv. `callstack`, na ktorom sú ukladané návratové adresy. 

Pomerne dôležitou funkciou je `Frames.resolve_symbol()`, ktorá, pokiaľ je symbolom premenná, vráti jej hodnotu a typ, inak vráti ten istý symbol. A teda, ak môže byť argumentom inštrukcie premenná alebo hodnota, nie je nutné toto rozlišovať.

## test.php
Skript je implementovaný v jednom súbore. Kód je štrukturovaný do logických celkov s využitím procedurálneho programovania. Každá funkcia a trieda v zdrojovom kóde sú zdokumentované.

### Vnútorná reprezentácia
Skript využíva dve pomocné triedy využívané ako klasické štruktúry ako napr. v jazyku C. Trieda `Arguments` obsahuje argumenty a ich implicitné hodnoty. Trieda `Stats` obsahuje celkový počet vykonaných testov a počet úspešne vykonaných testov.  

### Pricíp činnosti
Po spracovaní a kontrole argumentov programu sú testy prechádzané funkciou `exec_tests_rec`, ktorá vykoná všetky testy v zadanom adresári testov. Pokiaľ adresár testov obsahuje podadresáre a skript bol spustený s argumentom `--recursive`, funkcia rekurzívne volá sama seba na každý z podadresárov a vykoná tak aj všetky testy v podadresároch, pričom zanorenie podadresárov je limitované len veľkosťou zásobníka. 

Samotné vykonávanie testu má na starosti funkcia `exec_test()`, ktorá pred vykonaním vygeneruje chýbajúce vstupné súbory a následne podľa argumentov programu vykoná test skriptov parse.php a/alebo interpret.py. Súbory generované týmito skriptami sú ukladané v adresári `test-out` s rovnakou štruktúrov podadresárov ako súbory testov. Ak nebol zadaný argument programu `--noclean` sú tieto súbory po vykonaní testu odstraňované. 

V priebehu činnosti skript vypisuje priebeh a výsledky jednotlivých testov na štandardný chybový výstup a zároveň generuje HTML dokument s výsledkami testov na štandardný výstup.

### Generovanie výstupného HTML dokumentu
Skript pred vykonaním testu vypíše hlavičku HTML, ktorá obsahuje najmä CSS štýly. Taktiež vygeneruje hlavičku tabuľky v tele HTML dokumentu, do ktorej je potom po každom vykonanom teste vygenerovaný záznam. Po vykonaní všetkých testov je vygenerovaná druhá tabuľka, ktorá zobrazuje štatistiky o výkone testov. Nakoniec je HTML dokument ukončený. 

Úspešnosť testov je farebne odlíšená.



