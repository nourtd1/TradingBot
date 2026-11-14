# Programme de recherche — cycle 2 — rapport

_Généré le 2026-11-14 08:20 — source : données MT5 (/sessions/laughing-busy-cori/mnt/outputs/TradingBot/data/univers) — plan : docs/RECHERCHE_PLAN_CYCLE2.md (règles et critères fixés avant les calculs)._

## En bref

**Verdict du développement (cycle 2) : NO-GO.** Aucune hypothèse du cycle 2 ne remplit tous les critères fixés à l'avance. On n'engage pas d'argent et le contrôle final reste sous clé.

- **C1** (Tournant du mois sur les indices (D1), achat uniquement) : **REJETÉE** — Sharpe trop faible, t-stat trop faible (< 3,0), trop peu d'années positives, pas assez robuste, pas mieux que la même méthode toujours acheteuse. Sharpe 0.05, t-stat 0.18, 0.0 % par an, pire baisse 5.0 %, 228 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 63 436 $ sur un compte standard et 634 $ sur un compte cent.
- **C2** (Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien) : **REJETÉE** — t-stat trop faible (< 3,0), pire baisse trop forte, pas assez robuste, pas mieux que la même méthode toujours acheteuse. Sharpe 0.59, t-stat 2.50, 6.0 % par an, pire baisse 29.4 %, 141 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 69 003 $ sur un compte standard et 690 $ sur un compte cent.
- **P** (Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)) : **NON ÉVALUÉE** — aucune composante (C1, C2, S3) n'est retenue seule : règle du plan, P n'est pas évaluée.

**Ce que « retenue » veut dire** : seulement que l'hypothèse passe les critères sur les données déjà connues. Il reste le contrôle final (12 mois jamais regardés, une seule fois), le test sur des marchés jamais vus et au moins 3 mois de démo. Un backtest ne garantit rien.

## Conditions du test

- Développement : jusqu'au 2025-11-13 inclus. Le contrôle final (2025-11-14 → 2026-11-13) est verrouillé dès le chargement et n'a PAS été regardé.
- Critères : ceux du cycle 1 avec t-stat >= 3.0 et la référence « même méthode toujours acheteuse » (critère 7).
- Capital simulé : 10 000 $ ; C1 : 0,5 % de risque par position ; C2 : cible de volatilité ; P : un tiers du capital par composante. Coûts complets (spread, glissements, swaps, conversion en USD) comme au cycle 1.
- Univers chargé : forex : AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY ; indices : GER40, JP225, NAS100, US30, US500 ; métaux : XAGUSD, XAUUSD
- Absents chez le broker : BTCUSD (introuvable chez le broker : alias cherchés BTCUSD, XBTUSD, BITCOIN) ; ETHUSD (introuvable chez le broker : alias cherchés ETHUSD, ETHEREUM)
- Exclus : UK100 (pas de bougies D1 dans la période autorisée)

## C1 — Tournant du mois sur les indices (D1), achat uniquement

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 13.2 ans / 228 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.05 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | 0.18 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 5.0 % | <= 15 % | OK |
| 5 | Années civiles positives | 42 % | >= 60 % | KO |
| 6 | Robustesse | variantes : entrée J-1 0.01, sortie 3e jour -0.07, stop 4 ATR -0.00 ; coûts doublés : -0.14 ; symboles positifs : 2/5 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)) | 0.05 contre 0.35 | Sharpe > référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2012-09-03 → 2025-11-13 (13.2 ans) |
| Symboles simulés | 5 |
| Trades / signaux refusés | 228 / 336 |
| Gagnants | 52.2 % |
| Rendement total | 0.7 % |
| Rendement annualisé (CAGR) | 0.05 % |
| Volatilité annualisée | 1.1 % |
| Sharpe / t-stat | 0.05 / 0.18 |
| Pire baisse (clôture / pire prix) | 4.8 % / 5.0 % |
| Années civiles positives | 42 % |
| Swaps payés (-) ou reçus (+) | -207 $ |
| Spread et glissements payés | 123 $ |
| Arrêt -15 % (daté, non bloquant) | jamais atteint |
| Ordres annulés, jour d'entrée absent des données | 19 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 336.

Référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)), coûts compris : Sharpe 0.35, t-stat 1.26, 1.02 % par an, pire baisse 8.4 %, 373 trades.

Contribution par classe : indices 65 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 39 | 77 $ |
| JP225 | 0 | 0 $ |
| NAS100 | 0 | 0 $ |
| US30 | 37 | 64 $ |
| US500 | 152 | -76 $ |

Par année : 2013 0.1 % ; 2014 -0.9 % ; 2015 -1.1 % ; 2016 -1.2 % ; 2017 3.0 % ; 2018 -0.5 % ; 2019 -1.4 % ; 2020 1.2 % ; 2021 -0.0 % ; 2022 -0.1 % ; 2023 0.6 % ; 2024 0.4 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -1.8 %, médiane 0.0 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| entrée J-1 | 0.01 | 0.05 | 0.01 % | 6.6 % | 235 |
| sortie 3e jour | -0.07 | -0.24 | -0.07 % | 4.2 % | 226 |
| stop 4 ATR | -0.00 | -0.02 | -0.01 % | 3.0 % | 179 |
| coûts doublés | -0.14 | -0.50 | -0.16 % | 6.1 % | 225 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **63 436 $** sur un compte standard, **634.36 $** sur un compte cent (564 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 564 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 71 trades pris sur 564 signaux ; capital final 19.74 $ ; pire baisse 2.6 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 63 436 $ sur un compte standard et 634 $ sur un compte cent.

## C2 — Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 18.2 ans / 141 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.59 | >= 0.5 | OK |
| 3 | t-stat du rendement journalier moyen | 2.50 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 29.4 % | <= 15 % | KO |
| 5 | Années civiles positives | 65 % | >= 60 % | OK |
| 6 | Robustesse | variantes : SMA150 0.48, SMA250 0.46, évaluation mensuelle 0.54 ; coûts doublés : 0.29 ; symboles positifs : 6/7 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)) | Sharpe 0.59 contre 0.44 ; pire baisse 29.4 % contre 43.2 % (2/3 = 28.8 %) | Sharpe > référence ET pire baisse <= 2/3 de celle de la référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2007-08-29 → 2025-11-13 (18.2 ans) |
| Symboles simulés | 7 |
| Trades / signaux refusés | 141 / 233 |
| Gagnants | 26.2 % |
| Rendement total | 188.8 % |
| Rendement annualisé (CAGR) | 6.00 % |
| Volatilité annualisée | 11.0 % |
| Sharpe / t-stat | 0.59 / 2.50 |
| Pire baisse (clôture / pire prix) | 27.6 % / 29.4 % |
| Années civiles positives | 65 % |
| Swaps payés (-) ou reçus (+) | -8 303 $ |
| Spread et glissements payés | 642 $ |
| Arrêt -15 % (daté, non bloquant) | 2013-02-15 00:00:00 |
| Rééquilibrages hebdomadaires | 1017 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 233.

Référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)), coûts compris : Sharpe 0.44, t-stat 1.88, 5.22 % par an, pire baisse 43.2 %, 26 trades.

Contribution par classe : indices 9 315 $ ; métaux 9 569 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 21 | 1 931 $ |
| JP225 | 0 | 0 $ |
| NAS100 | 2 | 1 682 $ |
| US30 | 18 | 2 433 $ |
| US500 | 21 | 3 269 $ |
| XAGUSD | 44 | 1 628 $ |
| XAUUSD | 35 | 7 940 $ |

Par année : 2008 0.6 % ; 2009 11.2 % ; 2010 26.7 % ; 2011 9.1 % ; 2012 -4.1 % ; 2013 2.0 % ; 2014 -9.6 % ; 2015 -10.3 % ; 2016 4.9 % ; 2017 20.6 % ; 2018 -8.4 % ; 2019 7.7 % ; 2020 -1.4 % ; 2021 7.9 % ; 2022 -7.1 % ; 2023 5.0 % ; 2024 28.1 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -12.4 %, médiane 5.9 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| SMA150 | 0.48 | 2.07 | 4.69 % | 31.5 % | 186 |
| SMA250 | 0.46 | 1.95 | 4.46 % | 32.0 % | 126 |
| évaluation mensuelle | 0.54 | 2.30 | 5.57 % | 27.4 % | 89 |
| coûts doublés | 0.29 | 1.25 | 2.59 % | 43.4 % | 157 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **69 003 $** sur un compte standard, **690.03 $** sur un compte cent (2926 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 2926 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 42 trades pris sur 2926 signaux ; capital final 27.57 $ ; pire baisse 15.4 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 69 003 $ sur un compte standard et 690 $ sur un compte cent.

## P — Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)

**NON ÉVALUÉE** : aucune composante (C1, C2, S3) n'est retenue seule : règle du plan, P n'est pas évaluée. Règle du plan : la combinaison n'est jugée que si au moins une de ses composantes est retenue seule ; elle n'a donc pas été calculée.

## S3 jugée seule avec les critères du cycle 2 (sert seulement à décider si P est évaluée)

**REJETÉE** — Sharpe 0.61, t-stat 2.16, pire baisse 2.0 %, 187 trades.

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 12.5 ans / 187 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.61 | >= 0.5 | OK |
| 3 | t-stat du rendement journalier moyen | 2.16 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 2.0 % | <= 15 % | OK |
| 5 | Années civiles positives | 82 % | >= 60 % | OK |
| 6 | Robustesse | variantes : RSI < 5 0.32, RSI < 20 0.58, sortie SMA10 0.75 ; coûts doublés : 0.39 | variantes >= 0.3 ; coûts doublés >= 0.3 | OK |
| 7 | Mieux que la référence passive (US500 acheté et conservé) | 0.61 contre 0.74 | Sharpe > référence | KO |

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

chargement 14.7 s, C1_base 2.0 s, C1_robustesse 0.7 s, C1_capital 0.3 s, C2_base 1.2 s, C2_robustesse 1.3 s, C2_capital 0.5 s, S3_composante 1.0 s, total_commande 21.9 s
