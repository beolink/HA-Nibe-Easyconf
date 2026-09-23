"""Explanations written for someone who owns a heat pump, not for a service technician.

`descriptions.py` builds a text for every register out of NIBE's own title and
a glossary of designations. That is right for the eight hundred registers
nobody has an opinion about, and it is how a register NIBE never documented
still says something. But for the values a person actually looks at or changes
it produces "Measures outdoor temperature (BT1)", which says what the title
already said.

This module holds real explanations for those: what the value is, what it does
to the house, and what happens if you change it. They are matched against
NIBE's title, so one entry covers both series and both of its spellings - the
S-series writes "Current outdoor temperature (BT1)", the F-series "BT1 Outdoor
Temperature". First match wins, which is why the more specific patterns come
first: "Calc. Supply" before "supply", the cooling degree minutes before the
ordinary ones, a pump's speed before a pump's mode.

The patterns are written per family rather than per register, because an
installation only shows the registers its own accessories bring: one house has
an exhaust air module, the next a pool, a third eight climate systems. A
pattern that covers the family explains all of them, whether or not this pump
has them, so a scan that finds an accessory brings explained values with it.

Anything not listed here keeps the built text. A guess dressed up as an
explanation would be worse than NIBE's shorthand, so what is written here was
verified in NIBE's documentation, in the register's own unit and range, or on a
real pump. Where the meaning of a service value could not be established, the
text says what kind of value it is and that it is for fault finding, rather
than inventing a purpose for it.
"""

from __future__ import annotations

import re

from .translations_extra import translate

#: NIBE title -> (Swedish, English). Ordered: the first pattern that matches an
#: entity's title decides.
EXPLANATIONS: list[tuple[re.Pattern[str], tuple[str, str]]] = [
    # ------------------------------------------------------------- heating
    (
        re.compile(r"heat(ing)? curve|värmekurva", re.I),
        (
            "Kurvan bestämmer hur varmt vatten pumpen skickar ut till elementen "
            "vid en viss utetemperatur: ju kallare ute, desto varmare vatten. "
            "En högre siffra ger en brantare kurva, alltså mer värme när det är "
            "riktigt kallt men ungefär detsamma när det är milt. Höj en siffra i "
            "taget och vänta ett dygn: huset svarar långsamt.",
            "The curve decides how hot the water going out to the radiators is at "
            "a given outdoor temperature: the colder it is outside, the hotter the "
            "water. A higher number makes the curve steeper, so more heat when it "
            "is truly cold and about the same when it is mild. Change it one step "
            "at a time and wait a day; a house answers slowly.",
        ),
    ),
    (
        re.compile(r"heat(ing)? offset|curve offset|kurvförskjutning", re.I),
        (
            "Flyttar hela värmekurvan upp eller ner lika mycket vid alla "
            "utetemperaturer. Ett steg motsvarar ungefär en halv grad inomhus. "
            "Använd den när huset är jämnt för svalt eller för varmt oavsett "
            "väder; är det bara vid sträng kyla det blir kallt är det i stället "
            "kurvan som ska höjas.",
            "Moves the whole heating curve up or down by the same amount at every "
            "outdoor temperature. One step is roughly half a degree indoors. Use "
            "it when the house is evenly too cool or too warm whatever the "
            "weather; if it only goes cold in hard frost, raise the curve instead.",
        ),
    ),
    (
        re.compile(r"degree.?minutes.*cool|cooling degree.?minutes|gradminuter.*kyla", re.I),
        (
            "Samma räknesätt som gradminuterna för värme, fast för kyla: hur "
            "länge och hur mycket för varmt huset har varit. Pumpen startar "
            "kyldriften när talet blivit tillräckligt stort.",
            "The same arithmetic as the degree minutes for heating, but for "
            "cooling: how long and by how much the house has been too warm. The "
            "pump starts cooling once the number has grown far enough.",
        ),
    ),
    (
        re.compile(r"degree.?minutes|gradminuter", re.I),
        (
            "Gradminuterna är pumpens mått på hur mycket värme huset saknar. Varje grad som "
            "framledningen ligger under det kurvan ber om räknas varje minut, så "
            "talet blir mer negativt ju längre värmen uteblir. Vid ett visst "
            "negativt tal startar kompressorn, och när värmen kommit ikapp går "
            "talet mot noll igen. Det behöver normalt inte ändras för hand.",
            "Degree minutes are the pump's measure of how much heat the house is missing. Every "
            "degree the supply temperature falls short of what the curve asks for "
            "counts once a minute, so the number grows more negative the longer "
            "the heat is missing. At a certain negative number the compressor "
            "starts, and as the house catches up the number climbs back towards "
            "zero. It rarely needs changing by hand.",
        ),
    ),
    # ---------------------------------------------------------- hot water
    (
        re.compile(r"temporary lux|tillfällig lyx", re.I),
        (
            "Höjer varmvattentemperaturen tillfälligt, i tre, sex eller tolv "
            "timmar, eller som en engångshöjning tills tanken är laddad. Bra före "
            "gäster eller ett bad. Pumpen går tillbaka till sitt vanliga läge av "
            "sig själv, och höjningen kostar mer el eftersom elpatronen ofta "
            "hjälper till.",
            "Raises the hot water temperature for a while - three, six or twelve "
            "hours, or one single heat-up. Useful before guests or a bath. The "
            "pump returns to its normal mode on its own, and the boost costs more "
            "electricity because the immersion heater usually helps.",
        ),
    ),
    (
        re.compile(r"hot ?water (demand |comfort )?mode|varmvattenläge|varmvattenbehov", re.I),
        (
            "Hur varmt tappvattnet ska hållas. Litet räcker för ett hushåll som "
            "duschar kort, medel är normalläget, och stort ger varmast vatten och "
            "mest el eftersom elpatronen får hjälpa till oftare. Smart control "
            "låter pumpen lära sig när ni brukar använda varmvatten.",
            "How hot the tap water is kept. Small suits a household that showers "
            "briefly, medium is the normal setting, and large gives the hottest "
            "water and the highest bill, since the immersion heater helps more "
            "often. Smart control lets the pump learn when you use hot water.",
        ),
    ),
    # ----------------------------------------------------------- operation
    (
        re.compile(r"allow add|permit additional heat|tillåt (elpatron|tillsats)", re.I),
        (
            "Om pumpen får ta hjälp av elpatronen när kompressorn inte räcker "
            "till, vid sträng kyla eller när varmvattnet ska bli extra varmt. "
            "Elpatronen är ren el och dyrare än kompressorn; stängs den av kan "
            "huset bli svalare de kallaste dygnen.",
            "Whether the pump may call on the immersion heater when the compressor "
            "cannot keep up, in hard frost or when the hot water is to go extra "
            "hot. The immersion heater is plain electricity and dearer than the "
            "compressor; switching it off can leave the house cooler on the "
            "coldest days.",
        ),
    ),
    (
        re.compile(r"allow heating|permit heating|tillåt värme", re.I),
        (
            "Om pumpen alls får värma huset. Av betyder att bara varmvatten och "
            "eventuell kyla sköts, vilket är vad man vill sommartid eller när en "
            "energistyrning tillfälligt vill stoppa värmen.",
            "Whether the pump may heat the house at all. Off leaves it looking "
            "after hot water and any cooling only, which is what you want in "
            "summer, or when an energy manager wants the heating paused.",
        ),
    ),
    (
        re.compile(r"allow cooling|permit cooling|tillåt kyla", re.I),
        (
            "Om pumpen får kyla huset när det blir för varmt inne.",
            "Whether the pump may cool the house when it gets too warm indoors.",
        ),
    ),
    (
        re.compile(r"^operating mode$|^operational mode$|^driftläge$", re.I),
        (
            "Auto låter pumpen själv välja när kompressorn och elpatronen "
            "används, och är rätt i nästan alla lägen. Manuellt låser valet, och "
            "endast tillskott stänger av kompressorn och värmer huset med enbart "
            "el, vilket är dyrt och mest tänkt för service.",
            "Auto lets the pump decide for itself when the compressor and the "
            "immersion heater run, and is right in nearly every case. Manual locks "
            "the choice, and add-heat-only stops the compressor and heats the "
            "house on electricity alone, which is expensive and mostly meant for "
            "servicing.",
        ),
    ),
    (
        re.compile(r"holiday|semester", re.I),
        (
            "Sänker värmen och varmvattnet medan huset står tomt, utan att stänga "
            "av något. Hur mycket och hur länge ställs in i pumpens egen meny.",
            "Lowers heating and hot water while the house is empty, without "
            "switching anything off. How far and for how long is set in the pump's "
            "own menu.",
        ),
    ),
    (
        re.compile(r"immersion max|max int(ernal)?\.? add|elpatron, max", re.I),
        (
            "Hur många kilowatt av elpatronen pumpen som mest får använda. Ett "
            "lägre tak sparar el men kan göra huset svalare vid sträng kyla, och "
            "ett högre kräver att husets säkringar räcker till.",
            "The most the immersion heater may draw, in kilowatts. A lower ceiling "
            "saves electricity but can leave the house cooler in hard frost, and a "
            "higher one has to fit within the fuses of the house.",
        ),
    ),
    (
        re.compile(r"reset alarm|alarm reset|återställ larm", re.I),
        (
            "Kvitterar ett larm, precis som återställningsknappen i pumpens "
            "display. Larmet kommer tillbaka om orsaken finns kvar.",
            "Acknowledges an alarm, exactly as the reset button on the pump's own "
            "display does. The alarm returns if its cause is still there.",
        ),
    ),
    (
        re.compile(r"alarm action lower room|vid larm: sänk rum", re.I),
        (
            "Om pumpen ska sänka rumstemperaturen medan ett larm är aktivt, för "
            "att spara energi tills felet är åtgärdat.",
            "Whether the pump lowers the room temperature while an alarm is "
            "active, to save energy until the fault is seen to.",
        ),
    ),
    (
        re.compile(r"alarm action lower (hw|hot water)|vid larm: sänk vv", re.I),
        (
            "Om pumpen ska sänka varmvattentemperaturen medan ett larm är "
            "aktivt.",
            "Whether the pump lowers the hot water temperature while an alarm is "
            "active.",
        ),
    ),
    # ------------------------------------------------------ fans and pumps
    (
        re.compile(r"(brine|köldbärar).*(speed|varvtal)|gp2.*status", re.I),
        (
            "Hur fort köldbärarpumpen går, i procent. Det är den som cirkulerar "
            "vätskan i borrhålet eller markslingan.",
            "How fast the brine pump is running, as a percentage. It is the one "
            "circulating the fluid through the borehole or the ground loop.",
        ),
    ),
    (
        re.compile(r"(heating medium|supply|värmebärar).*(speed|varvtal)|gp1", re.I),
        (
            "Hur fort värmebärarpumpen går, i procent. Det är den som cirkulerar "
            "vattnet ut till elementen eller golvslingorna.",
            "How fast the heating medium pump is running, as a percentage. It is "
            "the one circulating water out to the radiators or the floor loops.",
        ),
    ),
    (
        re.compile(r"brine (medium )?pump|kb-pump|köldbärarpump", re.I),
        (
            "Hur köldbärarpumpen körs: intermittent betyder bara när kompressorn "
            "går och drar minst el, kontinuerlig betyder hela tiden, och tio "
            "dagar kontinuerlig används efter en installation för att lufta "
            "systemet.",
            "How the brine pump runs: intermittent means only while the compressor "
            "runs and uses the least electricity, continuous means all the time, "
            "and ten days continuous is used after an installation to bleed the "
            "system.",
        ),
    ),
    (
        re.compile(r"heating medium pump|vb-pump|värmebärarpump", re.I),
        (
            "Hur värmebärarpumpen körs: bara vid behov, vilket drar minst el, "
            "eller kontinuerligt, vilket ger jämnare temperatur i huset.",
            "How the heating medium pump runs: only when needed, which uses the "
            "least electricity, or continuously, which keeps the temperature in "
            "the house more even.",
        ),
    ),
    (
        re.compile(r"exhaust air fan speed|frånluftsfläkt|fläkthastighet", re.I),
        (
            "Fläktens hastighet i procent av full fart. Högre fart ger mer "
            "ventilation och mer värme att återvinna ur frånluften, men också mer "
            "ljud och elförbrukning. Hastighet 1 till 4 är de lägen du kan välja "
            "tillfälligt i pumpens meny, till exempel vid matlagning eller "
            "bortavaro.",
            "The fan's speed, as a percentage of full. Faster means more "
            "ventilation and more heat to recover from the exhaust air, but also "
            "more noise and more electricity. Speeds 1 to 4 are the settings you "
            "can pick temporarily in the pump's menu, for cooking or for being "
            "away.",
        ),
    ),
    # ----------------------------------------------------- what it reports
    (
        re.compile(r"(average|medel).*(bt1|outdoor|ute)|bt1 average", re.I),
        (
            "Utetemperaturen utjämnad över det senaste dygnet. Pumpen använder "
            "medelvärdet i stället för ögonblicksvärdet för att inte jaga varje "
            "molnskugga.",
            "The outdoor temperature averaged over the last day. The pump works "
            "from the average rather than the instant reading, so it does not "
            "chase every passing cloud.",
        ),
    ),
    (
        re.compile(r"outdoor temperature|utetemperatur", re.I),
        (
            "Utetemperaturen som pumpen själv mäter med sin givare (BT1) på husets "
            "norrsida. Det är den som avgör hur varmt vatten värmekurvan ber om.",
            "The outdoor temperature the pump measures with its own sensor (BT1) on the "
            "north wall. It is what decides how hot the water the heating curve "
            "asks for is.",
        ),
    ),
    (
        re.compile(r"calc\.? supply|calculated supply|beräknad framledning", re.I),
        (
            "Den framledningstemperatur värmekurvan ber om just nu. Skillnaden "
            "mellan den och den verkliga framledningen är vad gradminuterna "
            "räknar på.",
            "The supply temperature the heating curve is asking for right now. The "
            "difference between it and the actual supply temperature is what the "
            "degree minutes count.",
        ),
    ),
    (
        re.compile(r"supply (line|temp)|framledning", re.I),
        (
            "Temperaturen på vattnet (BT2) pumpen skickar ut till elementen eller "
            "golvslingorna just nu.",
            "The temperature of the water (BT2) the pump is sending out to the radiators "
            "or floor loops right now.",
        ),
    ),
    (
        re.compile(r"return (line|temp)|returledning", re.I),
        (
            "Temperaturen på vattnet (BT3) som kommer tillbaka från huset. Skillnaden "
            "mot framledningen visar hur mycket värme huset tagit upp: några "
            "grader är normalt, och en mycket liten skillnad betyder att huset "
            "inte behöver värmen.",
            "The temperature of the water (BT3) coming back from the house. The "
            "difference from the supply temperature shows how much heat the house "
            "took: a few degrees is normal, and very little difference means the "
            "house does not need the heat.",
        ),
    ),
    (
        re.compile(r"hw top|hot water top|varmvatten topp", re.I),
        (
            "Temperaturen högst upp i varmvattenberedaren (BT7), där det varmaste "
            "vattnet ligger. Det är ungefär det du får ur kranen.",
            "The temperature at the top of the hot water cylinder (BT7), where the "
            "hottest water sits. It is roughly what comes out of the tap.",
        ),
    ),
    (
        re.compile(
            r"hw load|hot water charging|controlling hot water sensor|varmvattenladdning", re.I
        ),
        (
            "Temperaturen där pumpen laddar varmvattnet (BT6). Den styr när laddningen "
            "startar och slutar, och ligger lägre än toppen i beredaren.",
            "The temperature where the pump charges the hot water (BT6). It decides when "
            "charging starts and stops, and reads lower than the top of the "
            "cylinder.",
        ),
    ),
    (
        re.compile(r"brine in|köldbärare in|kb-in", re.I),
        (
            "Temperaturen på vätskan (BT10) som kommer in från borrhålet eller "
            "markslingan. Sjunker den ovanligt lågt över en vinter tas mer värme "
            "ur berget än det hinner återhämta.",
            "The temperature of the fluid (BT10) coming in from the borehole or ground "
            "loop. If it sinks unusually low over a winter, more heat is being "
            "taken from the ground than it recovers.",
        ),
    ),
    (
        re.compile(r"brine out|köldbärare ut|kb-ut", re.I),
        (
            "Temperaturen på vätskan (BT11) som går tillbaka ut i borrhålet, efter att "
            "pumpen tagit sin värme. Skillnaden mot den ingående visar hur mycket "
            "värme som hämtats.",
            "The temperature of the fluid (BT11) going back out to the borehole after the "
            "pump has taken its heat. The difference from the incoming one shows "
            "how much heat was collected.",
        ),
    ),
    (
        re.compile(r"condensor out|condenser out|kondensor", re.I),
        (
            "Temperaturen direkt efter kondensorn (BT12), där köldmediet lämnar över sin "
            "värme till husets vatten. Den ligger normalt strax över "
            "framledningen.",
            "The temperature straight after the condenser (BT12), where the refrigerant "
            "hands its heat to the water of the house. It normally sits just above "
            "the supply temperature.",
        ),
    ),
    (
        re.compile(r"hot gas|hetgas|discharge", re.I),
        (
            "Temperaturen på den heta gasen (BT14) ut från kompressorn, den varmaste "
            "punkten i kretsen. Hög temperatur är normal när framledningen ska "
            "vara varm; ovanligt hög under lång tid är ett tecken på fel.",
            "The temperature of the hot gas (BT14) leaving the compressor, the hottest "
            "point in the circuit. A high reading is normal when the supply "
            "temperature is high; unusually high for a long time is a sign of a "
            "fault.",
        ),
    ),
    (
        re.compile(r"liquid line|vätskeledning", re.I),
        (
            "Temperaturen på köldmediet (BT15) sedan det kondenserat till vätska, på väg "
            "tillbaka mot förångaren.",
            "The temperature of the refrigerant (BT15) once it has condensed to a liquid, "
            "on its way back to the evaporator.",
        ),
    ),
    (
        re.compile(r"suction|sugg?as", re.I),
        (
            "Temperaturen på gasen (BT17) som sugs in i kompressorn. Tillsammans med "
            "förångartemperaturen visar den hur väl kretsen tar upp värme.",
            "The temperature of the gas (BT17) drawn into the compressor. With the "
            "evaporator temperature it shows how well the circuit is picking up "
            "heat.",
        ),
    ),
    (
        re.compile(r"evaporator|förångare", re.I),
        (
            "Temperaturen i förångaren, där köldmediet kokar och tar upp värmen "
            "från köldbäraren eller frånluften.",
            "The temperature in the evaporator, where the refrigerant boils and "
            "takes up heat from the brine or the exhaust air.",
        ),
    ),
    (
        re.compile(r"room (average )?temp|rumstemperatur", re.I),
        (
            "Rumstemperaturen där rumsgivaren (BT50) sitter. Pumpen kan använda den för "
            "att finjustera värmen utöver vad kurvan säger.",
            "The room temperature where the room sensor (BT50) sits. The pump can use it "
            "to trim the heating beyond what the curve says.",
        ),
    ),
    (
        re.compile(r"^prio$|driftprioritering|priority", re.I),
        (
            "Vad pumpen arbetar med just nu: värme, varmvatten, pool eller "
            "ingenting. Den gör en sak i taget och växlar efter behov.",
            "What the pump is working on right now: heating, hot water, the pool, "
            "or nothing. It does one thing at a time and switches as needed.",
        ),
    ),
    (
        re.compile(r"^alarm$|^larm$|larmnummer|alarm number", re.I),
        (
            "Pumpens larm i klartext. Inget larm betyder att allt är som det ska; "
            "ett larm står kvar tills orsaken är åtgärdad och larmet kvitterats.",
            "The pump's alarm in words. No alarm means all is well; an alarm stays "
            "until its cause is seen to and the alarm is acknowledged.",
        ),
    ),
    (
        re.compile(r"compressor frequency|kompressorfrekvens|frekvens.*kompressor", re.I),
        (
            "Hur fort kompressorn går just nu. En modern värmepump varvar upp och "
            "ner efter husets behov i stället för att starta och stanna, och låg "
            "frekvens under lång tid är det mest effektiva den kan göra.",
            "How fast the compressor is running right now. A modern heat pump "
            "varies its speed with the demand of the house instead of starting and "
            "stopping, and a low frequency for a long time is the most efficient "
            "thing it can do.",
        ),
    ),
    (
        re.compile(r"compr\.? in power|compressor power input|kompressor.*eleffekt", re.I),
        (
            "Hur mycket el kompressorn drar just nu. Delat med den värme pumpen "
            "avger blir det värmefaktorn.",
            "How much electricity the compressor is drawing right now. Divided "
            "into the heat the pump delivers, it gives the coefficient of "
            "performance.",
        ),
    ),
    (
        re.compile(r"el\.?add\.? power|internal additional heat|elpatron.*effekt", re.I),
        (
            "Hur mycket el elpatronen använder just nu. Noll betyder att "
            "kompressorn klarar sig själv, vilket är det normala.",
            "How much electricity the immersion heater is using right now. Zero "
            "means the compressor is coping on its own, which is the normal case.",
        ),
    ),
    (
        re.compile(r"flow sensor|flöde", re.I),
        (
            "Flödet genom kretsen, i liter per minut. För lågt flöde gör att "
            "pumpen inte får ut sin värme och kan ge larm.",
            "The flow through the circuit, in litres per minute. Too little flow "
            "keeps the pump from delivering its heat and can raise an alarm.",
        ),
    ),
    (
        re.compile(r"pressure sensor, condenser|högtryck|high press", re.I),
        (
            "Trycket på den heta sidan av kylkretsen. Det stiger när "
            "framledningen ska vara varm, och ett för högt tryck stoppar "
            "kompressorn med ett larm.",
            "The pressure on the hot side of the refrigerant circuit. It rises when "
            "the supply temperature is to be high, and too high a pressure stops "
            "the compressor with an alarm.",
        ),
    ),
    (
        re.compile(r"low press|lågtryck", re.I),
        (
            "Trycket på den kalla sidan av kylkretsen. Ett för lågt tryck betyder "
            "att pumpen inte får upp tillräckligt med värme ur berget eller "
            "luften, och stoppar kompressorn med ett larm.",
            "The pressure on the cold side of the refrigerant circuit. Too low a "
            "pressure means the pump is not getting enough heat out of the ground "
            "or the air, and it stops the compressor with an alarm.",
        ),
    ),
    (
        re.compile(r"tot\.? production|heat meter.*heat|avgiven värme", re.I),
        (
            "Räknare över den värme pumpen avgett sedan den togs i drift. "
            "Tillsammans med den tillförda elen ger den värmefaktorn.",
            "A counter of the heat the pump has delivered since it was "
            "commissioned. With the electricity it used, it gives the coefficient "
            "of performance.",
        ),
    ),
    (
        re.compile(r"tot\.? consumption|tillförd energi|tillförd el", re.I),
        (
            "Räknare över den el pumpen använt sedan den togs i drift, kompressor "
            "och elpatron tillsammans.",
            "A counter of the electricity the pump has used since it was "
            "commissioned, compressor and immersion heater together.",
        ),
    ),
    (
        re.compile(r"heat meter.*hw|varmvatten.*mätare", re.I),
        (
            "Räknare över den värme som gått till varmvattnet sedan pumpen togs i "
            "drift.",
            "A counter of the heat that has gone into hot water since the pump was "
            "commissioned.",
        ),
    ),
    (
        re.compile(r"op\.?time compr|run time compressor|drifttid.*kompressor", re.I),
        (
            "Antal timmar kompressorn gått sedan pumpen togs i drift.",
            "The number of hours the compressor has run since the pump was "
            "commissioned.",
        ),
    ),
    (
        re.compile(r"op\.?time add|run time additional|drifttid.*tillsats", re.I),
        (
            "Antal timmar elpatronen gått sedan pumpen togs i drift. Många timmar "
            "i förhållande till kompressorn betyder dyr värme och är värt att "
            "titta närmare på.",
            "The number of hours the immersion heater has run since the pump was "
            "commissioned. Many hours compared with the compressor means expensive "
            "heat and is worth looking into.",
        ),
    ),
    (
        re.compile(r"bt12 offset|justering bt12", re.I),
        (
            "Finjustering av givaren efter kondensorn (BT12), om den visar fel "
            "jämfört med en referensmätning. Rör den bara om en installatör bett "
            "om det.",
            "A trim for the sensor after the condenser (BT12), for when it reads "
            "wrong against a reference measurement. Leave it alone unless an "
            "installer asks for it.",
        ),
    ),
    (
        re.compile(r"reversing valve|växelventil|qn10", re.I),
        (
            "Växelventilen (QN10) som avgör om kompressorns värme går till huset "
            "eller till varmvattenberedaren. Pumpen gör en sak i taget och lägger "
            "om ventilen när den byter.",
            "The reversing valve (QN10) that decides whether the compressor's heat "
            "goes to the house or to the hot water cylinder. The pump does one at a "
            "time and throws the valve when it switches.",
        ),
    ),
    (
        re.compile(r"compressor (status|state)|kompressorstatus", re.I),
        (
            "Om kompressorn går just nu. Den startar när gradminuterna sjunkit "
            "tillräckligt och varvar sedan upp och ner efter husets behov.",
            "Whether the compressor is running right now. It starts once the degree "
            "minutes have fallen far enough, and then varies its speed with the "
            "demand of the house.",
        ),
    ),
    (
        re.compile(r"compressor starts|kompressorstarter", re.I),
        (
            "Antal gånger kompressorn startat sedan pumpen togs i drift. Många "
            "starter i förhållande till drifttiden betyder att den pendlar, "
            "vilket sliter och sänker verkningsgraden.",
            "How many times the compressor has started since the pump was "
            "commissioned. Many starts compared with the running hours means it is "
            "cycling, which wears it and costs efficiency.",
        ),
    ),
    (
        re.compile(r"^defrosting(?! time)|^avfrostning(?!stid)", re.I),
        (
            "Om pumpen avfrostar just nu. En luftvärmepump lägger på sig is på "
            "förångaren och tinar bort den med jämna mellanrum; en bergvärmepump "
            "gör det aldrig.",
            "Whether the pump is defrosting right now. An air source pump ices up "
            "its evaporator and thaws it at intervals; a ground source pump never "
            "does.",
        ),
    ),
    (
        re.compile(r"^current \(be\d\)|^ström\b", re.I),
        (
            "Strömmen i en av faserna in till pumpen. Den mäts för att husets "
            "säkringar inte ska lösa ut: blir strömmen för hög drar pumpen först "
            "ner elpatronen.",
            "The current in one of the phases feeding the pump. It is measured so "
            "the fuses of the house do not blow: if the current runs high the pump "
            "turns the immersion heater down first.",
        ),
    ),
    (
        re.compile(r"fan speed|fläktvarvtal|fläkthastighet", re.I),
        (
            "Fläktens varvtal i procent av full fart.",
            "The fan's speed, as a percentage of full.",
        ),
    ),
    (
        re.compile(r"energy log.*(produced|producerad)", re.I),
        (
            "Pumpens egen energilogg: hur mycket värme den gav den senaste "
            "timmen. Loggen förs separat för värme, varmvatten och kyla.",
            "The pump's own energy log: how much heat it delivered over the last "
            "hour. The log is kept separately for heating, hot water and cooling.",
        ),
    ),
    (
        re.compile(r"energy log.*(used|använd)", re.I),
        (
            "Pumpens egen energilogg: hur mycket el den använde den senaste "
            "timmen. Jämfört med den värme som producerades samma timme ger den "
            "timmens värmefaktor.",
            "The pump's own energy log: how much electricity it used over the last "
            "hour. Set against the heat produced in the same hour, it gives that "
            "hour's coefficient of performance.",
        ),
    ),
    (
        re.compile(
            r"instantaneous used power|^current power|energy log.*current power|momentan.*effekt",
            re.I,
        ),
        (
            "Pumpens elförbrukning just nu, kompressor och elpatron tillsammans.",
            "The pump's electricity use right now, compressor and immersion heater "
            "together.",
        ),
    ),
    (
        re.compile(r"eme ?20|total energy", re.I),
        (
            "Mätvärde från en extern elmätare (EME 20) som pumpen läser av. Den "
            "används för att mäta förbrukningen utan en separat mätare i "
            "elcentralen.",
            "A reading from an external electricity meter (EME 20) the pump reads. "
            "It measures consumption without a separate meter in the fuse box.",
        ),
    ),
    (
        re.compile(r"ext\.? supply|external supply|bt25", re.I),
        (
            "Framledningstemperaturen mätt av en extra givare (BT25), till exempel "
            "efter en shuntgrupp eller i en andra värmekrets.",
            "The supply temperature measured by an extra sensor (BT25), for "
            "instance after a mixing valve or in a second heating circuit.",
        ),
    ),
    # ------------------------------------------------- ventilation, FLM, ERS
    # Everything below covers registers a particular installation may or may
    # not have. They are written all the same: an accessory found on a scan
    # brings its registers with it, and they should arrive explained.
    (
        re.compile(r"return time fan|fläktåtergångstid", re.I),
        (
            "Hur länge en tillfälligt vald fläkthastighet gäller innan fläkten "
            "går tillbaka till normal. Den används när man vädrar ut matos eller "
            "höjer ventilationen medan huset är fullt av folk: man väljer en "
            "annan hastighet och behöver inte komma ihåg att ställa tillbaka den.",
            "How long a temporarily chosen fan speed lasts before the fan returns "
            "to normal. It is for airing out cooking smells or running the "
            "ventilation harder while the house is full: you pick another speed "
            "and do not have to remember to set it back.",
        ),
    ),
    (
        re.compile(r"time between filter replacement|filter alarm|filterlarm", re.I),
        (
            "Hur många månader det går mellan påminnelserna om att rengöra "
            "ventilationsfiltret. Ett igensatt filter ger sämre luftflöde, sämre "
            "återvinning och en pump som arbetar mer för samma värme.",
            "How many months pass between the reminders to clean the ventilation "
            "filter. A blocked filter means less airflow, less recovered heat and "
            "a pump working harder for the same warmth.",
        ),
    ),
    (
        re.compile(r"defrosting time \(flm|tid mellan avfrost", re.I),
        (
            "Kortaste tiden mellan två avfrostningar av växlaren i "
            "frånluftsmodulen. Växlaren kyls ner när modulen tar värme ur "
            "ventilationsluften, och fukten i luften kan frysa på den. "
            "Avfrostningen värmer växlaren så isen smälter och rinner ut genom "
            "kondensslangen.",
            "The shortest time between two defrostings of the exhaust air "
            "module's heat exchanger. The exchanger cools down as the module "
            "takes heat out of the ventilation air, and the moisture in that air "
            "can freeze onto it. Defrosting warms the exchanger so the ice melts "
            "and runs out through the condensation hose.",
        ),
    ),
    (
        re.compile(r"excess temperature \(flm", re.I),
        (
            "Hur många grader varmare än önskat det får bli inomhus innan "
            "frånluftsmodulen börjar kyla. En liten siffra ger kyla tidigt, en "
            "stor låter huset bli varmare först.",
            "How many degrees warmer than wanted the house may get before the "
            "exhaust air module starts cooling. A small number starts cooling "
            "early, a large one lets the house warm up first.",
        ),
    ),
    (
        re.compile(r"set point value, cooling \(flm|cooling heat sensor set point", re.I),
        (
            "Den temperatur kylan siktar på när frånluftsmodulen kyler huset med "
            "den svala köldbärarvätskan från borrhålet.",
            "The temperature the cooling aims for when the exhaust air module "
            "cools the house with the cool brine from the borehole.",
        ),
    ),
    (
        re.compile(
            r"^cooling \(flm|cooling activated \(flm|flm ?\d* ?cooling status|^cooling status",
            re.I,
        ),
        (
            "Om frånluftsmodulen får kyla huset. Kylan kommer från köldbäraren i "
            "marken och kostar nästan ingen el, men den ger en mild kyla - inte "
            "det en luftkonditionering ger.",
            "Whether the exhaust air module may cool the house. The cooling comes "
            "from the brine in the ground and costs almost no electricity, but it "
            "is a mild cooling - not what an air conditioner gives.",
        ),
    ),
    (
        re.compile(r"pump speed \(flm|^pump \d \(flm\)|continuous operation.*pump", re.I),
        (
            "Cirkulationspumpen i frånluftsmodulen, som driver köldbäraren genom "
            "modulens växlare. Hastigheten avgör hur mycket värme som hämtas ur "
            "ventilationsluften; kontinuerlig drift låter den gå även när "
            "kompressorn står still.",
            "The circulation pump in the exhaust air module, which drives the "
            "brine through the module's exchanger. Its speed decides how much "
            "heat is taken out of the ventilation air; continuous operation lets "
            "it run even when the compressor is stopped.",
        ),
    ),
    (
        re.compile(r"(flm ?\d* )?(exhaust air )?fan speed [1-4]\b|^speed [1-4]\b|^fan mode [1-4]\b",
                   re.I),
        (
            "Luftflödet vid en av de fyra valbara fläkthastigheterna, i procent "
            "av full fart. Hastigheterna används av schemat och av "
            "tillfälliga lägen som forcerad ventilation; normalhastigheten är den "
            "huset går på till vardags.",
            "The airflow at one of the four selectable fan speeds, as a "
            "percentage of full speed. The speeds are what the schedule and "
            "temporary modes such as forced ventilation use; the normal speed is "
            "the one the house runs on day to day.",
        ),
    ),
    (
        re.compile(r"exhaust air temp|exh\. air \(|bt20\b", re.I),
        (
            "Temperaturen på luften som ventilationen suger ut ur huset, mätt "
            "innan värmen tas ur den (BT20). Den ligger nära rumstemperaturen och "
            "är den värme frånluftsmodulen har att hämta ur.",
            "The temperature of the air the ventilation draws out of the house, "
            "measured before its heat is taken (BT20). It sits close to room "
            "temperature, and it is the heat the exhaust air module has to work "
            "with.",
        ),
    ),
    (
        re.compile(r"vented air temp|bt21\b", re.I),
        (
            "Temperaturen på luften efter att värmen tagits ur den, på väg ut ur "
            "huset (BT21). Skillnaden mot frånluften visar hur mycket värme "
            "modulen återvinner just nu.",
            "The temperature of the air after its heat has been taken, on its way "
            "out of the house (BT21). The difference from the exhaust air shows "
            "how much heat the module is recovering right now.",
        ),
    ),
    (
        re.compile(r"supply air temp|bt22\b", re.I),
        (
            "Temperaturen på den friska luften som blåses in i huset (BT22).",
            "The temperature of the fresh air blown into the house (BT22).",
        ),
    ),
    (
        re.compile(r"night cooling|nattsvalka", re.I),
        (
            "Nattsvalka: en varm sommarnatt ökar fläkten ventilationen och "
            "blåser in svalare uteluft i huset. Den startar när det är varmare "
            "inne än ute och kostar bara fläktens el.",
            "Night cooling: on a warm summer night the fan raises the "
            "ventilation and blows cooler outdoor air into the house. It starts "
            "when it is warmer inside than out, and costs no more than the fan's "
            "electricity.",
        ),
    ),
    (
        re.compile(r"outdoor air mixing|outdoor air mixture|mixing outdoor air|ul mixture", re.I),
        (
            "Inblandning av uteluft i ventilationen, för hus där frånluften "
            "ensam inte räcker till. Inställningarna bestämmer när uteluft "
            "blandas in och hur hårt fläkten då går.",
            "Mixing outdoor air into the ventilation, for houses where the "
            "exhaust air alone is not enough. The settings decide when outdoor "
            "air is mixed in and how hard the fan then runs.",
        ),
    ),
    (
        re.compile(r"reduced ventilation|adjust the ventilation|set the ventilation", re.I),
        (
            "Sänkt ventilation, som pumpen kan använda när ingen är hemma eller "
            "när uteluften är mycket kall. Mindre luft ger mindre värmeförlust "
            "men också sämre luftkvalitet, så den bör användas sparsamt.",
            "Reduced ventilation, which the pump can use when nobody is home or "
            "when the outdoor air is very cold. Less air means less heat lost, "
            "but also poorer air quality, so it should be used sparingly.",
        ),
    ),
    (
        re.compile(r"min\. vent temp|min vent temp", re.I),
        (
            "Den lägsta temperatur ventilationsluften tillåts hålla i "
            "återvinningsmodulen ERS. Inställningen finns för att modulen inte "
            "ska blåsa in för kall luft i huset.",
            "The lowest temperature the ventilation air is allowed to hold in the "
            "ERS recovery module. The setting is there so the module does not "
            "blow air that is too cold into the house.",
        ),
    ),
    (
        re.compile(r"blocking actions \(ers|^ers [1-4]$|ers \d+ accessory", re.I),
        (
            "Återvinningsmodulen ERS, som tar värme ur frånluften och lämnar den "
            "till tilluften utan att gå via värmepumpen. Inställningen styr "
            "modulens egen drift; vad de enskilda lägena gör står i tillbehörets "
            "anvisning.",
            "The ERS recovery module, which takes heat out of the exhaust air and "
            "hands it to the supply air without going through the heat pump. The "
            "setting governs the module's own operation; what each mode does is "
            "in the accessory's own manual.",
        ),
    ),
    (
        re.compile(r"external ers .*speed|external .*accessory gq\d speed", re.I),
        (
            "Hastigheten på en av fläktarna i återvinningsmodulen ERS, styrd "
            "utifrån i stället för av modulen själv.",
            "The speed of one of the fans in the ERS recovery module, set from "
            "outside rather than by the module itself.",
        ),
    ),
    (
        re.compile(r"humidity average|relative humidity|^hts [1-4]|hts \d+ accessory", re.I),
        (
            "Luftfuktigheten inomhus, mätt av tillbehöret HTS. Pumpen använder "
            "den för att kyla utan att det bildas kondens på rör och golv.",
            "The indoor humidity, measured by the HTS accessory. The pump uses it "
            "to cool without condensation forming on pipes and floors.",
        ),
    ),
    (
        re.compile(r"prevent humidity|limit humidity", re.I),
        (
            "Skydd mot kondens vid kyla: pumpen håller tillbaka kylan när luften "
            "är så fuktig att det skulle börja droppa på kalla rör eller "
            "golvslingor. Utan det kan fukt samlas där den inte syns.",
            "Condensation protection while cooling: the pump holds the cooling "
            "back when the air is humid enough that cold pipes or floor loops "
            "would start to drip. Without it, moisture can gather where it cannot "
            "be seen.",
        ),
    ),
    # --------------------------------------------- climate systems and rooms
    (
        re.compile(r"climate system \d+ accessory|^climate system \d+$|^system \d+ \(rmu\)", re.I),
        (
            "En extra värmekrets med egen shunt, pump och framledningsgivare - "
            "till exempel golvvärme på ett plan och radiatorer på ett annat. Varje "
            "krets har sin egen kurva och kan hålla sin egen temperatur. Rumsenheten "
            "RMU hör till en krets och styr den från det rum den sitter i.",
            "An extra heating circuit with its own mixing valve, pump and supply "
            "sensor - underfloor heating on one floor and radiators on another, "
            "say. Each circuit has its own curve and can hold its own temperature. "
            "An RMU room unit belongs to one circuit and runs it from the room it "
            "hangs in.",
        ),
    ),
    (
        re.compile(r"mixing valve amp|shuntförstärkning", re.I),
        (
            "Hur kraftigt shuntventilen svarar när framledningen avviker från sitt "
            "börvärde. Ett högt värde rättar snabbt men kan få temperaturen att "
            "pendla, ett lågt värde är lugnare men långsammare.",
            "How hard the mixing valve answers when the supply temperature strays "
            "from its set point. A high value corrects quickly but can make the "
            "temperature swing; a low one is calmer but slower.",
        ),
    ),
    (
        re.compile(r"shunt wait|shuntväntetid", re.I),
        (
            "Hur länge shuntventilen väntar mellan sina steg. Vattnet behöver tid "
            "att nå fram och givaren tid att känna av det; en för kort väntetid "
            "får ventilen att jaga sin egen svans.",
            "How long the mixing valve waits between its steps. The water needs "
            "time to arrive and the sensor time to feel it; too short a wait sets "
            "the valve chasing its own tail.",
        ),
    ),
    (
        re.compile(r"mixing valve state|oper\. mode shunt|shunt.*(state|status)", re.I),
        (
            "Vad shuntventilen gör just nu: öppnar, stänger eller står stilla. Den "
            "blandar returvatten i framledningen så att kretsen får den temperatur "
            "kurvan begär, även när pumpen levererar varmare vatten än så.",
            "What the mixing valve is doing right now: opening, closing or standing "
            "still. It blends return water into the supply so the circuit gets the "
            "temperature the curve asks for, even when the pump delivers hotter "
            "water than that.",
        ),
    ),
    (
        re.compile(r"(min|max)\.? supply( system)?\b|min\.? framledning|max\.? framledning", re.I),
        (
            "Den lägsta respektive högsta temperatur pumpen får skicka ut i "
            "kretsen, oavsett vad kurvan räknar fram. Taket skyddar framför allt "
            "golvvärme: för varmt vatten skadar trägolv och kan spräcka fogar. "
            "Golvvärme brukar ligga runt 35-45 °C, radiatorer högre.",
            "The lowest and highest temperature the pump may send out into the "
            "circuit, whatever the curve works out. The ceiling matters most for "
            "underfloor heating: water that is too hot damages wooden floors and "
            "can crack joints. Underfloor heating usually sits around 35-45 °C, "
            "radiators higher.",
        ),
    ),
    (
        re.compile(r"calc\.? cooling supply|beräknad.*kyl", re.I),
        (
            "Den framledningstemperatur kylan siktar på just nu, uträknad ur "
            "kylkurvan och utetemperaturen.",
            "The supply temperature the cooling is aiming for right now, worked "
            "out from the cooling curve and the outdoor temperature.",
        ),
    ),
    (
        re.compile(r"cool curve|cooling curve|kylkurva", re.I),
        (
            "Kylans motsvarighet till värmekurvan: ju varmare det är ute, desto "
            "svalare vatten skickas ut i kretsen. En högre siffra ger mer kyla en "
            "varm dag.",
            "The cooling's answer to the heating curve: the warmer it is outside, "
            "the cooler the water sent out into the circuit. A higher number gives "
            "more cooling on a warm day.",
        ),
    ),
    (
        re.compile(r"cool offset|cooling offset", re.I),
        (
            "Flyttar hela kylkurvan upp eller ner lika mycket vid alla "
            "utetemperaturer. Använd den när det är jämnt för svalt eller för "
            "varmt inomhus när kylan går.",
            "Moves the whole cooling curve up or down by the same amount at every "
            "outdoor temperature. Use it when the house is evenly too cool or too "
            "warm while the cooling runs.",
        ),
    ),
    (
        re.compile(r"room sensor .*(cool|kyla)|room sensor cool", re.I),
        (
            "Rumsgivarens inställningar för kyldrift: vilken rumstemperatur kylan "
            "ska hålla, och hur hårt avvikelsen från den får påverka.",
            "The room sensor's settings for cooling: what room temperature the "
            "cooling should hold, and how strongly a deviation from it is allowed "
            "to act.",
        ),
    ),
    (
        re.compile(r"use room sensor|rumsgivare.*(används|aktiv)", re.I),
        (
            "Om rumsgivaren får påverka värmen eller bara visas. Med den påslagen "
            "rättar pumpen kurvan efter den verkliga rumstemperaturen, vilket "
            "hjälper i hus där sol, eldstad eller många människor svänger "
            "temperaturen. I ett hus med termostater på elementen kan den i "
            "stället göra styrningen orolig.",
            "Whether the room sensor is allowed to act on the heating or is only "
            "shown. With it on, the pump corrects the curve by the real room "
            "temperature, which helps in houses where sun, a fire or a crowd swing "
            "it. In a house with thermostats on the radiators it can instead make "
            "the control restless.",
        ),
    ),
    (
        re.compile(r"room sensor set ?point|room sensor setpoint|önskad rumstemperatur", re.I),
        (
            "Den rumstemperatur pumpen ska hålla när rumsgivaren är påslagen.",
            "The room temperature the pump should hold when the room sensor is "
            "switched on.",
        ),
    ),
    (
        re.compile(r"room sensor factor|rumsgivarfaktor", re.I),
        (
            "Hur hårt en avvikelse i rumstemperaturen får ändra framledningen. Ett "
            "högt värde rättar snabbt men kan ge svängningar; ett lågt värde låter "
            "kurvan bestämma mest.",
            "How strongly a deviation in room temperature is allowed to change the "
            "supply temperature. A high value corrects quickly but can make it "
            "swing; a low one leaves most of the say to the curve.",
        ),
    ),
    (
        re.compile(r"external adjustment with room sensor", re.I),
        (
            "Vilken rumstemperatur den externa kontakten ska begära när den sluts, "
            "i ett system som har rumsgivare. Kontakten kan till exempel komma från "
            "ett larm, ett tidur eller en styrning för billig el.",
            "What room temperature the external contact asks for when it closes, in "
            "a system that has a room sensor. The contact can come from an alarm, a "
            "timer or a control that follows the electricity price.",
        ),
    ),
    (
        re.compile(r"external adjustment|extern justering|external reading", re.I),
        (
            "Extern justering: en potentialfri kontakt som ändrar värmen när den "
            "sluts, genom att flytta kurvförskjutningen ett bestämt antal steg. "
            "Den används för att sänka värmen när ingen är hemma eller när elen är "
            "dyr, utan att röra pumpens egna inställningar.",
            "External adjustment: a dry contact that changes the heating when it "
            "closes, by moving the curve offset a set number of steps. It is used "
            "to lower the heating when nobody is home or when electricity is dear, "
            "without touching the pump's own settings.",
        ),
    ),
    (
        re.compile(r"zone \d+ affected by ecs|external adjustment input.*ecs", re.I),
        (
            "Vilka zoner i huset som hör till det extra klimatsystemet ECS. En zon "
            "är ett rum eller en grupp rum med egen givare; den som hör till ECS "
            "styrs av den kretsens kurva i stället för huvudsystemets.",
            "Which zones of the house belong to the extra ECS climate system. A "
            "zone is a room or a group of rooms with its own sensor; one that "
            "belongs to ECS follows that circuit's curve rather than the main "
            "system's.",
        ),
    ),
    (
        re.compile(r"smart home ctrl|smart home", re.I),
        (
            "Om kretsen får styras av ett hemautomationssystem utifrån, vid sidan "
            "av pumpens egna inställningar.",
            "Whether the circuit may be steered by a home automation system from "
            "outside, alongside the pump's own settings.",
        ),
    ),
    (
        re.compile(r"floor drying|golvtork", re.I),
        (
            "Golvtorksfunktionen: efter att en betongplatta gjutits körs värmen "
            "enligt ett schema av perioder med bestämda temperaturer, så att "
            "plattan torkar utan att spricka. Den används en gång vid nybygge och "
            "ska stängas av efteråt.",
            "The floor drying function: after a concrete slab has been cast, the "
            "heating runs to a schedule of periods at set temperatures so the slab "
            "dries without cracking. It is used once on a new build and switched "
            "off afterwards.",
        ),
    ),
    (
        re.compile(r"(heating|cooling) use mix\.? valve", re.I),
        (
            "Om kretsens shuntventil ska användas för värme respektive kyla. En "
            "krets utan shunt får samma temperatur som pumpen skickar ut.",
            "Whether the circuit's mixing valve is used for heating and for "
            "cooling. A circuit without one gets the same temperature the pump "
            "sends out.",
        ),
    ),
    (
        re.compile(r"extra heating system pump|extra.*cirkulationspump", re.I),
        (
            "Den extra cirkulationspump som driver runt vattnet i den här kretsen.",
            "The extra circulation pump that drives the water round this circuit.",
        ),
    ),
    # ------------------------------------------------------------------ pool
    (
        re.compile(r"pool \d+ (start|stop) temperature|pool.*(start|stopp)temperatur", re.I),
        (
            "Pumpen börjar värma poolen när pooltemperaturen fallit till "
            "starttemperaturen och slutar när den nått stopptemperaturen. Ett "
            "större avstånd mellan dem ger färre men längre poolladdningar, vilket "
            "är skonsammare för kompressorn.",
            "The pump starts heating the pool when the pool temperature has fallen "
            "to the start temperature, and stops when it reaches the stop "
            "temperature. A wider gap between them means fewer but longer pool "
            "charges, which is gentler on the compressor.",
        ),
    ),
    (
        re.compile(r"pool \d* ?accessory|pool \d+ activated|pool \d* ?pump", re.I),
        (
            "Poolvärmningen: pumpen låter en del av sin värme gå till poolen "
            "genom en växlare med egen pump, mellan varmvatten och husvärme i "
            "prioritet. Den kan stängas av utan att resten av anläggningen "
            "påverkas.",
            "Pool heating: the pump lets part of its heat go to the pool through an "
            "exchanger with its own pump, ranked between hot water and house "
            "heating. It can be switched off without touching the rest of the "
            "installation.",
        ),
    ),
    (
        re.compile(r"^pool\b|pool \(bt51|bt51", re.I),
        (
            "Pooltemperaturen, mätt av givaren BT51 i poolens krets.",
            "The pool temperature, measured by sensor BT51 in the pool's circuit.",
        ),
    ),
    # --------------------------------------- additional heat, price, sources
    (
        re.compile(r"energy price \d{2}:\d{2}|elpris \d", re.I),
        (
            "Elpriset för en bestämd timme på dygnet, som pumpen använder när den "
            "väljer mellan el och en annan värmekälla eller när den flyttar "
            "varmvatten och värme till billiga timmar. Priserna anges i samma "
            "enhet för alla timmar; det är förhållandet mellan dem som styr.",
            "The electricity price for one hour of the day, which the pump uses "
            "when it chooses between electricity and another heat source, or when "
            "it moves hot water and heating to the cheap hours. The prices are "
            "given in the same unit for every hour; it is the ratio between them "
            "that decides.",
        ),
    ),
    (
        re.compile(r"smart energy source|el\.? price|energy source prio", re.I),
        (
            "Smart energikälla: pumpen väljer själv mellan de värmekällor som "
            "finns - kompressor, elpatron, panna, solvärme - efter vad de kostar "
            "och i vilken ordning de får användas. Priserna och prioriteringen är "
            "vad den räknar på; start-DM säger hur stort värmeunderskottet ska "
            "vara innan en viss källa tas in.",
            "Smart energy source: the pump chooses for itself between the heat "
            "sources it has - compressor, immersion heater, boiler, solar - by "
            "what they cost and in what order they may be used. The prices and the "
            "priority are what it works from; the start DM says how large the heat "
            "deficit must be before a given source is brought in.",
        ),
    ),
    (
        re.compile(r"active days|aktiva dagar", re.I),
        (
            "Vilka veckodagar schemat gäller. Värdet är en summa av dagarna, en "
            "bit per dag, så ett udda tal betyder att måndagen ingår.",
            "Which weekdays the schedule applies to. The value is a sum of the "
            "days, one bit each, so an odd number means Monday is included.",
        ),
    ),
    (
        re.compile(r"(shunt|step) controlled add|external add|add\.? heat.*(shunt|step)"
                   r"|tillsats.*shunt", re.I),
        (
            "En värmekälla vid sidan av värmepumpen: en ved-, olje-, gas- eller "
            "pelletspanna, eller elsteg i en extern tank. Pumpen startar den när "
            "dess egen värme inte räcker, och shunten blandar in dess värme i "
            "kretsen.",
            "A heat source beside the heat pump: a wood, oil, gas or pellet "
            "boiler, or electric steps in an external tank. The pump starts it "
            "when its own heat is not enough, and the mixing valve blends that "
            "heat into the circuit.",
        ),
    ),
    (
        re.compile(r"ground ?water pump|grundvattenpump", re.I),
        (
            "Pumpen i ett grundvattensystem, som lyfter vatten ur brunnen genom "
            "växlaren och tillbaka. Den går bara när kompressorn behöver värme "
            "ur vattnet.",
            "The pump in a ground water system, which lifts water out of the well "
            "through the exchanger and back. It runs only while the compressor "
            "needs heat from the water.",
        ),
    ),
    (
        re.compile(r"solar|sol(fångare|panel)|pv panel|eme \d", re.I),
        (
            "Solvärme eller solel som pumpen tar hänsyn till: solfångare som "
            "laddar tanken eller borrhålet, eller solceller vars överskott får gå "
            "till varmvatten och värme i stället för ut på nätet.",
            "Solar heat or solar power the pump takes into account: collectors "
            "that charge the tank or the borehole, or panels whose surplus is sent "
            "to hot water and heating instead of out onto the grid.",
        ),
    ),
    (
        re.compile(r"^permit\b|permit \(", re.I),
        (
            "Om den här värmekällan eller kompressorn får starta just nu. Den kan "
            "vara spärrad av ett schema, av en extern kontakt, av en larmåtgärd "
            "eller för att en annan källa har företräde.",
            "Whether this heat source or compressor is allowed to start right now. "
            "It can be held back by a schedule, by an external contact, by an "
            "alarm action, or because another source has priority.",
        ),
    ),
    # -------------------------------------- several heat pumps, run counters
    (
        re.compile(r"compressor, (total time|oper\.? time).*(pool|cooling|energy storage)"
                   r"|compressor, total time", re.I),
        (
            "Räknare över hur länge kompressorn arbetat med just den uppgiften - "
            "pool, kyla, energilager - sedan pumpen togs i drift. Räknarna visar "
            "vad anläggningens arbete går åt till; de går bara uppåt.",
            "A counter of how long the compressor has worked on that one task - "
            "pool, cooling, energy storage - since the pump was commissioned. The "
            "counters show what the installation's work goes to; they only ever "
            "rise.",
        ),
    ),
    (
        re.compile(r"compressor, requested|compressor, blocked|requested.*compressor", re.I),
        (
            "Om styrningen begär att den här kompressorn ska gå. En begärd "
            "kompressor som ändå står stilla väntar oftast på sin starttid eller "
            "är spärrad.",
            "Whether the control is asking for this compressor to run. One that is "
            "asked for and still stands still is usually waiting out its start "
            "delay, or is blocked.",
        ),
    ),
    (
        re.compile(r"frost protection heat exchanger|frysskydd", re.I),
        (
            "Frysskyddet vaktar växlaren: blir köldbäraren för kall stoppas "
            "kompressorn innan vattnet i växlaren kan frysa och spränga den.",
            "Freeze protection watches the exchanger: if the brine gets too cold "
            "the compressor is stopped before the water in the exchanger can "
            "freeze and split it.",
        ),
    ),
    (
        re.compile(r"time to defrosting|tid till avfrost", re.I),
        (
            "Tiden tills nästa avfrostning av luftväxlaren. Under avfrostningen "
            "vänder pumpen kylan en kort stund för att smälta bort is; den ger "
            "ingen värme just då, och det är normalt.",
            "The time until the next defrosting of the air exchanger. During a "
            "defrost the pump turns the cold round for a short while to melt the "
            "ice off; it gives no heat just then, and that is normal.",
        ),
    ),
    (
        re.compile(r"generated power|^power \(|effekt \(", re.I),
        (
            "Den värmeeffekt pumpen räknar ut att den lämnar just nu, av "
            "temperaturerna och flödet. Den är en beräkning, inte en mätning, och "
            "ska läsas som en storleksordning.",
            "The heat output the pump works out that it is giving right now, from "
            "the temperatures and the flow. It is a calculation rather than a "
            "measurement, and should be read as an order of magnitude.",
        ),
    ),
    (
        re.compile(r"fan (status|rpm|speed current)|fläktvarvtal", re.I),
        (
            "Fläkten i utedelen, som drar uteluft genom växlaren. Varvtalet följer "
            "hur mycket värme pumpen hämtar; i mild väderlek räcker ett lågt varv.",
            "The fan in the outdoor unit, which pulls outdoor air through the "
            "exchanger. Its speed follows how much heat the pump is taking; in "
            "mild weather a low speed is enough.",
        ),
    ),
    (
        re.compile(r"seconds of blank time left|blank time|charge pump|laddpump", re.I),
        (
            "Laddpumpen driver vattnet mellan värmepumpen och tanken. Spärrtiden "
            "är den stund pumpen måste stå still efter ett stopp innan den får "
            "starta igen, så att den inte startar och stoppar i korta ryck.",
            "The charge pump drives the water between the heat pump and the tank. "
            "The blank time is the spell it has to stand still after a stop before "
            "it may start again, so it does not start and stop in short bursts.",
        ),
    ),
    # ------------------------------------------- the refrigerant circuit
    # These are the pump's own regulation of its cooling circuit. An owner
    # cannot set them, but a reading that has gone out of its usual range is
    # often the first sign of something, so they are explained rather than
    # dismissed.
    (
        re.compile(r"superheat (reference|temp\.? reference)|överhettningsreferens", re.I),
        (
            "Den överhettning styrningen siktar på. Expansionsventilen öppnas och "
            "stängs tills den uppmätta överhettningen möter det här värdet.",
            "The superheat the control is aiming for. The expansion valve opens and "
            "closes until the measured superheat meets this value.",
        ),
    ),
    (
        re.compile(r"superheat|överhettning", re.I),
        (
            "Överhettningen är hur många grader varmare köldmediegasen är än den "
            "temperatur den kokar vid i sitt tryck. Några graders överhettning "
            "betyder att allt köldmedium hunnit koka bort innan det når "
            "kompressorn - vätska in i kompressorn skadar den.",
            "Superheat is how many degrees hotter the refrigerant gas is than the "
            "temperature it boils at under its own pressure. A few degrees of "
            "superheat mean all the refrigerant has boiled away before it reaches "
            "the compressor - liquid entering a compressor damages it.",
        ),
    ),
    (
        re.compile(r"degree of opening (eev|evi)|expansion valve|expansionsventil", re.I),
        (
            "Hur mycket expansionsventilen är öppen, i procent. Ventilen släpper "
            "in köldmedium i förångaren; ju mer värme som ska hämtas, desto mer "
            "öppnar den.",
            "How far the expansion valve is open, as a percentage. The valve lets "
            "refrigerant into the evaporator; the more heat there is to take, the "
            "further it opens.",
        ),
    ),
    (
        re.compile(r"(eev|evi)[- ](pv|ssh|te)|set point value (eev|evi)|^(eev|evi)\b", re.I),
        (
            "Ett arbetsvärde ur styrningen av expansionsventilen: det uppmätta "
            "värdet, dess börvärde eller skillnaden mellan dem. EEV är "
            "huvudventilen, EVI den ventil som sprutar in köldmedium mitt i "
            "kompressionen för att pumpen ska klara riktigt kallt väder. Värdena "
            "är till för felsökning.",
            "A working figure from the expansion valve's control: the measured "
            "value, its set point, or the difference between them. EEV is the main "
            "valve, EVI the one that injects refrigerant midway through the "
            "compression so the pump can cope with truly cold weather. These "
            "figures are for fault finding.",
        ),
    ),
    (
        re.compile(r"injection|insprutning|bt81", re.I),
        (
            "Insprutningskretsen (EVI), som tar in en del av köldmediet mitt i "
            "kompressionen. Den kyler kompressorn och låter pumpen ge varmt vatten "
            "även när det är mycket kallt ute.",
            "The injection circuit (EVI), which takes part of the refrigerant in "
            "midway through the compression. It cools the compressor and lets the "
            "pump give hot water even when it is very cold outside.",
        ),
    ),
    (
        re.compile(r"hi press|high press|hög(t)? tryck|bp9", re.I),
        (
            "Högtryckssidan i kylkretsen, den varma sidan efter kompressorn. "
            "Trycket räknas om till den temperatur köldmediet kondenserar vid, så "
            "värdet visas i grader. Ett högt värde följer varmt framledningsvatten; "
            "blir det för högt stannar kompressorn på högtryckspressostaten.",
            "The high pressure side of the refrigerant circuit, the hot side after "
            "the compressor. The pressure is converted to the temperature the "
            "refrigerant condenses at, so the value is shown in degrees. A high "
            "value follows hot supply water; too high and the compressor stops on "
            "the high pressure switch.",
        ),
    ),
    (
        re.compile(r"lo press|low press|låg(t)? tryck|bp8", re.I),
        (
            "Lågtryckssidan i kylkretsen, den kalla sidan före kompressorn, "
            "omräknad till den temperatur köldmediet kokar vid. Ett lågt värde "
            "betyder att det är ont om värme att hämta - för lite flöde i "
            "köldbäraren, en igensatt växlare eller ett borrhål som tagit slut.",
            "The low pressure side of the refrigerant circuit, the cold side "
            "before the compressor, converted to the temperature the refrigerant "
            "boils at. A low value means there is little heat to take - too little "
            "brine flow, a blocked exchanger, or a borehole that has given what it "
            "has.",
        ),
    ),
    (
        re.compile(r"pressure sensor|tryckgivare|^bp\d+\b", re.I),
        (
            "En tryckgivare i kylkretsen. Pumpen räknar om trycket till den "
            "temperatur köldmediet kokar eller kondenserar vid, vilket säger mer om "
            "hur kretsen arbetar än trycket i sig.",
            "A pressure sensor in the refrigerant circuit. The pump converts the "
            "pressure to the temperature the refrigerant boils or condenses at, "
            "which says more about how the circuit is working than the pressure "
            "itself.",
        ),
    ),
    (
        re.compile(r"unprocessed|obehandlad|raw value", re.I),
        (
            "Givarens värde innan pumpen jämnat ut det. Det obehandlade värdet "
            "hoppar mer och används vid felsökning; det utjämnade är det "
            "styrningen arbetar med.",
            "The sensor's value before the pump has smoothed it. The unprocessed "
            "figure jumps about more and is used in fault finding; the smoothed one "
            "is what the control works from.",
        ),
    ),
    (
        re.compile(r"blockfreq|blocked frequency|blockerad frekvens", re.I),
        (
            "Ett frekvensområde kompressorn hoppar över. Vissa varvtal får rör "
            "eller hus att vibrera eller låta; då spärras just det området och "
            "kompressorn arbetar över eller under det i stället.",
            "A band of frequencies the compressor skips. Some speeds set pipes or "
            "the building humming; that band is then blocked and the compressor "
            "works above or below it instead.",
        ),
    ),
    (
        re.compile(r"prot\.? status|protection status|skyddsstatus", re.I),
        (
            "Vilket skydd som håller tillbaka kompressorn just nu - för högt "
            "tryck, för hög ström, för hög temperatur. Noll betyder att inget "
            "skydd ingriper.",
            "Which protection is holding the compressor back right now - pressure "
            "too high, current too high, temperature too high. Zero means no "
            "protection is stepping in.",
        ),
    ),
    (
        re.compile(r"temperature, inverter|inverter temp|kylfläns", re.I),
        (
            "Temperaturen i invertern, elektroniken som styr kompressorns varvtal. "
            "Den stiger med belastningen och sänker kompressorns fart om den blir "
            "för hög.",
            "The temperature inside the inverter, the electronics that set the "
            "compressor's speed. It rises with the load, and the inverter slows the "
            "compressor down if it climbs too far.",
        ),
    ),
    (
        re.compile(r"current sensor|strömkännare", re.I),
        (
            "Strömkännarna mäter strömmen i husets huvudsäkringar. Pumpen "
            "begränsar sig själv, först elpatronen och sedan kompressorn, innan "
            "säkringen löser ut.",
            "The current sensors measure the current through the house's main "
            "fuses. The pump limits itself, first the immersion heater and then the "
            "compressor, before a fuse would blow.",
        ),
    ),
    (
        re.compile(r"collector in|collector out|köldbärare (in|ut)|bt26|bt27", re.I),
        (
            "Köldbärarens temperatur in i och ut ur växlaren. Skillnaden mellan "
            "dem, vanligen ett par grader, visar hur mycket värme som hämtas ur "
            "marken eller luften. En växande skillnad eller en sjunkande "
            "ingångstemperatur säger att flödet minskat eller att källan tröttnat.",
            "The brine's temperature into and out of the exchanger. The difference "
            "between them, usually a couple of degrees, shows how much heat is "
            "being taken from the ground or the air. A widening difference, or a "
            "falling inlet temperature, says the flow has dropped or the source is "
            "tiring.",
        ),
    ),
    # ------------------------------------------------ relays, inputs, service
    (
        re.compile(r"(relay status|status, relay)|reläutgång", re.I),
        (
            "Om reläutgången är sluten. Reläerna styr yttre saker: pumpar, "
            "ventiler, en panna eller en larmindikering.",
            "Whether the relay output is closed. The relays run outside things: "
            "pumps, valves, a boiler or an alarm indication.",
        ),
    ),
    (
        re.compile(r"forced control|tvångsstyrning", re.I),
        (
            "Tvångsstyrning: en utgång ställs för hand i stället för av "
            "styrningen, för att prova en pump eller en ventil vid service. Låt den "
            "inte stå kvar - pumpen styr inte det som tvångsstyrs.",
            "Forced control: an output is set by hand instead of by the control, to "
            "test a pump or a valve during service. Do not leave it that way - the "
            "pump does not steer what is forced.",
        ),
    ),
    (
        re.compile(r"^aux\b|aux ?\d|ax\d+ ?(input|output)|extra ?in(gång|put)", re.I),
        (
            "En AUX-ingång eller AUX-utgång: en fri anslutning som ges en uppgift "
            "i pumpens meny, till exempel en extern kontakt som spärrar värmen "
            "eller ett relä som startar något när larm går.",
            "An AUX input or output: a free connection given a job in the pump's "
            "menu, such as an external contact that blocks the heating, or a relay "
            "that starts something when an alarm is raised.",
        ),
    ),
    (
        re.compile(r"^version|software version|^status \(|com percentage|^be5|aa23", re.I),
        (
            "Ett servicevärde från pumpens egen elektronik: kortets "
            "programversion, dess tillstånd eller hur väl det kommunicerar med "
            "resten. Värdet används vid felsökning och behöver inte tolkas i "
            "vardagen.",
            "A service value from the pump's own electronics: a board's software "
            "version, its state, or how well it is talking to the rest. It is used "
            "in fault finding and does not need reading day to day.",
        ),
    ),
    (
        re.compile(r"filtering time|filtreringstid|averaging time", re.I),
        (
            "Hur länge givarens värde medelvärdesbildas innan funktionen reagerar "
            "på det. En längre tid gör att en kort svängning inte startar eller "
            "stoppar något i onödan.",
            "How long the sensor's value is averaged before the function acts on "
            "it. A longer time keeps a brief swing from starting or stopping "
            "something needlessly.",
        ),
    ),
    (
        re.compile(r"start temperature|starttemperatur", re.I),
        (
            "Den temperatur som får funktionen att starta. Under den gör "
            "funktionen ingenting.",
            "The temperature that sets the function going. Below it the function "
            "does nothing.",
        ),
    ),
    (
        re.compile(r"temperature to transfer to borehole|återladdning|recharge", re.I),
        (
            "Återladdning av borrhålet: överskottsvärme från kyla eller sol förs "
            "ner i berget i stället för att vädras bort. Det håller borrhålet "
            "varmare till nästa vinter.",
            "Recharging the borehole: surplus heat from cooling or from the sun is "
            "sent down into the rock instead of being thrown away. It keeps the "
            "borehole warmer for the next winter.",
        ),
    ),
    # The S-series and the F-series say the same things in different words.
    # These carry the explanations above over to the other spelling.
    (
        re.compile(r"flm ?\d* ?speed (\d|normal)|^fan mode \d|fan speed (\d|normal)", re.I),
        (
            "Luftflödet vid en av de valbara fläkthastigheterna, i procent av full "
            "fart. Normalhastigheten är den huset går på till vardags; de numrerade "
            "används av schemat och av tillfälliga lägen.",
            "The airflow at one of the selectable fan speeds, as a percentage of "
            "full speed. The normal speed is the one the house runs on day to day; "
            "the numbered ones are what the schedule and temporary modes use.",
        ),
    ),
    (
        re.compile(r"fan return time|flm ?\d* ?defrost|flm ?\d* ?over ?temp"
                   r"|flm ?\d* ?set point|flm ?\d* ?pump|flm ?\d* ?accessory|flm ?\d* ?fan"
                   r"|blocking \(ers|external ers .*(fire ?place|guard)", re.I),
        (
            "En inställning för frånluftsmodulen eller återvinningsmodulen: hur "
            "ofta växlaren avfrostas, hur länge en vald fläkthastighet gäller, hur "
            "modulens pump går, eller vad som får blockera den. Modulen tar värme "
            "ur ventilationsluften innan den lämnar huset.",
            "A setting for the exhaust air or recovery module: how often its "
            "exchanger is defrosted, how long a chosen fan speed lasts, how its "
            "pump runs, or what may block it. The module takes heat out of the "
            "ventilation air before it leaves the house.",
        ),
    ),
    (
        re.compile(r"rmu system|roomsensor \d|humidity: rmu|shunt amplification"
                   r"|calculated cooling supply", re.I),
        (
            "Hör till en rumsenhet eller en värmekrets: rumsenheten RMU visar och "
            "styr temperaturen i det rum den sitter i, och kretsens egna "
            "inställningar avgör hur varmt eller svalt vatten den får.",
            "Belongs to a room unit or a heating circuit: an RMU room unit shows "
            "and sets the temperature in the room it hangs in, and the circuit's "
            "own settings decide how hot or cool the water it gets is.",
        ),
    ),
    # ------------------------------------------- cooling, price, accessories
    (
        re.compile(r"sg ?ready", re.I),
        (
            "SG Ready: två ingångar från elnätet eller en energistyrning som säger "
            "om elen är dyr eller billig just nu. Pumpen svarar med att hålla "
            "tillbaka eller lägga på lite extra värme och varmvatten, så att mer av "
            "förbrukningen hamnar på de billiga timmarna.",
            "SG Ready: two inputs from the grid or an energy manager saying whether "
            "electricity is dear or cheap right now. The pump answers by holding "
            "back, or by laying on a little extra heat and hot water, so that more "
            "of what it uses falls in the cheap hours.",
        ),
    ),
    (
        re.compile(r"smart price adaption|prisstyrning|price area|spot ?pris", re.I),
        (
            "Prisstyrning: pumpen hämtar dygnets elpriser och flyttar varmvatten "
            "och en del av värmen till de billiga timmarna. Huset märker det inte, "
            "eftersom det är trögt nog att bära några timmar på sin egen värme.",
            "Price adaption: the pump takes the day's electricity prices and moves "
            "hot water and part of the heating into the cheap hours. The house does "
            "not notice, being slow enough to carry a few hours on its own warmth.",
        ),
    ),
    (
        re.compile(r"supp\.? air curve|sam ?\d*[ ,]|supply air curve", re.I),
        (
            "Tilluftskurvan för tilluftsmodulen SAM: vilken temperatur luften som "
            "blåses in i huset ska ha vid en viss utetemperatur. Modulen värmer "
            "huset genom ventilationen i stället för genom radiatorer.",
            "The supply air curve for the SAM supply air module: what temperature "
            "the air blown into the house should have at a given outdoor "
            "temperature. The module heats the house through the ventilation rather "
            "than through radiators.",
        ),
    ),
    (
        re.compile(r"cooling [24]-pipe|passive cooling|active cooling|^acs\b|acs .*qn", re.I),
        (
            "Kyldriften: passiv kyla tar den svala köldbäraren direkt från "
            "borrhålet genom en växlare och kostar nästan bara pumpel, aktiv kyla "
            "vänder kylkretsen och kyler med kompressorn. Tvårörssystem delar rör "
            "med värmen, fyrörssystem har egna. Start-DM säger hur stort "
            "kylbehovet ska vara innan kylan startar.",
            "The cooling: passive cooling takes the cool brine straight from the "
            "borehole through an exchanger and costs little more than pump "
            "electricity, active cooling turns the refrigerant circuit round and "
            "cools with the compressor. A two pipe system shares its pipes with the "
            "heating, a four pipe system has its own. The start DM says how large "
            "the demand for cooling must be before cooling starts.",
        ),
    ),
    (
        re.compile(r"cooling delta|delta temp", re.I),
        (
            "Hur stor skillnad kylan ska hålla mellan fram- och returledning vid en "
            "given utetemperatur. En större skillnad ger mindre flöde och svalare "
            "vatten.",
            "How large a difference the cooling holds between supply and return at "
            "a given outdoor temperature. A larger difference means less flow and "
            "cooler water.",
        ),
    ),
    (
        re.compile(r"(heating|cooling) connected|cooling activated|kyla ansluten", re.I),
        (
            "Om kretsen är inkopplad för värme respektive kyla. En krets som bara "
            "är inkopplad för värme får aldrig svalt vatten, hur varmt det än blir.",
            "Whether the circuit is connected for heating and for cooling. One that "
            "is connected for heating only never gets cool water, however warm it "
            "gets.",
        ),
    ),
    (
        re.compile(r"hwc |hot water circulation|vvc|varmvattencirk", re.I),
        (
            "Varmvattencirkulation (VVC): en pump håller varmvattnet i rörelse i "
            "rören så att det kommer varmt direkt i kranen. Det kostar värme dygnet "
            "runt, så den brukar köras i perioder - därav start- och stopptiderna.",
            "Hot water circulation: a pump keeps the hot water moving in the pipes "
            "so it arrives hot at the tap at once. It costs heat around the clock, "
            "so it is usually run in periods - hence the start and stop times.",
        ),
    ),
    (
        re.compile(r"energy meter|^pulse|pulse .*meter|be6", re.I),
        (
            "En extern energimätare som pumpen läser, antingen över kommunikation "
            "eller som pulser från en elmätare. Den används för att mäta vad "
            "anläggningen drar utan en egen mätare i elcentralen.",
            "An external energy meter the pump reads, either over communication or "
            "as pulses from an electricity meter. It measures what the installation "
            "draws without a meter of its own in the fuse box.",
        ),
    ),
    (
        re.compile(r"(temperature|pressure|flow) \(bm\d|bm\d|emk ?\d|flow sensor", re.I),
        (
            "Mätvärde från en flödesmätare i värmebärarkretsen (till exempel EMK). "
            "Med flödet och temperaturskillnaden känd kan pumpen räkna ut hur många "
            "kilowattimmar värme den verkligen levererat.",
            "A reading from a flow meter in the heating circuit (an EMK, for "
            "instance). Knowing the flow and the temperature difference, the pump "
            "can work out how many kilowatt hours of heat it has really delivered.",
        ),
    ),
    # ------------------------------------------------ compressor and inverter
    (
        re.compile(r"compressor, (number of starts|time to start|oper\.? time)"
                   r"|compressor size|compressor sensor|heat pump type|functionality, heat pump"
                   r"|max compressor speed|min compressor speed", re.I),
        (
            "Uppgifter om kompressorn: dess storlek och typ, hur många gånger den "
            "startat, hur länge den gått och hur länge det är kvar till nästa "
            "tillåtna start. Kompressorn mår bäst av få och långa gångtider; täta "
            "starter sliter.",
            "Facts about the compressor: its size and type, how many times it has "
            "started, how long it has run, and how long is left until it may start "
            "again. A compressor is happiest with few, long runs; frequent starts "
            "wear it.",
        ),
    ),
    (
        re.compile(r"inverter", re.I),
        (
            "Invertern styr kompressorns varvtal så att pumpen kan ge precis den "
            "effekt huset behöver i stället för att starta och stoppa. Statusen och "
            "felkoderna här är dess egna, och läses vid felsökning.",
            "The inverter sets the compressor's speed so the pump can give just the "
            "output the house needs instead of starting and stopping. The status "
            "and fault codes here are its own, and are read in fault finding.",
        ),
    ),
    (
        re.compile(r"(speed|operating mode).*circulation pump|circulation pump.*(speed|mode)"
                   r"|standby mode|waiting mode", re.I),
        (
            "Cirkulationspumpens fart och driftläge i ett visst arbetssätt - värme, "
            "varmvatten, kyla eller väntan. En pump som går fortare flyttar mer "
            "värme men drar mer el och kan höras i rören; i väntläge går den långsamt "
            "eller står still.",
            "The circulation pump's speed and mode in one kind of operation - "
            "heating, hot water, cooling or waiting. A faster pump moves more heat "
            "but draws more electricity and can be heard in the pipes; in waiting "
            "mode it runs slowly or stands still.",
        ),
    ),
    (
        re.compile(r"defrost requested|last defrost|start fan de-?icing|de-?icing", re.I),
        (
            "Avfrostningen av luftväxlaren: om en avfrostning begärts, när den "
            "senaste skedde och hur fläkten hjälper till att smälta isen. "
            "Avfrostningar hör till i fuktig kyla runt noll grader.",
            "The defrosting of the air exchanger: whether one has been asked for, "
            "when the last one happened, and how the fan helps melt the ice. "
            "Defrosts belong to damp cold around freezing.",
        ),
    ),
    (
        re.compile(r"diff\.? pr\.? airflow|bp15|airflow", re.I),
        (
            "Tryckskillnaden över luftvägen, som modulen räknar om till luftflöde. "
            "Ett fallande flöde vid samma fläktvarv betyder oftast igensatt filter.",
            "The pressure difference across the air path, which the module converts "
            "to airflow. A falling flow at the same fan speed usually means a "
            "blocked filter.",
        ),
    ),
    (
        re.compile(r"available compressors|docked compressors|used compressors|installed \("
                   r"|serial index|has one phase|protection mode|^blocked$|^activate$",
                   re.I),
        (
            "Uppgift om vad som finns installerat och får användas i anläggningen - "
            "vilka värmepumpar och kompressorer som är inkopplade, och om något är "
            "spärrat. Den sätts vid installationen och ändras sällan.",
            "A statement of what is installed and may be used in the installation - "
            "which heat pumps and compressors are connected, and whether anything "
            "is blocked. It is set at installation and rarely changed.",
        ),
    ),
    (
        re.compile(r"boiler temperature|bt52|panntemperatur", re.I),
        (
            "Temperaturen i en ansluten panna (BT52). Pumpen använder den för att "
            "veta om pannans värme är varm nog att användas.",
            "The temperature in a connected boiler (BT52). The pump uses it to know "
            "whether the boiler's heat is warm enough to use.",
        ),
    ),
    (
        re.compile(r"outd(oor)? temp.*(ers|az30|bt23)|bt23", re.I),
        (
            "Utetemperaturen mätt av en egen givare vid ventilationsmodulen (BT23), "
            "vid sidan av husets ordinarie utegivare.",
            "The outdoor temperature measured by the ventilation module's own "
            "sensor (BT23), beside the house's ordinary outdoor sensor.",
        ),
    ),
    (
        re.compile(r"point offset|punktförskjutning", re.I),
        (
            "Punktförskjutning: höjer eller sänker värmen bara runt en viss "
            "utetemperatur. Den används när huset blir för svalt i just ett "
            "temperaturområde, till exempel runt noll grader, utan att resten av "
            "kurvan ska ändras.",
            "Point offset: raises or lowers the heating only around one particular "
            "outdoor temperature. It is used when the house goes cool in just one "
            "band, around freezing say, without changing the rest of the curve.",
        ),
    ),
    (
        re.compile(r"dm start (heating|hot water|cooling)|start dm", re.I),
        (
            "Hur stort värmeunderskottet, mätt i gradminuter, ska vara innan just "
            "den här funktionen startar. Ett djupare värde gör att pumpen väntar "
            "längre och går längre stunder när den väl startar.",
            "How large the heat deficit, counted in degree minutes, has to be "
            "before this particular function starts. A deeper value makes the pump "
            "wait longer and then run for longer once it does start.",
        ),
    ),
    (
        re.compile(r"^fuse|huvudsäkring|fuse size", re.I),
        (
            "Husets huvudsäkring i ampere. Pumpen använder den tillsammans med "
            "strömkännarna för att hålla sig under gränsen: den drar ner elpatron "
            "och kompressor i stället för att säkringen ska lösa ut.",
            "The house's main fuse in amperes. Together with the current sensors "
            "the pump uses it to stay under the limit: it turns the immersion "
            "heater and the compressor down rather than let a fuse blow.",
        ),
    ),
    (
        re.compile(r"more hot water.*minutes|^more hot water", re.I),
        (
            "Hur länge en engångshöjning av varmvattnet ska hålla i sig innan "
            "pumpen går tillbaka till sitt vanliga läge.",
            "How long a one-time increase of the hot water lasts before the pump "
            "goes back to its ordinary mode.",
        ),
    ),
    (
        re.compile(r"set point value \(rh\)|\brh\b|relativ fuktighet", re.I),
        (
            "Den relativa luftfuktighet styrningen siktar på. Den används för att "
            "kyla utan kondens och, i hus med avfuktning, för att hålla luften "
            "lagom torr.",
            "The relative humidity the control aims for. It is used to cool without "
            "condensation and, in a house with dehumidification, to keep the air "
            "reasonably dry.",
        ),
    ),
    (
        re.compile(r"^language$|^time format|^date format|^start time$|^operating time$", re.I),
        (
            "En inställning för pumpens egen display: språk, tidsformat eller "
            "klockslag. Den påverkar bara vad som visas i pumpens meny, inte hur "
            "den arbetar.",
            "A setting for the pump's own display: language, time format or a time "
            "of day. It changes only what the pump's menu shows, not how it works.",
        ),
    ),
    (
        re.compile(r"\+ ?adjust", re.I),
        (
            "+Adjust låter husets egen golvvärmestyrning tala om för pumpen hur "
            "mycket värme rummen verkligen begär. Pumpen sänker då framledningen "
            "så långt rummen tillåter, vilket ger jämnare värme och lägre "
            "förbrukning än en kurva som gissar.",
            "+Adjust lets the house's own underfloor heating control tell the pump "
            "how much heat the rooms are really asking for. The pump then lowers "
            "the supply temperature as far as the rooms allow, which gives evener "
            "heat and lower consumption than a curve that guesses.",
        ),
    ),
    (
        re.compile(r"cut off frequency|cut-?off freq", re.I),
        (
            "Ett frekvensområde kompressorn hoppar över, mellan start och stopp. "
            "Det används när ett visst varvtal får rör eller hus att låta.",
            "A band of frequencies the compressor skips, between its start and "
            "stop. It is used when one particular speed sets pipes or the building "
            "humming.",
        ),
    ),
    (
        re.compile(r"^pump speed|pump speed \(|^flm \d+$|flm \d+ cooling", re.I),
        (
            "Farten på en cirkulationspump i anläggningen, i procent. Högre fart "
            "flyttar mer värme men drar mer el och hörs mer i rören.",
            "The speed of a circulation pump in the installation, as a percentage. "
            "A higher speed moves more heat but draws more electricity and is heard "
            "more in the pipes.",
        ),
    ),
    (
        re.compile(r"oil temperature|bt29", re.I),
        (
            "Temperaturen i kompressorns olja. Den ska vara varm nog att oljan "
            "inte binder köldmedium innan kompressorn startar; en kall kompressor "
            "värms därför en stund först.",
            "The temperature of the compressor's oil. It has to be warm enough that "
            "the oil does not hold refrigerant when the compressor starts; a cold "
            "compressor is therefore warmed for a while first.",
        ),
    ),
    (
        re.compile(r"outgoing hot water|bt70|hot water comfort (return|heater)|bt8[23]", re.I),
        (
            "Temperaturen på varmvattnet på väg ut till kranarna, efter "
            "blandningsventilen. Den ligger lägre än tankens egen temperatur, "
            "eftersom ventilen blandar i kallvatten så att ingen ska skålla sig.",
            "The temperature of the hot water on its way out to the taps, after the "
            "mixing valve. It is lower than the tank's own temperature, because the "
            "valve blends in cold water so nobody is scalded.",
        ),
    ),
    (
        re.compile(r"heating dump|bt75|bt57|eq\d", re.I),
        (
            "Hör till kylsystemet: överskottsvärmen från kylan förs bort, till "
            "borrhålet eller till en annan krets, i stället för tillbaka in i "
            "huset.",
            "Belongs to the cooling system: the surplus heat from cooling is led "
            "away, to the borehole or to another circuit, instead of back into the "
            "house.",
        ),
    ),
    (
        re.compile(r"temperature limiter|fd1|electrical anode|fr1", re.I),
        (
            "Ett skydd i pumpen: temperaturbegränsaren bryter strömmen till "
            "elpatronen om vattnet blir för varmt, och anoden skyddar tanken mot "
            "korrosion. Båda ska vara i ordning; larmar de behövs service.",
            "A protection in the pump: the temperature limiter cuts the power to "
            "the immersion heater if the water gets too hot, and the anode protects "
            "the tank against corrosion. Both should be in order; if they raise an "
            "alarm, the pump needs a service call.",
        ),
    ),
    (
        re.compile(r"(pressure|temperature) \d* ?\(sft\)|sft", re.I),
        (
            "Ett mätvärde från en givare i kretsen, läst av ett tillbehör. Det "
            "används vid felsökning och för tillbehörets egen reglering.",
            "A reading from a sensor in the circuit, taken by an accessory. It is "
            "used in fault finding and for the accessory's own control.",
        ),
    ),
    (
        re.compile(r"pool \d* ?valve|gp\d+ pool|period pool", re.I),
        (
            "Växelventilen som leder värmen till poolen i stället för till huset, "
            "och hur länge poolen får ha den. Pumpen kan bara värma en sak i taget.",
            "The valve that sends the heat to the pool instead of to the house, and "
            "how long the pool may have it. The pump can only heat one thing at a "
            "time.",
        ),
    ),
    (
        re.compile(r"ventilation mode|extra cooling|compressor restrictions"
                   r"|op\.?time electrical heater|prio, hot water|is the compressor accessible",
                   re.I),
        (
            "Ett driftläge eller en begränsning i anläggningen: vilket "
            "ventilationsläge som gäller, om extra kyla får tas ut, vad som "
            "begränsar kompressorn eller hur länge elpatronen fått arbeta med "
            "varmvattnet.",
            "A mode or a limit in the installation: which ventilation mode is in "
            "force, whether extra cooling may be taken, what is holding the "
            "compressor back, or how long the immersion heater has worked on the "
            "hot water.",
        ),
    ),
    # ------------------------------------------------- the accessory flags
    (
        re.compile(r"preset flow|inställt flöde|flow dt|flöde.*\bdt\b", re.I),
        (
            "Vad pumpen räknar med för flöde i värmebärarkretsen, och vilken "
            "temperaturskillnad den arbetar med. Den använder dem för att räkna "
            "ut hur många kilowattimmar värme den lämnat - utan ett flöde, mätt "
            "eller angivet, står värmemätarna stilla och någon värmefaktor går "
            "inte att räkna fram.",
            "What flow the pump assumes in the heating circuit, and what "
            "temperature difference it is working with. It uses them to work out "
            "how many kilowatt hours of heat it has delivered - without a flow, "
            "measured or given, the heat meters stand still and no coefficient of "
            "performance can be worked out.",
        ),
    ),
    (
        re.compile(r"modbus ?40", re.I),
        (
            "Inställningar för MODBUS 40, tillbehöret som låter pumpen tala med "
            "omvärlden - här via gatewayen som den här integrationen pratar med. "
            "Att registren svarar är i sig beskedet att MODBUS 40 är valt i "
            "pumpens meny 5.2; någon egen ja-eller-nej-flagga för tillbehöret "
            "finns inte. LOG.SET är listan över värden pumpen skickar av sig "
            "själv, utan att bli tillfrågad.",
            "Settings for MODBUS 40, the accessory that lets the pump talk to the "
            "outside world - here through the gateway this integration speaks to. "
            "That these registers answer at all is the word that MODBUS 40 is "
            "chosen in the pump's menu 5.2; there is no yes-or-no flag of its own "
            "for it. LOG.SET is the list of values the pump sends unasked.",
        ),
    ),
    (
        re.compile(r"^opt\b|opt (boiler|rel|hyster|state|version)|aux block opt", re.I),
        (
            "OPT, styrningen av en extern panna - olja, gas eller pellets. Pumpen "
            "startar pannan när dess egen värme inte räcker och blandar in "
            "pannans värme i systemet, i stället för att gå på elpatronen.",
            "OPT, the control of an external boiler - oil, gas or pellets. The "
            "pump starts the boiler when its own heat is not enough and blends "
            "the boiler's heat into the system, rather than falling back on the "
            "immersion heater.",
        ),
    ),
    (
        re.compile(r"\bbt28\b", re.I),
        (
            "Utetemperaturen mätt av värmepumpmodulens egen givare (BT28), vid "
            "sidan av husets ordinarie utegivare. Den sitter där maskinen står, "
            "så den kan skilja sig från husets - och det är den maskinen själv "
            "räknar med.",
            "The outdoor temperature measured by the heat pump module's own "
            "sensor (BT28), beside the house's ordinary outdoor sensor. It sits "
            "where the machine stands, so it can differ from the house's - and it "
            "is the one the machine itself works from.",
        ),
    ),
    (
        re.compile(r"outdoor unit|utedel|f2040|f2120|f2050|\bams\b", re.I),
        (
            "Hör till utedelen - luft/vatten-värmepumpen som står ute och som "
            "en SMO eller VVM styr. NIBE lägger hela den under beteckningen "
            "EB101: kompressorns frekvens och tillstånd, dess egen utegivare, "
            "avfrostningen, fläkten och den effekt den räknar ut att den "
            "lämnar. Det är där värmen görs, och det är därför de läses av "
            "sig själva på de modellerna.",
            "Belongs to the outdoor unit - the air/water heat pump standing "
            "outside, which an SMO or a VVM controls. NIBE puts the whole of it "
            "under the designation EB101: the compressor's frequency and state, "
            "its own outdoor sensor, the defrosting, the fan, and the output it "
            "works out that it is giving. That is where the heat is made, which "
            "is why these are read by default on those models.",
        ),
    ),
    (
        re.compile(r"sms ?40", re.I),
        (
            "Tillbehöret SMS 40, som låter pumpen styras med textmeddelanden från "
            "en telefon. Det användes innan pumparna fick nätverk.",
            "The SMS 40 accessory, which lets the pump be controlled by text "
            "messages from a phone. It was how one reached a pump before they had "
            "networks.",
        ),
    ),
    (
        re.compile(r"hpac|brine shunt|köldbärarshunt", re.I),
        (
            "En kylmodul mellan köldbäraren och värmesystemet: shunten blandar den "
            "svala vätskan från borrhålet i kretsen så att huset kan kylas utan "
            "att kompressorn behöver gå.",
            "A cooling module between the brine and the heating system: the mixing "
            "valve blends the cool liquid from the borehole into the circuit so "
            "the house can be cooled without the compressor running.",
        ),
    ),
    (
        re.compile(r"\baccessory\b", re.I),
        (
            "Säger om det här tillbehöret är registrerat i pumpens egen meny. Ett "
            "nej är lika mycket ett svar som ett ja: pumpen visar bara "
            "inställningar för de tillbehör den vet om, och letar man efter en "
            "funktion som saknas är det ofta här den börjar.",
            "Says whether this accessory is registered in the pump's own menu. A "
            "no is as much of an answer as a yes: the pump only shows settings for "
            "the accessories it knows about, and a function somebody is looking "
            "for and cannot find often begins here.",
        ),
    ),
]

#: Explanations for the entities this integration adds on its own, which have
#: no NIBE register title to match against.
OWN_EXPLANATIONS: dict[str, tuple[str, str]] = {
    "heating_mode": (
        "Ställer husets värme i ett av fyra lägen genom att flytta "
        "kurvförskjutningen: blockerad, ekonomi, normal och boost. Värmen stängs "
        "aldrig av - huset går på sin egen tröghet och pumpen håller sin minsta "
        "framledning. Läget finns för en energistyrning som vill flytta värmen "
        "till timmar då elen är billig; normalläget är det som pumpen stod på "
        "när läget först användes.",
        "Puts the heating into one of four modes by moving the curve offset: "
        "blocked, eco, normal and boost. Heating is never switched off - the house "
        "coasts on its own thermal mass and the pump keeps its minimum supply "
        "temperature. The mode exists for an energy manager that wants to move "
        "heating to the hours when electricity is cheap; normal is the offset the "
        "pump stood at when the mode was first used.",
    ),
    "heat_not_counted": (
        "Pumpen räknar inte värmen den levererar. Registren för värmemängd "
        "finns och svarar, men siffran rör sig aldrig: NIBE:s energimätning "
        "kräver en flödesmätare (EMK 300 eller EMK 500), och utan den finns "
        "ingenting att dela elen med. Därför saknas värmefaktorn här. Elen "
        "räknas ändå, och duger till energipanelen.",
        "The pump does not measure the heat it delivers. The heat meter "
        "registers are there and answer, but the figure never moves: NIBE's "
        "energy metering needs a flow meter (an EMK 300 or EMK 500), and "
        "without one there is nothing to divide the electricity by. That is why "
        "there is no coefficient of performance here. The electricity is counted "
        "all the same, and is good for the energy dashboard.",
    ),
    "counted_electricity": (
        "Elen värmepumpen har använt, räknad i stället för mätt. F-serien har "
        "ingen egen elmätare, men den rapporterar vad kompressorn och "
        "elpatronen drar just nu, och hur fort de två cirkulationspumparna "
        "går. Effekten summeras över tiden precis som en mätare gör, med "
        "NIBE:s egna wattsiffror för pumparna och ett påslag för styrsystemet. "
        "Kompressorns siffra kommer från invertern och är god; pumparna är en "
        "modell och elektroniken en uppskattning, så helheten ligger några "
        "procent fel. Attributen visar varje del för sig. Vill man ha det exakt "
        "sätter man en elmätare på pumpens krets.",
        "The electricity the pump has used, counted rather than measured. The "
        "F-series has no meter of its own, but it reports what the compressor "
        "and the immersion heater draw right now, and how fast its two "
        "circulation pumps are running. The power is added up over time the "
        "way a meter does, using NIBE's own watt figures for the pumps and an "
        "allowance for the control system. The compressor's figure comes from "
        "the inverter and is good; the pumps are a model and the electronics an "
        "estimate, so the whole is a few percent out. The attributes show each "
        "part on its own. For an exact figure, put a meter on the pump's "
        "circuit.",
    ),
    "hot_water_boost": (
        "Slår på en engångshöjning av varmvattnet, samma sak som tillfällig lyx "
        "i pumpens meny. Pumpen laddar beredaren extra varm en gång och går "
        "sedan tillbaka av sig själv.",
        "Switches on a one-time increase of the hot water, the same thing as "
        "temporary lux in the pump's menu. The pump charges the cylinder extra hot "
        "once and then returns to normal on its own.",
    ),
    "cop_day": (
        "Värmefaktorn det senaste dygnet: hur många kilowattimmar värme pumpen "
        "gett per kilowattimme el. Tre betyder att två tredjedelar av värmen kom "
        "gratis ur berget eller luften. Ett enskilt dygn säger mindre än året, "
        "eftersom varmvatten och avfrostning slår igenom hårdare på kort tid.",
        "The coefficient of performance over the last day: how many kilowatt hours "
        "of heat the pump gave per kilowatt hour of electricity. Three means two "
        "thirds of the heat came free from the ground or the air. A single day says "
        "less than a year, since hot water and defrosting weigh heavier over a "
        "short span.",
    ),
    "cop_lifetime": (
        "Värmefaktorn över pumpens hela liv, räknad ur dess egna räknare för "
        "producerad värme och förbrukad el. Den behöver ingen väntetid - den "
        "finns första dagen - men den rör sig långsamt och säger mer om "
        "anläggningen i stort än om den här vintern. Vill man jämföra år mot "
        "år är det årsvärdet som gäller.",
        "The coefficient of performance over the pump's whole life, from its "
        "own counters for heat delivered and electricity used. It needs no "
        "waiting - it is there the first day - but it moves slowly and says "
        "more about the installation as a whole than about this winter. To "
        "compare one year with another, the yearly figure is the one.",
    ),
    "cop_lifetime_gateway": (
        "Värmefaktorn över hela den tid den här integrationen har räknat. "
        "F-serien har ingen elmätare, så elen räknas fram ur effekten pumpen "
        "rapporterar och startar den dag integrationen installerades; pumpens "
        "egna värmemätare mäts från samma stund, så de två talen täcker samma "
        "sträcka. Den blir mer värd ju längre den har fått räkna.",
        "The coefficient of performance over everything this integration has "
        "counted. The F-series has no electricity meter, so the electricity is "
        "worked out from the power the pump reports and starts the day the "
        "integration was installed; the pump's own heat meters are measured "
        "from the same moment, so the two figures cover the same stretch. It is "
        "worth more the longer it has been counting.",
    ),
    "cop_year": (
        "Värmefaktorn över ett helt år, vilket är det tal som går att jämföra "
        "med andra anläggningar: hela året räknat, med både kalla dygn och "
        "varmvatten. Innan pumpen har ett års mätvärden visas i stället "
        "livstidsvärdet, räknat från pumpens egna räknare.",
        "The coefficient of performance over a whole year, which is the figure "
        "worth comparing with other installations: the entire year counted, cold "
        "days and hot water included. Until a year has been measured, the lifetime "
        "figure from the pump's own counters is shown instead.",
    ),
    "manufactured": (
        "När pumpen tillverkades, uttytt ur serienumret: siffrorna efter "
        "artikelnumret är år och dagnummer.",
        "When the pump was built, read out of the serial number: the digits after "
        "the article number are the year and the day of the year.",
    ),
}


def explain(title: str, language: str = "sv") -> str | None:
    """The written explanation for a register's title, if there is one."""
    for pattern, text in EXPLANATIONS:
        if pattern.search(title or ""):
            return _pick(text, language)
    return None


def explain_own(key: str, language: str = "sv") -> str | None:
    """The explanation for one of this integration's own entities."""
    text = OWN_EXPLANATIONS.get(key)
    return _pick(text, language) if text else None


def _pick(text: tuple[str, str], language: str) -> str:
    return text[0] if language.startswith("sv") else translate(text[1], language)
