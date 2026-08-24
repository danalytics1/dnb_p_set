# Market-implied rendementsverwachtingen

- **Marktopname:** 2026-06-30
- **Basisvaluta:** EUR (buitenlandse categorieen valuta-afgedekt)
- **Universum:** Standaard beleggingsuniversum (NL pensioencontext)
- **Risicovrije conventie:** `rolled_cash`
- **Waarderingsconvergentie actief:** ja

Alle rendementen zijn meetkundig en per jaar, tenzij anders vermeld.

## 1. Risicopremies per beleggingscategorie

| Beleggingscategorie | Categorie | Risicopremie 5j | E[R] 5j | Risicopremie 15j | E[R] 15j |
| --- | --- | ---: | ---: | ---: | ---: |
| Liquiditeiten (EUR) | Vastrentend | 0.00% | 2.15% | 0.00% | 2.20% |
| Staatsobligaties EMU | Vastrentend | 0.58% | 2.73% | 0.58% | 2.78% |
| Inflatiegekoppelde staatsobligaties (EUR) | Vastrentend | 0.30% | 2.45% | 0.30% | 2.50% |
| Bedrijfsobligaties investment grade (EUR) | Vastrentend | 0.73% | 2.88% | 0.80% | 3.00% |
| High yield bedrijfsobligaties (EUR) | Vastrentend | 1.15% | 3.30% | 1.34% | 3.54% |
| Emerging market debt (harde valuta) | Vastrentend | 2.59% | 4.74% | 2.78% | 4.98% |
| Nederlandse hypotheken | Vastrentend | 1.66% | 3.81% | 1.66% | 3.86% |
| Aandelen ontwikkelde markten | Zakelijke waarden | 2.79% | 4.94% | 2.86% | 5.06% |
| Aandelen Europa | Zakelijke waarden | 4.84% | 6.99% | 4.81% | 7.01% |
| Aandelen opkomende markten | Zakelijke waarden | 4.14% | 6.29% | 4.06% | 6.26% |
| Beursgenoteerd vastgoed | Zakelijke waarden | 4.00% | 6.15% | 3.66% | 5.86% |
| Niet-genoteerd vastgoed (core) | Reele activa | 3.02% | 5.17% | 3.25% | 5.45% |
| Infrastructuur (core, niet-genoteerd) | Reele activa | 4.37% | 6.52% | 4.34% | 6.54% |
| Grondstoffen | Reele activa | 1.87% | 4.02% | 1.78% | 3.98% |
| Private equity (buyout) | Zakelijke waarden | 4.23% | 6.38% | 4.32% | 6.52% |

### Risicovrije rente (identiek voor alle categorieen)

| Horizon | Zero rate | Termijnpremie | Risicovrije rente |
| --- | ---: | ---: | ---: |
| 5 jaar | 2.40% | 0.25% | 2.15% |
| 15 jaar | 2.95% | 0.75% | 2.20% |

## 2. Opbouw uit bouwstenen

### Horizon 5 jaar

#### Liquiditeiten (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| **Verwacht rendement** | **2.15%** | | risicovrij 2.15% + risicopremie 0.00% |

*Diagnostiek:* spot_rate = 0.024

#### Staatsobligaties EMU

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.40% | markt | Termijnpremie bij duration 7.5j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Landenspread | 0.20% | markt | Waargenomen spread van de staatsobligatie-index boven de referentiecurve (swap of AAA-staat). |
| Af: verwacht kredietverlies | -0.02% | aanname | Verwachte wanbetalingskosten (kans x LGD) op basis van historische soevereine defaultstatistieken; niet uit de marktprijs af te leiden zonder de risicopremie mee te nemen. |
| **Verwacht rendement** | **2.73%** | | risicovrij 2.15% + risicopremie 0.58% |

*Diagnostiek:* index_yield = 0.02794, spot_rate = 0.024, term_premium_at_duration = 0.004, duration = 7.5

#### Inflatiegekoppelde staatsobligaties (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.43% | markt | Termijnpremie bij duration 8j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Af: inflatierisicopremie | -0.21% | markt | Een inflatiegekoppelde obligatie draagt geen inflatierisico en ontvangt de inflatierisicopremie die in de nominale curve zit dus niet (Grishchenko & Huang, 2013; D'Amico, Kim & Wei, 2018). |
| Liquiditeitspremie linkers | 0.10% | aanname | De markt voor inflatiegekoppelde obligaties is minder liquide dan de nominale markt; de breakeven onderschat de verwachte inflatie daardoor (Pflueger & Viceira, 2016). |
| Af: verwacht kredietverlies | -0.02% | aanname | Verwachte wanbetalingskosten (kans x LGD) op basis van historische soevereine defaultstatistieken; niet uit de marktprijs af te leiden zonder de risicopremie mee te nemen. |
| **Verwacht rendement** | **2.45%** | | risicovrij 2.15% + risicopremie 0.30% |

*Diagnostiek:* real_yield = 0.006125, breakeven_inflation = 0.02009, expected_inflation = 0.01799, inflation_risk_premium = 0.0021, duration = 8

#### Bedrijfsobligaties investment grade (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.22% | markt | Termijnpremie bij duration 4.5j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 0.95% | markt | Waargenomen option-adjusted spread van 0.95%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.13% | aanname | OAS beweegt van 0.95% naar 1.09% (69% van de weg naar het langetermijnniveau van 1.15%, halfwaardetijd 3j); koerseffect -SD x dOAS over 5 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -0.06% | aanname | Defaultkans 0.10% x (1 - recovery 40%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.25% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **2.88%** | | risicovrij 2.15% + risicopremie 0.73% |

*Diagnostiek:* oas = 0.0095, index_yield = 0.03325, duration = 4.5, spread_duration = 4.6, expected_credit_loss = 0.0006, spread_over_expected_loss = 15.83

#### High yield bedrijfsobligaties (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.12% | markt | Termijnpremie bij duration 3j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 3.80% | markt | Waargenomen option-adjusted spread van 3.80%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.35% | aanname | OAS beweegt van 3.80% naar 4.35% (69% van de weg naar het langetermijnniveau van 4.60%, halfwaardetijd 3j); koerseffect -SD x dOAS over 5 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -2.16% | aanname | Defaultkans 3.60% x (1 - recovery 40%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.25% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **3.30%** | | risicovrij 2.15% + risicopremie 1.15% |

*Diagnostiek:* oas = 0.038, index_yield = 0.0605, duration = 3, spread_duration = 3.2, expected_credit_loss = 0.0216, spread_over_expected_loss = 1.759

#### Emerging market debt (harde valuta)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.39% | markt | Termijnpremie bij duration 6.3j op USD_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 3.20% | markt | Waargenomen option-adjusted spread van 3.20%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.35% | aanname | OAS beweegt van 3.20% naar 3.47% (69% van de weg naar het langetermijnniveau van 3.60%, halfwaardetijd 3j); koerseffect -SD x dOAS over 5 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -0.55% | aanname | Defaultkans 1.10% x (1 - recovery 50%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.10% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **4.74%** | | risicovrij 2.15% + risicopremie 2.59% |

*Diagnostiek:* oas = 0.032, index_yield = 0.07108, duration = 6.3, spread_duration = 6.3, expected_credit_loss = 0.0055, spread_over_expected_loss = 5.818

#### Nederlandse hypotheken

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.43% | markt | Termijnpremie bij duration 8j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 1.40% | markt | Waargenomen option-adjusted spread van 1.40%; dit is de enige component die volledig uit de marktprijs komt. |
| Af: verwacht kredietverlies | -0.02% | aanname | Defaultkans 0.15% x (1 - recovery 85%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: vervroegde-aflossingskosten | -0.15% | aanname | Negatieve convexiteit en vervroegde aflossing bij hypotheken en MBS. |
| **Verwacht rendement** | **3.81%** | | risicovrij 2.15% + risicopremie 1.66% |

*Diagnostiek:* oas = 0.014, index_yield = 0.04033, duration = 8, spread_duration = 8, expected_credit_loss = 0.000225, spread_over_expected_loss = 62.22

#### Aandelen ontwikkelde markten

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 1.90% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 1.30% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 2.07% | markt | Breakeven-inflatie op 5 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 1.50% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | -0.48% | aanname | CAPE beweegt van 26.5 naar 25.9 (25% van de weg naar 24.0, halfwaardetijd 12j); geannualiseerd over 5 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -3.50% | afgeleid | -3.50%: verwachte gemiddelde korte rente in USD over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. Valuta-afdekking ruilt vervolgens de lokale kasrente om voor die van de basisvaluta (gedekte rentepariteit). |
| **Verwacht rendement** | **4.94%** | | risicovrij 2.15% + risicopremie 2.79% |

*Diagnostiek:* dividend_yield = 0.019, net_payout_yield = 0.032, expected_inflation = 0.02066, real_growth = 0.015, local_risk_free = 0.035, cape = 26.5, implied_cost_of_equity = 0.0688, implied_erp_vs_long_rf = 0.0248

#### Aandelen Europa

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 3.20% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 0.80% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.79% | markt | Breakeven-inflatie op 5 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 1.20% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.00% | aanname | CAPE beweegt van 20.0 naar 20.0 (25% van de weg naar 20.0, halfwaardetijd 12j); geannualiseerd over 5 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -2.15% | afgeleid | -2.15%: verwachte gemiddelde korte rente in EUR over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **6.99%** | | risicovrij 2.15% + risicopremie 4.84% |

*Diagnostiek:* dividend_yield = 0.032, net_payout_yield = 0.04, expected_inflation = 0.01791, real_growth = 0.012, local_risk_free = 0.0215, cape = 20, implied_cost_of_equity = 0.0699, implied_erp_vs_long_rf = 0.0414

#### Aandelen opkomende markten

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 2.80% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 0.10% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 2.07% | markt | Breakeven-inflatie op 5 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 2.50% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.17% | aanname | CAPE beweegt van 14.5 naar 14.6 (25% van de weg naar 15.0, halfwaardetijd 12j); geannualiseerd over 5 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -3.50% | afgeleid | -3.50%: verwachte gemiddelde korte rente in USD over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. Valuta-afdekking ruilt vervolgens de lokale kasrente om voor die van de basisvaluta (gedekte rentepariteit). |
| **Verwacht rendement** | **6.29%** | | risicovrij 2.15% + risicopremie 4.14% |

*Diagnostiek:* dividend_yield = 0.028, net_payout_yield = 0.029, expected_inflation = 0.02066, real_growth = 0.025, local_risk_free = 0.035, cape = 14.5, implied_cost_of_equity = 0.0745, implied_erp_vs_long_rf = 0.0305

#### Beursgenoteerd vastgoed

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 4.20% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | -0.60% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.61% | markt | Breakeven-inflatie op 5 jaar minus de inflatierisicopremie, x doorwerking 90%. |
| Reële winstgroei | 0.00% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.94% | aanname | PRICE_TO_NAV beweegt van 0.9 naar 0.9 (35% van de weg naar 1.0, halfwaardetijd 8j); geannualiseerd over 5 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -2.15% | afgeleid | -2.15%: verwachte gemiddelde korte rente in EUR over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **6.15%** | | risicovrij 2.15% + risicopremie 4.00% |

*Diagnostiek:* dividend_yield = 0.042, net_payout_yield = 0.036, expected_inflation = 0.01612, real_growth = 0, local_risk_free = 0.0215, price_to_nav = 0.88, implied_cost_of_equity = 0.0588, implied_erp_vs_long_rf = 0.0303

#### Niet-genoteerd vastgoed (core)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Direct rendement | 4.80% | markt | Netto aanvangsrendement / cap rate op basis van actuele taxatie- of transactiewaarden. Taxatiewaarden lopen achter op transactieprijzen (Geltner, 1991), dus dit is minder 'marktprijs' dan een beursnotering. |
| Af: onderhoudsinvesteringen | -0.80% | aanname | Investeringen nodig om het inkomen in stand te houden; verlagen het netto rendement. |
| Verwachte inflatie | 1.61% | markt | Breakeven-inflatie minus inflatierisicopremie, x doorwerking 90% in huren/tarieven. |
| Waarderingsverandering (yield shift) | -0.74% | aanname | Aanvangsrendement beweegt van 4.80% naar 4.98% (44% van de weg naar 5.20%); waardegevoeligheid 20.8. |
| Illiquiditeitspremie | 0.30% | aanname | Vergoeding voor de lock-up. Niet af te lezen uit een prijs en empirisch omstreden van omvang. |
| Af: risicovrije rente (lokaal) | -2.15% | afgeleid | -2.15%: verwachte gemiddelde korte rente in EUR over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **5.17%** | | risicovrij 2.15% + risicopremie 3.02% |

*Diagnostiek:* income_yield = 0.048, expected_inflation = 0.01612, local_risk_free = 0.0215

#### Infrastructuur (core, niet-genoteerd)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Direct rendement | 4.80% | markt | Netto aanvangsrendement / cap rate op basis van actuele taxatie- of transactiewaarden. Taxatiewaarden lopen achter op transactieprijzen (Geltner, 1991), dus dit is minder 'marktprijs' dan een beursnotering. |
| Af: onderhoudsinvesteringen | -0.60% | aanname | Investeringen nodig om het inkomen in stand te houden; verlagen het netto rendement. |
| Verwachte inflatie | 1.52% | markt | Breakeven-inflatie minus inflatierisicopremie, x doorwerking 85% in huren/tarieven. |
| Reële inkomensgroei | 0.30% | aanname | Reële groei van de netto huur- of tariefinkomsten bovenop inflatie. |
| Waarderingsverandering (yield shift) | 0.00% | aanname | Aanvangsrendement beweegt van 4.80% naar 4.80% (44% van de weg naar 4.80%); waardegevoeligheid 20.8. |
| Illiquiditeitspremie | 0.50% | aanname | Vergoeding voor de lock-up. Niet af te lezen uit een prijs en empirisch omstreden van omvang. |
| Af: risicovrije rente (lokaal) | -2.15% | afgeleid | -2.15%: verwachte gemiddelde korte rente in EUR over 5 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **6.52%** | | risicovrij 2.15% + risicopremie 4.37% |

*Diagnostiek:* income_yield = 0.048, expected_inflation = 0.01523, local_risk_free = 0.0215

#### Grondstoffen

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Rolrendement | -0.60% | markt | Geannualiseerde helling van de huidige termijnmarktcurve; negatief bij contango, positief bij backwardation (Erb & Harvey, 2006). |
| Spotprijsontwikkeling | 2.07% | afgeleid | Verwachte inflatie x doorwerking 100% plus een reële spotgroei van 0.00%. De aanname van nul reële spotgroei sluit aan bij het langetermijnbewijs voor trendloze reële grondstofprijzen (Erb & Harvey, 2006). |
| Herbalanceringsrendement | 0.40% | aanname | Meetkundig voordeel van periodiek herwegen van een mandje met lage onderlinge correlatie (Willenbrock, 2011). |
| **Verwacht rendement** | **4.02%** | | risicovrij 2.15% + risicopremie 1.87% |

*Diagnostiek:* roll_yield = -0.006, expected_inflation = 0.02066

#### Private equity (buyout)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.15% | afgeleid | z(5y) - TP(5y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Beta x risicopremie referentie | 3.48% | afgeleid | 1.25 x de risicopremie van 'Aandelen ontwikkelde markten' (2.79% boven doorgerold kasgeld). Beta boven 1 weerspiegelt de hogere financiële hefboom en de small/mid cap tilt van buyouts (L'Her e.a., 2016). |
| Illiquiditeitspremie | 0.75% | aanname | Vergoeding voor het niet kunnen verhandelen gedurende de looptijd (Ang, Papanikolaou & Westerfield, 2014). De omvang is omstreden: Phalippou (2020) vindt na correctie voor small caps nauwelijks meerrendement. |
| **Verwacht rendement** | **6.38%** | | risicovrij 2.15% + risicopremie 4.23% |

*Diagnostiek:* reference = equity_dm, reference_premium = 0.02788, beta = 1.25

### Horizon 15 jaar

#### Liquiditeiten (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| **Verwacht rendement** | **2.20%** | | risicovrij 2.20% + risicopremie 0.00% |

*Diagnostiek:* spot_rate = 0.0295

#### Staatsobligaties EMU

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.40% | markt | Termijnpremie bij duration 7.5j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Landenspread | 0.20% | markt | Waargenomen spread van de staatsobligatie-index boven de referentiecurve (swap of AAA-staat). |
| Af: verwacht kredietverlies | -0.02% | aanname | Verwachte wanbetalingskosten (kans x LGD) op basis van historische soevereine defaultstatistieken; niet uit de marktprijs af te leiden zonder de risicopremie mee te nemen. |
| **Verwacht rendement** | **2.78%** | | risicovrij 2.20% + risicopremie 0.58% |

*Diagnostiek:* index_yield = 0.02794, spot_rate = 0.0295, term_premium_at_duration = 0.004, duration = 7.5

#### Inflatiegekoppelde staatsobligaties (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.43% | markt | Termijnpremie bij duration 8j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Af: inflatierisicopremie | -0.21% | markt | Een inflatiegekoppelde obligatie draagt geen inflatierisico en ontvangt de inflatierisicopremie die in de nominale curve zit dus niet (Grishchenko & Huang, 2013; D'Amico, Kim & Wei, 2018). |
| Liquiditeitspremie linkers | 0.10% | aanname | De markt voor inflatiegekoppelde obligaties is minder liquide dan de nominale markt; de breakeven onderschat de verwachte inflatie daardoor (Pflueger & Viceira, 2016). |
| Af: verwacht kredietverlies | -0.02% | aanname | Verwachte wanbetalingskosten (kans x LGD) op basis van historische soevereine defaultstatistieken; niet uit de marktprijs af te leiden zonder de risicopremie mee te nemen. |
| **Verwacht rendement** | **2.50%** | | risicovrij 2.20% + risicopremie 0.30% |

*Diagnostiek:* real_yield = 0.006125, breakeven_inflation = 0.02009, expected_inflation = 0.01799, inflation_risk_premium = 0.0021, duration = 8

#### Bedrijfsobligaties investment grade (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.22% | markt | Termijnpremie bij duration 4.5j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 0.95% | markt | Waargenomen option-adjusted spread van 0.95%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.06% | aanname | OAS beweegt van 0.95% naar 1.14% (97% van de weg naar het langetermijnniveau van 1.15%, halfwaardetijd 3j); koerseffect -SD x dOAS over 15 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -0.06% | aanname | Defaultkans 0.10% x (1 - recovery 40%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.25% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **3.00%** | | risicovrij 2.20% + risicopremie 0.80% |

*Diagnostiek:* oas = 0.0095, index_yield = 0.03325, duration = 4.5, spread_duration = 4.6, expected_credit_loss = 0.0006, spread_over_expected_loss = 15.83

#### High yield bedrijfsobligaties (EUR)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.12% | markt | Termijnpremie bij duration 3j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 3.80% | markt | Waargenomen option-adjusted spread van 3.80%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.17% | aanname | OAS beweegt van 3.80% naar 4.58% (97% van de weg naar het langetermijnniveau van 4.60%, halfwaardetijd 3j); koerseffect -SD x dOAS over 15 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -2.16% | aanname | Defaultkans 3.60% x (1 - recovery 40%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.25% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **3.54%** | | risicovrij 2.20% + risicopremie 1.34% |

*Diagnostiek:* oas = 0.038, index_yield = 0.0605, duration = 3, spread_duration = 3.2, expected_credit_loss = 0.0216, spread_over_expected_loss = 1.759

#### Emerging market debt (harde valuta)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.39% | markt | Termijnpremie bij duration 6.3j op USD_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 3.20% | markt | Waargenomen option-adjusted spread van 3.20%; dit is de enige component die volledig uit de marktprijs komt. |
| Spreadwaardering | -0.16% | aanname | OAS beweegt van 3.20% naar 3.59% (97% van de weg naar het langetermijnniveau van 3.60%, halfwaardetijd 3j); koerseffect -SD x dOAS over 15 jaar geannualiseerd. |
| Af: verwacht kredietverlies | -0.55% | aanname | Defaultkans 1.10% x (1 - recovery 50%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: afwaarderingsverlies | -0.10% | aanname | Gedwongen verkoop van fallen angels door ratinggrenzen in de index (Ng & Phelps, 2011; Ben Dor & Xu, 2015). |
| **Verwacht rendement** | **4.98%** | | risicovrij 2.20% + risicopremie 2.78% |

*Diagnostiek:* oas = 0.032, index_yield = 0.07108, duration = 6.3, spread_duration = 6.3, expected_credit_loss = 0.0055, spread_over_expected_loss = 5.818

#### Nederlandse hypotheken

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Termijnpremie (duration) | 0.43% | markt | Termijnpremie bij duration 8j op EUR_nominal; verwacht meerrendement van duratierisico boven doorgerold kasgeld (Adrian, Crump & Moench, 2013). |
| Kredietopslag (OAS) | 1.40% | markt | Waargenomen option-adjusted spread van 1.40%; dit is de enige component die volledig uit de marktprijs komt. |
| Af: verwacht kredietverlies | -0.02% | aanname | Defaultkans 0.15% x (1 - recovery 85%) op basis van historische ratingbureau-statistieken; niet uit de spread zelf afgeleid omdat de spread ook risicopremie bevat (Giesecke e.a., 2011). |
| Af: vervroegde-aflossingskosten | -0.15% | aanname | Negatieve convexiteit en vervroegde aflossing bij hypotheken en MBS. |
| **Verwacht rendement** | **3.86%** | | risicovrij 2.20% + risicopremie 1.66% |

*Diagnostiek:* oas = 0.014, index_yield = 0.04033, duration = 8, spread_duration = 8, expected_credit_loss = 0.000225, spread_over_expected_loss = 62.22

#### Aandelen ontwikkelde markten

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 1.90% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 1.30% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.98% | markt | Breakeven-inflatie op 15 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 1.50% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | -0.37% | aanname | CAPE beweegt van 26.5 naar 25.1 (58% van de weg naar 24.0, halfwaardetijd 12j); geannualiseerd over 15 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -3.45% | afgeleid | -3.45%: verwachte gemiddelde korte rente in USD over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. Valuta-afdekking ruilt vervolgens de lokale kasrente om voor die van de basisvaluta (gedekte rentepariteit). |
| **Verwacht rendement** | **5.06%** | | risicovrij 2.20% + risicopremie 2.86% |

*Diagnostiek:* dividend_yield = 0.019, net_payout_yield = 0.032, expected_inflation = 0.0198, real_growth = 0.015, local_risk_free = 0.0345, cape = 26.5, implied_cost_of_equity = 0.06791, implied_erp_vs_long_rf = 0.02391

#### Aandelen Europa

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 3.20% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 0.80% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.81% | markt | Breakeven-inflatie op 15 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 1.20% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.00% | aanname | CAPE beweegt van 20.0 naar 20.0 (58% van de weg naar 20.0, halfwaardetijd 12j); geannualiseerd over 15 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -2.20% | afgeleid | -2.20%: verwachte gemiddelde korte rente in EUR over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **7.01%** | | risicovrij 2.20% + risicopremie 4.81% |

*Diagnostiek:* dividend_yield = 0.032, net_payout_yield = 0.04, expected_inflation = 0.01807, real_growth = 0.012, local_risk_free = 0.022, cape = 20, implied_cost_of_equity = 0.06993, implied_erp_vs_long_rf = 0.04143

#### Aandelen opkomende markten

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 2.80% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | 0.10% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.98% | markt | Breakeven-inflatie op 15 jaar minus de inflatierisicopremie. |
| Reële winstgroei | 2.50% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.13% | aanname | CAPE beweegt van 14.5 naar 14.8 (58% van de weg naar 15.0, halfwaardetijd 12j); geannualiseerd over 15 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -3.45% | afgeleid | -3.45%: verwachte gemiddelde korte rente in USD over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. Valuta-afdekking ruilt vervolgens de lokale kasrente om voor die van de basisvaluta (gedekte rentepariteit). |
| **Verwacht rendement** | **6.26%** | | risicovrij 2.20% + risicopremie 4.06% |

*Diagnostiek:* dividend_yield = 0.028, net_payout_yield = 0.029, expected_inflation = 0.0198, real_growth = 0.025, local_risk_free = 0.0345, cape = 14.5, implied_cost_of_equity = 0.07439, implied_erp_vs_long_rf = 0.03039

#### Beursgenoteerd vastgoed

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Dividendrendement | 4.20% | markt | Dividend over de huidige indexkoers; direct waarneembaar. |
| Netto inkoop eigen aandelen | -0.60% | markt | Netto verandering van het aantal uitstaande aandelen. Negatief bij verwatering. Samen met dividend het totale payout yield (Straehl & Ibbotson, 2017). |
| Verwachte inflatie | 1.63% | markt | Breakeven-inflatie op 15 jaar minus de inflatierisicopremie, x doorwerking 90%. |
| Reële winstgroei | 0.00% | aanname | Aangenomen reële winstgroei per aandeel. Per-aandeel groei blijft structureel achter bij economische groei door netto uitgifte en verwatering (Bernstein & Arnott, 2003; Straehl & Ibbotson, 2017). |
| Waarderingsverandering | 0.63% | aanname | PRICE_TO_NAV beweegt van 0.9 naar 1.0 (73% van de weg naar 1.0, halfwaardetijd 8j); geannualiseerd over 15 jaar (Campbell & Shiller, 1998). |
| Af: risicovrije rente (lokaal) | -2.20% | afgeleid | -2.20%: verwachte gemiddelde korte rente in EUR over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **5.86%** | | risicovrij 2.20% + risicopremie 3.66% |

*Diagnostiek:* dividend_yield = 0.042, net_payout_yield = 0.036, expected_inflation = 0.01627, real_growth = 0, local_risk_free = 0.022, price_to_nav = 0.88, implied_cost_of_equity = 0.05895, implied_erp_vs_long_rf = 0.03045

#### Niet-genoteerd vastgoed (core)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Direct rendement | 4.80% | markt | Netto aanvangsrendement / cap rate op basis van actuele taxatie- of transactiewaarden. Taxatiewaarden lopen achter op transactieprijzen (Geltner, 1991), dus dit is minder 'marktprijs' dan een beursnotering. |
| Af: onderhoudsinvesteringen | -0.80% | aanname | Investeringen nodig om het inkomen in stand te houden; verlagen het netto rendement. |
| Verwachte inflatie | 1.63% | markt | Breakeven-inflatie minus inflatierisicopremie, x doorwerking 90% in huren/tarieven. |
| Waarderingsverandering (yield shift) | -0.47% | aanname | Aanvangsrendement beweegt van 4.80% naar 5.13% (82% van de weg naar 5.20%); waardegevoeligheid 20.8. |
| Illiquiditeitspremie | 0.30% | aanname | Vergoeding voor de lock-up. Niet af te lezen uit een prijs en empirisch omstreden van omvang. |
| Af: risicovrije rente (lokaal) | -2.20% | afgeleid | -2.20%: verwachte gemiddelde korte rente in EUR over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **5.45%** | | risicovrij 2.20% + risicopremie 3.25% |

*Diagnostiek:* income_yield = 0.048, expected_inflation = 0.01627, local_risk_free = 0.022

#### Infrastructuur (core, niet-genoteerd)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Direct rendement | 4.80% | markt | Netto aanvangsrendement / cap rate op basis van actuele taxatie- of transactiewaarden. Taxatiewaarden lopen achter op transactieprijzen (Geltner, 1991), dus dit is minder 'marktprijs' dan een beursnotering. |
| Af: onderhoudsinvesteringen | -0.60% | aanname | Investeringen nodig om het inkomen in stand te houden; verlagen het netto rendement. |
| Verwachte inflatie | 1.54% | markt | Breakeven-inflatie minus inflatierisicopremie, x doorwerking 85% in huren/tarieven. |
| Reële inkomensgroei | 0.30% | aanname | Reële groei van de netto huur- of tariefinkomsten bovenop inflatie. |
| Waarderingsverandering (yield shift) | 0.00% | aanname | Aanvangsrendement beweegt van 4.80% naar 4.80% (82% van de weg naar 4.80%); waardegevoeligheid 20.8. |
| Illiquiditeitspremie | 0.50% | aanname | Vergoeding voor de lock-up. Niet af te lezen uit een prijs en empirisch omstreden van omvang. |
| Af: risicovrije rente (lokaal) | -2.20% | afgeleid | -2.20%: verwachte gemiddelde korte rente in EUR over 15 jaar. Het model levert een totaalrendement; door de lokale kasrente af te trekken blijft de risicopremie over. |
| **Verwacht rendement** | **6.54%** | | risicovrij 2.20% + risicopremie 4.34% |

*Diagnostiek:* income_yield = 0.048, expected_inflation = 0.01536, local_risk_free = 0.022

#### Grondstoffen

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Rolrendement | -0.60% | markt | Geannualiseerde helling van de huidige termijnmarktcurve; negatief bij contango, positief bij backwardation (Erb & Harvey, 2006). |
| Spotprijsontwikkeling | 1.98% | afgeleid | Verwachte inflatie x doorwerking 100% plus een reële spotgroei van 0.00%. De aanname van nul reële spotgroei sluit aan bij het langetermijnbewijs voor trendloze reële grondstofprijzen (Erb & Harvey, 2006). |
| Herbalanceringsrendement | 0.40% | aanname | Meetkundig voordeel van periodiek herwegen van een mandje met lage onderlinge correlatie (Willenbrock, 2011). |
| **Verwacht rendement** | **3.98%** | | risicovrij 2.20% + risicopremie 1.78% |

*Diagnostiek:* roll_yield = -0.006, expected_inflation = 0.0198

#### Private equity (buyout)

| Bouwsteen | Bijdrage | Herkomst | Toelichting |
| --- | ---: | --- | --- |
| Risicovrije rente | 2.20% | afgeleid | z(15y) - TP(15y) van EUR_nominal: verwachte gemiddelde korte rente (Adrian, Crump & Moench, 2013). |
| Beta x risicopremie referentie | 3.57% | afgeleid | 1.25 x de risicopremie van 'Aandelen ontwikkelde markten' (2.86% boven doorgerold kasgeld). Beta boven 1 weerspiegelt de hogere financiële hefboom en de small/mid cap tilt van buyouts (L'Her e.a., 2016). |
| Illiquiditeitspremie | 0.75% | aanname | Vergoeding voor het niet kunnen verhandelen gedurende de looptijd (Ang, Papanikolaou & Westerfield, 2014). De omvang is omstreden: Phalippou (2020) vindt na correctie voor small caps nauwelijks meerrendement. |
| **Verwacht rendement** | **6.52%** | | risicovrij 2.20% + risicopremie 4.32% |

*Diagnostiek:* reference = equity_dm, reference_premium = 0.02856, beta = 1.25

## 3. Volledigheid en beperkingen

De kolom *aandeel aanname* geeft per categorie aan welk deel van de risicopremie niet uit marktprijzen komt maar uit de literatuur. Hoe hoger dit getal, hoe minder de uitkomst 'market implied' is.

| Beleggingscategorie | Aandeel aanname |
| --- | ---: |
| Liquiditeiten (EUR) | 0% |
| Staatsobligaties EMU | 3% |
| Inflatiegekoppelde staatsobligaties (EUR) | 16% |
| Bedrijfsobligaties investment grade (EUR) | 27% |
| High yield bedrijfsobligaties (EUR) | 41% |
| Emerging market debt (harde valuta) | 22% |
| Nederlandse hypotheken | 9% |
| Aandelen ontwikkelde markten | 18% |
| Aandelen Europa | 13% |
| Aandelen opkomende markten | 24% |
| Beursgenoteerd vastgoed | 10% |
| Niet-genoteerd vastgoed (core) | 18% |
| Infrastructuur (core, niet-genoteerd) | 14% |
| Grondstoffen | 13% |
| Private equity (buyout) | 18% |

