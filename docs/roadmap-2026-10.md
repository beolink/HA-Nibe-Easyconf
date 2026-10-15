# Roadmap för Nibe Local Easyconf

Nibe Local Easyconf står på 1.15.0, släppt 2026-10-15 och utrullad samma morgon på båda husen: HA FB med en S1155-16 över Modbus TCP (1 203 entiteter, 158 påslagna) och HA VV med en F1255-16 CU genom NibeGW-gatewayen (990 entiteter, 112 påslagna). 368 tester går gröna, 327 utan Home Assistant och 41 under en riktig kärna. Starkt i dag: pumpen probas i stället för att gissas ur en registerkarta, och svarar därför bara med det den har; varje register förklaras på svenska och engelska för någon som äger en värmepump, inte för en servicetekniker; F-serien får en värmefaktor ur en räknad elsiffra där pumpen saknar elmätare; sidan bär översikt, styrning, grafer och hela listan på en flik var; skanningen läser om sig själv efter en uppdatering; och sedan 1.15.0 finns termostat, varmvattenberedare och knappar, byggda av register som redan fanns, så att Home Assistants eget termostatkort, schemaläggare och röstassistenter talar med pumpen.

Granskningen lämnade 45 poster: 38 förslag (R1 till R38), fyra luckor som kritikerpasset fann (L1 till L4) och tre iakttagelser från husen samma dag (V1 till V3). Den svarar på fyra saker: att det som är fel eller bara lovat blir rätt och bevisat - givare som inte finns ska inte vara påslagna entiteter, en tryckning på sidan ska inte registrera ett tillbehör i pumpen, och CI ska köra de tester som faktiskt gäller Home Assistant; att integrationen förklarar sina egna tystnader i stället för att överlåta det till den som frågar; att sidan säger vad pumpen gör, varför och vad det kostar, även på en telefon; och att en främling med en S1255 eller en F750 kan installera, felanmäla och ta bort den utan hjälp från Täby. Sist står det som kräver en mätning i husen eller ett beslut av ägaren.

Så togs roadmapen fram, och det skiljer sig från CTC-roadmapen: en läsare, inte fem. Varje modul lästes i sin helhet - 35 Python-filer, kortet, testerna, CI och README - och åtta perspektiv gicks igenom i tur och ordning (driftsäkerhet, HA-idiomatik, data och insikt, dashboardens utseende, dashboardens styrning, underhållbarhet, säkerhet och integritet, spridning). Varje förslag prövades mot koden för genomförbarhet och mot ägarens faktiska behov för värde, ur minnesanteckningarna om husen och ur de två installationernas levande tillstånd, läst genom Supervisor-API:t 2026-10-15 (entiteter, otillgängliga rader, larm, en veckas loggrader). Ett kritikerpass letade luckor i det som just byggts och i det som en mogen HA-integration brukar ha. Sidan har däremot inte gåtts igenom i en webbläsare: den kräver inloggning, och det står bland de öppna frågorna. Varje post bär sina belägg som fil och rad; radnumren gäller commit fe65b66 (1.15.0).

| Fas | Poster | Vad fasen ger |
|---|---|---|
| Fas 1: rätt och säkert | 12 | Inga påslagna entiteter som alltid är otillgängliga, inga tillbehörsflaggor som brytare, ingen nolla av misstag från talfältet, en start som inte väntar på skanningen, och en CI som kör HA-sviten. |
| Fas 2: nytta i vardagen | 10 | Larmet märks, värmefaktorn finns per vecka och månad, spetsvärmeandelen syns, och sidan visar vad pumpen gjorde när och varför - kretsen, gradminuterna och dygnsremsan. |
| Fas 3: enkelt för nybörjaren och externa användare | 5 | README säger hur man tar bort, kopplar till energipanelen och felanmäler; adressen kan bytas utan ny installation; flödets texter och F-seriens ord finns på svenska. |
| Fas 4: kraft för den avancerade | 3 | Priset per kWh värme, kortet i korteditorn, och tangentbord och skärmläsare som fungerar. |
| Fas 5: hållbart att underhålla och sprida | 5 | Släpp ur taggen med kontroller, kvalitetsskalan som checklista, S-serien och kortets DOM under test, och statistikens egna nycklar hållna mot backenden. |
| Fas 6: väntar på mätning eller beslut | 7 | Sju poster som väntar på ett prov på FB eller VV, hårdvara ingen här har, eller ett ja från ägaren. |

## Gör nu

Små poster utan beroenden som ger tydlig nytta direkt.

- **R4: Talfältet skriver aldrig 0 av misstag, reglaget skriver en gång, och en avvisad skrivning syns** (dashboard, Fas 1). Ett tömt fält skriver i dag `Number("") = 0` till pumpen - på kurvförskjutningen är 0 ett giltigt värde.
- **L1: Termostaten erbjuder inte heat/cool på en pump utan kyla** (teknik, Fas 1). Infördes i 1.15.0: F1255:an på VV har ingen kyla men kyltabellen finns i kartan.
- **R8: Samtyckestexten är på ett språk och säger allt** (teknik, Fas 1). Den svenska texten slutar med en engelsk mening om `ha_id` och loggräknare.
- **R7: Husens adresser bort ur de publika testerna** (teknik, Fas 1). Gatewayens riktiga adress står i två testfiler.
- **R9: Tjänsterna finns innan någon post laddats** (teknik, Fas 1). Kvalitetsskalans action-setup; en tjänst som inte finns ger ett obegripligt fel i en automation.
- **R12: Värmefaktor över 7 och 30 dygn** (teknik, Fas 2). Proven sparas redan i 400 dagar; bara divisionen saknas.
- **R14: Kompressorstarter som räknare** (teknik, Fas 2). Utan enhet får registret ingen state_class och ingen långtidsstatistik.
- **R10: Sidan får inte svämma över på en smal telefon** (dashboard, Fas 1). Två rutnät kräver 340 px på en skärm som har 288.
- **L2: Kortets ordtabeller har samma nycklar på alla fyra språk** (dashboard, Fas 1). Ett ord som saknas på ett språk visas som `undefined`.

## Fas 1: rätt och säkert

Det som är fel eller bara lovat. S-serien slår på entiteter för givare pumpen inte har och visar dem otillgängliga för evigt (R1, V2); tillbehörsflaggorna är brytare på fliken Styrning, så en tryckning registrerar en frånluftsmodul i pumpen (R2); omskanningen efter en uppdatering håller upp Home Assistants start (R3, V3); talfältet kan skriva 0 och reglaget skriver för varje piltryck (R4); integrationen vet varför en siffra saknas men säger det bara i loggen (R5); CI hoppar över de 41 tester som gäller Home Assistant (R6); husens adresser står i de publika testerna (R7); samtycket blandar språk (R8); tjänsterna finns först när en post laddats (R9); sidan svämmar över på telefon (R10); och två luckor i 1.15.0 (L1, L2). Klar när FB:s 16 otillgängliga rader är borta eller förklarade, när ingen tillbehörsflagga kan vändas av misstag, när CI är röd om HA-sviten faller, och när ett tömt fält inte skriver något.

### Teknik

#### R1: S-serien: en givare som inte rapporterar blir ingen påslagen entitet

**Problem.** På S-serien avgör `default_enabled` om en entitet är på ur titeln ensam (`is_core_register`), aldrig ur vad skanningen fann. `CORE_COMPONENTS` räknar upp BT16, BT20 och BT21 - förångare och frånluftsgivare - så en bergvärmepump utan frånluft får sex frånluftsgivare påslagna som svarar med sentinellen. HA FB har 16 sådana sedan varje omstart: fem inställningar för externa givare, tre BT20, tre BT21, returledning EP15, lågtryck, förångare BT16, displayens varmvattengivare och förångare 2 (V2). F-serien gör rätt: `fseries.is_default(meta, reporting)` kräver ett värde vid skanningen. **Lösning.** `NibeCoordinator.default_enabled` tar hänsyn till `discovery.reporting` på samma sätt; en entitet för ett register som svarade sentinellen skapas avstängd. `_async_switch_on_new_defaults` slår redan på det integrationen själv stängt av när `default_enabled` blir sant, så en givare som börjar rapportera efter en omskanning slår på sig själv. Befintliga installationer: integrationen kan inte veta om ägaren slog på raderna, så de får ett reparationsärende (R5) som räknar upp dem och erbjuder att stänga av. **Nytta.** FB slipper 16 rader som aldrig säger något; externa S-användare får en enhetssida där otillgänglig betyder något; underhållaren slipper frågan "varför är frånluft otillgänglig på min bergvärmepump".

Ansträngning: S. Risk: låg. Beroenden: R5 för de befintliga. Belägg: custom_components/nibe_local_easyconf/coordinator.py:131, const.py:62 till 69 och 162 till 183, entity.py:50, gateway_coordinator.py:272, fseries.py:491 till 505; HA FB 2026-10-15 09:55, 16 rader `unavailable` sedan 07:42:07.

#### R2: Tillbehörsflaggorna kan vändas med en tryckning, och står på fliken Styrning

**Problem.** Varje register vars titel slutar på "accessory" är påslaget (`is_accessory_flag` först i `is_core_register`), och eftersom det är skrivbart 0/1 blir det en `switch`. Kortet räknar alla brytare som styrning, så "FLM 1 accessory", "Pool 1 accessory" och "EME20 Activated" står som växlar under Styrning, och en tryckning säger åt pumpen att den har en frånluftsmodul eller en energimätare. På VV är 47302 till 47304, 48930 och 49297 sådana, alla på som förval. Avsnittet "Tillbehör registrerade" på sidan är tänkt som ett svar, inte som en knapprad. **Lösning.** Flaggorna blir `binary_sensor` som förval - svaret ja eller nej, grönt eller rött som i dag - och `_async_remove_moved_entities` tar bort brytarna. Den som monterar ett tillbehör registrerar det på pumpens display, som NIBE avser; för den som ändå vill skriva från Home Assistant tar alternativen ett "installatörsläge" som gör dem till brytare igen. Kortets `controlRows` lämnar dessutom allt som matchar `ACCESSORY_PATTERN` utanför Styrning oavsett domän. **Nytta.** Alla: ett tillbehör kan inte registreras av misstag från en telefon i soffan. Externa användare med okända modeller mest, där flaggornas betydelse är minst känd.

Ansträngning: M. Risk: medel - entitetsdomänen byts, så en automation som läser `switch.*_accessory` får ett nytt id; README säger det, och ingen sådan automation är känd. Beroenden: inga. Belägg: const.py:148 till 183 och 222 till 240, nibe-easyconf-card.js:450 till 457 och 347; VV 2026-10-15, `nle_reg.sh`: 47302 Climate system 2 accessory = Off (val: Off, On), 48930/49297 default_on.

#### R3: Omskanningen efter en uppdatering håller inte upp starten

**Problem.** När integrationens version är en annan än skanningens läses registren om inuti `async_setup_entry` - omkring en minut på S-serien, "en och en halv minut" genom gatewayen - innan en enda entitet finns. Home Assistant varnade på FB 2026-10-15 09:42:02: "Waiting for integrations to complete setup: nibe_local_easyconf" (V3). Varje release gör det igen i varje hus. **Lösning.** Posten sätts upp direkt på den sparade skanningen; omläsningen körs som bakgrundsuppgift efter `async_at_started`, och posten laddas om bara om `present` eller `reporting` ändrades. Misslyckas den behålls den gamla, som i dag. **Nytta.** Alla hus: en uppdatering kostar inte en minut utan entiteter; EMS på VV, som binder värmeläget, ser det inte försvinna och komma tillbaka.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: __init__.py:224 till 235 och den motsvarande gatewaygrenen under `_async_setup_gateway_entry` ("en minut och en halv" i kommentaren), storage.py:1 till 18; HA FB-loggen 2026-10-15 09:42:02.

#### R5: Reparationer: integrationen förklarar sina egna tystnader

**Problem.** Fyra saker som integrationen vet säger den bara i loggen eller inte alls: att pumpens värmemätare står stilla och därför ingen värmefaktor finns (`_async_remove_cop_entities` efter en WARNING), att omskanningen misslyckades och den gamla används, att gatewayen inte svarat (UpdateFailed, entiteter otillgängliga, ingen orsak i gränssnittet), och att en termostat saknar rumsgivare (ett attribut, `room_sensor_fitted`). De tre supportfrågor som ställdes om husen i oktober - varför VV saknar COP, varför FB saknade inomhustemperatur, varför en status var en siffra - var alla sådana. **Lösning.** `repairs.py` med ärenden för: värmemätare som inte rör sig (text ur `heat_not_counted`, EMK 300/500), skanning som behölls, gateway tyst över tio minuter, påslagna entiteter som alltid är otillgängliga (R1, med en åtgärd som stänger av dem), och rumsgivare som saknas när någon väljer heat. Texterna i strings.json på båda språken. **Nytta.** Externa användare får skälet där de letar; ägaren slipper ställa frågan; underhållaren slipper svara.

Ansträngning: M. Risk: låg. Beroenden: R1. Belägg: __init__.py:392 och 399 (varningen och borttagningen), 229 till 235, gateway_coordinator.py:368 till 372, climate.py:242 (attributet).

#### R6: CI kör Home Assistant-sviten

**Problem.** Jobbet `tests` installerar `pytest` och `nibe` och inget mer, så `tests/test_gateway_homeassistant.py` (38 tester) och `tests/test_write_homeassistant.py` (3) hoppas över med `importorskip`. Allt som gäller uppsättningsflödet, entiteterna under en riktig kärna, termostaten, varmvattenberedaren och återläsningen testas bara på Macen. En grön CI säger inget om det. **Lösning.** Ett jobb till med `pytest-homeassistant-custom-component` i två lägen: husens Home Assistant (2026.9) och golvet i hacs.json (2025.2), på den Python respektive release kräver, med `-o asyncio_mode=auto` som lokalt. Matrisen säger varför varje ben finns. **Nytta.** Underhållaren: en ändring som bryter uppsättningen blir röd innan den når husen; externa bidragsgivare får samma svit som ägaren.

Ansträngning: S till M - pytest-homeassistant-custom-component drar hela kärnan, några minuter per ben. Risk: medel, golvet 2025.2 kan sakna något sviten antar; då sägs det i matrisen. Beroenden: inga. Belägg: .github/workflows/validate.yml:29 till 51, tests/test_gateway_homeassistant.py:21 (`pytest.importorskip`), tests/test_write_homeassistant.py:14; 41 av 368 tester.

#### R7: Hygien: husens adresser bort ur de publika testerna

**Problem.** `tests/test_gateway_homeassistant.py:49` sätter `HOST = "10.0.50.47"`, gatewayens riktiga adress i VV, och `tests/test_gateway.py:182` använder samma; `tests/test_write_homeassistant.py:5` säger "site 120", som är FB:s adressnät. Ett publikt repo ska inte bära husens nät. **Lösning.** RFC 5737-adresser (192.0.2.47) i testerna, "utvecklingsenheten" och "det andra huset" i texterna, och ett hygientest som fäller sviten om ett 10.x-nät eller en riktig serie dyker upp igen - som CTC:s F6.1. Commit-historiken lämnas. **Nytta.** Ägaren, vars nät i dag ligger på GitHub; externa som delar loggar.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: tests/test_gateway_homeassistant.py:49, tests/test_gateway.py:182, 206, 325, 350, tests/test_write_homeassistant.py:5.

#### R8: Samtyckestexten är på ett språk och säger allt

**Problem.** `send_statistics` under alternativen är en svensk text som slutar med en engelsk mening: "It also sends a hash that links the beolink plugins running on the same Home Assistant, how many warnings and errors the integration logged since the previous report, and whether it is running or waiting to start again". Den meningen är den enda som nämner `ha_id` och loggräknarna, så den svenska läsaren får dem bara om den läser engelska. Samma text i strings.json och sv.json. **Lösning.** Meningen på svenska, och ett test som läser de tre filernas alternativtexter och fäller en text som blandar språk (ett engelskt funktionsord i sv, ett svenskt i en). **Nytta.** Externa svenska användare får ett sant samtycke; ägaren får löftet och nyttolasten lika på båda språken.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: strings.json:105 och translations/sv.json, samma nyckel; README, Anonymous statistics.

#### R9: Tjänsterna finns innan någon post laddats

**Problem.** `_register_services` anropas från `async_setup_entry`, och det finns inget `async_setup`. Före den första posten, eller medan pumpen inte svarar och posten ligger i SETUP_RETRY, finns inte `rescan_registers` och `import_energy_history`, och en automation som anropar dem får "service not found". Kvalitetsskalans regel action-setup säger just detta. **Lösning.** `async_setup` registrerar tjänsterna en gång; en tjänst utan laddad post svarar med ServiceValidationError med översättningsnyckel. **Nytta.** Automationer som överlever en omstart; en rad till i R34:s checklista.

Ansträngning: S. Risk: låg. Beroenden: inga. Belägg: __init__.py:651 och anropen i båda uppsättningsvägarna (275 och 410 i 1.15.0).

#### L1: Termostaten erbjuder heat/cool bara på en pump som kan kyla

**Problem.** `NibeClimate` erbjuder `heat_cool` när kartan har kylbörvärdet och "Cooling with room sensor" bär en värdetabell - vilket varje F-seriekarta gör - så F1255:an på VV, som inte har någon kyla, skulle erbjuda läget så snart en rumsgivare rapporterade, och ett val skulle skriva 47340 = 1 på en pump utan kylkrets. Infördes i 1.15.0. **Lösning.** Läget kräver dessutom att pumpen kyler: traiten `cooling` i posten (satt ur EQ1-BT64 på F-serien, 30338 på S-serien) eller att kylframledningen rapporterar. Testet med rumsgivare får en variant utan kyla. **Nytta.** Ingen F-ägare utan kyla får ett läge som skriver något pumpen inte har.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: climate.py:111 till 116 (`_can_cool`), 177 till 184, const.py CONF_TRAITS, fseries.py:116 (COOLING_TITLES), registry.py `_TRAIT_REGISTERS`.

### Dashboard

#### R4: Talfältet skriver aldrig 0 av misstag, reglaget skriver en gång, och en avvisad skrivning syns

**Problem.** Talfältets `change` skickar `field.value` som det är, och `serviceFor` gör `Number(value)`: ett tömt fält blir 0, och på kurvförskjutningen (-10 till 10) och gradminuterna är 0 ett värde Home Assistant godtar - så den som raderar för att skriva ett nytt tal och råkar lämna fältet har skrivit 0 till pumpen. Reglaget skickar på varje `change`, och ett `input type="range"` avger `change` för varje piltryck, så tangentbordet skriver till pumpen per steg. `callService` anropas utan `catch`, så en avvisad skrivning (utanför gränserna, pumpen svarar inte) syns bara i konsolen; `pending` nollas efter sex sekunder vad som än hände. **Lösning.** Ett tomt eller icke-numeriskt fält skickar ingenting och återställs; värdet klipps mot `min`/`max` innan det skickas; reglaget skriver först 400 ms efter sista piltrycket; `callService` fångar fel och visar dem med `hass-notification`, och `pending` släpps på svar, inte på klockan. Allt i de rena hjälparna så node-testerna pinnar det, med det tömda fältet som första fall. **Nytta.** Alla med Styrning på sidan - förvalet. Underhållaren slipper felsöka en kurvförskjutning som blev 0 "av sig själv".

Ansträngning: S. Risk: låg. Beroenden: inga. Belägg: nibe-easyconf-card.js:1284, 613, 1261, 931, 1190 till 1192.

#### R10: Sidan får inte svämma över på en smal telefon

**Problem.** `.cards` (Styrning) och `.grid` (Alla värden) är `repeat(auto-fill, minmax(340px, 1fr))`. En telefon på 320 CSS-pixlar har 288 kvar efter sidans 16 px på var sida, en på 360 har 328: båda får en kolumn på 340 och en vågrät rullning över hela sidan. Räknat, inte provat på en telefon - det hör till den webbläsargenomgång som står under öppna frågor. **Lösning.** `minmax(min(340px, 100%), 1fr)` på båda, samma på `.tiles` för säkerhets skull, och en klistrad flikrad på en lång lista. **Nytta.** Alla som öppnar sidan i appen, vilket är där en värmepumpssida oftast öppnas.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: nibe-easyconf-card.js:657, 749, 676 (`.tiles` 140 px är fint).

#### L2: Kortets ordtabeller har samma nycklar på alla fyra språk

**Problem.** `TEXT` har en tabell per språk (sv, de, fr, en) som fylls i för hand; 1.15.0 lade till `press` i fyra ställen. Saknas en nyckel i ett språk skriver kortet `undefined` på knappen, och inget test ser det. **Lösning.** Ett node-test som jämför nyckelmängderna mellan språken, och ett som kräver att varje nyckel kortet använder finns i tabellen. **Nytta.** Underhållaren; de tyska och franska läsarna som ingen här kan prova.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: nibe-easyconf-card.js:49 till 190 (`TEXT`), 1243 (`text.press`).

## Fas 2: nytta i vardagen

Sidan säger vad pumpen gör och varför. Larmet blir en händelse med återställningsknappen bredvid (R11, V1), värmefaktorn finns per vecka och månad (R12), spetsvärmeandelen räknas (R13), kompressorstarterna blir räknare (R14), tillbehören blir egna enheter (R15) och diagnostiken bär det ett ärende behöver (R16). På sidan: dygnsremsan (R17), kretsschemat (R18), gradminutmätaren (R19) och energin per del (R20).

### Teknik

#### R11: Larmet som händelse, med återställningen bredvid

**Problem.** Ett larm är en text i en sensor och ett rött chip på översikten; inget händer när det kommer. VV har haft larm 181 "Failed periodic increase" så länge att ingen vet när det kom (V1) - sidan visar det, men bara för den som öppnar den. Återställningsknappen från 1.15.0 står på fliken Styrning, inte vid larmet. **Lösning.** En `event`-entitet som avger larmnummer och text när koden ändras, en persistent avisering med förklaringen ur `alarms.json`/`alarms_fseries.json`, och på översikten en larmbanderoll med återställningsknappen i stället för chipet när koden inte är 0. **Nytta.** Alla hus: ett larm märks i appen; VV:s ägare får frågan om varför den periodiska höjningen misslyckas i stället för en röd ruta.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: sensor.py:48 till 60 och 78 till 81, nibe-easyconf-card.js:674 och 1024 till 1031, 256 (`QUICK_CONTROLS` utan återställningen); VV 2026-10-15: `sensor.nibe_f1255_16_cu_alarm_code` = Failed periodic increase, kod 181.

#### R12: Värmefaktor över 7 och 30 dygn ur proven som redan sparas

**Problem.** `CopTracker` sparar ett prov per dygn i 400 dygn och räknar bara dygn, rullande år och livstid. Veckan och månaden - det en ägare jämför med elräkningen - saknas, fast proven ligger där. **Lösning.** `result_span(days)` ur det äldsta provet inom spannet, med samma minsta förbrukning som året skalad till spannet, och två sensorer till med samma attribut och förklaringar; kortet lägger dem bland nyckeltalen. **Nytta.** FB får vecka och månad direkt ur de 280 importerade proven; VV får dem allt eftersom räknaren växer.

Ansträngning: S. Risk: låg. Beroenden: inga. Belägg: cop.py:30 till 50, 267 till 300, sensor.py:180 till 263.

#### R13: Spetsvärmeandel: hur stor del av värmen elpatronen gjorde

**Problem.** Ingen siffra säger hur mycket av året som var elpatron. F-serien har delarna: `Parts.addition` mot `Parts.compressor` i den räknade elen. S-serien har pumpens egna energiloggar per timme för tillsatsen och de två totalerna "inklusive el", men ingen entitet sätter dem mot varandra. **Lösning.** En sensor per dygn, månad, rullande år och livstid på F-serien ur `Parts`, och på S-serien ur "Used energy by additional heater" summerad över dagen med Home Assistants statistik, med `basis` och förklaring som värmefaktorn har. **Nytta.** En ägare som ser 12 % spets i januari vet var pengarna gick; en extern med en underdimensionerad pump ser det på en månad.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: power.py:58 till 72, names.py:106 till 122 (energiloggens titlar), sensor.py:119 till 178.

#### R14: Räknare utan enhet blir räknare

**Problem.** `units.resolve` sätter state_class ur enheten. "Compressor starts EB100-EP14" (43416) och S-seriens "Compressor, number of starts" (31535, 31490, 31445) har ingen enhet, får ingen state_class och därmed ingen långtidsstatistik - så starter per dygn, det tydligaste måttet på kortcykling, går inte att rita. **Lösning.** `resolve` ger `total_increasing` åt titlar med "starts" och "number of starts", och kortets energigraf tar med starter per dygn som staplar. **Nytta.** Alla: starter per dygn på fliken Prestanda, och Home Assistants egna statistikkort kan rita dem.

Ansträngning: S. Risk: låg - en state_class som tillkommer skapar statistik från nu, ingen gammal går sönder. Beroenden: inga. Belägg: units.py:48 till 73; kartorna: 43416 utan enhet, 31535/31490/31445 utan enhet.

#### R15: Underenheter per tillbehör

**Problem.** Allt sitter på en enhet, `identifiers={(DOMAIN, entry_id)}`: 1 203 entiteter på FB. Home Assistants enhetssida blir oanvändbar, och sidans Alla värden bär hela bördan. **Lösning.** `via_device` för utedelen EB101 (SMO/VVM), poolen, FLM/ERS-modulerna och klimatsystem 2 till 4, var och en med sina register ur samma titelmönster som `NON_DEFAULT` redan känner. Entitets-id:n ändras inte; kortets `device_id`-filter följer barnen; en migrering flyttar befintliga entiteter till rätt enhet. **Nytta.** En enhetssida per sak; ett SMO 40-hus ser utedelen som en maskin.

Ansträngning: M till L. Risk: medel - automationer som pekar på `device_id` följer inte med; README säger det. Beroenden: inga, men hellre före R26 (varje ny användare gör migreringen större). Belägg: entity.py:138 till 156, const.py:111 till 146, fseries.py:213 till 225 (ACCESSORIES).

#### R16: Diagnostiken bär det ett ärende behöver

**Problem.** Diagnostikexporten ger anslutning, skanningens summor, antal prenumerationer och de rapporterande registren med värde. Den saknar det ett ärende om COP, el eller värmeläge behöver: värmefaktorns prov (antal och spann), elräknarens delar och baslinjer, värmelägets tillstånd, gatewayens pollschema (vad som är försenat, vad som backar), `last_update_success`, nibe-bibliotekets version och vilka register som prenumereras. **Lösning.** Allt ovan som avsnitt, lagren via sina egna `as_diagnostics()`; inget maskeras utöver det som redan hålls lokalt (adressen är husets eget nät). En ärendemall i `.github/ISSUE_TEMPLATE` ber om filen (R21). **Nytta.** Underhållaren får svaret i första ärendet; ägaren slipper ssh.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: diagnostics.py:13 till 53.

### Dashboard

#### R17: Dygnsremsan: vad pumpen gjorde när

**Problem.** Frågan "varför var igår dyrt" har inget svar på sidan: Status-registret (31029/43086) säger värme, varmvatten, pool, kyla eller av just nu, och dess historia finns i recordern, men ingen ritar den. **Lösning.** En remsa över de senaste 24 timmarna, färgad per status ur `history/history_during_period` över websocket, under statuschipen på översikten, med avfrostning och tillsats som streck ovanpå där registren finns. Byggd i kortet med samma rena hjälpare för segmenteringen, testade i node. **Nytta.** Alla: dygnet i en blick; den som bytt elavtal ser om varmvattnet gick på dyra timmar.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: nibe-easyconf-card.js:215 till 224 (STATUS_PATTERNS), official.py:120 till 128 (PRIORITY).

#### R18: Kretsschemat på översikten

**Problem.** Temperaturerna står som en lista med siffror; vad som är in och ut, före och efter kompressorn, kräver att man vet det. **Lösning.** En SVG i temafärger med köldbärare in/ut, kompressorn med frekvens och effekt, kondensor, framledning/retur, varmvattentank och rumsgivare, där bara det ritas som pumpen har: traiterna i posten (`ground_source`, `exhaust_air`, `hot_water`, `cooling`) och utedelen EB101 på SMO/VVM väljer topologi. Det är skillnaden mot CTC, där R44 ströks för att topologin inte var känd - här är den det. **Nytta.** Alla: kretsen läses på en sekund, som i myUplinks flödesbild; en nybörjare förstår vad BT10 och BT11 är utan att läsa.

Ansträngning: L. Risk: medel - ett fel schema är sämre än inget, så varje topologi provas mot ett hus eller en registerkarta innan den ritas. Beroenden: R10. Belägg: nibe-easyconf-card.js:233 till 255 (READING_PATTERNS), const.py CONF_TRAITS, registry.py:158 till 170 (_TRAIT_REGISTERS), fseries.py:394 till 405.

#### R19: Gradminutmätaren med start- och tillsatsgränserna

**Problem.** Gradminuterna är det tal som förklarar varför kompressorn startar och varför elpatronen går in, men står som en siffra utan sina gränser. Gränserna finns som register: "DM start heating" (47206 på F, 40098 på S), "DM diff start add." (48072) och "DM diff. start additional heat" (40680), kylans 47342/47343 och 40173/40174. **Lösning.** En mätare på översikten med nuvärdet och gränserna markerade, och förklaringen under: "kompressorn startar vid -60, elpatronen vid -460". Registren prenumereras bara när mätaren visas. **Nytta.** Lär en ägare mer om sin pump än någon graf; en extern som undrar varför elpatronen går får svaret.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: kartorna: F 43005/40940, 47206, 48072, 47342, 47343; S 40012, 40098, 40680, 40173, 40174; nibe-easyconf-card.js:240 (`degree ?minutes`).

#### R20: Energi per del på fliken Prestanda

**Problem.** `Parts` bokför kompressor, tillsats, pumpar och elektronik var för sig, men sidan visar bara summan; S-serien har timloggen per ändamål. Energigrafen är tre staplar av totaler. **Lösning.** Staplar per dygn uppdelade per del (F) eller per ändamål (S: värme, varmvatten, tillsats), värmefaktorn som linje ovanpå, 30 dygn. **Nytta.** Alla: var elen gick syns per dygn; R13:s andel får sin graf.

Ansträngning: M. Risk: låg. Beroenden: R13. Belägg: power.py:58 till 72, nibe-easyconf-card.js:538 till 546 (energigrafen).

### Iakttagelser från husen 2026-10-15

- **V1: VV har ett aktivt larm utan avisering.** `sensor.nibe_f1255_16_cu_alarm_code` = "Failed periodic increase" (kod 181); hur länge vet ingen, eftersom tillståndet nollställs vid varje omstart och inget loggar händelsen. Bär R11. Ägaren kan nu trycka på *Reset alarm* på enheten; om larmet kommer tillbaka är det den periodiska varmvattenhöjningen som inte når sin stopptemperatur - värt att ställa mot EMS:s blockering av tillsatsen.
- **V2: FB visar 16 otillgängliga entiteter sedan varje omstart.** Fem externa givarinställningar, tre BT20, tre BT21, returledning EP15, lågtryck, förångare BT16, displayens varmvattengivare och förångare 2 - alla för hårdvara en S1155-16 utan frånluft inte har. Bär R1.
- **V3: Starten på FB väntade på integrationen.** "Waiting for integrations to complete setup" 09:42:02 efter installationen av 1.15.0, medan registren lästes om. Bär R3. I övrigt en veckas loggar utan en enda varning från integrationen på något av husen, och VV:s 28 otillgängliga rader direkt efter omstarten var 0 efter ett pollvarv.

## Fas 3: enkelt för nybörjaren och externa användare

En främling installerar, förstår, felanmäler och tar bort utan hjälp. README saknar tre avsnitt som varje installation behöver (R21), en pump som byter adress måste tas bort och läggas till igen (R22), uppsättningsflödets fält har ingen hjälptext (R23), de egna entiteternas namn följer inte språkbytet utan omstart och tyska och franska är tomma tabeller (R24), och F-seriens ord står på engelska i en svensk sida (R25).

#### R21: README: ta bort, energipanelen, felanmälan

**Problem.** README har varken "Ta bort integrationen", "Energipanelen" eller "Felsökning". Den som tar bort posten vet inte att `.storage/nibe_local_easyconf.stats` (installationens slumpade id) och kortresursen stannar och att långtidsstatistiken ligger kvar under entitets-id:na; den som vill ha pumpen i energipanelen får gissa bland "Tot. production", "Tot. consumption" och "Electricity used (counted)"; den som felanmäler vet inte att diagnostikexporten finns. Kvalitetsskalans docs-removal-instructions. **Lösning.** Tre avsnitt, och en ärendemall i `.github/ISSUE_TEMPLATE/` som ber om Home Assistant-version, modell, anslutningsväg och diagnostikfilen (R16). **Nytta.** Externa användare främst; underhållaren får ärenden med underlag.

Ansträngning: S. Risk: ingen. Beroenden: R16 för mallen. Belägg: README.md, rubrikerna 25 till 605 saknar alla tre; __init__.py:637 till 648 (vad `async_remove_entry` tar bort).

#### R22: Adress, portar och Modbus-id kan ändras utan ny installation

**Problem.** DHCP uppdaterar adressen bara för en post vars unique_id är serienumret (`_abort_if_unique_id_configured(updates={CONF_HOST: host})`); en post skapad för hand utan serie heter `host:port:unit` och följer inte med när routern delar ut en ny adress, och ingen gateway byter port utan ny post. Att ta bort och lägga till posten ger nya entitets-id:n - det är exakt vad säkert läge gjorde med FB:s statistik. **Lösning.** Ett `reconfigure`-steg i flödet som tar adress och portar, provar anslutningen som uppsättningen gör och uppdaterar posten; serienumret läses om via omvänd DNS när det går. **Nytta.** Alla som bygger om nätet; ett års statistik överlever.

Ansträngning: M. Risk: låg. Beroenden: inga. Belägg: config_flow.py:117 till 150 (dhcp), 277 till 330 (unique_id ur adress när serien saknas), 450 till 471.

#### R23: Uppsättningsflödets fält får hjälptext

**Problem.** Ingen av flödets åtta steg har `data_description`; bara alternativen har. Den som ser "Modbus-id" eller "läsport 9999 / skrivport 10000" utan förklaring gissar. Kvalitetsskalans regel config-flow. **Lösning.** `data_description` per fält på båda språken, och ett test som kräver att varje fält i varje steg har en. **Nytta.** Externa användare; en rad till i R34.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: strings.json, `config.step.*` utan `data_description` (kontrollerat 2026-10-15), config_flow.py:235 till 280 och 488 till 530.

#### R24: De egna entiteternas namn ur översättningarna, och tyska och franska fyllda eller strukna

**Problem.** Värmeläge, boost, COP-sensorerna, termostaten, varmvattnet och knapparna sätter `_attr_name` på svenska eller engelska vid skapandet, så ett språkbyte i Home Assistant syns först efter omstart, och namnet ligger inte där Home Assistant väntar det (`translation_key` + `name` i strings). `LANGUAGES` lovar tyska och franska, men `TEXTS["de"]` och `TEXTS["fr"]` är tomma och translations/de.json och fr.json finns inte - en tysk läsare får engelska namn och ett tyskt kort. **Lösning.** Namnen ur översättningarna för alla egna entiteter (registerentiteterna behåller sina, de är dynamiska); antingen fylls de och fr i av någon som talar språken, eller så krymper `LANGUAGES` till det som finns. **Nytta.** Externa användare utanför Sverige; ägaren får en regel ("allt följer Home Assistants språk") som koden håller utan omstart.

Ansträngning: S till M. Risk: låg. Beroenden: inga. Belägg: select.py:73, sensor.py:100 och 140, climate.py:91, water_heater.py:62, button.py:69, translations_extra.py:15 till 27.

#### R25: F-seriens värden på svenska

**Problem.** Över F-seriens kartor finns 113 skilda värdeord; `LABELS_SV` har 50. 63 visas på engelska i en svensk sida, bland dem ECO, HEATING, ACTIVE DEFROST, BLOCKING, EXTERNAL REQUEST, INTERNAL ADDITION, LOW PRICE, FIXED PRICE och FAN MODE 1 till 4 - språknamn och datumformat kan stå, resten inte. **Lösning.** Tabellen fylls för allt som inte är ett språknamn eller ett format, och ett test räknar upp det som återstår så att nästa karta inte tyst lägger till engelska. **Nytta.** VV och varje svensk F-ägare.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: fseries.py:512 till 565 (LABELS_SV), räknat över `F_SERIES_MODELS` 2026-10-15.

## Fas 4: kraft för den avancerade

#### R26: Priset per kWh värme, och vad direktverkande el hade kostat

**Problem.** Värmefaktorn säger hur många kilowattimmar värme en kilowattimme el gav, inte vad värmen kostade. Ägaren byter elavtal 2026-10-31; frågan "vad kostar en grad till" har inget svar på sidan. **Lösning.** Ett valfritt pris i alternativen (en entitet: Nordpool, Tibber eller energipanelens prisentitet), och ur det öre per kWh värme för dygnet och månaden samt besparingen mot direktverkande el; en rad bland nyckeltalen och en linje i R20. **Nytta.** Ägaren vid avtalsbytet; varje extern med timpris.

Ansträngning: M. Risk: låg. Beroenden: R12, R20, en prisentitet. Belägg: cop.py, power.py; config_flow.py:671 till 740 (alternativen).

#### R27: Kortet i korteditorn

**Problem.** `getStubConfig` finns men ingen `getConfigElement`, så kortet konfigureras i YAML; `device_id` och `tabs` är det enda att ställa men måste skrivas. **Lösning.** En editor med enhetsväljare och flikbockar, och kortets beskrivning i kortväljaren på sidans språk. **Nytta.** Den som bygger egna instrumentpaneler; nybörjaren som inte skriver YAML.

Ansträngning: S till M. Risk: låg. Beroenden: inga. Belägg: nibe-easyconf-card.js:1489 till 1491, 1515 till 1521.

#### R28: Tillgänglighet: flikar, paneler och fält som skärmläsaren förstår

**Problem.** Flikraden har `role="tablist"` och knapparna `role="tab"`, men panelerna saknar `role="tabpanel"` och `aria-controls`/`aria-labelledby`; raderna i listan är `role="button"` med `aria-expanded`, vilket är rätt; sökfältet saknar etikett utöver platshållaren; ⓘ har `aria-label`. **Lösning.** Panelerna får roller och id:n, fältet en `aria-label`, fokusordningen provas med tangentbord, och ett node-test över det statiska. **Nytta.** Den som navigerar med tangentbord eller skärmläsare; en rad till i R34.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: nibe-easyconf-card.js:827 till 836, 888, 1386 till 1395.

## Fas 5: hållbart att underhålla och sprida

#### R29: Släpp ur taggen, med kontroller

**Problem.** 36 släpp på fem veckor har gjorts för hand: `git tag`, `git push`, `gh release create` med anteckningar ur en fil i `work/`. Ingenting kontrollerar att taggen heter manifestets version, att commiten ligger på main eller att Validate gått grönt på den; 1.14.4 commitades utan att släppas. **Lösning.** `release.yml` som CTC:s: ett tag `vX.Y.Z` kontrollerar versionen, att commiten är på main och väntar på hela Validate (inklusive R6), skriver anteckningarna ur den annoterade taggen och skapar släppet; dokumentet säger `git push --atomic origin main vX.Y.Z`. **Nytta.** Underhållaren; HACS-användare får bara det som passerat allt.

Ansträngning: S till M. Risk: låg. Beroenden: R6. Belägg: `gh release list` 2026-10-15: 36 släpp sedan v1.0.0 2026-09-09; work/releases/v1.15.0.md.

#### R30: quality_scale.yaml som levande checklista

**Problem.** Manifestet säger `"quality_scale": "silver"` utan att något håller det: action-setup (R9), config-flow (R23), docs-removal-instructions (R21), reconfigure (R22) och parallel-updates är ogjorda eller oprövade. hassfest läser bara core-integrationers fil, så inget i CI ser det. **Lösning.** `quality_scale.yaml` med varje regel som done, todo eller exempt och en kommentar som säger varför, och ett test som kräver att varje regel finns, att varje done-rad håller det hassfest skulle kräva, och att manifestets nivå inte överstiger det som är gjort. **Nytta.** Underhållaren får en lista i stället för ett påstående; en extern bidragsgivare ser var det går att hjälpa.

Ansträngning: M. Risk: ingen. Beroenden: inga. Belägg: manifest.json:26.

#### R31: S-serien under Home Assistant

**Problem.** Den enda sviten under en riktig kärna är F-serien mot `FakeNibeGW`. S-serien - uppsättningsflödet med sökning, DHCP, probningen av 1 600 register, blockläsningen, återläsningen, termostaten på FB:s register - har inga HA-nivåtester; `test_write_homeassistant.py` prövar koordinatorn ensam. R1 och R2 ändrar just S-seriens förval. **Lösning.** En falsk Modbus-pump (asyncio-server med registerminne ur en skanning av FB) och samma slags tester som F-serien har: flöde, entiteter, skrivning, omskanning, omladdning. **Nytta.** Underhållaren; varje S-ägare.

Ansträngning: M. Risk: låg. Beroenden: R6 för att det ska köras i CI. Belägg: tests/test_gateway_homeassistant.py:1 till 12, tests/test_write_homeassistant.py:1 till 10; work/data/entities-fb.json som underlag.

#### R32: Kortets DOM under test

**Problem.** Node-testerna laddar de rena hjälparna; allt i `customElements`-grenen - widgetarna, uppdateringen av dem, `pending`, klick på ⓘ, flikbytet - är oprövat utanför en webbläsare. R4 ändrar just det. **Lösning.** jsdom i node, ett `hass`-attrapp och tester för varje widget: tömt fält, klippning, reglagets fördröjning, en avvisad skrivning, ⓘ som öppnar och stänger, flik som minns. **Nytta.** Underhållaren; R4 får sina bevis.

Ansträngning: M. Risk: låg. Beroenden: R4. Belägg: tests/test_card.py:1 till 9 ("the DOM part is not tested here").

#### R33: stats.py:s egna nycklar hålls mot backenden

**Problem.** Kontraktstestet prövar det `stats_extra` bygger men inte nycklarna `stats.py` lägger till själv (`ha_id`, `log_errors`, `log_warnings`). Backenden avvisar hela rapporten vid en okänd toppnyckel, så en nyckel den inte känner skulle tysta varje rapport utan ett fel på denna sida. Står på README:s roadmap sedan 1.7.2. **Lösning.** Testet läser `EXTRA_KEYS` och toppnycklarna ur stats.py med `ast` och prövar dem mot backendens regler. **Nytta.** Underhållaren; flottans siffror.

Ansträngning: S. Risk: ingen. Beroenden: inga. Belägg: tests/test_backend_contract.py, stats.py (delad, oförändrad).

## Fas 6: väntar på mätning eller beslut

#### R34: In i HACS standardlista

**Problem.** Integrationen installeras som eget repo i HACS; en sökning i HACS hittar den inte. Förutsättningarna finns - brand/, hacs.json, README, licens, HACS-jobbet grönt - men listningen är ett beslut om synlighet, och varje ny användare gör R15:s migrering och R2:s domänbyte dyrare om de kommer efter. **Lösning.** När R1, R2, R15 och R21 är gjorda: PR till hacs/default från beolinks fork, med ett test som håller repot till det HACS kräver (CTC:s R75). **Nytta.** Spridning; frågan är om ägaren vill ha den nu.

Ansträngning: S. Risk: låg. Beroenden: R1, R2, R15, R21 och ägarens ja. Belägg: `gh api`: 1 stjärna, 0 ärenden, skapad 2026-09-09.

#### R35: Levererad värme på F-serien utan EMK

**Problem.** F1255:an på VV mäter inte värmen den levererar: båda värmemätarsetten står på 650,7/246,8 kWh genom 208 timmars statistik och 25 kWh kompressor, BF1 svarar inget, och NIBE:s energimätning kräver EMK 300/500. Utan det får VV aldrig någon värmefaktor. **Lösning.** Opt-in i alternativen: ΔT (BT2 - BT3) gånger flödet, där flödet antingen skrivs in av ägaren (uppmätt vid injustering) eller tas ur pumpkurvan vid aktuell pumphastighet, integrerat som elen i power.py och märkt uppskattad i attributen. **Vad som väntar.** Ett flöde att räkna med: ägaren läser injusteringsprotokollet eller mäter, annars är siffran en gissning på en gissning.

Ansträngning: M. Risk: medel. Beroenden: ägarens flöde. Belägg: power.py:48 till 54, fseries.py:371 till 373, README Coefficient of performance.

#### R36: Värmefaktor för SMO 20/40 ur utedelens beräknade effekt

**Problem.** SMO och VVM har ingen kompressor och ingen elmätare; utedelen rapporterar "EB101-EP14 Calculated Power Outdoor Unit" och värmemätarna finns. Ingen här har en SMO att prova mot. **Lösning.** Räkna elen ur den beräknade effekten som power.py gör ur kompressoreffekten, med samma delar. **Vad som väntar.** En SMO 40-installation som rapporterar i statistiken, eller en extern användare.

Ansträngning: M. Risk: medel. Beroenden: hårdvara. Belägg: fseries.py:394 till 405 (OUTDOOR_UNIT_TITLES).

#### R37: NIBE:s MODBUS 40-tillbehör som alternativ till gatewayen

**Problem.** Den som redan har NIBE:s MODBUS 40 och en TCP-till-RTU-omvandlare kan inte använda integrationen: bara holdingregister, adresserade med sitt fulla nummer (40004 är 0x9C44) före version 10, skrivning bara med Write Multiple Registers, 2,1 s per register utanför LOG.SET. **Lösning.** En tredje transport som återanvänder gatewaykoordinatorns schema och F-seriens förval. **Vad som väntar.** Ett MODBUS 40 att mäta mot; ingen här har ett.

Ansträngning: L. Risk: medel. Beroenden: hårdvara. Belägg: README Roadmap före 1.15.0, work/references/modbus40-manual.txt.

#### L3: Zonens börvärde (42506) mot klimatsystemets (40207) på S-serien

**Problem.** Termostaten skriver "Room sensor set point value climate system 1" (40207), som core nibe_heatpump. S-seriens nyare firmware har zoner med "Desired room temperature for zone 1" (42506). På FB står båda på 20,0 - men om pumpen reglerar på zonens värde skriver termostaten i tomma luften när rumsgivaren används. **Vad som väntar.** Ett prov på FB: skriv 40207 till 20,5, läs 42506, återställ. En skrivning till ägarens pump, så ägarens ja först.

Ansträngning: S. Risk: låg. Beroenden: ägarens ja. Belägg: climate_systems.py:100 till 109, work/scripts/read_s_registers.py 2026-10-15: 40207 = 20,0, 42506 = 20,0.

#### L4: S-seriens engångshöjning

**Problem.** "More hot water" (40698) bär inga värden i någon karta eller i NIBE:s registerlista, så S-serien har varken boost-brytare eller boost i varmvattenberedaren. FB svarar 0 och "More hot water status" (31079) 0. F-serien använder 4 för engångshöjningen. **Vad som väntar.** Ett prov på FB: skriv 4, läs 31079 och displayen, låt beredaren ladda en gång. En skrivning till ägarens pump, så ägarens ja först.

Ansträngning: S. Risk: låg - beredaren laddas en gång. Beroenden: ägarens ja. Belägg: hot_water_boost.py:17 till 19, read_s_registers.py 2026-10-15: 40698 = 0, 31079 = 0, 40226 = 0.

#### R38: Kyla med rumsgivare på S-serien

**Problem.** "Cooling with room sensors" (40171) har faktor 10, max 41 och ingen värdetabell, så termostaten erbjuder inte heat/cool på S-serien alls. FB kyler inte, så det går inte att mäta här. **Vad som väntar.** En S-pump med kyla (S1255 med ACS 310) som rapporterar i statistiken, eller NIBE:s registerlista med värdena.

Ansträngning: S. Risk: låg. Beroenden: hårdvara eller dokumentation. Belägg: climate.py:19 till 22, kartan: 40171 u8 f=10 min 0 max 41.

## Prövat och lagt åt sidan

Förslag som prövades mot koden eller mot husens behov och ströks, med skälet.

- **Nivåindelad polling på S-serien** (struket: ingen vinst). Blockläsningen kostar en rundresa per sammanhängande spann, inte per register, och `plan_spans` bryggar korta luckor; gatewayen har redan sitt schema (`PollSchedule`). Belägg: discovery.py:213 till 262, gateway.py `PollSchedule`.
- **Bekräftelse före varje skrivning i kortet** (struket i värde). Home Assistants egen dialog bekräftar inte, EMS skriver utan att fråga, och de verkliga fällorna är nollan ur talfältet (R4) och tillbehörsflaggorna (R2), som båda får riktiga lösningar.
- **Värmeläge för klimatsystem 2 till 4** (struket tills någon har ett). Förskjutningarna finns som talentiteter; ingen känd installation har ett andra system, och tre lärda "normal" till utan användare är tre tillstånd att hålla rätt.
- **NIBE:s symbol i sidomenyn** (struket). Sidomenyn tar ett ikonnamn, inte en bild; en handritad vektor av någon annans varumärke är sämre än mdi-ikonen. Belägg: frontend.py:33 till 41.
- **Energipanelen fylls i av integrationen** (struket: går inte). Home Assistant har inget API för att lägga sensorer i energipanelen; README säger vilka (R21).
- **Pinna nibe-biblioteket** (struket). Home Assistant installerar sin egen nibe för nibe_heatpump; en pinne skulle få den att installera en till. Belägg: manifest.json `nibe>=2.24.0`, validate.yml:36 till 43.
- **Fler-agent-granskning som CTC:s** (gjordes inte). En läsare läste allt; det står i inledningen, och det är skälet till att posterna är 44 och inte 79.

## Öppna frågor

- **Tillbehörsflaggorna (R2):** ska de alls kunna skrivas från Home Assistant, eller räcker displayen? Svaret avgör om "installatörsläget" behövs.
- **Zonens börvärde (L3) och engångshöjningen (L4):** båda kräver en skrivning till FB:s pump. Ett ja från ägaren, så görs provet och roadmapen uppdateras.
- **VV:s larm 181 (V1):** tryck på *Reset alarm* och se om det kommer tillbaka; i så fall är frågan om EMS:s blockering av tillsatsen hindrar den periodiska höjningen från att nå sin stopptemperatur (40062-motsvarigheten på F-serien).
- **R15 före eller efter HACS-listningen (R34):** varje ny användare gör migreringen större; R2:s domänbyte likaså.
- **Priskällan (R26):** Nordpool-integrationen, Tibber eller energipanelens prisentitet - och vilket avtal som gäller efter 2026-10-31.
- **Släppkadensen (R29):** husen får i dag en build innan den taggas; vill ägaren att samma tagg går till husen och HACS, eller behålla förhandsutrullningen?
- **Webbläsargenomgången:** sidan på FB och VV är inte gången flik för flik i en webbläsare - R10 är räknad, inte sedd. Med ägarens inloggade Chrome går det att göra på en kvart, i mörkt och ljust tema och på telefonbredd.
- **Flottan:** statistikbackenden vet hur många installationer som rapporterar och vilka modeller; siffran avgör hur mycket R24:s tyska och franska och R36:s SMO är värda. Ägaren läser den i stats-adminen.
