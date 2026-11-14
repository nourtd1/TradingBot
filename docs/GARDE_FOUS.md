# Garde-fous — règles appliquées à tout le code du bot

Aucun bot ne garantit des gains. Ces règles servent à deux choses : ne passer en argent réel qu'avec une stratégie qui a prouvé un avantage sur des données qu'elle n'a jamais vues, et faire en sorte qu'une erreur (de stratégie, de code ou de connexion) coûte peu.

Elles passent avant le cahier des charges. Les valeurs chiffrées sont des valeurs par défaut : le cahier des charges peut les durcir, mais les assouplir demande ta validation explicite. Les règles marquées **[non négociable]** ne bougent pas.

## 1. Le parcours avant d'engager de l'argent **[non négociable]**

1. **Backtest** avec frais et slippage réalistes, sur une période qui contient des marchés haussiers, baissiers et sans tendance.
2. **Validation hors échantillon (walk-forward)** : les paramètres sont choisis sur une période et jugés sur une autre, jamais sur la même.
3. **Paper trading** (prix réels, argent fictif) pendant au moins 4 semaines, avec assez de trades pour comparer au backtest.
4. **Réel avec un petit capital** (par défaut 10 % du capital prévu au maximum), puis montée progressive seulement si les résultats restent cohérents avec le paper trading.

Une stratégie qui échoue à une étape retourne en recherche. On ne « tente pas quand même ».

## 2. Limites de risque (valeurs par défaut)

| Limite | Défaut | Ce qui se passe si elle est atteinte |
|---|---|---|
| Risque par trade (perte si le stop est touché) | 1 % du capital | la taille de position est réduite en conséquence |
| Perte maximale sur une journée | 3 % du capital | plus aucune nouvelle position jusqu'au lendemain (heure du serveur du broker) |
| Drawdown maximal depuis le plus haut | 15 % | arrêt complet, redémarrage manuel uniquement |
| Positions ouvertes en même temps | 1 (cahier des charges) | les nouveaux signaux sont ignorés |
| Levier effectif (valeur de la position / capital) | 10 maximum | la taille de position est réduite. L'or en CFD est un produit à levier : c'est la taille de position qui contrôle le risque, pas le levier du compte |
| Taille de position | toujours arrondie vers le bas | si le lot minimal du broker dépasse le risque autorisé, le trade est refusé, jamais arrondi vers le haut |

## 3. Exécution **[non négociable]**

- Chaque position a un stop-loss **enregistré chez la plateforme**, pas seulement dans le bot : si le bot, le PC ou internet tombe, la protection reste en place.
- Au démarrage, le bot réconcilie son état avec la plateforme (positions et ordres ouverts) avant toute décision.
- En cas de doute (données manquantes ou en retard, erreur d'API, état incohérent, horloge décalée), le bot ne trade pas : il s'abstient, journalise et alerte.
- Les règles de la plateforme sont respectées : taille minimale, précision des prix et des quantités, limites de requêtes.
- Un arrêt d'urgence simple existe : stopper le bot et, en option, fermer toutes les positions.

## 4. Sécurité des comptes **[non négociable]**

- Clés API avec permission **trading uniquement**, **retrait désactivé**, restreintes à ton adresse IP si la plateforme le permet.
- Les clés vivent dans `%USERPROFILE%\.tradingbot\.env` : jamais dans le code, jamais dans le dossier du projet, jamais dans les journaux, jamais dans une conversation.
- Le mode par défaut est le paper trading. Passer en réel demande une action explicite de ta part.

## 5. Honnêteté des résultats

- Tout rapport de backtest indique la période, les frais et le slippage utilisés, le nombre de trades, le drawdown maximal et la comparaison avec un simple achat-conservation (buy & hold).
- Moins de 100 trades : le résultat n'est pas statistiquement significatif et il est présenté comme tel.
- Un résultat « trop beau » (Sharpe supérieur à 3, aucun mois perdant, courbe parfaitement lisse) est présumé faux jusqu'à preuve du contraire : biais d'anticipation, surapprentissage, frais oubliés.
- Peu de paramètres, et une stratégie doit rester correcte quand on bouge un peu ses paramètres.

## 6. Qualité du code

- Tests automatiques obligatoires pour tout ce qui touche au risque, à la taille des positions et aux ordres. Aucun passage en réel sans tests verts.
- Chaque décision et chaque ordre sont journalisés avec leur raison.
- Toute modification du code d'une stratégie validée relance le parcours à partir de l'étape concernée.
