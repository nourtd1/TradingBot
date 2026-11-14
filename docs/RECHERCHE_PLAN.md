# Programme de recherche multi-marchés — plan pré-enregistré

_Écrit le 13/11/2026, **avant** d'avoir vu la moindre donnée des nouveaux marchés. Ne pas modifier les règles, paramètres ni critères après avoir vu des résultats. Toute idée nouvelle née des résultats devient une hypothèse pour un **prochain** cycle, avec de nouvelles données de contrôle._

Priorité des documents : `GARDE_FOUS.md` > ce plan > le reste.

## 0. Contexte et objectif

L'utilisateur veut un bot qui rapporte de l'argent, sur n'importe quel marché disponible dans MT5. La stratégie FVG sur l'or a été rejetée (NO-GO, 13/11/2026).

Ses choix :

- positions intraday **et** sur plusieurs jours ;
- profil **prudent** : viser 10 à 20 % par an, pire baisse d'environ 15 % ;
- marchés : forex majeur, métaux, indices, crypto.

Son capital réel prévu est d'**environ 20 $** : il est étudiant et veut réinvestir ses gains. Cette contrainte est traitée à la section 6.

La méthode : tester **peu** d'hypothèses, choisies parce qu'elles ont des preuves publiées solides, avec des paramètres figés à l'avance, et garder **12 mois de données jamais regardés** pour un unique test final. Tester des centaines de variantes et garder la meilleure produit presque toujours une stratégie qui échoue en réel.

## 1. Univers

Noms génériques. Les noms exacts chez le broker sont trouvés à l'export et consignés dans `data/univers/univers.json`.

| Classe | Symboles |
|---|---|
| Forex | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD |
| Métaux | XAUUSD, XAGUSD |
| Indices | US500 (S&P 500), NAS100 (Nasdaq 100), US30 (Dow Jones), GER40 (DAX), UK100 (FTSE), JP225 (Nikkei) |
| Crypto | BTCUSD, ETHUSD |

Un symbole absent chez le broker est simplement retiré, et le rapport le dit.

**Données à exporter :**

- **D1 et H1** : tout l'historique disponible, jusqu'à 20 ans ;
- **M15** : 5 ans, seulement pour XAUUSD, EURUSD, GBPUSD, US500, NAS100 et GER40 ;
- `symbol_info.json` par symbole, avec contrat, lots, devises, swaps, `trade_calc_mode` et heures de cotation si elles sont disponibles ;
- `spread_stats.json` par symbole.

## 2. Périodes

- **Développement** : du début des données au **2025-11-13** inclus.
- **Contrôle final (hold-out)** : du **2025-11-14** au **2026-11-13**. Il n'est calculé **qu'une fois**, uniquement pour les finalistes, après avoir figé le choix. Le code doit empêcher de le calculer par accident : il faut un drapeau explicite `--controle-final`.
- Les indicateurs peuvent utiliser l'historique antérieur à une période. Aucune décision ne peut utiliser une donnée future.

## 3. Hypothèses (paramètres figés)

Règles communes à toutes les stratégies :

- Les signaux sont calculés à la **clôture** d'une bougie et exécutés à l'**ouverture de la bougie suivante**, sauf pour les ordres stop de S4.
- `ATR20` est la moyenne simple sur 20 bougies du *true range*.
- Chaque position a un **stop enregistré chez le broker** (garde-fou §3).
- Le risque d'une position est la perte au stop, glissement compris, rapportée à l'equity au moment de l'entrée.

### S1 — Cassure de Donchian (suivi de tendance, D1), tous les symboles, achat et vente

- **Entrée longue** si la clôture dépasse le plus haut des 55 bougies **précédentes**. Entrée courte, symétrique, si la clôture passe sous le plus bas des 55 précédentes.
- **Sortie d'un long** si la clôture passe sous le plus bas des 20 bougies précédentes (symétrique pour un short).
- **Stop initial** à 2 × ATR20 du prix d'entrée, jamais déplacé contre la position.
- Une seule position par symbole.
- **Variantes voisines** : 40/15 et 80/30 bougies ; stop à 3 × ATR20.

### S2 — Momentum temporel (TSMOM, D1), tous les symboles, rééquilibrage hebdomadaire

- À la dernière clôture D1 de chaque semaine, le **signal** est le signe du rendement sur **365 jours calendaires** (prix de clôture le plus récent ≤ t − 365 j). L'achat ou la vente est exécuté à l'ouverture suivante.
- **Taille** : la position est dimensionnée pour que sa volatilité annualisée vaille 10 %/√N de l'equity, avec N le nombre de symboles disponibles à cette date. La volatilité est l'écart-type des rendements journaliers sur 60 bougies × √252, ou × √365 pour la crypto.
- Le **levier total** est plafonné à 10 × l'equity, en réduisant toutes les positions dans la même proportion.
- **Stop de sécurité** à 4 × ATR20 du prix d'entrée. S'il est touché, la position reste à plat jusqu'au rééquilibrage suivant.
- On ne rééquilibre une position (de même sens) que si sa taille cible s'écarte de plus de 25 % de sa taille actuelle, pour limiter les frais.
- **Variantes voisines** : rendement sur 182 et 91 jours.

### S3 — Retour à la moyenne sur les indices (D1), achat uniquement

- **Entrée** si la clôture est au-dessus de la SMA200 et que le RSI(2) (Wilder) est sous 10 : achat à l'ouverture suivante.
- **Sortie** à l'ouverture suivante quand la clôture repasse au-dessus de la SMA5, ou après 10 bougies.
- **Stop** à 3 × ATR20.
- **Univers principal** : les indices. Le même test sur les autres classes est donné pour information seulement.
- **Variantes voisines** : seuil de RSI à 5 et à 20 ; sortie sur SMA10.

### S4 — Cassure du range d'ouverture (intraday, M15)

Symboles : XAUUSD, EURUSD, GBPUSD, US500, NAS100, GER40.

- **Range** : plus haut et plus bas des 4 bougies M15 qui suivent l'ouverture de la session, en heure serveur (UTC+2 l'hiver, UTC+3 l'été, comme Londres et Francfort) :
  - 10:00 pour XAUUSD, EURUSD, GBPUSD et GER40 (ouverture de Londres et Francfort) ;
  - 16:30 pour US500 et NAS100 (ouverture de New York). Le décalage de 2 à 3 semaines par an lié aux changements d'heure américains est accepté et signalé dans le rapport.
- **Ordres** : achat-stop au plus haut du range et vente-stop au plus bas, valables jusqu'à 3 heures avant la clôture forcée.
- Le premier ordre déclenché annule l'autre. Au plus un trade par jour et par symbole.
- **Stop** de l'autre côté du range.
- **Pas d'objectif de gain** : sortie à la clôture forcée, à **21:55** pour le forex et les métaux, à **22:45** pour les indices américains et allemands.
- Le jour est ignoré si le range est inférieur à 3 × le spread médian de l'heure.
- **Variantes voisines** : range de 2 bougies ; objectif de gain à 2R.

Les variantes voisines servent **uniquement** à tester la robustesse. On ne choisit jamais la « meilleure ».

## 4. Coûts et exécution (communs, prudents)

- **Spread** : le maximum du spread de la bougie et de la médiane horaire de `spread_stats.json`. Les bougies sont en Bid ; un achat se fait à l'Ask.
- **Glissement** : 0,5 × le spread médian du symbole sur les ordres au marché, 1 × ce spread sur les stops touchés et les ordres stop d'entrée.
- **Gap** à travers un stop : la sortie se fait à l'ouverture.
- **Stop et objectif dans la même bougie** : le stop passe en premier.
- **Commission** : 0 sur MetaQuotes-Demo. Le paramètre par symbole reste prévu.
- **Swap** : appliqué à chaque position ouverte au passage de minuit serveur, selon `swap_mode`. Le mercredi (`swap_rollover3days`) compte triple. Un mode non géré bloque le calcul pour ce symbole, sans erreur silencieuse.
  - Limite connue : seuls les swaps **actuels** sont connus, appliqués à tout l'historique, ce que le rapport signale.
- **Conversion en USD** : le P&L dans la devise de profit est converti au cours du jour, par exemple JPY via USDJPY ou EUR via EURUSD. Il n'est jamais supposé en USD.
- **Lots** : la taille est arrondie vers le bas au pas du broker. Elle est refusée si elle est inférieure au minimum, et ce refus est compté (section 6).

## 5. Gestion du risque du portefeuille (valeurs pré-enregistrées)

- Risque par position : **0,5 %** pour S1, S3 et S4. S2 suit sa propre cible de volatilité.
- Somme des risques ouverts : **4 %** au maximum. Au-delà, les nouveaux signaux sont ignorés et comptés. Ce plafond concerne S1, S3 et S4 ; **il ne s'applique pas à S2**, bornée par sa cible de volatilité et par le levier (précision du 13/11/2026, faite avant d'avoir vu les données).
- Levier effectif total : **10** au maximum.
- Les gardes du bot réel (-3 % par jour, -15 % de drawdown) s'appliquent en mode évaluation, comme pour SentiTrade : la limite journalière reste active, l'arrêt définitif est daté mais n'arrête pas la simulation.
- Capital simulé : **10 000 $**, pour mesurer l'avantage de la stratégie sans que le lot minimum ne fausse les résultats. Le cas d'un petit capital est traité à part (section 6).

## 6. Le petit capital : faisabilité

Pour chaque stratégie, le rapport calcule :

- le **capital minimum** pour lequel au moins 95 % des signaux peuvent être pris avec un risque ≤ 2 % par position, au lot minimum du broker ;
- une simulation à **20 $**, sur un compte standard et sur un compte « cent ». Un compte cent est une offre de certains brokers où les lots sont 100 fois plus petits : 20 $ s'y gèrent alors comme 2 000 $.

Le rapport le dit sans détour : si 20 $ ne permettent pas de respecter les règles de risque, la stratégie n'est **pas** jouable en réel avec ce capital.

## 7. Critères de sélection (sur la période de développement, à 10 000 $)

Une hypothèse est **retenue pour le contrôle final** si elle remplit **toutes** ces conditions :

1. Assez de données : au moins 8 ans pour S1 à S3, au moins 4 ans pour S4, et au moins 100 trades (ou 100 changements de position pour S2).
2. **Sharpe annualisé ≥ 0,5** après tous les coûts, calculé sur les rendements journaliers du portefeuille.
3. **t-stat ≥ 2,5** sur le rendement journalier moyen. Ce seuil est plus exigeant que 2, parce qu'on teste 4 hypothèses (correction pour tests multiples).
4. **Drawdown max ≤ 15 %**, mesuré au pire prix des bougies.
5. Positive sur au moins 60 % des années civiles complètes.
6. **Robustesse** :
   - toutes les variantes voisines ont un Sharpe ≥ 0,3 ;
   - avec des coûts doublés (spread, glissement, swap), le Sharpe reste ≥ 0,3 ;
   - pour S1, S2 et S4, au moins la moitié des symboles contribuent positivement : l'avantage ne doit pas venir d'un seul marché chanceux.
7. Elle fait mieux que la référence passive : un panier équipondéré en achat-conservation, avec le même risque, ou le Sharpe de l'indice US500 en achat-conservation pour S3.

Les finalistes, au plus deux (ou leur combinaison prévue : S1 + S2 à parts égales de risque), sont ensuite figés, puis calculés **une seule fois** sur le contrôle final.

**Ils sont confirmés** si les deux conditions suivantes sont remplies :

- le rendement sur 12 mois n'est pas sous le 5ᵉ percentile des rendements sur 12 mois du développement, estimé par bootstrap par blocs de 20 jours ;
- le drawdown du contrôle final reste ≤ 15 %.

**Verdicts possibles :**

- **GO paper trading** : au moins 4 semaines en démo, puis réel prudent selon `GARDE_FOUS.md`.
- **À CREUSER** : de nouvelles hypothèses pour un cycle suivant, avec de nouvelles données de contrôle (les mois à venir).
- **NO-GO**.

## 8. Livrables

- `reports/recherche_<date>/` : un rapport clair en français pour l'utilisateur (résumé en langage simple en tête), plus le détail par stratégie, symbole et année ;
- les tableaux de robustesse ;
- le capital minimum ;
- les courbes d'equity ;
- `resume.json`.
