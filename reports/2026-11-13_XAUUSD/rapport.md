# Rapport de backtest SentiTrade — XAUUSD

_Généré le 2026-11-13 18:59 — source : données MT5 (XAUUSD, /sessions/laughing-busy-cori/mnt/outputs/TradingBot/data/mt5)_

## En bref

**Verdict : NO-GO.** La stratégie ne montre pas d'avantage exploitable. Elle retourne en recherche ; on n'engage pas d'argent.

Raisons du NO-GO : espérance hors échantillon <= 0 (-0.141 R) ; espérance (-0.217 R) sous le 75e percentile de la référence (-0.107 R).

- Période simulée : du 2022-04-14 au 2026-11-14, capital de départ 3 000 $.
- 909 trades, dont 43 % gagnants. En moyenne, un trade a rapporté -0.22 fois le montant risqué (-2.73 $).
- Résultat : -82.7 % au total (capital final 520 $), pire baisse depuis un plus haut 82.8 %.
- Pour comparer, acheter de l'or et le garder aurait donné +96.2 % (pire baisse 28.7 %).
- Face à des entrées tirées au hasard dans le sens de la tendance (même gestion), la stratégie fait mieux que 11 % des tirages (il faudrait plus de 90 % pour un GO).
- **Le compte a atteint la limite de -15 % depuis son plus haut** (2022-05-12) : le bot réel se serait arrêté ce jour-là. Pour juger la stratégie sur toute la période, le backtest a continué au-delà.

Rappel : un backtest ne garantit rien. Même un GO ne mène qu'au paper trading (docs/GARDE_FOUS.md §1).

## Verdict : critères fixés à l'avance (spec §6)

| n° | critère | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Nombre de trades (total / hors échantillon) | 909 / 309 | >= 100 / >= 40 | OK |
| 2 | Espérance hors échantillon (OOS), après coûts | -0.141 R | >= +0.10 R | KO |
| 3 | Profit factor hors échantillon | 0.73 | >= 1.2 | KO |
| 4 | Drawdown max (période) / 95e percentile Monte Carlo | 82.8 % / 84.7 % | <= 15 % / <= 25 % | KO |
| 5 | Espérance au-dessus du 90e percentile de « tendance seule » | -0.217 R (p90 = -0.065 R) | > p90 | KO |
| 6 | Robustesse : espérance > 0 en IS et en OOS pour les plafonds de SL 3/5/8/12 $ (mode bord) et avec coûts doublés | plafonds de SL : 0/4 ; coûts doublés : non | >= 3/4 plafonds ; coûts doublés : oui | KO |

Règle : **GO** si les 6 critères sont OK ; **NO-GO** si l'espérance OOS est <= 0 ou sous le 75e percentile de la référence « tendance seule » ; sinon **À CREUSER**.

## Conditions du test

- Période : 2022-04-14 → 2026-11-14 (fin exclue) ; indicateurs calculés sur tout l'historique disponible, y compris avant la période.
- Résolution d'exécution : **M1**
- Capital initial : 3 000 $ (compte en USD).
- Coûts : spread réel de chaque bougie, avec un plancher par heure (médiane du spread des ticks par heure, spread_stats.json (10 jours)) ; glissement à l'entrée et sur TP1/clôture 0.05 $ ; glissement sur stop 0.1 $ ; commission 0.0 $ par lot aller-retour. Pas de swap (positions fermées le jour même).
- Risque : 1.0 % par trade, perte journalière max 3.0 %, arrêt à 15.0 % de drawdown, levier effectif max 10.0.
- Stratégie : EMA 50 H1, entrées 09:00-21:00, clôture 21:55, entrée « bord », SL plafonné à 5.0 $, TP1 à 1.0 R (0.5 de la position), setup valable 8 bougies M15, spread max 0.3 $.

## Résultats détaillés (période complète)

| mesure | valeur |
| --- | ---: |
| Nombre de trades | 909 |
| Taux de réussite | 42.7 % |
| Gain moyen (trades gagnants) | 0.806 R |
| Perte moyenne (trades perdants) | -0.979 R |
| Espérance par trade | -0.217 R / -2.73 $ |
| t de Student de l'espérance | -5.06 |
| Profit factor | 0.51 |
| Rendement total | -82.7 % |
| Rendement annualisé (CAGR) | -31.8 % |
| Drawdown max | 82.8 % (2484 $) |
| Plus longue période sous le plus haut | 1674 jours |
| Plus longue série de trades perdants | 8 |
| Sharpe (journalier, annualisé) | -2.59 |
| Mois perdants / mois avec trades | 25 / 31 |
| Arrêt définitif (-15 %) | oui, le 2022-05-12 |

### Par année

| année | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022 | 342 | 37 % | -0.355 | -121.4 | -2013.24 |
| 2023 | 422 | 47 % | -0.100 | -42.3 | -326.88 |
| 2024 | 145 | 43 % | -0.231 | -33.4 | -139.77 |

### Par mois

| mois | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2022-04 | 21 | 38 % | -0.414 | -8.7 | -229.03 |
| 2022-05 | 45 | 40 % | -0.350 | -15.7 | -375.36 |
| 2022-06 | 38 | 42 % | -0.298 | -11.3 | -228.28 |
| 2022-07 | 31 | 32 % | -0.543 | -16.8 | -319.15 |
| 2022-08 | 45 | 47 % | -0.097 | -4.4 | -82.46 |
| 2022-09 | 43 | 35 % | -0.428 | -18.4 | -275.43 |
| 2022-10 | 45 | 31 % | -0.388 | -17.5 | -212.15 |
| 2022-11 | 40 | 38 % | -0.245 | -9.8 | -118.32 |
| 2022-12 | 34 | 29 % | -0.552 | -18.8 | -173.06 |
| 2023-01 | 33 | 48 % | -0.200 | -6.6 | -47.96 |
| 2023-02 | 39 | 46 % | -0.303 | -11.8 | -88.48 |
| 2023-03 | 35 | 43 % | 0.114 | 4.0 | 16.80 |
| 2023-04 | 30 | 43 % | -0.108 | -3.2 | -24.83 |
| 2023-05 | 45 | 40 % | -0.260 | -11.7 | -70.13 |
| 2023-06 | 33 | 48 % | -0.349 | -11.5 | -65.20 |
| 2023-07 | 32 | 44 % | -0.363 | -11.6 | -59.49 |
| 2023-08 | 38 | 63 % | 0.536 | 20.4 | 89.53 |
| 2023-09 | 41 | 41 % | 0.079 | 3.2 | -3.51 |
| 2023-10 | 41 | 51 % | -0.218 | -8.9 | -41.25 |
| 2023-11 | 33 | 48 % | -0.229 | -7.6 | -35.69 |
| 2023-12 | 22 | 45 % | 0.142 | 3.1 | 3.33 |
| 2024-01 | 26 | 58 % | -0.068 | -1.8 | -8.52 |
| 2024-02 | 29 | 41 % | -0.347 | -10.1 | -49.05 |
| 2024-03 | 17 | 29 % | -0.579 | -9.8 | -38.56 |
| 2024-04 | 8 | 50 % | 0.314 | 2.5 | 11.32 |
| 2024-05 | 19 | 47 % | -0.328 | -6.2 | -28.57 |
| 2024-06 | 14 | 29 % | -0.433 | -6.1 | -20.43 |
| 2024-07 | 12 | 58 % | 0.259 | 3.1 | 17.93 |
| 2024-10 | 8 | 38 % | 0.109 | 0.9 | 1.71 |
| 2024-11 | 5 | 20 % | -0.715 | -3.6 | -15.84 |
| 2024-12 | 7 | 43 % | -0.338 | -2.4 | -9.76 |

### Long / short

| sens | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| long | 464 | 40 % | -0.266 | -123.4 | -1431.09 |
| short | 445 | 45 % | -0.166 | -73.8 | -1048.80 |

### Par heure d'entrée (heure serveur)

| heure | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 09h | 8 | 50 % | 0.002 | 0.0 | -20.47 |
| 10h | 97 | 43 % | -0.247 | -24.0 | -244.71 |
| 11h | 95 | 41 % | -0.376 | -35.8 | -334.99 |
| 12h | 108 | 46 % | -0.047 | -5.1 | -69.12 |
| 13h | 87 | 51 % | 0.045 | 4.0 | -170.52 |
| 14h | 78 | 49 % | -0.144 | -11.2 | -184.79 |
| 15h | 104 | 38 % | -0.301 | -31.3 | -428.50 |
| 16h | 56 | 29 % | -0.506 | -28.4 | -350.63 |
| 17h | 54 | 48 % | -0.099 | -5.3 | -113.88 |
| 18h | 51 | 39 % | -0.279 | -14.2 | -144.45 |
| 19h | 73 | 49 % | -0.118 | -8.6 | -81.11 |
| 20h | 98 | 35 % | -0.380 | -37.2 | -336.72 |

### Par raison de sortie

| sortie | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| clôture forcée 21h55 | 123 | 85 % | 1.672 | 205.7 | 1576.94 |
| stop touché (perte) | 500 | 0 % | -1.000 | -500.0 | -4971.20 |
| runner sorti au point d'entrée | 286 | 99 % | 0.340 | 97.2 | 914.37 |

### Setups, rejets et blocages

- Setups créés : 3420 ; remplacés par un FVG plus récent : 1240 ; entrées : 909.
- FVG rejetés (dans le sens de la tendance, en session) : sl_trop_loin 1671, formation_hors_session 402.
- Setups annulés : refus_taille:lot_non_divisible 623, expire 335, hors_session 193, spread_trop_large 99, tendance 18, sl_depasse_au_toucher 2, hors_session_au_toucher 1.
- Entrées annulées car le spread dépassait le maximum au moment du toucher (CDC §3.4) : 99.
- TP1 atteint sans fermeture partielle possible (lot indivisible, SL passé au point d'entrée) : 0.
- Jours de semaine bloqués par le filtre ADR : 55 sur 1184 ; journées bloquées par la perte journalière max : 1.

## Comparaison avec deux références

**Achat-conservation de l'or** sur la même période : +96.2 % (de 1977.47 à 3880.73), drawdown max 28.7 %. Sans levier ; la stratégie, elle, est à levier et ne garde jamais de position la nuit.

**« Tendance seule »** (200 tirages de 909 trades, graine 20261113) : entrées au marché à des clôtures M15 tirées au hasard en session, dans le sens de la tendance H1, SL tiré parmi les distances de SL de la stratégie, mêmes sorties, même risque.

| espérance par tirage | valeur |
| --- | ---: |
| médiane | -0.146 R |
| 75e percentile | -0.107 R |
| 90e percentile | -0.065 R |
| stratégie | -0.217 R |
| percentile de la stratégie | 11 % |

## Dans l'échantillon / hors échantillon (60 % / 40 %)

Coupure le 2025-01-13. Deux simulations indépendantes, chacune avec 3 000 $ au départ. Aucun paramètre n'a été optimisé.

| mesure | IS (60 % initiaux) | OOS (40 % finaux) |
| --- | ---: | ---: |
| Trades | 909 | 309 |
| Taux de réussite | 42.7 % | 44.7 % |
| Espérance (R) | -0.217 | -0.141 |
| Espérance ($) | -2.73 | -3.09 |
| Profit factor | 0.51 | 0.73 |
| Rendement | -82.7 % | -31.8 % |
| Drawdown max | 82.8 % | 35.0 % |
| Sharpe | -3.37 | -1.41 |
| Arrêt définitif | oui | oui |

## Sensibilité aux paramètres (pour information)

On ne choisit pas « le meilleur » réglage : une stratégie solide reste correcte quand on bouge un peu ses paramètres. Chaque ligne = deux simulations (IS et OOS) ; `*` = réglage de base.

| réglage | trades IS | trades OOS | espérance IS (R) | espérance OOS (R) | PF OOS | espérance totale (R) | arrêt -15 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| sl_plafond=3, bord | 839 | 126 | -0.240 | 0.017 | 1.10 | -0.206 | IS, OOS |
| * sl_plafond=5, bord | 909 | 309 | -0.217 | -0.141 | 0.73 | -0.198 | IS, OOS |
| sl_plafond=8, bord | 950 | 537 | -0.208 | -0.049 | 0.86 | -0.150 | IS, OOS |
| sl_plafond=12, bord | 946 | 616 | -0.208 | -0.049 | 0.86 | -0.145 | IS, OOS |
| sl_plafond=3, milieu | 785 | 73 | -0.216 | -0.002 | 0.90 | -0.198 | IS |
| sl_plafond=5, milieu | 960 | 245 | -0.190 | -0.184 | 0.68 | -0.189 | IS, OOS |
| sl_plafond=8, milieu | 1004 | 475 | -0.179 | -0.159 | 0.65 | -0.173 | IS, OOS |
| sl_plafond=12, milieu | 1002 | 511 | -0.180 | -0.121 | 0.73 | -0.160 | IS, OOS |
| validite=4 | 906 | 262 | -0.220 | -0.108 | 0.75 | -0.195 | IS, OOS |
| * validite=8 | 909 | 309 | -0.217 | -0.141 | 0.73 | -0.198 | IS, OOS |
| validite=16 | 947 | 325 | -0.216 | -0.165 | 0.70 | -0.203 | IS, OOS |
| * spread_max=0.30 | 909 | 309 | -0.217 | -0.141 | 0.73 | -0.198 | IS, OOS |
| spread_max=0.50 | 911 | 310 | -0.217 | -0.139 | 0.73 | -0.197 | IS, OOS |
| coûts doublés | 782 | 310 | -0.274 | -0.165 | 0.68 | -0.243 | IS, OOS |

## Monte Carlo (ordre des trades)

1000 permutations de la séquence des 909 R obtenus (risque 0.8166417337140698 % par trade, capital composé, graine 20261114). Cela montre la baisse qu'on aurait pu subir avec les mêmes trades dans un autre ordre.

| drawdown max | valeur |
| --- | ---: |
| médiane | 83.1 % |
| 95e percentile | 84.7 % |
| pire cas | 86.7 % |

Le rendement final est le même pour toutes les permutations (-82.7 %). À titre d'information, un tirage avec remise (bootstrap) donne un rendement final entre -88.9 % et -71.0 % (5e-95e percentiles), avec 100 % de chances de finir en perte.

## Hypothèses de simulation (prudentes) et limites

- Aucune anticipation : un signal à la clôture d'une bougie M15 n'est exécutable qu'à partir de la bougie suivante ; tendance H1 et filtre ADR n'utilisent que des bougies clôturées.
- Entrée au marché par le bot quand le prix touche le niveau (Ask pour un achat, Bid pour une vente), au niveau ou à l'ouverture si le prix a sauté au-delà, plus le glissement.
- Dans une même bougie, si le stop et le TP1 sont tous deux possibles, on suppose que le **stop** est touché d'abord. Le TP1 n'est jamais pris sur la bougie d'entrée ; le stop, si.
- Le stop au point d'entrée posé après TP1 n'est actif qu'à partir de la bougie suivante.
- Un gap au-delà du stop sort au prix d'ouverture (pire que le stop), plus le glissement.
- Si le prix d'entrée réel est déjà au-delà du stop au moment du toucher, le setup est annulé (le broker refuserait l'ordre).
- La garde de risque voit l'equity au pire prix de chaque bougie, puis à la clôture. Après un arrêt définitif, la position est fermée à l'ouverture de la bougie suivante et plus rien n'est tradé.
- Le R d'un trade = résultat / (lots × perte par lot si le stop est touché, commission comprise).
- Limites : pas de requotes ni de refus d'ordre, pas de latence au-delà du glissement fixe, spread de la bougie supposé valable toute la bougie, pas de swap ni de frais de financement, données du broker supposées exactes. En résolution M15, l'ordre des prix dans la bougie est inconnu.

## Temps de calcul

| section | secondes |
| --- | ---: |
| chargement_donnees | 19.9 |
| signaux | 0.2 |
| base | 8.7 |
| references | 35.5 |
| total_commande | 79.9 |
| isoos | 3.8 |
| sensibilite | 55.6 |
| montecarlo | 0.1 |
