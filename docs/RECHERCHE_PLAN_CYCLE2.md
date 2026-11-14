# Programme de recherche — cycle 2 (plan pré-enregistré)

_Écrit le 14/11/2026, après le NO-GO du cycle 1 et **avant** tout calcul des hypothèses ci-dessous. Les règles, paramètres et critères de ce document ne changent plus une fois les résultats vus._

Priorité des documents : `GARDE_FOUS.md` > ce plan > `RECHERCHE_PLAN.md`, qui reste valable pour tout ce que ce plan ne précise pas : coûts §4, plancher de spread et retrait des journées figées du 14/11/2026, gestion du risque §5, petit capital §6, conventions d'exécution.

## 0. Leçons du cycle 1 et honnêteté statistique

**Ce que le cycle 1 a appris**, constaté sur la période de développement :

- Sur des CFD, les swaps rendent coûteuse la détention longue. Le trading très fréquent est écrasé par les spreads.
- Le suivi de tendance et le momentum n'ont pas montré d'avantage sur ces 14 marchés.
- Acheter et garder les indices a obtenu le meilleur ratio rendement/risque.
- Acheter les baisses des indices (S3) était positif, mais peu exposé.

**Le problème méthodologique.** Ces leçons viennent des **mêmes données** de développement que celles du cycle 2. Choisir de nouvelles hypothèses après les avoir vues est une forme de recherche guidée par les données. Pour compenser :

1. on teste **peu** d'hypothèses (2, plus 1 combinaison déclarée maintenant) ;
2. on exige plus sur le développement : **t-stat ≥ 3,0** au lieu de 2,5 ;
3. la preuve décisive vient de données **jamais vues** :
   - les 12 mois sous clé (du 2025-11-14 au 2026-11-13), utilisés **une seule fois** ;
   - les marchés **nouveaux** d'un vrai broker (§5) ;
   - au moins **3 mois de démo** en temps réel.

## 1. Hypothèses

Conventions du cycle 1 : signal à la clôture D1, exécution à l'ouverture suivante, `ATR20` = moyenne simple sur 20 bougies du true range, stop enregistré chez le broker.

### C1 — Effet « tournant du mois » sur les indices (achat uniquement)

C'est un effet documenté depuis des décennies (Ariel 1987 ; Lakonishok et Smidt 1988 ; McConnell et Xu 2008) : une grande part de la hausse des actions se concentre entre le dernier jour de bourse d'un mois et les premiers jours du suivant. Comme la position ne dure qu'environ 4 jours par mois, elle paie peu de swaps.

- **Univers** : les indices disponibles (US500, NAS100, US30, GER40, JP225 et, chez le nouveau broker, tout indice actions large).
- **Jour J** : dernier jour ouvré (lundi à vendredi) du mois. Les jours fériés sont ignorés, ce qui est prudent : on entre au pire un jour trop tôt.
- **Entrée** : à l'ouverture de **J**. L'ordre part à la clôture de la veille, si le jour ouvré suivant est J.
- **Sortie** : à l'ouverture du **4ᵉ jour de cotation** du nouveau mois. On compte les bougies D1 réellement reçues depuis le début du mois : la sortie a lieu après 3 bougies terminées. La position dure donc J, J+1, J+2 et J+3.
- **Stop** de sécurité à 3 × ATR20. Risque de **0,5 %** par position.
- **Variantes voisines** :
  - entrée à J-1, sortie à l'ouverture du 4ᵉ jour ;
  - entrée à J, sortie à l'ouverture du 3ᵉ jour ;
  - stop à 4 × ATR20.

### C2 — Indices et métaux avec filtre de tendance (achat ou rien)

Ces marchés ont une dérive positive de long terme. On les détient seulement quand ils sont au-dessus de leur moyenne de 200 jours, et on sort pendant les grandes baisses (Faber 2007 ; Moskowitz, Ooi et Pedersen 2012 pour la version tendance).

- **Univers** : les indices et les métaux (XAUUSD, XAGUSD), plus les nouveaux marchés de même nature chez le nouveau broker. Pas de forex.
- **Signal**, évalué à la dernière clôture D1 de chaque semaine : **1** si la clôture est au-dessus de la SMA200, **0** sinon. Jamais de vente à découvert.
- **Taille** : ciblage de volatilité. La volatilité visée par position vaut 10 % / √N, avec N le nombre de symboles dont le signal est calculable. La volatilité est l'écart-type sur 60 jours × √252, ou × √365 pour la crypto.
- **Plafonds** :
  - levier total de 10 ;
  - rééquilibrage seulement au-delà de 25 % d'écart avec la taille cible.
- Le **plafond de risque ouvert de 4 % ne s'applique pas**, comme pour S2.
- **Stop** de sécurité à 4 × ATR20. S'il est touché, on reste à plat jusqu'au signal hebdomadaire suivant.
- **Variantes voisines** : SMA150, SMA250, et évaluation mensuelle (dernière clôture du mois).

### P — Combinaison déclarée : C1 + C2 + S3

Les trois composantes reçoivent chacune un tiers du capital. S3 est appliqué **exactement comme au cycle 1**, sans le modifier.

La combinaison est jugée sur la somme des rendements journaliers. Elle n'est retenue que si **au moins une** de ses composantes est retenue seule, sinon elle n'est pas évaluée. Cette règle évite qu'un mélange d'éléments faibles passe par chance.

### Ce qui n'est **pas** testé, et pourquoi

- **Carry en forex** : les swaps historiques ne sont pas disponibles, seuls ceux d'aujourd'hui le sont. Le test serait faux.
- **Toute nouvelle variante de FVG, S1, S2 ou S4** : ces méthodes sont rejetées, et les retoucher reviendrait à faire du surapprentissage.

## 2. Périodes

Elles sont inchangées :

- **développement** : jusqu'au 2025-11-13 ;
- **contrôle final** : du 2025-11-14 au 2026-11-13, encore jamais calculé, réservé aux finalistes du cycle 2, **une seule fois**.

## 3. Critères de sélection (développement, 10 000 $)

Ce sont ceux de `RECHERCHE_PLAN.md` §7, avec les changements suivants :

- **Critère 3** : la t-stat doit être **≥ 3,0**.
- **Critère 7**, la référence est la **même méthode, toujours acheteuse** : mêmes symboles, même taille et même stop.
  - Pour C1, on achète en permanence au même risque. Il faut un **Sharpe supérieur** à cette référence.
  - Pour C2, on achète en permanence avec la même cible de volatilité. Il faut un **Sharpe supérieur** et un **drawdown au plus égal aux 2/3** de celui de la référence.
  - Cette référence prouve que le *timing* ajoute de la valeur par rapport au simple fait d'être acheteur.
- **Critère 6** (part des symboles positifs) : il s'applique à C1 et à C2.

## 4. Confirmation sur le contrôle final

On retient au plus deux finalistes, la combinaison P comptant pour un. Chacun est confirmé si :

- son rendement sur 12 mois n'est pas sous le 5ᵉ percentile du développement, estimé par bootstrap par blocs de 20 jours ;
- son drawdown reste ≤ 15 %.

## 5. Nouveau broker : test supplémentaire sur des marchés jamais vus

Il faut un compte démo chez un broker régulé qui propose la crypto, l'énergie et d'autres indices. Les finalistes y sont recalculés **sans aucun changement**, seulement sur les marchés absents du cycle 1, par exemple BTCUSD, ETHUSD, le pétrole et d'autres indices actions. Seule la période de développement est utilisée.

Ce test est **informatif mais bloquant** : si la stratégie a un Sharpe négatif sur ces nouveaux marchés, elle ne passe pas en démo.

## 6. Ensuite

Une stratégie confirmée passe en **démo pendant au moins 3 mois**, chez le nouveau broker, sur un compte cent si possible, et uniquement en démo (`GARDE_FOUS.md` §1). Après ces 3 mois, on compare les résultats de la démo à la distribution du backtest. L'argent réel n'est envisagé qu'après cette comparaison, et seulement avec l'accord explicite de l'utilisateur.
