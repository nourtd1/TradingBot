# Verdict du backtest SentiTrade sur l'or — expliqué simplement

_13 novembre 2026. Données : XAUUSD, MetaQuotes-Demo, bougies de 1 minute de novembre 2021 à novembre 2026. La simulation commence le 14 avril 2022, après 150 jours laissés au calcul des indicateurs._

## Verdict : NO-GO

La stratégie du cahier des charges (FVG M15 dans le sens de la tendance H1, stop derrière la structure plafonné à 5 $, TP1 à 1R puis breakeven, clôture à 21h55) **perd de l'argent de façon régulière**. Ce n'est pas de la malchance. **On ne passe pas au bot réel.**

## Les chiffres clés

| | Résultat | Ce qu'il fallait pour un GO |
|---|---|---|
| Gain moyen par trade, période de contrôle (déc. 2024 à nov. 2026, 309 trades) | **-0,14 fois le risque** | au moins +0,10 |
| Dollars gagnés pour 1 $ perdu (même période) | **0,73** | au moins 1,20 |
| Capital de 3 000 $, simulé sur toute la période | **520 $ à la fin (-83 %)** | pire baisse ≤ 15 % |
| Comparaison avec des entrées au hasard dans le sens de la tendance (même gestion) | **fait mieux que 11 % des tirages seulement** | mieux que 90 % |
| Stabilité : 4 plafonds de stop et coûts doublés | **0 variante positive sur les deux périodes** | au moins 3 sur 4 |

Le compte de 3 000 $ aurait franchi la limite de -15 % dès le **12 mai 2022**. Le vrai bot se serait arrêté ce jour-là. Courant 2024, le capital restant ne permettait même plus d'ouvrir une position divisible en deux, d'où la courbe plate ensuite.

## Ce n'est ni un problème de coûts ni un bug

Trois vérifications complémentaires ont été faites par l'architecte, avec un capital de 100 000 $ pour que la taille de position ne bloque jamais :

| Variante | Trades | Gain moyen par trade | Fiabilité statistique |
|---|---|---|---|
| Coûts réalistes | 1 435 | -0,18 R | t = -5,7 : perte quasi certaine |
| **Sans aucun coût** (ni spread minimal, ni glissement) | 1 433 | **-0,10 R** | t = -3,1 |
| Entrée au milieu du vide au lieu du bord | 1 376 | -0,18 R | t = -5,8 |

Même dans un monde sans frais, la stratégie perd. Elle perd aussi chaque année (2023 est juste à l'équilibre sans coûts), à l'achat comme à la vente, et avec tous les réglages testés. Pour rappel, le moteur de backtest a été audité de façon indépendante et ne fabrique ni gains ni pertes sur des prix aléatoires.

Une explication probable : quand le prix revient toucher le bord de l'imbalance, celle-ci est en général entièrement comblée, ce qui signale souvent que l'élan s'est épuisé. Les entrées FVG font **moins bien que des entrées au hasard** dans la même tendance.

À titre de comparaison seulement, et sans valeur de conseil : sur la même période, l'or acheté et conservé a pris environ +96 %, avec une pire baisse de 29 %.

## Ce que ça ne veut pas dire

- **Inverser la stratégie** (vendre là où elle achète) **n'est pas une solution**. Sans coûts, l'inverse gagnerait environ +0,10 R ; avec les coûts, il resterait autour de zéro. Et choisir une règle *après* avoir vu les résultats, c'est exactement le piège du surapprentissage.
- Ce n'est pas la fin du projet. Les outils construits (export MT5, moteur de backtest, gestion du risque, rapport avec critères fixés à l'avance) sont réutilisables pour tester une autre idée.
