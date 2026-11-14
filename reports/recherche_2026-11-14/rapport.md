# Programme de recherche multi-marchés — rapport

_Généré le 2026-11-14 07:46 — source : données MT5 (/sessions/laughing-busy-cori/mnt/outputs/TradingBot/data/univers) — plan : docs/RECHERCHE_PLAN.md (règles et critères fixés avant les données)._

## En bref

**Verdict du développement : NO-GO.** Aucune hypothèse ne remplit tous les critères fixés à l'avance. On n'engage pas d'argent. Toute nouvelle idée devient une hypothèse d'un PROCHAIN cycle, testée sur de nouvelles données de contrôle (« À CREUSER »), sans réutiliser celles-ci.

- **S1** (Cassure de Donchian (suivi de tendance, D1), achat et vente, tous les symboles) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -0.15, -1.8 % par an, pire baisse 47.2 %, 825 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 34 855 $ sur un compte standard et 349 $ sur un compte cent.
- **S2** (Momentum temporel (TSMOM, D1), ciblage de volatilité, rééquilibrage hebdomadaire) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -0.11, -2.4 % par an, pire baisse 48.9 %, 684 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 10 476 $ sur un compte standard et 105 $ sur un compte cent.
- **S3** (Retour à la moyenne sur les indices (D1), achat uniquement) : **REJETÉE** — t-stat trop faible, pas mieux que la référence passive. Sharpe 0.61, 0.7 % par an, pire baisse 2.0 %, 187 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ : il faudrait 63 674 $ sur un compte standard et 637 $ sur un compte cent.
- **S4** (Cassure du range d'ouverture (intraday, M15)) : **REJETÉE** — Sharpe trop faible, t-stat trop faible, pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la référence passive. Sharpe -1.20, -28.3 % par an, pire baisse 83.5 %, 6229 trades. Faisabilité avec 20 $ (taille des positions seulement, pas la rentabilité) : pas jouable avec 20 $ sur un compte standard (il faudrait 831 $) ; jouable seulement sur un compte cent (minimum 8.31 $).

**Avec 20 $** : une stratégie n'est jouable que si 20 $ permettent de prendre le lot minimum du broker en risquant au plus 2 % par position sur au moins 95 % des signaux. Sinon, elle n'est PAS jouable en réel avec ce capital, même si elle est rentable sur 10 000 $.

Rappel : un backtest ne garantit rien. Même une hypothèse confirmée ne mène qu'au paper trading (docs/GARDE_FOUS.md §1).

## Conditions du test

- Développement : jusqu'au 2025-11-13 inclus. Le contrôle final (2025-11-14 → 2026-11-13) est verrouillé dès le chargement des données et n'a PAS été regardé.
- Capital simulé : 10 000 $ ; risque 0,5 % par position (S1, S3, S4), S2 en ciblage de volatilité ; risque ouvert <= 4 % ; levier <= 10 ; une position par symbole ; garde -3 %/jour active ; arrêt -15 % daté mais non bloquant.
- Coûts : spread = max(spread de la bougie, médiane horaire) ; achat à l'Ask ; glissement 0,5 × spread médian au marché, 1 × sur stops et ordres stop ; gap à travers un stop exécuté à l'ouverture ; swaps selon swap_mode (×3 le jour prévu) ; commission 0 ; P&L converti en USD au cours du jour.
- Univers : forex : AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY ; indices : GER40, JP225, NAS100, US30, US500 ; métaux : XAGUSD, XAUUSD
- Absents chez le broker (retirés) : BTCUSD (introuvable chez le broker : alias cherchés BTCUSD, XBTUSD, BITCOIN) ; ETHUSD (introuvable chez le broker : alias cherchés ETHUSD, ETHEREUM)
- Exclus (données ou coûts inutilisables) : UK100 (pas de bougies D1 dans la période autorisée)

## S1 — Cassure de Donchian (suivi de tendance, D1), achat et vente, tous les symboles

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 18.8 ans / 825 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.15 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -0.64 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 47.2 % | <= 15 % | KO |
| 5 | Années civiles positives | 41 % | >= 60 % | KO |
| 6 | Robustesse | variantes : 40/15 -0.07, 80/30 0.03, stop 3 ATR -0.16 ; coûts doublés : -0.37 ; symboles positifs : 4/14 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -0.15 contre 0.63 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2007-02-01 → 2025-11-13 (18.8 ans) |
| Symboles simulés | 14 |
| Trades / signaux refusés | 825 / 724 |
| Gagnants | 26.9 % |
| Résultat moyen par trade | -0.077 R |
| Rendement total | -28.7 % |
| Rendement annualisé (CAGR) | -1.79 % |
| Volatilité annualisée | 9.3 % |
| Sharpe | -0.15 |
| t-stat | -0.64 |
| Pire baisse (clôture / pire prix) | 47.0 % / 47.2 % |
| Années civiles positives | 41 % |
| Swaps payés (-) ou reçus (+) | -2 637 $ |
| Spread et glissements payés | 764 $ |
| Arrêt -15 % (daté, non bloquant) | 2014-03-25 00:00:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 684 ; plafond de 4 % de risque ouvert atteint : 40.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 0.63, rendement total 128.1 % sans frais ; au même risque que la stratégie : 5.54 % par an.

Contribution par classe : forex -2 228 $ ; indices -1 264 $ ; métaux 621 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| AUDUSD | 92 | -655 $ |
| EURUSD | 80 | 884 $ |
| GBPUSD | 88 | -468 $ |
| GER40 | 40 | -294 $ |
| JP225 | 0 | 0 $ |
| NAS100 | 1 | 157 $ |
| NZDUSD | 88 | -535 $ |
| US30 | 33 | -550 $ |
| US500 | 57 | -578 $ |
| USDCAD | 83 | -282 $ |
| USDCHF | 84 | -830 $ |
| USDJPY | 86 | -342 $ |
| XAGUSD | 36 | 38 $ |
| XAUUSD | 57 | 583 $ |

Par année : 2008 13.2 % ; 2009 0.0 % ; 2010 6.2 % ; 2011 -9.4 % ; 2012 -3.5 % ; 2013 5.2 % ; 2014 7.0 % ; 2015 -11.7 % ; 2016 -3.1 % ; 2017 -2.1 % ; 2018 1.4 % ; 2019 -12.3 % ; 2020 2.0 % ; 2021 -10.9 % ; 2022 -1.9 % ; 2023 -4.4 % ; 2024 -5.5 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -13.5 %, médiane -2.0 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 40/15 | -0.07 | -0.32 | -1.16 % | 36.2 % | 1010 |
| 80/30 | 0.03 | 0.14 | -0.17 % | 41.0 % | 618 |
| stop 3 ATR | -0.16 | -0.71 | -1.18 % | 32.3 % | 658 |
| coûts doublés | -0.37 | -1.62 | -3.61 % | 58.0 % | 795 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **34 855 $** sur un compte standard, **348.55 $** sur un compte cent (1549 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 4616 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 101 trades pris sur 4172 signaux ; capital final 18.10 $ ; pire baisse 17.1 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 34 855 $ sur un compte standard et 349 $ sur un compte cent.

## S2 — Momentum temporel (TSMOM, D1), ciblage de volatilité, rééquilibrage hebdomadaire

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 18.0 ans / 684 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.11 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -0.48 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 48.9 % | <= 15 % | KO |
| 5 | Années civiles positives | 47 % | >= 60 % | KO |
| 6 | Robustesse | variantes : 182 jours 0.18, 91 jours 0.02 ; coûts doublés : -0.33 ; symboles positifs : 4/14 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -0.11 contre 0.63 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2007-11-16 → 2025-11-13 (18.0 ans) |
| Symboles simulés | 14 |
| Trades / signaux refusés | 684 / 1916 |
| Gagnants | 33.5 % |
| Résultat moyen par trade | -0.178 R |
| Rendement total | -35.6 % |
| Rendement annualisé (CAGR) | -2.42 % |
| Volatilité annualisée | 13.5 % |
| Sharpe | -0.11 |
| t-stat | -0.48 |
| Pire baisse (clôture / pire prix) | 48.6 % / 48.9 % |
| Années civiles positives | 47 % |
| Swaps payés (-) ou reçus (+) | -4 320 $ |
| Spread et glissements payés | 814 $ |
| Arrêt -15 % (daté, non bloquant) | 2008-09-08 00:00:00 |
| Rééquilibrages hebdomadaires | 1027 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 1916.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 0.63, rendement total 121.5 % sans frais ; au même risque que la stratégie : 7.84 % par an.

Contribution par classe : forex -4 555 $ ; indices 707 $ ; métaux 287 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| AUDUSD | 63 | -1 787 $ |
| EURUSD | 70 | -908 $ |
| GBPUSD | 79 | -634 $ |
| GER40 | 38 | -135 $ |
| JP225 | 0 | 0 $ |
| NAS100 | 0 | 0 $ |
| NZDUSD | 76 | -806 $ |
| US30 | 11 | 449 $ |
| US500 | 25 | 393 $ |
| USDCAD | 72 | -701 $ |
| USDCHF | 83 | -1 271 $ |
| USDJPY | 71 | 1 552 $ |
| XAGUSD | 25 | 478 $ |
| XAUUSD | 71 | -191 $ |

Par année : 2008 12.7 % ; 2009 -11.4 % ; 2010 5.7 % ; 2011 -1.6 % ; 2012 -14.3 % ; 2013 9.6 % ; 2014 10.6 % ; 2015 5.3 % ; 2016 -17.1 % ; 2017 4.0 % ; 2018 -18.2 % ; 2019 -8.4 % ; 2020 5.8 % ; 2021 -5.4 % ; 2022 14.0 % ; 2023 -10.0 % ; 2024 -4.3 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -20.8 %, médiane -2.8 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| 182 jours | 0.18 | 0.75 | 1.52 % | 52.5 % | 939 |
| 91 jours | 0.02 | 0.07 | -0.79 % | 50.7 % | 1299 |
| coûts doublés | -0.33 | -1.40 | -4.88 % | 66.1 % | 665 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **10 476 $** sur un compte standard, **104.76 $** sur un compte cent (10651 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 10651 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 180 trades pris sur 10651 signaux ; capital final 19.78 $ ; pire baisse 14.8 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 10 476 $ sur un compte standard et 105 $ sur un compte cent.

## S3 — Retour à la moyenne sur les indices (D1), achat uniquement

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 12.5 ans / 187 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.61 | >= 0.5 | OK |
| 3 | t-stat du rendement journalier moyen | 2.16 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 2.0 % | <= 15 % | OK |
| 5 | Années civiles positives | 82 % | >= 60 % | OK |
| 6 | Robustesse | variantes : RSI < 5 0.32, RSI < 20 0.58, sortie SMA10 0.75 ; coûts doublés : 0.39 | variantes >= 0.3 ; coûts doublés >= 0.3 | OK |
| 7 | Mieux que la référence passive (US500 acheté et conservé) | 0.61 contre 0.74 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2013-05-14 → 2025-11-13 (12.5 ans) |
| Symboles simulés | 5 |
| Trades / signaux refusés | 187 / 391 |
| Gagnants | 73.3 % |
| Résultat moyen par trade | 0.098 R |
| Rendement total | 8.6 % |
| Rendement annualisé (CAGR) | 0.66 % |
| Volatilité annualisée | 1.1 % |
| Sharpe | 0.61 |
| t-stat | 2.16 |
| Pire baisse (clôture / pire prix) | 1.8 % / 2.0 % |
| Années civiles positives | 82 % |
| Swaps payés (-) ou reçus (+) | -136 $ |
| Spread et glissements payés | 107 $ |
| Arrêt -15 % (daté, non bloquant) | jamais atteint |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 391.

Référence passive (US500 acheté et conservé) : Sharpe 0.74, rendement total 308.4 % sans frais ; au même risque que la stratégie : 0.81 % par an.

Contribution par classe : indices 861 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 34 | 86 $ |
| JP225 | 0 | 0 $ |
| NAS100 | 0 | 0 $ |
| US30 | 39 | 59 $ |
| US500 | 114 | 715 $ |

Par année : 2014 0.4 % ; 2015 0.3 % ; 2016 0.7 % ; 2017 2.6 % ; 2018 -1.0 % ; 2019 0.4 % ; 2020 0.3 % ; 2021 0.6 % ; 2022 -0.3 % ; 2023 0.0 % ; 2024 2.3 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -0.8 %, médiane 0.6 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| RSI < 5 | 0.32 | 1.14 | 0.26 % | 2.2 % | 89 |
| RSI < 20 | 0.58 | 2.06 | 0.86 % | 2.2 % | 341 |
| sortie SMA10 | 0.75 | 2.64 | 0.99 % | 2.1 % | 183 |
| coûts doublés | 0.39 | 1.38 | 0.42 % | 2.2 % | 185 |

Pour information seulement (hors critères) — même test sur les autres classes : Sharpe -0.08, t-stat -0.36, 752 trades.

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **63 674 $** sur un compte standard, **636.74 $** sur un compte cent (578 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 734 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 57 trades pris sur 696 signaux ; capital final 20.56 $ ; pire baisse 1.3 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 63 674 $ sur un compte standard et 637 $ sur un compte cent.

## S4 — Cassure du range d'ouverture (intraday, M15)

**REJETÉE**

| n° | critère (plan §7) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 5.0 ans / 6229 | >= 4 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -1.20 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -2.69 | >= 2.5 | KO |
| 4 | Drawdown max au pire prix | 83.5 % | <= 15 % | KO |
| 5 | Années civiles positives | 25 % | >= 60 % | KO |
| 6 | Robustesse | variantes : range 2 bougies -0.99, objectif 2R -1.74 ; coûts doublés : -3.45 ; symboles positifs : 2/6 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence passive (panier équipondéré acheté et conservé) | -1.20 contre 1.00 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2020-11-16 → 2025-11-13 (5.0 ans) |
| Symboles simulés | 6 |
| Trades / signaux refusés | 6229 / 671 |
| Gagnants | 37.4 % |
| Résultat moyen par trade | -0.050 R |
| Rendement total | -81.0 % |
| Rendement annualisé (CAGR) | -28.28 % |
| Volatilité annualisée | 25.0 % |
| Sharpe | -1.20 |
| t-stat | -2.69 |
| Pire baisse (clôture / pire prix) | 83.4 % / 83.5 % |
| Années civiles positives | 25 % |
| Swaps payés (-) ou reçus (+) | 0 $ |
| Spread et glissements payés | 11 461 $ |
| Arrêt -15 % (daté, non bloquant) | 2020-12-14 17:30:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 671.

Jours ignorés (S4) : range_incomplet : 47 ; range_trop_etroit : 117.

Référence passive (panier équipondéré acheté et conservé) : Sharpe 1.00, rendement total 60.9 % sans frais ; au même risque que la stratégie : 24.57 % par an.

Contribution par classe : forex -6 064 $ ; indices 1 133 $ ; métaux -3 166 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| EURUSD | 1290 | -3 684 $ |
| GBPUSD | 1290 | -2 379 $ |
| GER40 | 967 | 1 253 $ |
| NAS100 | 508 | 137 $ |
| US500 | 1114 | -257 $ |
| XAUUSD | 1060 | -3 166 $ |

Par année : 2021 -38.2 % ; 2022 8.4 % ; 2023 -33.1 % ; 2024 -46.6 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -51.9 %, médiane -28.1 % (seuil du contrôle final).

Robustesse (pour information sur la stabilité ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| range 2 bougies | -0.99 | -2.22 | -28.00 % | 81.6 % | 6192 |
| objectif 2R | -1.74 | -3.89 | -30.10 % | 83.6 % | 6205 |
| coûts doublés | -3.45 | -7.71 | -47.21 % | 95.9 % | 4434 |

Petit capital (plan §6) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **831 $** sur un compte standard, **8.31 $** sur un compte cent (7047 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 7047 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 3873 trades pris sur 7047 signaux ; capital final 4.95 $ ; pire baisse 75.6 %.
- Conclusion : pas jouable avec 20 $ sur un compte standard (il faudrait 831 $) ; jouable seulement sur un compte cent (minimum 8.31 $).

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

chargement 13.0 s, S1_robustesse 2.6 s, S1_capital 1.6 s, S2_robustesse 2.2 s, S2_capital 1.7 s, S3_robustesse 0.7 s, S3_capital 0.5 s, S4_robustesse 15.0 s, S4_capital 13.8 s, total_commande 51.5 s
