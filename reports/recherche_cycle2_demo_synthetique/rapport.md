# Programme de recherche — cycle 2 — rapport

_Généré le 2026-11-14 08:12 — source : données synthétiques (marche aléatoire, graine 1) — plan : docs/RECHERCHE_PLAN_CYCLE2.md (règles et critères fixés avant les calculs)._

> **Données synthétiques** : ce rapport teste le moteur, il ne dit RIEN des vrais marchés.

## En bref

**Verdict du développement (cycle 2) : NO-GO.** Aucune hypothèse du cycle 2 ne remplit tous les critères fixés à l'avance. On n'engage pas d'argent et le contrôle final reste sous clé.

- **C1** (Tournant du mois sur les indices (D1), achat uniquement) : **REJETÉE** — Sharpe trop faible, t-stat trop faible (< 3,0), pire baisse trop forte, trop peu d'années positives, pas assez robuste. Sharpe -0.76, t-stat -3.19, -1.0 % par an, pire baisse 17.1 %, 859 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 4 667 $ sur un compte standard et 47 $ sur un compte cent.
- **C2** (Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien) : **REJETÉE** — Sharpe trop faible, t-stat trop faible (< 3,0), pire baisse trop forte, trop peu d'années positives, pas assez robuste, pas mieux que la même méthode toujours acheteuse. Sharpe -0.86, t-stat -3.57, -4.8 % par an, pire baisse 62.1 %, 338 trades. Faisabilité avec 20 $ (taille des positions seulement) : pas jouable avec 20 $ : il faudrait 6 301 $ sur un compte standard et 63 $ sur un compte cent.
- **P** (Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)) : **NON ÉVALUÉE** — aucune composante (C1, C2, S3) n'est retenue seule : règle du plan, P n'est pas évaluée.

**Ce que « retenue » veut dire** : seulement que l'hypothèse passe les critères sur les données déjà connues. Il reste le contrôle final (12 mois jamais regardés, une seule fois), le test sur des marchés jamais vus et au moins 3 mois de démo. Un backtest ne garantit rien.

## Conditions du test

- Développement : jusqu'au 2025-11-13 inclus. Le contrôle final (2025-11-14 → 2026-11-13) est verrouillé dès le chargement et n'a PAS été regardé.
- Critères : ceux du cycle 1 avec t-stat >= 3.0 et la référence « même méthode toujours acheteuse » (critère 7).
- Capital simulé : 10 000 $ ; C1 : 0,5 % de risque par position ; C2 : cible de volatilité ; P : un tiers du capital par composante. Coûts complets (spread, glissements, swaps, conversion en USD) comme au cycle 1.
- Univers chargé : crypto : BTCUSD, ETHUSD ; forex : AUDUSD, EURUSD, GBPUSD, NZDUSD, USDCAD, USDCHF, USDJPY ; indices : GER40, JP225, NAS100, UK100, US30, US500 ; métaux : XAGUSD, XAUUSD

## C1 — Tournant du mois sur les indices (D1), achat uniquement

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.8 ans / 859 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.76 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -3.19 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 17.1 % | <= 15 % | KO |
| 5 | Années civiles positives | 25 % | >= 60 % | KO |
| 6 | Robustesse | variantes : entrée J-1 -0.77, sortie 3e jour -0.60, stop 4 ATR -0.80 ; coûts doublés : -1.41 ; symboles positifs : 2/6 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)) | -0.76 contre -0.76 | Sharpe > référence | OK |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-01-29 → 2025-11-13 (17.8 ans) |
| Symboles simulés | 6 |
| Trades / signaux refusés | 859 / 425 |
| Gagnants | 44.2 % |
| Rendement total | -15.9 % |
| Rendement annualisé (CAGR) | -0.97 % |
| Volatilité annualisée | 1.3 % |
| Sharpe / t-stat | -0.76 / -3.19 |
| Pire baisse (clôture / pire prix) | 17.1 % / 17.1 % |
| Années civiles positives | 25 % |
| Swaps payés (-) ou reçus (+) | -416 $ |
| Spread et glissements payés | 1 044 $ |
| Arrêt -15 % (daté, non bloquant) | 2024-08-05 00:00:00 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 425.

Référence (C1 toujours long (même risque 0,5 %, même stop 3 ATR)), coûts compris : Sharpe -0.76, t-stat -3.20, -2.22 % par an, pire baisse 35.1 %, 1096 trades.

Contribution par classe : indices -1 592 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| GER40 | 185 | 46 $ |
| JP225 | 214 | -838 $ |
| NAS100 | 214 | -694 $ |
| UK100 | 32 | 86 $ |
| US30 | 0 | 0 $ |
| US500 | 214 | -192 $ |

Par année : 2009 1.5 % ; 2010 -0.6 % ; 2011 -0.6 % ; 2012 -0.1 % ; 2013 0.3 % ; 2014 0.5 % ; 2015 -0.6 % ; 2016 -1.7 % ; 2017 -1.7 % ; 2018 -3.8 % ; 2019 -1.8 % ; 2020 -1.7 % ; 2021 -0.9 % ; 2022 0.9 % ; 2023 -1.8 % ; 2024 -2.6 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -2.9 %, médiane -0.9 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| entrée J-1 | -0.77 | -3.24 | -1.11 % | 18.9 % | 852 |
| sortie 3e jour | -0.60 | -2.55 | -0.67 % | 12.9 % | 859 |
| stop 4 ATR | -0.80 | -3.39 | -0.73 % | 12.5 % | 765 |
| coûts doublés | -1.41 | -5.94 | -1.79 % | 27.5 % | 840 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **4 667 $** sur un compte standard, **46.67 $** sur un compte cent (1284 signaux).
- Simulation à 20 $ sur un compte standard : 0 trades pris sur 1284 signaux ; capital final 20.00 $ ; pire baisse 0.0 %.
- Simulation à 20 $ sur un compte cent : 383 trades pris sur 1284 signaux ; capital final 18.53 $ ; pire baisse 9.6 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 4 667 $ sur un compte standard et 47 $ sur un compte cent.

## C2 — Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien

**REJETÉE**

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.1 ans / 338 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | -0.86 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | -3.57 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 62.1 % | <= 15 % | KO |
| 5 | Années civiles positives | 6 % | >= 60 % | KO |
| 6 | Robustesse | variantes : SMA150 -0.75, SMA250 -0.83, évaluation mensuelle -1.00 ; coûts doublés : -1.82 ; symboles positifs : 2/10 | variantes >= 0.3 ; coûts doublés >= 0.3 ; >= 50 % des symboles positifs | KO |
| 7 | Mieux que la référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)) | Sharpe -0.86 contre -0.65 ; pire baisse 62.1 % contre 63.1 % (2/3 = 42.0 %) | Sharpe > référence ET pire baisse <= 2/3 de celle de la référence | KO |

| mesure | valeur |
| --- | ---: |
| Période évaluée | 2008-10-07 → 2025-11-13 (17.1 ans) |
| Symboles simulés | 10 |
| Trades / signaux refusés | 338 / 967 |
| Gagnants | 18.0 % |
| Rendement total | -57.2 % |
| Rendement annualisé (CAGR) | -4.84 % |
| Volatilité annualisée | 5.6 % |
| Sharpe / t-stat | -0.86 / -3.57 |
| Pire baisse (clôture / pire prix) | 62.0 % / 62.1 % |
| Années civiles positives | 6 % |
| Swaps payés (-) ou reçus (+) | -3 193 $ |
| Spread et glissements payés | 1 016 $ |
| Arrêt -15 % (daté, non bloquant) | 2012-04-06 00:00:00 |
| Rééquilibrages hebdomadaires | 932 |

Signaux non pris : lot minimum du broker trop gros pour le risque autorisé : 967.

Référence (C2 toujours long (même cible de volatilité, même stop 4 ATR)), coûts compris : Sharpe -0.65, t-stat -2.70, -5.45 % par an, pire baisse 63.1 %, 130 trades.

Contribution par classe : crypto -878 $ ; indices -2 752 $ ; métaux -2 087 $.

| symbole | trades | résultat net |
| --- | ---: | ---: |
| BTCUSD | 26 | 37 $ |
| ETHUSD | 30 | -915 $ |
| GER40 | 37 | -470 $ |
| JP225 | 46 | -736 $ |
| NAS100 | 39 | -357 $ |
| UK100 | 26 | -732 $ |
| US30 | 18 | 205 $ |
| US500 | 41 | -661 $ |
| XAGUSD | 29 | -1 230 $ |
| XAUUSD | 46 | -857 $ |

Par année : 2009 -4.9 % ; 2010 -4.9 % ; 2011 -1.2 % ; 2012 -6.9 % ; 2013 -6.8 % ; 2014 -4.9 % ; 2015 -2.1 % ; 2016 -9.8 % ; 2017 -11.7 % ; 2018 -0.2 % ; 2019 -11.5 % ; 2020 -0.1 % ; 2021 -9.6 % ; 2022 1.3 % ; 2023 -11.1 % ; 2024 -2.1 %.

Bootstrap (blocs de 20 jours, 5000 tirages) : 5e centile du rendement sur 12 mois -12.6 %, médiane -4.7 % (seuil du contrôle final).

Robustesse (stabilité seulement ; on ne choisit jamais « la meilleure » variante) :

| version | Sharpe | t-stat | CAGR | pire baisse | trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| SMA150 | -0.75 | -3.11 | -4.22 % | 58.3 % | 366 |
| SMA250 | -0.83 | -3.40 | -4.57 % | 59.7 % | 290 |
| évaluation mensuelle | -1.00 | -4.13 | -5.37 % | 65.4 % | 176 |
| coûts doublés | -1.82 | -7.51 | -9.81 % | 84.3 % | 331 |

Petit capital (plan §6 du cycle 1) :

- Capital minimum pour prendre 95 % des signaux au lot minimum (risque <= 2 %, levier <= 10) : **6 301 $** sur un compte standard, **63.01 $** sur un compte cent (3875 signaux).
- Simulation à 20 $ sur un compte standard : 39 trades pris sur 3875 signaux ; capital final 16.85 $ ; pire baisse 18.1 %.
- Simulation à 20 $ sur un compte cent : 167 trades pris sur 3875 signaux ; capital final 14.17 $ ; pire baisse 37.2 %.
- Conclusion : pas jouable avec 20 $ : il faudrait 6 301 $ sur un compte standard et 63 $ sur un compte cent.

## P — Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)

**NON ÉVALUÉE** : aucune composante (C1, C2, S3) n'est retenue seule : règle du plan, P n'est pas évaluée. Règle du plan : la combinaison n'est jugée que si au moins une de ses composantes est retenue seule ; elle n'a donc pas été calculée.

## S3 jugée seule avec les critères du cycle 2 (sert seulement à décider si P est évaluée)

**REJETÉE** — Sharpe 0.06, t-stat 0.26, pire baisse 2.6 %, 353 trades.

| n° | critère (plan cycle 2 §3) | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Assez de données (années / trades) | 17.1 ans / 353 | >= 8 ans / >= 100 | OK |
| 2 | Sharpe annualisé après coûts | 0.06 | >= 0.5 | KO |
| 3 | t-stat du rendement journalier moyen | 0.26 | >= 3.0 | KO |
| 4 | Drawdown max au pire prix | 2.6 % | <= 15 % | OK |
| 5 | Années civiles positives | 44 % | >= 60 % | KO |
| 6 | Robustesse | variantes : RSI < 5 -0.15, RSI < 20 -0.25, sortie SMA10 -0.11 ; coûts doublés : -0.35 | variantes >= 0.3 ; coûts doublés >= 0.3 | KO |
| 7 | Mieux que la référence passive (US500 acheté et conservé) | 0.06 contre 0.20 | Sharpe > référence | KO |

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

chargement 1.4 s, C1_base 2.6 s, C1_robustesse 1.3 s, C1_capital 0.5 s, C2_base 1.6 s, C2_robustesse 1.8 s, C2_capital 0.8 s, S3_composante 1.9 s, total_commande 12.1 s
