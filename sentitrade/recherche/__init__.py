"""Programme de recherche multi-marchés (docs/RECHERCHE_PLAN.md).

Modules :
- `donnees` : chargement de l'univers, verrou du contrôle final (hold-out), conversions en USD ;
- `couts` : spread effectif, glissements, swaps, P&L en USD ;
- `strategies` : S1 à S4 et leurs variantes voisines (paramètres figés du plan §3) ;
- `moteur` : moteur de portefeuille multi-symboles par barres ;
- `evaluation` : métriques, références, robustesse, petit capital, verdicts du plan §7 ;
- `rapport` : rapport en français et graphiques ;
- `synthetique` : générateur d'univers synthétique au format exact de l'exporteur ;
- cycle 2 (docs/RECHERCHE_PLAN_CYCLE2.md) : C1 et C2 dans `strategies`, combinaison P dans `moteur`,
  critères dans `evaluation`, sections et règle de P dans `cycle2`, rapport dans `rapport_cycle2`.
"""
