# SentiTrade — analyse du cahier des charges et plan de route

_13 novembre 2026. Document de référence entre toi et Claude : ce qui a été décidé, pourquoi, et ce qui reste à faire._

## 1. Les décisions que tu as validées

1. **Le backtest passe avant le bot.** On ne construit le programme qui passe des ordres que si la stratégie montre un avantage réel sur l'historique. Le même code de stratégie servira ensuite au bot.
2. **Le stop loss se place derrière la structure** (le plus bas ou le plus haut des trois bougies du FVG), avec un plafond de 5 $. Si la structure est plus loin, on ne prend pas le trade. Le backtest montre aussi les plafonds de 3, 8 et 12 $, pour information seulement.
3. **Trois protections s'ajoutent au cahier des charges** :
   - plus aucune entrée de la journée après -3 % ;
   - arrêt complet du bot à -15 % depuis le plus haut du compte ;
   - exposition limitée à 10 fois le capital.

## 2. Ce que l'analyse a corrigé ou précisé dans le cahier des charges

| Point | Le cahier des charges | Ce qui est appliqué | Pourquoi |
|---|---|---|---|
| Unités | « 50 pips = 5 $ = 500 points » | Tout est exprimé **en dollars** | Certains brokers cotent l'or à 3 décimales : 500 points y valent 0,50 $, pas 5 $ |
| Spread max | 30 points | **0,30 $** | Même raison |
| Entrée | Le prix revient toucher la zone | Entrée au marché quand le prix touche le plus haut (long) ou le plus bas (short) de la bougie 1 ; le setup reste valable **2 h** (8 bougies M15) | La durée de validité n'était pas définie |
| Tendance H1 | « EMA 50 orientée à la hausse » | EMA 50 plus haute qu'il y a 3 heures, calculée sur des bougies H1 **terminées** uniquement | Règle chiffrée, sans lire de donnée future |
| Heures | Entrées de 9h à 22h, clôture à 21h55 | Entrées de 9h à **21h**, et le motif de trois bougies doit **commencer après 9h** | Une entrée à 21h50 serait fermée 5 minutes plus tard ; un motif formé à 8h15 vient de la session asiatique que tu veux exclure |
| Spread trop large | Annuler l'entrée | Le setup est annulé | Conforme à ton texte |
| Filtre ADR | « Ni anormalement élevé, ni plat » | ADR 14 jours rapporté à la médiane des 100 derniers jours, accepté entre 0,5 et 2 | Ton texte ne donnait pas de seuils chiffrés |
| Taille de lot | « Exactement 1 % » | Arrondi **vers le bas** (jamais plus de 1 %, glissement du stop compris) ; trade refusé si le lot ne peut pas être coupé en deux pour le TP1 | Un arrondi vers le haut dépasse le risque prévu |
| Compte à 500 $ (phase réelle) | 1 % de risque, soit 5 $ | Avec un stop de 5 $, le lot minimum (0,01) risque 5,10 $, glissement compris : le trade est **refusé**. Avec un stop plus court, le lot de 0,01 ne peut pas être coupé en deux pour le TP1 | Il faudra soit un capital plus grand, soit une règle adaptée (à décider avant le réel) |
| Identifiants | Dans `config.json` | Dans `%USERPROFILE%\.tradingbot\.env`, hors du dossier partagé | Sécurité |
| Historique | 1 an, les « 100 dernières bougies » | Le maximum disponible (5 ans visés) ; le bot aura besoin d'environ 2 500 bougies H1 | Un an ne couvre qu'un seul régime de marché (l'or a beaucoup monté). L'EMA et le filtre ADR demandent un long historique |
| Évaluation | Taux de réussite et drawdown | Espérance par trade, profit factor, test hors échantillon, comparaison à des entrées au hasard | Un taux de réussite élevé peut cacher une stratégie perdante |
| Notifications | Push MT5 via MetaQuotes ID | Gardées pour les trades ; **alerte Telegram ou Discord** en plus pour les pannes du bot | Le push MT5 ne prévient pas si le programme Python plante |
| « Haute fréquence », latence < 10 ms | — | Pas nécessaire | Une stratégie en M15 n'en dépend pas ; un VPS Windows classique suffit |

## 3. Les critères de décision, fixés à l'avance

Le verdict est **GO** seulement si les six conditions sont réunies :

1. Au moins 100 trades au total, dont au moins 40 dans la période de contrôle, c'est-à-dire les 40 % les plus récents, que la stratégie n'a pas servi à régler.
2. Dans cette période de contrôle, un gain moyen d'au moins 0,10 fois le risque par trade, coûts déduits.
3. Dans cette même période, au moins 1,20 $ gagné pour 1 $ perdu.
4. Une pire baisse du compte de 15 % au plus, et de 25 % au plus dans 95 % des tirages au hasard sur l'ordre des trades.
5. Un résultat meilleur que 90 % des stratégies qui entrent au hasard dans le sens de la tendance avec la même gestion. Sinon, c'est la tendance qui gagne, pas les FVG.
6. Un résultat qui reste positif quand on change le plafond de stop ou qu'on double les coûts.

Même un GO ne mène qu'au compte démo (4 semaines minimum), jamais directement à l'argent réel.

## 4. Les phases

| Phase | Rôle | État |
|---|---|---|
| 0. Cadrage, règles exactes, architecture | Architecte (Claude) | ✅ fait |
| 1. Export des données MT5 + installation | Sous-agent ingénieur MT5 | ✅ code prêt, **à lancer sur ton PC** |
| 2. Cœur de stratégie (tendance, FVG, setups) | Sous-agent quant | ✅ fait, testé |
| 2. Taille de position et limites de risque | Sous-agent risk manager | ✅ fait, testé |
| 3. Moteur de backtest + rapport + verdict | Sous-agent quant backtest | ✅ fait, testé sur prix aléatoires (NO-GO, comme il se doit) |
| Audit indépendant | Sous-agent auditeur | ✅ aucun problème critique ; 5 corrections appliquées |
| 3b. Backtest sur tes vraies données + calibrage des coûts | Quant + auditeur | ✅ fait le 13/11/2026 : **NO-GO** (voir `reports/2026-11-13_XAUUSD/VERDICT_EXPLIQUE.md`) |
| 4. Bot MT5 (connexion, ordres, TP1/breakeven, 21h55, surveillance, reprise après redémarrage) | Ingénieur MT5 + risk manager + auditeur | ⛔ non construit : la stratégie FVG n'a pas d'avantage |
| 5. Compte démo, au moins 4 semaines, analyse hebdomadaire | Toi + Claude | 🔒 |
| 6. Réel avec un petit capital | Ta décision | 🔒 |

## 5. Points ouverts, à traiter en phase 3b ou 4

- **Spread historique.** Selon les brokers, il est parfois sous-estimé, voire à zéro, dans les vieilles données. Le rapport devra afficher le spread par année et tester un spread plus pessimiste.
- **Mode d'exécution du bot.** Le choix est entre deux options, et le backtest mesurera l'écart entre les deux avant de trancher :
  - des ordres en attente posés chez le broker, avec SL et expiration ;
  - une surveillance par le bot qui passe un ordre au marché quand le prix touche le niveau.
- **Tirages au hasard.** La comparaison avec les entrées au hasard est à renforcer avec des tirages par blocs de jours, ce qui la rendra plus exigeante.
- **Jours fériés à fermeture anticipée.** Les positions devront être fermées avant la clôture du marché ces jours-là.
- **Commission réelle de ton broker.** Elle est à 0 pour l'instant : à renseigner dans `config/config.json`.
- **Bot.** Il devra sauvegarder l'état de ses protections, pour qu'un redémarrage ne lève pas un arrêt à -15 %, et vérifier que les données MT5 sont à jour avant chaque décision.
