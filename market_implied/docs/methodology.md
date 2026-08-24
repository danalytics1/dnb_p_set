# Market-implied rendementsverwachtingen — methodologische verantwoording

*Versie 1.0 — behorend bij de Python-package `market_implied`.*

---

## Inhoud

1. [Uitgangspunten](#1-uitgangspunten)
2. [De risicovrije rente](#2-de-risicovrije-rente)
3. [Bouwstenen per beleggingscategorie](#3-bouwstenen-per-beleggingscategorie)
4. [Valuta](#4-valuta)
5. [Meetkundig versus rekenkundig](#5-meetkundig-versus-rekenkundig)
6. [Wat wel en niet market implied is](#6-wat-wel-en-niet-market-implied-is)
7. [Databronnen](#7-databronnen)
8. [Beperkingen](#8-beperkingen)
9. [Literatuur](#9-literatuur)

---

## 1. Uitgangspunten

### 1.1 De vergelijking

Voor elke beleggingscategorie *i* en horizon *H* geldt per constructie:

```
E[R_i(H)]  =  r_f(H)  +  RP_i(H)
```

met `r_f(H)` de verwachte risicovrije rente over de horizon en `RP_i(H)` de
risicopremie. De risicopremie is zelf een som van **bouwstenen**:

```
RP_i(H)  =  Σ_k  b_{i,k}(H)
```

Het eindresultaat is de tabel met per beleggingscategorie een risicopremie op
5 en 15 jaar; het verwachte rendement volgt door optelling bij de risicovrije
rente.

### 1.2 Waarom bouwstenen

Een bouwstenenbenadering scheidt wat je *waarneemt* van wat je *aanneemt*. Bij
een puntschatting ("aandelen doen 6%") is die scheiding onzichtbaar. De
bouwstenenmethode is de standaard in de literatuur over verwachte rendementen
(Ilmanen, 2011) en in de praktijk van vrijwel alle publieke capital market
assumptions. Elk blok in deze package draagt daarom een label `markt`,
`afgeleid` of `aanname`, en de rapportage toont per categorie welk deel van de
premie niet uit marktprijzen komt (kolom *aandeel aanname*).

### 1.3 Optellen versus vermenigvuldigen

Bouwstenen worden **rekenkundig opgeteld** tot een meetkundig (samengesteld)
jaarrendement. Dat is exact in continue samenstelling en de kruistermen die
worden verwaarloosd zijn tweede orde; het is de conventie van Grinold & Kroner
(2002). Waar exacte vermenigvuldiging nodig is, is `blocks.compound()`
beschikbaar. Koerseffecten die zich over de hele horizon voordoen (waardering,
spreadconvergentie) worden wél exact geannualiseerd via
`(1 + ΔP)^(1/H) − 1`, omdat de fout daar anders wél materieel wordt.

### 1.4 Twee horizonnen

De pakketconfiguratie rekent standaard op **5 jaar** (middellang) en
**15 jaar** (lang). Het horizonverschil ontstaat op drie plaatsen:

| Kanaal | Werking |
|---|---|
| Rentecurve | `r_f(5)` en `r_f(15)` verschillen zodra de curve niet vlak is. |
| Convergentiesnelheid | Een waarderings- of spreadgat sluit voor een groter deel over 15 jaar dan over 5 jaar, maar wordt over méér jaren uitgesmeerd. Het jaarlijkse effect is doorgaans kleiner op 15 jaar. |
| Inflatieverwachting | De breakeven-curve is niet vlak. |

Blokken die géén horizonafhankelijkheid kennen (termijnpremie bij een gegeven
duration, spread carry, verwacht kredietverlies) zijn per constructie gelijk op
beide horizonnen. Dat is geen tekortkoming maar een uitspraak: zonder
marktinformatie over de toekomstige premie is de beste schatting de huidige.

---

## 2. De risicovrije rente

**Eis:** de risicovrije rente is een component bij álle beleggingscategorieën
en volgt voor allemaal dezelfde logica. In deze package is `riskfree.py` de
enige plaats waar `r_f(H)` wordt bepaald; elk model roept dezelfde functie aan.

### 2.1 De affiene ontbinding

Een nominale zero rate valt uiteen in een verwachte-gemiddelde-korte-rente
component en een termijnpremie:

```
z(H)  =  E[gemiddelde korte rente over H]  +  TP(H)
```

Dit is de standaardontbinding uit de affiene termijnstructuurliteratuur.
Adrian, Crump & Moench (2013) leveren de meest gebruikte schatting (het
"ACM-model", gepubliceerd door de Federal Reserve Bank of New York);
Kim & Wright (2005) leveren een driefactoralternatief. Beide worden *uit de
dwarsdoorsnede van obligatieprijzen* geschat en zijn in die zin marktinformatie,
geen mening.

### 2.2 Twee conventies

| Conventie | Formule | Interpretatie |
|---|---|---|
| `rolled_cash` (standaard) | `r_f(H) = z(H) − TP(H)` | Het rendement op het doorrollen van kortlopende deposito's. Alle risicopremies zijn dan meerrendement **boven kasgeld**. |
| `spot` | `r_f(H) = z(H)` | De horizon-matched zerocouponrente. Voor een belegger met vaste horizon *H* is dit het werkelijk risicoloze rendement, zonder herbeleggingsrisico (Campbell & Viceira, 2002). |

**De keuze verandert de verdeling tussen risicovrij en premie, niet het totaal.**
De package dwingt dat af: elke bouwsteen is gedefinieerd als meerrendement boven
*lokaal doorgerold kasgeld*, en bij de `spot`-conventie wordt één expliciet
correctieblok toegevoegd. De test
`test_expected_returns_do_not_depend_on_the_reporting_convention` verifieert dat
alle verwachte rendementen tot op machineprecisie identiek zijn.

Onder de `spot`-conventie krijgt liquiditeit een *negatieve* risicopremie ter
grootte van `−TP(H)`: kasgeld blijft achter bij een horizon-matched
staatsobligatie. Dat is de correcte uitkomst en illustreert waarom de conventie
expliciet gemaakt moet worden.

### 2.3 Waarom niet gewoon de verwachtingshypothese

Een termijnpremie van nul veronderstellen (de pure verwachtingshypothese) is
geen neutrale keuze maar een sterke, empirisch verworpen aanname. Fama & Bliss
(1987), Campbell & Shiller (1991) en Cochrane & Piazzesi (2005) laten
overtuigend zien dat termijnpremies bestaan, variëren in de tijd en
voorspelbaar zijn. Een gepubliceerde ACM-schatting gebruiken is dus *minder*
aanname dan nul invullen. Wie toch de verwachtingshypothese wil: laat het blok
`term_premia` uit de marktopname weg, dan vallen beide conventies samen.

### 2.4 De curve zelf

De zero curve wordt geïnterpoleerd **lineair in de log-disconteringsfactor**,
equivalent aan stuksgewijs constante instantane forwards. Dit is de
marktstandaard omdat het strikt positieve impliciete forwards garandeert en de
invoerpunten exact reproduceert (Hagan & West, 2006). Voorbij de laatste
looptijd wordt geëxtrapoleerd met een vlakke forward. Par swap rates kunnen
worden gebootstrapt; de test `test_par_bootstrap_reprices_the_par_bond`
verifieert dat de gebootstrapte curve de invoerinstrumenten op pari zet.

---

## 3. Bouwstenen per beleggingscategorie

### 3.1 Overzicht

| Categorie | Model | Bouwstenen |
|---|---|---|
| Liquiditeiten | `cash` | `r_f` (+ eventuele depositospread) |
| Staatsobligaties | `nominal_bond` | `r_f` + `TP(D)` + landenspread − verwacht verlies |
| Inflatiegekoppeld | `index_linked_bond` | `r_f` + `TP(D)` − inflatierisicopremie + liquiditeitspremie |
| IG / HY / EMD / hypotheken | `spread_product` | `r_f` + `TP(D)` + OAS + spreadwaardering − verwacht kredietverlies − afwaarderingsdrag |
| Aandelen, genoteerd vastgoed | `grinold_kroner` | `r_f` + dividend + inkoop + inflatie + reële groei + waardering − lokaal kasgeld |
| Niet-genoteerd vastgoed, infra | `yield_and_growth` | `r_f` + direct rendement − capex + inflatie + reële groei + yield shift + illiquiditeit − lokaal kasgeld |
| Grondstoffen | `commodities` | `r_f` + rolrendement + spotontwikkeling + herbalancering |
| Private equity | `levered_beta` | `r_f` + β × premie referentie + illiquiditeit − extra kosten |

### 3.2 Nominale staatsobligaties

Uit de affiene ontbinding volgt dat het doorrollen van een obligatieportefeuille
met constante looptijd *D* de korte rente plus de termijnpremie bij *D*
oplevert:

```
E[R(H)]  =  r_f(H) + TP(D) + landenspread − verwacht kredietverlies
```

Bij `D = H` reduceert dit tot `r_f(H) + TP(H) = z(H)`: precies wat een
buy-and-hold zerocouponbelegger verdient. Deze identiteit wordt getest
(`test_horizon_matched_bond_earns_exactly_the_spot_rate`) en is het anker van
de hele constructie.

**Bewust weggelaten: renteterugkeer naar een "normaal" niveau.** Zo'n blok
overschrijft de marktprijs met een mening en hoort niet in een market-implied
raamwerk. De curve is wat hij is.

### 3.3 Inflatiegekoppelde obligaties

De breakeven-inflatie is een vertekende schatter van de verwachte inflatie: hij
bevat een inflatierisicopremie en wordt gedrukt door de mindere liquiditeit van
de linkermarkt (Grishchenko & Huang, 2013; D'Amico, Kim & Wei, 2018; Pflueger &
Viceira, 2016). Omdat

```
z_nom(D) = z_reëel(D) + breakeven(D)   en   breakeven = E[π] + IRP − LP
```

is het nominale verwachte rendement van een linker gelijk aan dat van een
nominale obligatie met dezelfde duration, **minus** de inflatierisicopremie die
hij niet ontvangt, **plus** de liquiditeitspremie die hij wél ontvangt. Dat is
precies hoe het model het opbouwt.

### 3.4 Kredietwaarden (IG, high yield, EMD, hypotheken)

```
E[R(H)] = r_f(H) + TP(D) + OAS + spreadwaardering − p·LGD − afwaarderingsdrag
```

**Waarom het verwachte verlies niet uit de spread wordt afgeleid.** De spread
uit de marktprijs terugrekenen naar een defaultkans en die er weer aftrekken
levert per definitie een premie van nul op: de spread ís de som van verwacht
verlies en risicopremie. Empirisch is het verschil groot en persistent.
Giesecke, Longstaff, Schaefer & Strebulaev (2011) laten over 150 jaar zien dat
Amerikaanse bedrijfsobligatiespreads gemiddeld ongeveer *twee keer* de
gerealiseerde kredietverliezen bedroegen. Elton, Gruber, Agrawal & Mann (2001)
tonen dat verwachte wanbetaling slechts een klein deel van de spread verklaart.
Het verwachte verlies komt daarom uit actuariële ratingbureaustatistieken
(Moody's en S&P jaarlijkse default studies; Altman & Kuehne voor de
Amerikaanse high yield reeks), en wat overblijft wordt als premie
gerapporteerd. Asvanunt & Richardson (2017) schatten de resulterende
kredietrisicopremie op ongeveer 1 tot 1,5 procent per jaar; de standaard­
configuratie ligt in die orde van grootte.

**Afwaarderingsdrag.** Indices met een ratinggrens moeten fallen angels
verkopen op het moment dat ze het slechtst geprijsd zijn. Ng & Phelps (2011)
kwantificeren dit verlies voor investment grade indices; Ben Dor & Xu (2015)
documenteren het herstel dat de index daarna misloopt. Voor high yield speelt
het spiegelbeeld bij rising stars en bij gedwongen verkoop van CCC-papier.

**Spreadwaardering.** Kredietspreads keren duidelijk sneller terug naar hun
gemiddelde dan aandelenwaarderingen (Duffee, 1998; Collin-Dufresne, Goldstein &
Martin, 2001). De standaardhalfwaardetijd is drie jaar. Het koerseffect volgt
uit `−SD × ΔOAS` over de horizon, exact geannualiseerd. Zetten op `null` — of
de hele run draaien met `--no-valuation` — geeft de pure carry-variant.

**Nederlandse hypotheken** zijn als spreadproduct gemodelleerd zonder
spreadconvergentie: de spread is structureel gedreven door
kapitaalregelgeving, distributiekosten en de beperkte verhandelbaarheid en
kent geen duidelijk marktgemiddelde om naartoe te bewegen. Het verwachte
verlies is minimaal (hoge recovery door het onderpand plus in een deel van de
markt de NHG-garantie); wél is er een drag door vervroegde aflossing.

### 3.5 Aandelen

**Route 1 — Grinold & Kroner (2002):**

```
E[R] ≈ dividendrendement + netto inkoop + verwachte inflatie
       + reële winstgroei per aandeel + waarderingsverandering
```

De eerste drie termen komen uit marktprijzen: dividend- en inkooprendement uit
de indexfundamentals, verwachte inflatie uit de breakeven-curve minus de
inflatierisicopremie. Het totale payout yield (dividend plus netto inkoop) is de
economisch juiste maatstaf voor het kasrendement, niet het dividend alleen —
Straehl & Ibbotson (2017) laten zien dat de langetermijnrendementen van aandelen
zich alleen met totale uitkeringen goed laten reconstrueren.

De **reële winstgroei per aandeel** is een aanname en geen marktprijs. Bernstein
& Arnott (2003) tonen in *"Earnings growth: the two percent dilution"* dat groei
per aandeel structureel ongeveer twee procentpunt achterblijft bij de
economische groei, doordat nieuwe ondernemingen buiten de index om worden
opgericht en bestaande ondernemingen aandelen uitgeven. Wie de groei liever
uit fundamentals afleidt, kan `real_growth_source: "sustainable"` zetten: dan
wordt `g = ROE × (1 − uitkeringsratio)` gebruikt, de fundamentele groei-identiteit
van Damodaran (2024), gedefleerd met de verwachte inflatie.

De **waarderingsverandering** laat CAPE (of een andere opgegeven maatstaf)
convergeren naar een referentieniveau met een halfwaardetijd. Campbell & Shiller
(1988, 1998) leggen de empirische basis: waarderingsratio's voorspellen
langetermijnrendementen omdat ze terugkeren. Asness (2012) bespreekt de
valkuilen — vooral dat het "eerlijke" niveau zelf onzeker is en in de tijd
verschuift. De standaard halfwaardetijd van twaalf jaar en het feit dat het
referentieniveau een configuratieparameter is, zijn een directe erkenning van
die onzekerheid. Dit blok is expliciet als `aanname` gelabeld en is het
grootste beoordelingselement in de aandelenpremie.

**Route 2 — impliciete kostenvoet van eigen vermogen (Damodaran, 2024).** Los de
interne rentevoet op waarbij de huidige indexkoers gelijk is aan de contante
waarde van een tweetraps kasstroomreeks. De eindgroei wordt begrensd door de
lange risicovrije rente: geen onderneming groeit blijvend sneller dan de
economie. Deze route gebruikt géén aanname over een "eerlijke" waardering — de
prijs is per definitie goed — maar wél over het groeipad. De uitkomst wordt bij
elke aandelencategorie als diagnostiek meegegeven, zodat het verschil met route
1 zichtbaar is. Groot uiteenlopen betekent dat het waarderingsblok het antwoord
domineert.

### 3.6 Vastgoed en infrastructuur

Beursgenoteerd vastgoed loopt door hetzelfde Grinold-Kroner-model, met
koers/NAV als waarderingsmaatstaf in plaats van CAPE en met een doorgaans
*negatief* inkooprendement (REIT's geven aandelen uit om te groeien).

Niet-genoteerd vastgoed en kerninfrastructuur gebruiken het
`yield_and_growth`-model: direct rendement minus instandhoudingsinvesteringen,
plus inflatiedoorwerking in huren of gereguleerde tarieven, plus reële groei,
plus een yield shift en een illiquiditeitspremie. De waardegevoeligheid voor een
verandering van het aanvangsrendement is standaard `1/y`, de
Gordon-groeiduration van een eeuwigdurende kasstroom.

Belangrijke waarschuwing bij deze categorieën: het startpunt is een
**taxatiewaarde**, geen transactieprijs. Taxaties zijn glad en lopen achter
(Geltner, 1991; Marcato & Key, 2007), waardoor het aanvangsrendement een
vertraagde en te stabiele weergave van de markt is. Deze categorieën zijn dus
minder "market implied" dan hun genoteerde tegenhangers, hoe stellig het getal
er ook uitziet.

### 3.7 Grondstoffen

```
E[R] = r_f + rolrendement + spotprijsontwikkeling + herbalanceringsrendement
```

Het **rolrendement** is de enige echt market-implied component: de
geannualiseerde helling van de huidige termijncurve. Erb & Harvey (2006) laten
zien dat de vorm van de termijncurve de dominante verklaring is voor de
dwarsdoorsnede van grondstoffenrendementen.

De **spotprijsontwikkeling** is een aanname. De standaard is dat spotprijzen de
inflatie bijhouden en niet meer — een reëel spotrendement van nul, in lijn met
Erb & Harvey (2006) en met het langetermijnbewijs voor trendloze reële
grondstofprijzen. Gorton & Rouwenhorst (2006) documenteerden een substantiële
historische futures-risicopremie; Bhardwaj, Gorton & Rouwenhorst (2015) komen
er tien jaar later op terug en vinden na de financialisering vanaf 2004 veel
zwakkere gerealiseerde premies. De standaardconfiguratie is daarom behoudend.

Het **herbalanceringsrendement** is het meetkundige voordeel van periodiek
herwegen van een mandje met lage onderlinge correlatie (Erb & Harvey, 2006;
Willenbrock, 2011). Reëel, maar bescheiden.

### 3.8 Private equity

Private markten hebben geen waarneembare prijs; een market-implied verwachting
kan daar alleen *relatief* tot stand komen. Het `levered_beta`-model prijst
buyout als een gehefboomde claim op beursgenoteerde aandelen:

```
RP_PE = β × RP_genoteerd + illiquiditeitspremie − kostenverschil
```

L'Her, Stoyanova, Shaw, Scott & Lai (2016) laten zien dat buyoutrendementen
nauw worden nagebootst door een gehefboomde small/mid cap aandelenportefeuille.
Harris, Jenkinson & Kaplan (2014) vinden dat buyoutfondsen de publieke markt
over de looptijd met circa 20 tot 27 procent hebben verslagen (ruwweg 3 procent
per jaar). Phalippou (2020) betoogt daartegenover dat het meerrendement grotendeels
verdwijnt zodra tegen een small cap index wordt gemeten en de vergoedingen
consistent worden verwerkt. Die onenigheid is de reden dat `beta`,
`illiquidity_premium` en `fee_drag` alle drie expliciete, zichtbare parameters
zijn in plaats van in het model verstopte constanten. Ang, Papanikolaou &
Westerfield (2014) leveren het theoretisch kader voor de illiquiditeitspremie.

Omdat het model de premie van de referentiecategorie schaalt, moet die
referentie eerst geëvalueerd zijn. De engine sorteert de categorieën
topologisch op hun afhankelijkheden en detecteert cykels.

---

## 4. Valuta

Alle niet-eurocategorieën worden verondersteld **valuta-afgedekt** te zijn, wat
gebruikelijk is voor een Nederlandse pensioenbelegger. Onder gedekte
rentepariteit geldt:

```
E[R_afgedekt, EUR] = E[R_lokaal] − r_kas,lokaal + r_kas,EUR
```

De risicopremie is daarmee valuta-invariant en het risicovrije blok is altijd
dat van de basisvaluta. Precies daarom is elke bouwsteen in deze package
gedefinieerd als meerrendement boven *lokaal* doorgerold kasgeld: de afdekking
draagt dan exact nul bij aan de premie en het risicovrije blok kan er zonder
correctie bovenop.

Niet afdekken verandert het market-implied antwoord niet: de valutatermijnkoers
prijst precies het renteverschil in, dus het verwachte valutaresultaat onder de
termijnmaatstaf is `r_EUR − r_lokaal`. Empirisch wijkt het gerealiseerde
resultaat daarvan af (de forward premium puzzle; Fama, 1984), maar het
exploiteren daarvan is een actieve strategie en geen marktverwachting.

---

## 5. Meetkundig versus rekenkundig

Alle bouwstenen tellen op tot een **meetkundig** (samengesteld) jaarrendement:
dat is wat een belegger over de horizon daadwerkelijk overhoudt en het juiste
getal voor vermogensprojecties. Voor gebruik in een gemiddelde-variantie-
optimalisatie is het **rekenkundige** rendement nodig; de conversie gebruikt de
standaard lognormale wig:

```
μ ≈ g + σ² / 2
```

(Ilmanen, 2011, hoofdstuk 2). Bij een volatiliteit van 20 procent scheelt dat
2 procentpunt — genoeg om een rangorde om te draaien, dus de tabel rapporteert
beide kolommen naast elkaar en benoemt welke welke is.

---

## 6. Wat wel en niet market implied is

Volledig uit marktprijzen af te lezen:

- de nominale en reële rentecurve, en daarmee `r_f(H)` en de breakevens;
- kredietopslagen (OAS) en durations;
- dividend- en inkooprendementen;
- de helling van de grondstoffentermijncurve;
- koers/NAV van beursgenoteerd vastgoed.

Uit de literatuur, niet uit prijzen:

- termijnpremies en inflatierisicopremies (modelschattingen *op basis van*
  prijzen — het middengebied);
- verwachte kredietverliezen, afwaarderingsdrag en vervroegde aflossing;
- reële winst- en huurgroei;
- "eerlijke" waarderings- en spreadniveaus en hun convergentiesnelheid;
- illiquiditeitspremies, herbalanceringsrendement, private-equity beta.

De rapportage kwantificeert dit per categorie als *aandeel aanname*: de absolute
omvang van aannameblokken gedeeld door de absolute omvang van alle
premieblokken. Bij hoge waarden — high yield en opkomende markten scoren in de
standaardconfiguratie het hoogst — is de uitkomst vooral een weerspiegeling van
de gekozen parameters. Draai `--no-valuation` om te zien wat er overblijft van
de tabel zonder enige convergentieaanname; het verschil is de omvang van de
mening.

---

## 7. Databronnen

Het meegeleverde bestand `data/market_snapshot_example.json` bevat
**illustratieve waarden, geen werkelijke marktdata**. Voor gebruik moet het
worden vervangen door een echte marktopname. Per veld:

| Veld | Bron |
|---|---|
| `curves.*_nominal` | Swapcurve (ESTR/EURIBOR, SOFR) of staatscurve, jaarlijks samengestelde zero rates. |
| `curves.*_real` | Inflatieswaps (HICPxT) of de TIPS-curve; Gürkaynak, Sack & Wright (2010) beschrijven de gangbare constructie. |
| `term_premia` | ACM-decompositie, gepubliceerd door de Federal Reserve Bank of New York; voor de euro ECB- of DNB-schattingen. |
| `inflation_risk_premia` | Grishchenko & Huang (2013), D'Amico, Kim & Wei (2018), of het verschil tussen breakevens en de ECB Survey of Professional Forecasters. |
| `instruments.credit.*` | Option-adjusted spreads, effective duration en spread duration uit de gebruikte indexfamilie (ICE BofA, Bloomberg). |
| `instruments.equity.*` | Indexfundamentals (MSCI, Bloomberg); CAPE volgens de Shiller-methodiek op tienjaars reële gemiddelde winst. |
| `instruments.commodities.*` | Geannualiseerde helling van de termijncurve van de gebruikte index. |
| `instruments.real_estate.*` | MSCI/INREV taxatiegebaseerde aanvangsrendementen; koers/NAV uit EPRA-data. |

Structurele aannames staan bewust **niet** in de marktopname maar in
`data/universe_default.json`, met per categorie de defaultkans, recovery,
groeivoet en convergentiehalfwaardetijd. Wie een getal wil verantwoorden hoeft
alleen die twee bestanden plus de git-hash te bewaren.

---

## 8. Beperkingen

1. **Één scenario, geen verdeling.** De uitkomst is een verwachting, geen
   scenarioset. Er wordt geen onzekerheidsband geproduceerd. Wie die nodig heeft
   moet de parameters variëren of een stochastisch model gebruiken.
2. **Volatiliteiten en correlaties zijn invoer, geen uitkomst.** De
   volatiliteiten dienen uitsluitend de meetkundig/rekenkundig-conversie.
   Correlaties zitten er helemaal niet in; voor portefeuilleoptimalisatie is een
   aanvullende bron nodig.
3. **Taxatiegebaseerde categorieën zijn gladgestreken.** Zie 3.6: het
   startpunt van niet-genoteerd vastgoed en infrastructuur loopt achter op de
   markt, wat de premie in een dalende markt te hoog en in een stijgende markt
   te laag maakt.
4. **Het waarderingsblok domineert de aandelenpremie.** Referentieniveau en
   halfwaardetijd zijn de meest invloedrijke en tegelijk minst onderbouwde
   parameters in het hele raamwerk. Behandel de aandelenpremie als een bandbreedte.
5. **Termijnpremieschattingen lopen uiteen.** ACM en Kim-Wright verschillen
   regelmatig tientallen basispunten. Dat raakt de verdeling tussen risicovrij
   en premie direct, en bij duration-afhankelijke categorieën ook het totaal.
6. **Geen belastingen, kosten of implementatieverlies.** Alle rendementen zijn
   bruto, behalve waar een categorie een expliciet kostenblok heeft.
7. **De configuratie is geen advies.** De meegeleverde parameters zijn een
   redelijk vertrekpunt uit de literatuur, geen aanbeveling van een
   beleggingsbeleid.

---

## 9. Literatuur

**Rentecurve en termijnpremie**

- Adrian, T., Crump, R. & Moench, E. (2013). Pricing the term structure with linear regressions. *Journal of Financial Economics*, 110(1), 110-138.
- Campbell, J. & Shiller, R. (1991). Yield spreads and interest rate movements: a bird's eye view. *Review of Economic Studies*, 58(3), 495-514.
- Campbell, J. & Viceira, L. (2002). *Strategic Asset Allocation: Portfolio Choice for Long-Term Investors.* Oxford University Press.
- Cochrane, J. & Piazzesi, M. (2005). Bond risk premia. *American Economic Review*, 95(1), 138-160.
- Fama, E. & Bliss, R. (1987). The information in long-maturity forward rates. *American Economic Review*, 77(4), 680-692.
- Gürkaynak, R., Sack, B. & Wright, J. (2010). The TIPS yield curve and inflation compensation. *American Economic Journal: Macroeconomics*, 2(1), 70-92.
- Hagan, P. & West, G. (2006). Interpolation methods for curve construction. *Applied Mathematical Finance*, 13(2), 89-129.
- Kim, D. & Wright, J. (2005). An arbitrage-free three-factor term structure model and the recent behavior of long-term yields. *Federal Reserve Board FEDS* 2005-33.

**Inflatie en linkers**

- D'Amico, S., Kim, D. & Wei, M. (2018). Tips from TIPS: the informational content of Treasury inflation-protected security prices. *Journal of Financial and Quantitative Analysis*, 53(1), 395-436.
- Grishchenko, O. & Huang, J. (2013). The inflation risk premium: evidence from the TIPS market. *Journal of Fixed Income*, 22(4), 5-30.
- Pflueger, C. & Viceira, L. (2016). Return predictability in the Treasury market: real rates, inflation, and liquidity. In *Handbook of Fixed-Income Securities*. Wiley.

**Krediet**

- Altman, E. & Kuehne, B. (diverse jaren). *Defaults and Returns in the High-Yield Bond Market.* NYU Salomon Center.
- Asvanunt, A. & Richardson, S. (2017). The credit risk premium. *Journal of Fixed Income*, 26(3), 6-24.
- Ben Dor, A. & Xu, Z. (2015). Should equity investors care about corporate bond prices? *Journal of Portfolio Management*, 41(4).
- Collin-Dufresne, P., Goldstein, R. & Martin, J. (2001). The determinants of credit spread changes. *Journal of Finance*, 56(6), 2177-2207.
- Duffee, G. (1998). The relation between Treasury yields and corporate bond yield spreads. *Journal of Finance*, 53(6), 2225-2241.
- Elton, E., Gruber, M., Agrawal, D. & Mann, C. (2001). Explaining the rate spread on corporate bonds. *Journal of Finance*, 56(1), 247-277.
- Giesecke, K., Longstaff, F., Schaefer, S. & Strebulaev, I. (2011). Corporate bond default risk: a 150-year perspective. *Journal of Financial Economics*, 102(2), 233-250.
- Ng, K. & Phelps, B. (2011). Capturing credit spread premium. *Financial Analysts Journal*, 67(3), 63-75.

**Aandelen**

- Asness, C. (2012). *An Old Friend: The Stock Market's Shiller P/E.* AQR Capital Management.
- Bernstein, W. & Arnott, R. (2003). Earnings growth: the two percent dilution. *Financial Analysts Journal*, 59(5), 47-55.
- Bogle, J. (1991). Investing in the 1990s: occam's razor revisited. *Journal of Portfolio Management*, 18(1), 88-91.
- Campbell, J. & Shiller, R. (1988). Stock prices, earnings, and expected dividends. *Journal of Finance*, 43(3), 661-676.
- Campbell, J. & Shiller, R. (1998). Valuation ratios and the long-run stock market outlook. *Journal of Portfolio Management*, 24(2), 11-26.
- Damodaran, A. (2024). *Equity Risk Premiums: Determinants, Estimation and Implications.* NYU Stern working paper (jaarlijkse editie).
- Grinold, R. & Kroner, K. (2002). The equity risk premium. *Investment Insights*, 5(3), Barclays Global Investors.
- Straehl, P. & Ibbotson, R. (2017). The long-run drivers of stock returns: total payouts and the real economy. *Financial Analysts Journal*, 73(3), 32-52.

**Reële activa**

- Bhardwaj, G., Gorton, G. & Rouwenhorst, K. G. (2015). *Facts and Fantasies about Commodity Futures Ten Years Later.* NBER Working Paper 21243.
- Erb, C. & Harvey, C. (2006). The strategic and tactical value of commodity futures. *Financial Analysts Journal*, 62(2), 69-97.
- Geltner, D. (1991). Smoothing in appraisal-based returns. *Journal of Real Estate Finance and Economics*, 4(3), 327-345.
- Gorton, G. & Rouwenhorst, K. G. (2006). Facts and fantasies about commodity futures. *Financial Analysts Journal*, 62(2), 47-68.
- Marcato, G. & Key, T. (2007). Smoothing and implications for asset allocation choices. *Journal of Portfolio Management*, 33(5), 85-98.
- Willenbrock, S. (2011). Diversification return, portfolio rebalancing, and the commodity return puzzle. *Financial Analysts Journal*, 67(4), 42-49.

**Private markten**

- Ang, A., Papanikolaou, D. & Westerfield, M. (2014). Portfolio choice with illiquid assets. *Management Science*, 60(11), 2737-2761.
- Harris, R., Jenkinson, T. & Kaplan, S. (2014). Private equity performance: what do we know? *Journal of Finance*, 69(5), 1851-1882.
- L'Her, J.-F., Stoyanova, R., Shaw, K., Scott, W. & Lai, C. (2016). A bottom-up approach to the risk-adjusted performance of the buyout fund market. *Financial Analysts Journal*, 72(4), 36-48.
- Phalippou, L. (2020). An inconvenient fact: private equity returns and the billionaire factory. *Journal of Investing*, 30(1), 11-39.

**Algemeen**

- Fama, E. (1984). Forward and spot exchange rates. *Journal of Monetary Economics*, 14(3), 319-338.
- Ilmanen, A. (2011). *Expected Returns: An Investor's Guide to Harvesting Market Rewards.* Wiley.
