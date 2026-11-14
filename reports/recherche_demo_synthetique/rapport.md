# Programme de recherche multi-marchés — rapport

_Généré le 2026-11-13 21:35 — source : données synthétiques (marche aléatoire, graine 1) — plan : docs/RECHERCHE_PLAN.md (règles et critères fixés avant les données)._

> **Données synthétiques** : ce rapport teste le moteur, il ne dit RIEN des vrais marchés.

## En bref

**Verdict du développement : NO-GO.** Aucune hypothèse ne remplit tous les critères fixés à l'avance. On n'engage pas d'argent. Toute nouvelle idée devient une hypothèse d'un PROCHAIN cycle, testée sur de nouvelles données de contrôle (« À CREUSER »), sans réutiliser celles-ci.

- **S1** (Cassure de Donchian (suivi de tendance, D1), achat et vente, tous les symboles) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -0.92, -5.3 % par an, pire baisse 66.4 %, 1082 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 3 219 $ sur un compte standard et 32 $ sur un compte cent.
- **S2** (Momentum temporel (TSMOM, D1), ciblage de volatilité, rééquilibrage hebdomadaire) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -0.99, -1.2 % par an, pire baisse 20.4 %, 435 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 5 472 $ sur un compte standard et 55 $ sur un compte cent.
- **S3** (Retour à la moyenne sur les indices (D1), achat uniquement) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe 0.06, 0.0 % par an, pire baisse 2.6 %, 353 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 5 743 $ sur un compte standard et 57 $ sur un compte cent.
- **S4** (Cassure du range d'ouverture (intraday, M15)) : **REJETÉE** — trop peu de données ou de trades, Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -5.62, -64.9 % par an, pire baisse 98.5 %, 4022 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ sur un compte standard (il faudrait 313 $) ; jouable seulement sur un compte cent (minimum 3.13 $).

**Avec 20 $** : une stratégie n'est jouable que si 20 $ permettent de prendre le lot minimum du broker en risquant au plus 2 % par position sur au moins 95 % des signaux. Sinon, elle n'est PAS jouable en réel avec ce capital, même si elle est rentable sur 10 000 $.

Rappel : un backtest ne garantit rien. Même une hypothèse confirmée ne mène qu'au paper trading (docs/GARDE_FOUS.md §1).

## Conditions du test

- Développement : jusqu'au 2025-11-13 inclus. Le contrôle final (2025-11-14 → 2026-11-13) est verrouillé dès le chargement des données et n'a PAS été regardé.
- Capital simulé : 10 000 $ ; risque 0,5 % par position (S1, S3, S4), S2 en ciblage de volatilité ; risque ouvert <= 4 % ; levier <= 10 ; une position par symbole ; garde -3 %/jour active ; arrêt -15 % daté mais non bloquant.
- Coûts : spread = max(spread de la bougie, médiane horaire) ; achat à l'Ask ; glissement 0,5 × spread médian au marché, 1 × sur stops et ordres stop ; gap à travers un stop exécuté à l'ouverture ; swaps selon swap_mode (×3 le jour prévu) ; commission 0 ; P&L converti en USD au cours du jour.
- Univers : crypto : BTCUSD, ETHUSD ; forex : AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY ; indices : GER40, JP225, NAS100, UK100, US30, US500 ; métaux : XAGUSD, XAUUSD

## S1 — Cassure de Donchian (suivi de tendance, D1), achat et vente, tous les symboles

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.7 ans / 1082 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.92 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -3.87 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 66.4 % | <= 15 % | KO |
| 5 | Années civiles positives | 12 % | >= 60 % | KO |
| 6 | Robustesse | variantes : 40/15 -1.12, 80/30 -0.96, stop 3 ATR -0.78 ; coûts doublés : -1.98 ; symboles positifs : 2/17 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -0.92 contre 0.12 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-03-18 → 2025-11-13 (17.7 ans) |
| Symboles simulés | 17 |
| Trades / signaux refusés | 1082 / 1456 |
| Gagnants | 25.5 % |
| Résultat moyen par trade | -0.197 R |
| Rendement total | -61.6 % |
| Rendement annualisé (CAGR) | -5.27 % |
| Volatilité annualisée | 5.7 % |
| Sharpe | -0.92 |
| t-stat | -3.87 |
| Pire baisse (clôture / pire prix) | 66.3 % / 66.4 % |
| Années civiles positives | 12 % |
| Swaps payés (-) ou reçus (+) | -2 523 $ |
| Spread et glissements payés | 2 588 $ |
| Arrêt -15 % (daté, non bloquant) | 2010-12-28 00:00:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 1278 ; plafond de 4 % de risque ouvert atteint : 178.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 0.12, rendement total 10.3 % sans frais ; au même risque que la stratégie : 0.53 % par an.

Contribution par classe : crypto -2 120 $ ; forex -2 163 $ ; indices -624 $ ; métaux -1 250 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| AUDUSD | 80 | -9 $ |
| BTCUSD | 78 | -625 $ |
| ETHUSD | 88 | -1 495 $ |
| EURUSD | 83 | -402 $ |
| GBPUSD | 30 | 32 $ |
| GER40 | 66 | 516 $ |
| JP225 | 76 | -8 $ |
| NAS100 | 76 | -337 $ |
| NZDUSD | 90 | -760 $ |
| UK100 | 25 | -286 $ |
| US30 | 0 | 0 $ |
| US500 | 78 | -509 $ |
| USDCAD | 79 | -424 $ |
| USDCHF | 73 | -119 $ |
| USDJPY | 74 | -481 $ |
| XAGUSD | 41 | -535 $ |
| XAUUSD | 45 | -715 $ |

Par année : 2009 -1.0 % ; 2010 -11.8 % ; 2011 -8.5 % ; 2012 2.9 % ; 2013 -9.9 % ; 2014 -11.9 % ; 2015 0.7 % ; 2016 -3.9 % ; 2017 -10.9 % ; 2018 -0.4 % ; 2019 -12.4 % ; 2020 -0.1 % ; 2021 -2.1 % ; 2022 -10.0 % ; 2023 -11.3 % ; 2024 -4.0 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -13.5 %, médiane -5.3 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 40/15 | -1.12 | -4.70 | -6.35 % | 73.0 % | 1299 |
| 80/30 | -0.96 | -4.03 | -5.39 % | 65.8 % | 846 |
| stop 3 ATR | -0.78 | -3.29 | -3.04 % | 47.5 % | 859 |
| coûts doublés | -1.98 | -8.31 | -9.83 % | 84.6 % | 1010 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **3 219 $** sur un compte standard, **32.19 $** sur un compte cent (2538 signaux).
- Simulation à 20 $ sur un compte standard : 88 trades pris sur 6480 signaux ; capital final 14.68 $ ; pire baisse 27.6 %.
- Simulation à 20 $ sur un compte cent : 344 trades pris sur 5440 signaux ; capital final 12.71 $ ; pire baisse 41.2 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 3 219 $ sur un compte standard et 32 $ sur un compte cent.

## S2 — Momentum temporel (TSMOM, D1), ciblage de volatilité, rééquilibrage hebdomadaire

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 16.9 ans / 435 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.99 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -4.08 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 20.4 % | <= 15 % | KO |
| 5 | Années civiles positives | 25 % | >= 60 % | KO |
| 6 | Robustesse | variantes : 182 jours -0.99, 91 jours -0.68 ; coûts doublés : -1.80 ; symboles positifs : 2/17 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -0.99 contre 0.20 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2009-01-01 → 2025-11-13 (16.9 ans) |
| Symboles simulés | 17 |
| Trades / signaux refusés | 435 / 10265 |
| Gagnants | 29.4 % |
| Résultat moyen par trade | -0.233 R |
| Rendement total | -18.9 % |
| Rendement annualisé (CAGR) | -1.23 % |
| Volatilité annualisée | 1.2 % |
| Sharpe | -0.99 |
| t-stat | -4.08 |
| Pire baisse (clôture / pire prix) | 20.3 % / 20.4 % |
| Années civiles positives | 25 % |
| Swaps payés (-) ou reçus (+) | -590 $ |
| Spread et glissements payés | 594 $ |
| Arrêt -15 % (daté, non bloquant) | 2023-03-20 00:00:00 |
| Rééquilibrages hebdomadaires | 932 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 10265.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 0.20, rendement total 18.9 % sans frais ; au même risque que la stratégie : 0.24 % par an.

Contribution par classe : crypto -1 121 $ ; forex -370 $ ; indices -395 $ ; métaux 0 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| AUDUSD | 20 | -159 $ |
| BTCUSD | 45 | -348 $ |
| ETHUSD | 55 | -773 $ |
| EURUSD | 71 | -192 $ |
| GBPUSD | 0 | 0 $ |
| GER40 | 54 | -188 $ |
| JP225 | 57 | -176 $ |
| NAS100 | 2 | 91 $ |
| NZDUSD | 44 | -9 $ |
| UK100 | 0 | 0 $ |
| US30 | 0 | 0 $ |
| US500 | 58 | -122 $ |
| USDCAD | 25 | -30 $ |
| USDCHF | 4 | 20 $ |
| USDJPY | 0 | 0 $ |
| XAGUSD | 0 | 0 $ |
| XAUUSD | 0 | 0 $ |

Par année : 2009 -0.6 % ; 2010 0.4 % ; 2011 -0.7 % ; 2012 0.1 % ; 2013 -0.6 % ; 2014 1.1 % ; 2015 -0.5 % ; 2016 -1.8 % ; 2017 -3.6 % ; 2018 0.5 % ; 2019 -4.4 % ; 2020 -0.2 % ; 2021 -0.7 % ; 2022 -2.8 % ; 2023 -4.3 % ; 2024 -2.9 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -3.3 %, médiane -1.3 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 182 jours | -0.99 | -4.14 | -1.28 % | 23.9 % | 555 |
| 91 jours | -0.68 | -2.87 | -0.88 % | 17.5 % | 671 |
| coûts doublés | -1.80 | -7.41 | -2.18 % | 31.5 % | 418 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **5 472 $** sur un compte standard, **54.72 $** sur un compte cent (14229 signaux).
- Simulation à 20 $ sur un compte standard : 39 trades pris sur 14229 signaux ; capital final 18.93 $ ; pire baisse 5.8 %.
- Simulation à 20 $ sur un compte cent : 157 trades pris sur 14229 signaux ; capital final 17.29 $ ; pire baisse 15.8 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 5 472 $ sur un compte standard et 55 $ sur un compte cent.

## S3 — Retour à la moyenne sur les indices (D1), achat uniquement

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.1 ans / 353 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.06 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | 0.26 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 2.6 % | <= 15 % | OK |
| 5 | Années civiles positives | 44 % | >= 60 % | KO |
| 6 | Robustesse | variantes : RSI < 5 -0.15, RSI < 20 -0.25, sortie SMA10 -0.11 ; coûts doublés : -0.35 | variantes >= 0.3 ; coûts doublés >= 0.3 | KO |
| 7 | Mieux que la référence passive (US500 acheté et conservé) | 0.06 contre 0.20 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-10-06 → 2025-11-13 (17.1 ans) |
| Symboles simulés | 6 |
| Trades / signaux refusés | 353 / 448 |
| Gagnants | 63.2 % |
| Résultat moyen par trade | 0.005 R |
| Rendement total | 0.8 % |
| Rendement annualisé (CAGR) | 0.05 % |
| Volatilité annualisée | 0.8 % |
| Sharpe | 0.06 |
| t-stat | 0.26 |
| Pire baisse (clôture / pire prix) | 2.5 % / 2.6 % |
| Années civiles positives | 44 % |
| Swaps payés (-) ou reçus (+) | -168 $ |
| Spread et glissements payés | 399 $ |
| Arrêt -15 % (daté, non bloquant) | jamais atteint |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 448.

Référence passive (US500 acheté et conservé) : Sharpe 0.20, rendement total 39.1 % sans frais ; au même risque que la stratégie : 0.16 % par an.

Contribution par classe : indices 82 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 58 | -32 $ |
| JP225 | 73 | -24 $ |
| NAS100 | 106 | 212 $ |
| UK100 | 8 | -32 $ |
| US30 | 0 | 0 $ |
| US500 | 108 | -42 $ |

Par année : 2009 0.1 % ; 2010 -0.6 % ; 2011 2.5 % ; 2012 -0.6 % ; 2013 -0.1 % ; 2014 -0.3 % ; 2015 0.7 % ; 2016 -0.3 % ; 2017 -1.0 % ; 2018 0.1 % ; 2019 0.5 % ; 2020 -1.1 % ; 2021 0.9 % ; 2022 -0.1 % ; 2023 -0.0 % ; 2024 0.0 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -1.3 %, médiane 0.1 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| RSI < 5 | -0.15 | -0.63 | -0.09 % | 2.5 % | 175 |
| RSI < 20 | -0.25 | -1.03 | -0.28 % | 7.7 % | 649 |
| sortie SMA10 | -0.11 | -0.47 | -0.11 % | 4.1 % | 330 |
| coûts doublés | -0.35 | -1.45 | -0.29 % | 6.1 % | 353 |

Pour information seulement (hors critères) — même test sur les autres classes : Sharpe -1.03, t-stat -4.25, 740 trades.

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **5 743 $** sur un compte standard, **57.43 $** sur un compte cent (801 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 1183 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 159 trades pris sur 1040 signaux ; capital final 20.15 $ ; pire baisse 1.4 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 5 743 $ sur un compte standard et 57 $ sur un compte cent.

## S4 — Cassure du range d'ouverture (intraday, M15)

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 4.0 ans / 4022 | >= 4 ans / >= 100 | KO |
| 2 | Sharpe annualisé après coûts | -5.62 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -11.22 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 98.5 % | <= 15 % | KO |
| 5 | Années civiles positives | 0 % | >= 60 % | KO |
| 6 | Robustesse | variantes : range 2 bougies -5.82, objectif 2R -6.54 ; coûts doublés : -7.81 ; symboles positifs : 1/6 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -5.62 contre 0.06 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2021-11-15 → 2025-11-13 (4.0 ans) |
| Symboles simulés | 6 |
| Trades / signaux refusés | 4022 / 2221 |
| Gagnants | 29.8 % |
| Résultat moyen par trade | -0.232 R |
| Rendement total | -98.5 % |
| Rendement annualisé (CAGR) | -64.89 % |
| Volatilité annualisée | 18.3 % |
| Sharpe | -5.62 |
| t-stat | -11.22 |
| Pire baisse (clôture / pire prix) | 98.5 % / 98.5 % |
| Années civiles positives | 0 % |
| Swaps payés (-) ou reçus (+) | 0 $ |
| Spread et glissements payés | 10 862 $ |
| Arrêt -15 % (daté, non bloquant) | 2022-01-10 11:30:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 2221.

Jours ignorés (S4) : range_trop_etroit : 12.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 0.06, rendement total 0.7 % sans frais ; au même risque que la stratégie : -0.58 % par an.

Contribution par classe : forex -1 254 $ ; indices -6 769 $ ; métaux -1 824 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| EURUSD | 809 | -1 708 $ |
| GBPUSD | 385 | 454 $ |
| GER40 | 936 | -3 060 $ |
| NAS100 | 591 | -1 644 $ |
| US500 | 900 | -2 065 $ |
| XAUUSD | 401 | -1 824 $ |

Par année : 2022 -82.7 % ; 2023 -67.6 % ; 2024 -59.5 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -75.4 %, médiane -65.1 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| range 2 bougies | -5.82 | -11.64 | -68.92 % | 99.1 % | 3312 |
| objectif 2R | -6.54 | -13.08 | -64.43 % | 98.4 % | 4258 |
| coûts doublés | -7.81 | -15.60 | -65.96 % | 98.6 % | 2391 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **313 $** sur un compte standard, **3.13 $** sur un compte cent (6252 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 6252 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 2518 trades pris sur 6252 signaux ; capital final 1.16 $ ; pire baisse 94.3 %.
- Conclusion : pas jouable avec 20 $ sur un compte standard (il faudrait 313 $) ; jouable seulement sur un compte cent (minimum 3.13 $).

## Interprétations prudentes des règles du plan

- Signal à la clôture, exécution à l'ouverture suivante du même symbole ; sur une même ouverture, toutes les sorties passent avant les entrées, et les entrées sont traitées dans l'ordre alphabétique des symboles (cela compte seulement quand un plafond est atteint).
- Spread à l'ouverture d'une bougie D1 : le plus grand du spread de la bougie D1, du spread de la première bougie H1 du jour et de la médiane de spread de cette heure-là (le premier tick du jour est souvent cher).
- Bougies D1 : l'ordre des prix dans la journée est inconnu ; un stop touché dans la journée est exécuté au stop moins un glissement, au prix d'ouverture en cas de gap ; l'equity « au pire prix » prend en même temps le pire prix de toutes les positions.
- Référence de la perte journalière (-3 %) : equity à minuit (une perte latente d'avant minuit n'est pas une perte du jour). L'arrêt à -15 % est daté mais ne stoppe pas la simulation (mode évaluation).
- Risque ouvert : risque initial en USD des positions (perte au stop, glissement compris), plus les ordres S4 en attente. Le plafond de 4 % s'applique aussi à S2, par réduction proportionnelle des positions rééquilibrées (comme le plafond de levier).
- S2 : rééquilibrage à l'ouverture de la première bougie de chaque semaine ISO avec les valeurs de la clôture précédente ; N = symboles dont le signal est calculable ; le stop de 4 ATR est posé à l'ouverture de la position et n'est pas déplacé par un ajustement de taille ; « changements de position » = positions ouvertes (les ajustements de taille ne sont pas comptés).
- S3 : la sortie après 10 bougies se fait à l'ouverture qui suit la 10e clôture en position (bougie d'entrée comprise).
- S4 : ordres valables sur les bougies entièrement avant l'échéance ; si les deux niveaux sont touchés dans la même bougie, on suppose le pire (entrée puis stop dans la même bougie) ; l'objectif 2R (variante) vaut 2 × la hauteur du range et n'est jamais pris dans la bougie d'entrée ; la clôture forcée se fait à l'ouverture de la bougie M15 qui contient 21:55 ou 22:45 (21:45 ou 22:45) ; taille calculée à la pose des ordres.
- Coûts doublés : spread et glissements × 2, swaps × 2 quand ils coûtent (un swap créditeur n'est pas doublé).
- Conversion en USD au cours de clôture de la veille de la paire de conversion (cours connu pendant tout le jour) ; une devise non convertible exclut le symbole.
- Swap : nuit facturée si le symbole a coté ce jour-là et que la position est ouverte à la clôture ; nuit triple le jour swap_rollover3days ; pour la crypto, cela peut compter le week-end deux fois (prudent).
- Années civiles complètes seulement ; un symbole sans trade ne compte pas comme « contribuant positivement ».
- Référence passive : panier équipondéré des mêmes symboles, sans frais ni swap (référence plus exigeante) ; S3 : US500 seul. On compare les Sharpe (la mise au même risque ne change pas le Sharpe).
- Capital minimum : plus petit capital qui permet de prendre au moins 95 % des signaux au lot minimum avec un risque <= 2 % ET un levier <= 10 (un signal répété plusieurs jours compte à chaque fois).

## Limites connues

- Seuls les swaps ACTUELS sont connus ; ils sont appliqués à tout l'historique.
- Les médianes de spread viennent des 10 derniers jours ouvrés (mesurés pendant la période de contrôle) ; ce sont des paramètres de coût, pas des prix.
- S4 : les ouvertures de New York (16:30 serveur) sont décalées d'une heure 2 à 3 semaines par an (changements d'heure américains), comme prévu par le plan.
- Le moteur ne modélise ni appel de marge, ni rejet d'ordre par le broker, ni distance minimale de stop, ni jours fériés autrement que par l'absence de bougie.
- Résultats passés : même une hypothèse confirmée ne garantit rien ; elle ne mène qu'au paper trading.

## Temps de calcul (dernière commande)

chargement 2.3 s, S1_base 3.8 s, S1_robustesse 4.0 s, S1_capital 1.6 s, S2_base 1.4 s, S2_robustesse 2.5 s, S2_capital 1.4 s, S3_base 1.5 s, S3_robustesse 1.4 s, S3_capital 0.6 s, S4_base 5.2 s, S4_robustesse 13.1 s, S4_capital 8.3 s, total_commande 47.5 s
