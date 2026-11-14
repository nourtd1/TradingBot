# ⚠ DONNÉES SYNTHÉTIQUES — ce rapport ne dit rien sur la rentabilité réelle

> Les prix de ce rapport sont une **marche aléatoire générée par ordinateur** (graine 1), sans aucun avantage exploitable. Il sert uniquement à vérifier que le moteur de backtest fonctionne et qu'il ne « trouve » pas de gains là où il n'y en a pas.

# Rapport de backtest SentiTrade — XAUUSD

_Généré le 2026-11-13 17:22 — source : données synthétiques (marche aléatoire, graine 1)_

## En bref

**Verdict : NO-GO.** La stratégie ne montre pas d'avantage exploitable. Elle retourne en recherche ; on n'engage pas d'argent.

Raisons du NO-GO : espérance hors échantillon <= 0 (-0.011 R).

- Période simulée : du 2023-01-01 au 2026-01-01, capital de départ 3 000 $.
- 988 trades, dont 47 % gagnants. En moyenne, un trade a rapporté -0.05 fois le montant risqué (-1.00 $).
- Résultat : -33.1 % au total (capital final 2 008 $), pire baisse depuis un plus haut 43.9 %.
- Pour comparer, acheter de l'or et le garder aurait donné +30.2 % (pire baisse 11.0 %).
- Face à des entrées tirées au hasard dans le sens de la tendance (même gestion), la stratégie fait mieux que 80 % des tirages (il faudrait plus de 90 % pour un GO).
- **Le compte a atteint la limite de -15 % depuis son plus haut** (2023-03-08) : le bot réel se serait arrêté ce jour-là. Pour juger la stratégie sur toute la période, le backtest a continué au-delà.

Rappel : un backtest ne garantit rien. Même un GO ne mène qu'au paper trading (docs/GARDE_FOUS.md §1).

## Verdict : critères fixés à l'avance (spec §6)

| n° | critère | valeur | seuil | résultat |
| --- | --- | --- | --- | --- |
| 1 | Nombre de trades (total / hors échantillon) | 988 / 441 | >= 100 / >= 40 | OK |
| 2 | Espérance hors échantillon (OOS), après coûts | -0.011 R | >= +0.10 R | KO |
| 3 | Profit factor hors échantillon | 1.00 | >= 1.2 | KO |
| 4 | Drawdown max (période) / 95e percentile Monte Carlo | 43.9 % / 52.0 % | <= 15 % / <= 25 % | KO |
| 5 | Espérance au-dessus du 90e percentile de « tendance seule » | -0.050 R (p90 = -0.033 R) | > p90 | KO |
| 6 | Robustesse : espérance > 0 en IS et en OOS pour les plafonds de SL 3/5/8/12 $ (mode bord) et avec coûts doublés | plafonds de SL : 0/4 ; coûts doublés : non | >= 3/4 plafonds ; coûts doublés : oui | KO |

Règle : **GO** si les 6 critères sont OK ; **NO-GO** si l'espérance OOS est <= 0 ou sous le 75e percentile de la référence « tendance seule » ; sinon **À CREUSER**.

## Conditions du test

- Période : 2023-01-01 → 2026-01-01 (fin exclue) ; indicateurs calculés sur tout l'historique disponible, y compris avant la période.
- Résolution d'exécution : **M1**
- Capital initial : 3 000 $ (compte en USD).
- Coûts : spread réel de chaque bougie ; glissement à l'entrée et sur TP1/clôture 0.05 $ ; glissement sur stop 0.1 $ ; commission 0.0 $ par lot aller-retour. Pas de swap (positions fermées le jour même).
- Risque : 1.0 % par trade, perte journalière max 3.0 %, arrêt à 15.0 % de drawdown, levier effectif max 10.0.
- Stratégie : EMA 50 H1, entrées 09:00-21:00, clôture 21:55, entrée « bord », SL plafonné à 5.0 $, TP1 à 1.0 R (0.5 de la position), setup valable 8 bougies M15, spread max 0.3 $.

## Résultats détaillés (période complète)

| mesure | valeur |
| --- | ---: |
| Nombre de trades | 988 |
| Taux de réussite | 46.7 % |
| Gain moyen (trades gagnants) | 1.010 R |
| Perte moyenne (trades perdants) | -0.978 R |
| Espérance par trade | -0.050 R / -1.00 $ |
| t de Student de l'espérance | -1.09 |
| Profit factor | 0.88 |
| Rendement total | -33.1 % |
| Rendement annualisé (CAGR) | -12.5 % |
| Drawdown max | 43.9 % (1351 $) |
| Plus longue période sous le plus haut | 1092 jours |
| Plus longue série de trades perdants | 10 |
| Sharpe (journalier, annualisé) | -0.61 |
| Mois perdants / mois avec trades | 26 / 36 |
| Arrêt définitif (-15 %) | oui, le 2023-03-08 |

### Par année

| année | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023 | 423 | 47 % | -0.085 | -35.9 | -787.65 |
| 2024 | 200 | 46 % | -0.052 | -10.4 | -226.94 |
| 2025 | 365 | 47 % | -0.009 | -3.2 | 22.84 |

### Par mois

| mois | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2023-01 | 32 | 47 % | -0.166 | -5.3 | -169.35 |
| 2023-02 | 31 | 52 % | -0.119 | -3.7 | -100.74 |
| 2023-03 | 46 | 46 % | -0.104 | -4.8 | -84.59 |
| 2023-04 | 22 | 50 % | -0.133 | -2.9 | -89.48 |
| 2023-05 | 31 | 39 % | -0.185 | -5.7 | -125.09 |
| 2023-06 | 41 | 39 % | -0.100 | -4.1 | -79.08 |
| 2023-07 | 40 | 45 % | -0.089 | -3.6 | -23.95 |
| 2023-08 | 33 | 67 % | 0.370 | 12.2 | 217.69 |
| 2023-09 | 38 | 53 % | 0.020 | 0.8 | 57.89 |
| 2023-10 | 36 | 44 % | -0.288 | -10.4 | -212.24 |
| 2023-11 | 37 | 38 % | -0.144 | -5.3 | -150.84 |
| 2023-12 | 36 | 44 % | -0.085 | -3.1 | -27.87 |
| 2024-01 | 18 | 39 % | -0.454 | -8.2 | -142.91 |
| 2024-02 | 14 | 36 % | -0.386 | -5.4 | -115.02 |
| 2024-03 | 21 | 43 % | -0.320 | -6.7 | -108.45 |
| 2024-04 | 14 | 43 % | -0.147 | -2.1 | -36.50 |
| 2024-05 | 2 | 0 % | -1.000 | -2.0 | -32.00 |
| 2024-06 | 2 | 50 % | -0.350 | -0.7 | -10.89 |
| 2024-07 | 21 | 57 % | 0.742 | 15.6 | 207.54 |
| 2024-08 | 15 | 60 % | 0.059 | 0.9 | 22.08 |
| 2024-09 | 14 | 36 % | 0.087 | 1.2 | 32.73 |
| 2024-10 | 13 | 38 % | -0.303 | -3.9 | -58.17 |
| 2024-11 | 37 | 46 % | -0.079 | -2.9 | -13.12 |
| 2024-12 | 29 | 55 % | 0.132 | 3.8 | 27.77 |
| 2025-01 | 20 | 35 % | 1.169 | 23.4 | 322.16 |
| 2025-02 | 38 | 55 % | 0.258 | 9.8 | 127.02 |
| 2025-03 | 37 | 46 % | -0.258 | -9.5 | -126.88 |
| 2025-04 | 37 | 38 % | -0.235 | -8.7 | -70.12 |
| 2025-05 | 32 | 59 % | 0.261 | 8.4 | 132.22 |
| 2025-06 | 36 | 50 % | -0.008 | -0.3 | -14.08 |
| 2025-07 | 39 | 44 % | -0.320 | -12.5 | -191.96 |
| 2025-08 | 39 | 41 % | -0.179 | -7.0 | -75.62 |
| 2025-09 | 33 | 48 % | -0.120 | -3.9 | -17.80 |
| 2025-10 | 34 | 56 % | 0.164 | 5.6 | 61.88 |
| 2025-11 | 15 | 33 % | -0.510 | -7.7 | -109.54 |
| 2025-12 | 5 | 60 % | -0.156 | -0.8 | -14.44 |

### Long / short

| sens | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| long | 524 | 49 % | 0.034 | 17.9 | 99.85 |
| short | 464 | 44 % | -0.145 | -67.4 | -1091.60 |

### Par heure d'entrée (heure serveur)

| heure | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 09h | 16 | 38 % | 0.007 | 0.1 | -8.99 |
| 10h | 81 | 52 % | 0.063 | 5.1 | 31.75 |
| 11h | 105 | 49 % | -0.033 | -3.5 | -36.71 |
| 12h | 119 | 43 % | -0.024 | -2.9 | -73.87 |
| 13h | 109 | 40 % | -0.234 | -25.5 | -447.75 |
| 14h | 112 | 42 % | -0.060 | -6.7 | -151.82 |
| 15h | 114 | 51 % | -0.039 | -4.4 | -68.68 |
| 16h | 73 | 51 % | -0.042 | -3.1 | -24.21 |
| 17h | 40 | 48 % | -0.104 | -4.2 | -87.63 |
| 18h | 57 | 47 % | -0.168 | -9.6 | -169.30 |
| 19h | 60 | 60 % | 0.337 | 20.2 | 359.01 |
| 20h | 102 | 42 % | -0.148 | -15.1 | -313.55 |

### Par raison de sortie

| sortie | trades | réussite | espérance (R) | total (R) | P&L ($) |
| --- | ---: | ---: | ---: | ---: | ---: |
| clôture forcée 21h55 | 160 | 88 % | 2.053 | 328.6 | 5137.69 |
| stop touché (perte) | 508 | 0 % | -1.000 | -508.0 | -8200.60 |
| runner sorti au point d'entrée | 320 | 100 % | 0.406 | 130.0 | 2071.16 |

### Setups, rejets et blocages

- Setups créés : 2060 ; remplacés par un FVG plus récent : 707 ; entrées : 988.
- FVG rejetés (dans le sens de la tendance, en session) : sl_trop_loin 1665, formation_hors_session 299.
- Setups annulés : expire 209, hors_session 147, tendance 9.
- Entrées annulées car le spread dépassait le maximum au moment du toucher (CDC §3.4) : 0.
- TP1 atteint sans fermeture partielle possible (lot indivisible, SL passé au point d'entrée) : 0.
- Jours de semaine bloqués par le filtre ADR : 8 sur 783 ; journées bloquées par la perte journalière max : 0.

## Comparaison avec deux références

**Achat-conservation de l'or** sur la même période : +30.2 % (de 3794.70 à 4941.00), drawdown max 11.0 %. Sans levier ; la stratégie, elle, est à levier et ne garde jamais de position la nuit.

**« Tendance seule »** (200 tirages de 988 trades, graine 20261113) : entrées au marché à des clôtures M15 tirées au hasard en session, dans le sens de la tendance H1, SL tiré parmi les distances de SL de la stratégie, mêmes sorties, même risque.

| espérance par tirage | valeur |
| --- | ---: |
| médiane | -0.090 R |
| 75e percentile | -0.058 R |
| 90e percentile | -0.033 R |
| stratégie | -0.050 R |
| percentile de la stratégie | 80 % |

## Dans l'échantillon / hors échantillon (60 % / 40 %)

Coupure le 2024-10-19. Deux simulations indépendantes, chacune avec 3 000 $ au départ. Aucun paramètre n'a été optimisé.

| mesure | IS (60 % initiaux) | OOS (40 % finaux) |
| --- | ---: | ---: |
| Trades | 547 | 441 |
| Taux de réussite | 45.9 % | 47.6 % |
| Espérance (R) | -0.085 | -0.011 |
| Espérance ($) | -1.86 | 0.03 |
| Profit factor | 0.81 | 1.00 |
| Rendement | -33.9 % | 0.4 % |
| Drawdown max | 43.9 % | 21.3 % |
| Sharpe | -1.10 | 0.11 |
| Arrêt définitif | oui | oui |

## Sensibilité aux paramètres (pour information)

On ne choisit pas « le meilleur » réglage : une stratégie solide reste correcte quand on bouge un peu ses paramètres. Chaque ligne = deux simulations (IS et OOS) ; `*` = réglage de base.

| réglage | trades IS | trades OOS | espérance IS (R) | espérance OOS (R) | PF OOS | espérance totale (R) | arrêt -15 % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| sl_plafond=3, bord | 181 | 207 | -0.020 | -0.075 | 0.87 | -0.049 | non |
| * sl_plafond=5, bord | 547 | 441 | -0.085 | -0.011 | 1.00 | -0.052 | IS, OOS |
| sl_plafond=8, bord | 761 | 533 | -0.125 | 0.004 | 1.03 | -0.072 | IS, OOS |
| sl_plafond=12, bord | 775 | 559 | -0.120 | -0.009 | 1.01 | -0.073 | IS, OOS |
| sl_plafond=3, milieu | 97 | 134 | -0.018 | -0.045 | 0.93 | -0.034 | non |
| sl_plafond=5, milieu | 433 | 402 | -0.046 | -0.009 | 0.98 | -0.028 | IS, OOS |
| sl_plafond=8, milieu | 769 | 536 | -0.107 | 0.005 | 0.99 | -0.061 | IS, OOS |
| sl_plafond=12, milieu | 826 | 586 | -0.087 | -0.006 | 0.97 | -0.053 | IS, OOS |
| validite=4 | 477 | 390 | -0.080 | -0.024 | 1.01 | -0.055 | IS, OOS |
| * validite=8 | 547 | 441 | -0.085 | -0.011 | 1.00 | -0.052 | IS, OOS |
| validite=16 | 581 | 461 | -0.061 | -0.011 | 0.99 | -0.039 | IS, OOS |
| * spread_max=0.30 | 547 | 441 | -0.085 | -0.011 | 1.00 | -0.052 | IS, OOS |
| spread_max=0.50 | 547 | 441 | -0.085 | -0.011 | 1.00 | -0.052 | IS, OOS |
| coûts doublés | 547 | 442 | -0.115 | -0.048 | 0.94 | -0.085 | IS, OOS |

## Monte Carlo (ordre des trades)

1000 permutations de la séquence des 988 R obtenus (risque 0.7006751343214821 % par trade, capital composé, graine 20261114). Cela montre la baisse qu'on aurait pu subir avec les mêmes trades dans un autre ordre.

| drawdown max | valeur |
| --- | ---: |
| médiane | 42.9 % |
| 95e percentile | 52.0 % |
| pire cas | 60.7 % |

Le rendement final est le même pour toutes les permutations (-33.1 %). À titre d'information, un tirage avec remise (bootstrap) donne un rendement final entre -61.7 % et +11.3 % (5e-95e percentiles), avec 90 % de chances de finir en perte.

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
| chargement_donnees | 1.0 |
| signaux | 0.0 |
| base | 4.0 |
| references | 19.3 |
| isoos | 1.5 |
| sensibilite | 16.9 |
| montecarlo | 0.0 |
| total_commande | 43.1 |
