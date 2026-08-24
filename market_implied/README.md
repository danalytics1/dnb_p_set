# `market_implied` — market-implied rendementsverwachtingen

Verwachte rendementen per beleggingscategorie, afgeleid uit **huidige
marktprijzen**, opgebouwd uit bouwstenen:

```
Verwacht rendement = risicovrije rente + risicopremie
```

De risicovrije rente volgt voor **alle** categorieën dezelfde logica; de
risicopremie wordt per categorie uit categoriespecifieke bouwstenen opgebouwd.
Horizons: 5 jaar (middellang) en 15 jaar (lang).

Deze package staat **volledig los van `dnb_p_set`**: geen imports in beide
richtingen, geen DNB-scenariodata, eigen tests. Afhankelijkheden zijn alleen
`numpy` en `pandas`; de map is bedoeld om als geheel gelicht te kunnen worden.
`market_implied/tests/test_separation.py` bewaakt dat.

## Snel starten

```console
$ python -m market_implied                          # de premietabel
$ python -m market_implied --format summary         # inclusief rekenkundig rendement
$ python -m market_implied --format markdown -o rapport.md
$ python -m market_implied --csv-dir uitvoer/
$ python -m market_implied --no-valuation           # pure carry, zonder convergentie
$ python -m market_implied --rf-convention spot     # andere splitsing risicovrij/premie
```

```python
from market_implied import build_expectations, load_market_snapshot, load_universe

snapshot = load_market_snapshot("market_implied/data/market_snapshot_example.json")
universe = load_universe("market_implied/data/universe_default.json")
result = build_expectations(snapshot, universe)

result.premium_matrix()     # risicopremie per categorie x horizon
result.summary_table()      # inclusief verwacht rendement en volatiliteit
result.blocks_table()       # elke bouwsteen, met herkomst en toelichting
result.diagnostics_table()  # indexyields, impliciete kostenvoet eigen vermogen
```

> **Let op.** `data/market_snapshot_example.json` bevat *illustratieve* cijfers,
> geen werkelijke marktdata. Vervang het door een echte marktopname voordat de
> uitkomsten ergens voor gebruikt worden.

## Voorbeelduitvoer

Op basis van de meegeleverde voorbeeldopname (EUR, valuta-afgedekt):

| Beleggingscategorie | Risicopremie 5j | Risicopremie 15j | E\[R] 5j | E\[R] 15j |
|---|---:|---:|---:|---:|
| Liquiditeiten (EUR) | 0,00% | 0,00% | 2,15% | 2,20% |
| Staatsobligaties EMU | 0,58% | 0,58% | 2,73% | 2,78% |
| Inflatiegekoppelde staatsobligaties | 0,30% | 0,30% | 2,45% | 2,50% |
| Bedrijfsobligaties investment grade | 0,73% | 0,80% | 2,88% | 3,00% |
| High yield bedrijfsobligaties | 1,15% | 1,34% | 3,30% | 3,54% |
| Emerging market debt (harde valuta) | 2,59% | 2,78% | 4,74% | 4,98% |
| Nederlandse hypotheken | 1,66% | 1,66% | 3,81% | 3,86% |
| Aandelen ontwikkelde markten | 2,79% | 2,86% | 4,94% | 5,06% |
| Aandelen Europa | 4,84% | 4,81% | 6,99% | 7,01% |
| Aandelen opkomende markten | 4,14% | 4,06% | 6,29% | 6,26% |
| Beursgenoteerd vastgoed | 4,00% | 3,66% | 6,15% | 5,86% |
| Niet-genoteerd vastgoed (core) | 3,02% | 3,25% | 5,17% | 5,45% |
| Infrastructuur (core) | 4,37% | 4,34% | 6,52% | 6,54% |
| Grondstoffen | 1,87% | 1,78% | 4,02% | 3,98% |
| Private equity (buyout) | 4,23% | 4,32% | 6,38% | 6,52% |

## Bouwstenen per categorie

| Categorie | Model | Opbouw van de risicopremie |
|---|---|---|
| Liquiditeiten | `cash` | — (definitie van risicovrij) |
| Staatsobligaties | `nominal_bond` | termijnpremie + landenspread − verwacht verlies |
| Inflatiegekoppeld | `index_linked_bond` | termijnpremie − inflatierisicopremie + liquiditeitspremie |
| IG / HY / EMD / hypotheken | `spread_product` | termijnpremie + OAS + spreadwaardering − verwacht kredietverlies − afwaarderingsdrag |
| Aandelen, genoteerd vastgoed | `grinold_kroner` | dividend + inkoop + inflatie + reële groei + waardering − lokaal kasgeld |
| Niet-genoteerd vastgoed, infra | `yield_and_growth` | direct rendement − capex + inflatie + groei + yield shift + illiquiditeit − lokaal kasgeld |
| Grondstoffen | `commodities` | rolrendement + spotontwikkeling + herbalancering |
| Private equity | `levered_beta` | β × premie referentie + illiquiditeit − kosten |

De volledige onderbouwing met literatuurverwijzingen per bouwsteen staat in
[`docs/methodology.md`](docs/methodology.md).

## Structuur

```
market_implied/
├── curves.py        zero curves, interpolatie, forwards, par-bootstrap
├── riskfree.py      de gedeelde risicovrije bouwsteen (één plek, alle categorieën)
├── blocks.py        BuildingBlock / ReturnBuildUp primitieven
├── marketdata.py    marktopname: laden en opvragen
├── universe.py      beleggingscategorieën en hun modelparameters
├── models/          bonds, credit, equity, real_assets, alternatives
├── engine.py        evalueert alles, lost afhankelijkheden op
├── report.py        tekst, markdown, CSV
├── cli.py           python -m market_implied
├── data/            marktopname + universumconfiguratie (JSON)
├── docs/            methodologische verantwoording
└── tests/           134 tests
```

## Een categorie toevoegen of aanpassen

Past een bestaand model? Voeg dan alleen een blok toe aan
`data/universe_default.json`:

```json
{
  "key": "credit_ig_usd",
  "name": "Bedrijfsobligaties investment grade (USD)",
  "category": "Vastrentend",
  "model": "spread_product",
  "currency": "USD",
  "volatility": 0.055,
  "params": {
    "quotes": "credit.usd_ig",
    "default_rate": 0.0010,
    "recovery_rate": 0.40,
    "downgrade_drag": 0.0025,
    "spread_reversion_half_life": 3.0
  }
}
```

Nieuwe logica nodig? Schrijf een functie en registreer die:

```python
from market_implied.models.base import AssetSpec, ModelContext, register
from market_implied.blocks import BuildingBlock, MARKET

@register("mijn_model")
def build(spec: AssetSpec, ctx: ModelContext):
    blocks = [BuildingBlock("carry", 0.01, source=MARKET, label="Carry")]
    return ctx.finish(spec, blocks)
```

Eén regel: elk premieblok is een **meerrendement boven lokaal doorgerold
kasgeld**. `ctx.finish()` zet daar het risicovrije blok bovenop en controleert
dat de bouwstenen exact optellen tot het verwachte rendement.

## Tests

```console
$ python -m pytest market_implied/tests -q
```

Naast de gebruikelijke unit tests worden drie structurele eigenschappen
bewaakt:

- **Optelling.** Elke `ReturnBuildUp` controleert bij constructie dat de
  bouwstenen exact optellen tot `risicovrij + risicopremie`.
- **Conventie-invariantie.** Verwachte rendementen zijn tot op machineprecisie
  identiek onder `rolled_cash` en `spot`; alleen de splitsing verschuift.
- **Curve-verankering.** Een obligatie met duration gelijk aan de horizon
  levert exact de zerocouponrente van de curve op.
