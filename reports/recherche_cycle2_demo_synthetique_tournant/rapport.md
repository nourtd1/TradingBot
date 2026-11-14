# Programme de recherche — cycle 2 — rapport

_Généré le 2026-11-14 08:13 — source : données synthétiques (marche aléatoire, graine 1, effet tournant du mois injecté sur les indices) — plan : docs/RECHERCHE_PLAN_CYCLE2.md (règles et critères fixés avant les calculs)._

> **Données synthétiques** : ce rapport teste le moteur, il ne dit RIEN des vrais marchés.

## En bref

**Contrôle final : CONFIRMÉ(S) : test des nouveaux marchés puis au moins 3 mois de démo.**
- C1 : CONFIRMÉE (suite : test des nouveaux marchés, puis au moins 3 mois de démo) (rendement 12 mois 0.5 %, 5e centile attendu -0.4 %, pire baisse 1.1 %).

**Test des nouveaux marchés (bloquant si Sharpe négatif) :**
- C1 : OK (informatif) : peut passer en démo si le contrôle final est confirmé (Sharpe 0.80, 214 trades sur AUS200).

**Verdict du développement (cycle 2) : EN ATTENTE DU CONTRÔLE FINAL.** Ces hypothèses passent tous les critères de développement du cycle 2. Elles ne sont PAS jouables : il faut choisir au plus deux finalistes (P compte pour un), les figer, les calculer UNE SEULE FOIS sur le contrôle final, passer le test des nouveaux marchés, puis au moins 3 mois de démo.

- **C1** (Tournant du mois sur les indices (D1), achat uniquement) : **RETENUE pour le contrôle final**. Sharpe 1.23, t-stat 5.19, 1.5 % par an, pire baisse 2.8 %, 711 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 11 192 $ sur un compte standard et 112 $ sur un compte cent.
- **C2** (Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien) : **REJETÉE** — Sharpe trop faible, t-stat trop faible (< 3,0), pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la même méthode toujours acheteuse. Sharpe -0.12, t-stat -0.51, -0.9 % par an, pire baisse 28.9 %, 312 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 14 869 $ sur un compte standard et 149 $ sur un compte cent.
- **P** (Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)) : **REJETÉE** — Sharpe trop faible, t-stat trop faible (< 3,0), pas assez robuste, pas mieux que la même méthode toujours acheteuse. Sharpe 0.29, t-stat 1.22, 0.4 % par an, pire baisse 6.8 %, 618 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 42 303 $ sur un compte standard et 423 $ sur un compte cent.

**Ce que « retenue » veut dire** : seulement que l'hypothèse passe les critères sur les données déjà connues. Il reste le contrôle final (12 mois jamais regardés, une seule fois), le test sur des marchés jamais vus et au moins 3 mois de démo. Un backtest ne garantit rien.

## Conditions du test

- Développement : jusqu'au 2025-11-13 inclus. Le contrôle final (2025-11-14 → 2026-11-13) est verrouillé dès le chargement et a été utilisé (voir plus bas).
- Critères : ceux du cycle 1 avec t-stat >= 3.0 et la référence « même méthode toujours acheteuse » (critère 7).
- Capital simulé : 10 000 $ ; C1 : 0,5 % de risque par position ; C2 : cible de volatilité ; P : un tiers du capital par composante. Coûts complets (spread, glissements, swaps, conversion en USD) comme au cycle 1.
- Univers chargé : crypto : BTCUSD, ETHUSD ; forex : AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY ; indices : GER40, JP225, NAS100, UK100, US30, US500 ; métaux : XAGUSD, XAUUSD

## C1 — Tournant du mois sur les indices (D1), achat uniquement

**RETENUE pour le contrôle final**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.8 ans / 711 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 1.23 | >= 0.5 | OK |
| 3 | t-stat du rendement journalier moyen | 5.19 | >= 3.0 | OK |
| 4 | Drawdown max au pire prix | 2.8 % | <= 15 % | OK |
| 5 | Années civiles positives | 94 % | >= 60 % | OK |
| 6 | Robustesse | variantes : entrée J-1 1.05, sortie 3e jour 1.19, stop 4 ATR 0.96 ; coûts doublés : 0.78 ; symboles positifs : 5/6 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | OK |
| 7 | Mieux que la référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)) | 1.23 contre 0.13 | Sharpe > référence | OK |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-01-29 → 2025-11-13 (17.8 ans) |
| Symboles simulés | 6 |
| Trades / signaux refusés | 711 / 573 |
| Gagnants | 58.1 % |
| Rendement total | 29.9 % |
| Rendement annualisé (CAGR) | 1.48 % |
| Volatilité annualisée | 1.2 % |
| Sharpe / t-stat | 1.23 / 5.19 |
| Pire baisse (clôture / pire prix) | 2.6 % / 2.8 % |
| Années civiles positives | 94 % |
| Swaps payés (-) ou reçus (+) | -415 $ |
| Spread et glissements payés | 640 $ |
| Arrêt -15 % (daté, non bloquant) | jamais atteint |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 573.

Référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)), coûts compris : Sharpe 0.13, t-stat 0.57, 0.32 % par an, pire baisse 11.3 %, 863 trades.

Contribution par classe : indices 2 992 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 150 | 907 $ |
| JP225 | 214 | 620 $ |
| NAS100 | 113 | 189 $ |
| UK100 | 20 | 177 $ |
| US30 | 0 | 0 $ |
| US500 | 214 | 1 099 $ |

Par année : 2009 4.0 % ; 2010 2.1 % ; 2011 2.2 % ; 2012 1.1 % ; 2013 1.9 % ; 2014 2.6 % ; 2015 2.1 % ; 2016 0.6 % ; 2017 1.2 % ; 2018 -0.9 % ; 2019 0.9 % ; 2020 0.7 % ; 2021 0.7 % ; 2022 3.9 % ; 2023 1.3 % ; 2024 0.1 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -0.4 %, médiane 1.5 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| entrée J-1 | 1.05 | 4.44 | 1.40 % | 2.1 % | 701 |
| sortie 3e jour | 1.19 | 5.03 | 1.22 % | 2.1 % | 699 |
| stop 4 ATR | 0.96 | 4.06 | 0.79 % | 2.1 % | 600 |
| coûts doublés | 0.78 | 3.29 | 0.91 % | 3.1 % | 695 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **11 192 $** sur un compte standard, **111.92 $** sur un compte cent (1284 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 1284 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 260 trades pris sur 1284 signaux ; capital final 21.85 $ ; pire baisse 1.7 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 11 192 $ sur un compte standard et 112 $ sur un compte cent.

## C2 — Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.1 ans / 312 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.12 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -0.51 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 28.9 % | <= 15 % | KO |
| 5 | Années civiles positives | 50 % | >= 60 % | KO |
| 6 | Robustesse | variantes : SMA150 -0.29, SMA250 -0.20, évaluation mensuelle -0.23 ; coûts doublés : -1.04 ; symboles positifs : 7/10 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)) | Sharpe -0.12 contre -0.15 ; pire baisse 28.9 % contre 31.8 % (2/3 = 21.2 %) | Sharpe > référence ET pire baisse <= 2/3 de celle de la référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-10-07 → 2025-11-13 (17.1 ans) |
| Symboles simulés | 10 |
| Trades / signaux refusés | 312 / 1086 |
| Gagnants | 24.4 % |
| Rendement total | -14.3 % |
| Rendement annualisé (CAGR) | -0.90 % |
| Volatilité annualisée | 5.9 % |
| Sharpe / t-stat | -0.12 / -0.51 |
| Pire baisse (clôture / pire prix) | 28.7 % / 28.9 % |
| Années civiles positives | 50 % |
| Swaps payés (-) ou reçus (+) | -4 746 $ |
| Spread et glissements payés | 1 430 $ |
| Arrêt -15 % (daté, non bloquant) | 2014-02-19 00:00:00 |
| Rééquilibrages hebdomadaires | 932 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 1086.

Référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)), coûts compris : Sharpe -0.15, t-stat -0.63, -1.57 % par an, pire baisse 31.8 %, 111 trades.

Contribution par classe : crypto -1 408 $ ; indices 2 623 $ ; métaux -2 643 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| BTCUSD | 26 | 51 $ |
| ETHUSD | 30 | -1 459 $ |
| GER40 | 33 | 232 $ |
| JP225 | 38 | 722 $ |
| NAS100 | 36 | 275 $ |
| UK100 | 14 | 280 $ |
| US30 | 6 | 319 $ |
| US500 | 36 | 795 $ |
| XAGUSD | 40 | -1 362 $ |
| XAUUSD | 53 | -1 281 $ |

Par année : 2009 3.2 % ; 2010 -4.2 % ; 2011 3.6 % ; 2012 -5.3 % ; 2013 -3.9 % ; 2014 1.2 % ; 2015 0.0 % ; 2016 -6.0 % ; 2017 -9.1 % ; 2018 6.7 % ; 2019 -7.3 % ; 2020 0.8 % ; 2021 -2.4 % ; 2022 6.2 % ; 2023 -6.2 % ; 2024 0.5 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -9.3 %, médiane -0.7 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| SMA150 | -0.29 | -1.20 | -1.82 % | 36.3 % | 350 |
| SMA250 | -0.20 | -0.82 | -1.34 % | 35.2 % | 284 |
| évaluation mensuelle | -0.23 | -0.96 | -1.49 % | 38.7 % | 169 |
| coûts doublés | -1.04 | -4.32 | -5.98 % | 68.3 % | 309 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **14 869 $** sur un compte standard, **148.69 $** sur un compte cent (4477 signaux).
- Simulation à 20 $ sur un compte standard : 30 trades pris sur 4477 signaux ; capital final 17.19 $ ; pire baisse 15.8 %.
- Simulation à 20 $ sur un compte cent : 120 trades pris sur 4477 signaux ; capital final 19.18 $ ; pire baisse 22.5 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 14 869 $ sur un compte standard et 149 $ sur un compte cent.

## P — Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.8 ans / 618 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.29 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | 1.22 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 6.8 % | <= 15 % | OK |
| 5 | Années civiles positives | 62 % | >= 60 % | OK |
| 6 | Robustesse | variantes : C1 entrée J-1 0.28, C1 sortie 3e jour 0.24, C1 stop 4 ATR 0.25, C2 SMA150 -0.05, C2 SMA250 0.17, C2 évaluation mensuelle 0.03, S3 RSI < 5 0.27, S3 RSI < 20 0.25, S3 sortie SMA10 0.28 ; coûts doublés : -0.73 ; symboles positifs : 5/10 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (meilleure référence des composantes : S3) | 0.29 contre 0.63 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-01-29 → 2025-11-13 (17.8 ans) |
| Symboles simulés | 10 |
| Trades / signaux refusés | 618 / 5000 |
| Gagnants | 52.4 % |
| Rendement total | 8.1 % |
| Rendement annualisé (CAGR) | 0.44 % |
| Volatilité annualisée | 1.6 % |
| Sharpe / t-stat | 0.29 / 1.22 |
| Pire baisse (clôture / pire prix) | 6.7 % / 6.8 % |
| Années civiles positives | 62 % |
| Swaps payés (-) ou reçus (+) | -916 $ |
| Spread et glissements payés | 661 $ |
| Arrêt -15 % (daté, non bloquant) | 2018-04-13 00:00:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 5000.

Référence (meilleure référence des composantes : S3) : Sharpe 0.63 ; références des composantes : C1 0.13, C2 -0.15, S3 0.63.

Contribution par classe : crypto -534 $ ; indices 1 389 $ ; métaux -77 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| BTCUSD | 26 | 54 $ |
| ETHUSD | 30 | -588 $ |
| GER40 | 21 | 245 $ |
| JP225 | 343 | 592 $ |
| NAS100 | 18 | 13 $ |
| UK100 | 0 | 0 $ |
| US30 | 0 | 0 $ |
| US500 | 176 | 540 $ |
| XAGUSD | 2 | -43 $ |
| XAUUSD | 2 | -34 $ |

Par année : 2009 2.1 % ; 2010 -2.4 % ; 2011 2.0 % ; 2012 0.3 % ; 2013 0.9 % ; 2014 0.7 % ; 2015 2.4 % ; 2016 -0.8 % ; 2017 -2.9 % ; 2018 1.0 % ; 2019 -1.9 % ; 2020 1.0 % ; 2021 -0.6 % ; 2022 2.4 % ; 2023 -1.1 % ; 2024 1.1 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -1.9 %, médiane 0.4 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| C1 entrée J-1 | 0.28 | 1.17 | 0.43 % | 6.7 % | 615 |
| C1 sortie 3e jour | 0.24 | 1.00 | 0.36 % | 7.0 % | 609 |
| C1 stop 4 ATR | 0.25 | 1.04 | 0.37 % | 6.9 % | 591 |
| C2 SMA150 | -0.05 | -0.19 | -0.08 % | 8.2 % | 634 |
| C2 SMA250 | 0.17 | 0.72 | 0.25 % | 8.7 % | 594 |
| C2 évaluation mensuelle | 0.03 | 0.11 | 0.03 % | 9.3 % | 526 |
| S3 RSI < 5 | 0.27 | 1.13 | 0.40 % | 6.7 % | 551 |
| S3 RSI < 20 | 0.25 | 1.07 | 0.40 % | 7.3 % | 740 |
| S3 sortie SMA10 | 0.28 | 1.20 | 0.44 % | 6.4 % | 611 |
| coûts doublés | -0.73 | -3.09 | -1.18 % | 22.9 % | 604 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **42 303 $** sur un compte standard, **423.03 $** sur un compte cent (7085 signaux).
- Simulation à 20 $ sur un compte standard : 19 trades pris sur 7214 signaux ; capital final 19.38 $ ; pire baisse 4.1 %.
- Simulation à 20 $ sur un compte cent : 399 trades pris sur 7134 signaux ; capital final 19.96 $ ; pire baisse 6.7 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 42 303 $ sur un compte standard et 423 $ sur un compte cent.

## S3 jugée seule avec les critères du cycle 2 (sert seulement à décider si P est évaluée)

**REJETÉE** — Sharpe 0.19, t-stat 0.78, pire baisse 1.8 %, 339 trades.

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.1 ans / 339 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.19 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | 0.78 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 1.8 % | <= 15 % | OK |
| 5 | Années civiles positives | 62 % | >= 60 % | OK |
| 6 | Robustesse | variantes : RSI < 5 -0.02, RSI < 20 0.05, sortie SMA10 -0.01 ; coûts doublés : -0.11 | variantes >= 0.3 ; coûts doublés >= 0.3 | KO |
| 7 | Mieux que la référence passive (US500 acheté et conservé) | 0.19 contre 0.63 | Sharpe > référence | KO |

## Contrôle final (calculé une seule fois)

_Calculé le 2026-11-14 08:14. Ne plus jamais le relancer pour ces hypothèses._

### C1 : CONFIRMÉE (suite : test des nouveaux marchés, puis au moins 3 mois de démo)

| n° | critère | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Rendement du contrôle final au-dessus du 5e centile du développement (bootstrap) | 0.5 % (5e centile -0.4 %) | >= 5e centile | OK |
| 2 | Drawdown du contrôle final au pire prix | 1.1 % | <= 15 % | OK |

Période 2025-11-14 → 2026-11-13, 30 trades, Sharpe 0.52.

## Nouveaux marchés (plan cycle 2 §5)

_Calculé le 2026-11-14 08:14 sur données synthétiques (marche aléatoire, graine 1, effet tournant du mois injecté sur les indices), période de développement seulement._

Nouveaux symboles (absents de l'univers de référence) : AUS200 (indices), XTIUSD (énergies).

| finaliste | symboles tradés | trades | Sharpe | t-stat | pire baisse | décision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| C1 | AUS200 | 214 | 0.80 | 3.37 | 1.6 % | OK (informatif) : peut passer en démo si le contrôle final est confirmé |

## Interprétations prudentes des règles du plan

- Conventions du cycle 1 inchangées : signal à la clôture D1, exécution à l'ouverture suivante, coûts du plan §4 (plancher de spread, journées figées retirées), risque §5, garde -3 %/jour, arrêt -15 % daté.
- C1, jour J : dernier lundi-vendredi du mois calendaire (jours fériés ignorés). L'ordre part à la clôture d'une bougie dont le jour ouvré suivant est J (J-1 pour la variante « entrée J-1 ») ; il ne vaut QUE pour l'ouverture de ce jour-là : si la bougie suivante reçue porte une autre date (férié, donnée manquante), l'ordre est annulé et compté (« ordres annulés, jour d'entrée absent ») ; on n'entre jamais en retard.
- C1 : si la veille de J manque dans les données, aucune clôture n'a J pour jour ouvré suivant : pas d'entrée ce mois-là (deviner un jour férié à l'avance serait de l'anticipation).
- C1, sortie : à l'ouverture qui suit la clôture de la 3e bougie D1 REÇUE du nouveau mois (2e pour la variante « sortie 3e jour »). Stop 3 ATR20 (de la veille) sous le prix d'entrée ; une position stoppée attend le mois suivant. Risque 0,5 %, plafonds de risque ouvert (4 %) et de levier (10) appliqués.
- Référence de C1 (critère 7) : mêmes indices, toujours long, même risque (0,5 %) et même stop (3 ATR). La position est renouvelée chaque mois à l'instant exact où C1 entre (sortie et rachat à la même ouverture, au risque de 0,5 % de l'equity du moment), et rachetée à l'ouverture qui suit un stop. Elle paie donc le même aller-retour mensuel que C1 : la différence mesurée est celle du moment de détention (et des swaps).
- C2 : mécanique de S2 (cible de volatilité 10 %/√N, N = symboles dont le signal est calculable, levier 10, rééquilibrage au-delà de 25 %, stop 4 ATR puis à plat jusqu'au rééquilibrage suivant, plafond de risque ouvert de 4 % non appliqué). Signal 1 si la clôture est STRICTEMENT au-dessus de la SMA, sinon 0 (la position est fermée) ; jamais de vente. Décision à la dernière clôture de la semaine ISO (du mois calendaire pour la variante mensuelle), exécution à l'ouverture suivante.
- C2, univers : indices, métaux, et les classes « énergies » et « crypto » si elles existent ; jamais le forex ; la classe « matières premières » n'est pas citée par le plan et n'est pas incluse. Crypto : volatilité × √365.
- Référence de C2 (critère 7) : même calcul avec le signal forcé à 1 dès que la SMA existe (même période, même N, même cible de volatilité, même stop). Critère : Sharpe plus élevé ET pire baisse au plus égale aux 2/3 de celle de la référence.
- P = C1 + C2 + S3 : chaque composante est simulée séparément sur un tiers du capital (tailles de lots réalistes pour ce tiers), et le rendement journalier de P est la moyenne des rendements des trois composantes (poids constants d'un tiers, comme un compte unique où chacune dimensionne sur le tiers de l'equity totale). Un jour sans bougie pour une composante, son rendement vaut 0. Pire prix : moyenne des rendements au pire prix (pires instants supposés simultanés).
- P n'est évaluée, et même calculée, que si au moins une composante est retenue SEULE avec les critères du cycle 2 ; S3 est alors jugée exactement comme au cycle 1 (référence US500) mais avec t-stat >= 3,0.
- P, robustesse : 9 versions où une seule composante est remplacée par l'une de ses variantes voisines ; coûts doublés sur les trois composantes ; part des symboles positifs appliquée aussi à P (prudence). Critère 7 de P : Sharpe plus élevé que la MEILLEURE des références de ses composantes.
- P, capital minimum : chaque composante ne dispose que d'un tiers du capital, le besoin de chaque signal est multiplié par 3.
- Nouveaux marchés (plan §5) : un symbole est « nouveau » si son nom générique est absent de l'univers de référence (univers.json de référence et univers du développement du cycle 2, symboles exclus compris). L'univers du nouveau broker est chargé en entier (pour les conversions en USD) mais les finalistes ne tradent que les nouveaux symboles de leurs classes, sur la période de développement seulement. Sharpe négatif : échec bloquant ; aucun nouveau marché ou Sharpe non calculable : non concluant, donc bloquant.

## Limites connues

- Les leçons du cycle 1 viennent des mêmes données de développement : la preuve décisive reste le contrôle final (une seule fois), les nouveaux marchés et au moins 3 mois de démo.
- Seuls les swaps ACTUELS sont connus ; ils sont appliqués à tout l'historique (les positions de C1 durent environ 4 jours, celles de C2 des semaines ou des mois).
- Les jours fériés ne sont connus que par l'absence de bougie ; C1 calcule J sur le calendrier lundi-vendredi.
- Les nouveaux symboles d'un autre broker n'ont pas de plancher de spread fixé à l'avance : leur coût repose sur leurs statistiques de spread mesurées.
- Le moteur ne modélise ni appel de marge, ni rejet d'ordre, ni distance minimale de stop.
- Résultats passés : même une hypothèse confirmée ne garantit rien ; elle ne mène qu'à la démo.

## Temps de calcul (dernière commande)

chargement 1.6 s, C1_base 2.5 s, C1_robustesse 1.2 s, C1_capital 0.5 s, C2_base 1.5 s, C2_robustesse 2.0 s, C2_capital 0.8 s, S3_composante 1.4 s, P_base 1.4 s, P_robustesse 9.8 s, P_capital 1.8 s, total_commande 24.8 s, controle_final 2.2 s, nouveaux_marches 2.9 s
