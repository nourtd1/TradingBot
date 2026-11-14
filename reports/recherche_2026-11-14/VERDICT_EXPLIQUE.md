# Recherche multi-marchés du 14/11/2026, expliquée simplement

**Marchés testés (14)** : 7 paires de forex, l'or, l'argent et 5 indices (S&P 500, Nasdaq, Dow Jones, DAX, Nikkei). Le Bitcoin et l'Ethereum n'existent pas chez ce broker. Le FTSE ne cote plus depuis mai 2026.

**Période** : jusqu'à 19 ans d'historique, de 2006 au 13/11/2025. Les 12 derniers mois restent sous clé et n'ont pas été regardés.

**Capital simulé** : 10 000 $, avec tous les frais (spread, glissement, swap). Avant de voir le moindre résultat, deux corrections prudentes ont été faites :

- le serveur démo affiche un spread de 0 sur l'EURUSD et le GBPUSD, ce qui est irréaliste ; ces spreads ont été relevés à des valeurs réalistes ;
- les journées où le prix du DAX était figé ont été retirées.

## Verdict : aucune des 4 méthodes n'est retenue

| Méthode | Résultat par an | Pire baisse | Pourquoi elle est rejetée |
|---|---|---|---|
| S1, suivi de tendance (cassures) | -1,8 % | 47 % | Pas d'avantage, même sans aucun frais : Sharpe proche de 0. |
| S2, momentum sur 12 mois | -2,4 % | 49 % | Petit avantage avant frais (Sharpe 0,26), entièrement mangé par les frais de nuit (swaps). |
| S3, acheter les baisses des indices | +0,7 % | 2 % | Positive et régulière, mais elle rapporte très peu. Elle n'est pas assez prouvée statistiquement et fait moins bien que garder l'indice. |
| S4, cassure de l'ouverture (intraday) | -28 % | 83 % | Légèrement gagnante avant frais, mais 6 000 trades en 5 ans : les spreads l'écrasent. |

## Les résultats sont-ils fiables ?

Les deux méthodes de tendance (S1 et S2) ont été recalculées par l'architecte avec un calcul indépendant et simplifié, **sans aucun frais**. Le résultat est le même :

| Méthode, sans frais | Sharpe | Rendement par an |
|---|---|---|
| S1, suivi de tendance | 0,04 | +0,5 % |
| S2, momentum sur 12 mois | 0,26 | +4 % |

Ce sont des niveaux trop faibles pour supporter des frais réels. Le rejet ne vient donc ni d'un bug ni de frais exagérés.

Une explication probable : ces méthodes sont documentées sur des **dizaines de marchés très variés** (obligations, matières premières, taux, actions du monde entier). Ici, 7 des 14 marchés sont des paires contre le dollar, qui bougent presque ensemble. Le portefeuille est donc beaucoup moins diversifié qu'il n'y paraît.

## Ce que montrent ces données

Sur cette période, **garder simplement un indice** (le S&P 500 par exemple) a fait mieux que toutes les méthodes actives testées. Le Sharpe du S&P 500 est de 0,74. Celui d'un panier de tous les marchés achetés et conservés est de 0,63.

Ce n'est pas un conseil d'investissement. C'est le constat de ce test.

## Le capital de 20 $

Même S3, la seule méthode positive, demande environ **640 $ sur un compte « cent »** pour respecter les règles de risque. Sur un compte standard, il en faudrait environ 64 000 $.

À 0,7 % par an, 20 $ rapporteraient environ 14 centimes par an.
