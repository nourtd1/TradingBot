# SentiTrade — spécification technique (contrat des modules)

Ce document traduit le cahier des charges (`docs/cahier_des_charges/CDC_original_sentitrade.md`) en règles exactes, sans place à l'interprétation. En cas de conflit : `docs/GARDE_FOUS.md` > ce document > le CDC. Décisions validées par l'utilisateur le 2026-11-13 : backtest d'abord, SL derrière la structure plafonné à 5 $ (autres plafonds testés pour information seulement), limites -3 %/jour, -15 % de drawdown, levier effectif ≤ 10.

Paramètres : `config/config.json`, chargé par `sentitrade/config.py` (déjà écrit, ne pas modifier sans accord de l'architecte). Tous les noms de paramètres ci-dessous sont ceux de ce fichier.

## 1. Conventions

- **Heure** : heure du serveur du broker, celle des bougies MT5. Les horodatages sont des `pd.Timestamp` **naïfs** qui représentent l'heure serveur. On ne les convertit jamais en UTC.
- **Bougie** : l'horodatage est l'heure d'**ouverture**. La bougie M15 de 10:00 couvre [10:00, 10:15) et n'est **clôturée et utilisable qu'à 10:15**. Idem H1 : la bougie de 10:00 est utilisable à 11:00.
- **Prix** : les bougies MT5 sont en **Bid**. Ask = Bid + spread, avec spread (prix) = `spread` (points, colonne des données) × `point`.
- **Unités** : prix et distances en dollars. Les points n'apparaissent qu'à la frontière MT5, via `SymboleSpec.point`.
- **Compte** : devise USD. Pour XAUUSD, le P&L d'un lot vaut Δprix × `taille_contrat`. En réel, le bot utilisera `mt5.order_calc_profit`.
- **Biais d'anticipation interdit** : à l'instant `t`, n'utiliser que des bougies dont la clôture est ≤ `t`. Chaque module de signal doit avoir un test qui le prouve.

## 2. Données (`data/mt5/`, produites par `scripts/exporter_donnees_mt5.py` sur le PC)

- `XAUUSD_M1.csv`, `XAUUSD_M15.csv`, `XAUUSD_H1.csv` (préfixe = nom réel du symbole chez le broker, par exemple `XAUUSD.p`). Colonnes exactes : `time,open,high,low,close,tick_volume,spread,real_volume`. `time` est au format `YYYY-MM-DD HH:MM:SS` (heure serveur), `spread` est en points (entier), le fichier est trié par `time` et ne contient pas de doublons.
- `symbol_info.json` : attributs MT5 du symbole avec leurs noms MT5. Au minimum `name, digits, point, trade_contract_size, volume_min, volume_step, volume_max, trade_stops_level, trade_tick_size, trade_tick_value, currency_profit, spread`, plus `export` (date, décalage serveur-UTC en heures, build du terminal) et `compte` (`currency, leverage, margin_mode, trade_mode, company, server`, **jamais** login, nom ni mot de passe).
- `spread_stats.json` : percentiles 50/90/99 du spread (en points) par heure serveur, calculés sur les ticks des 10 derniers jours ouvrés.
- `symbol_info.json` se lit avec `SymboleSpec.depuis_json()`.

## 3. Règles de stratégie

**Tendance H1** (`tendance_h1`). On calcule `EMA = close.ewm(span=ema_periode, adjust=False).mean()` sur les bougies H1. Pour la bougie H1 d'indice i, la valeur est connue à sa clôture (open + 1 h) et vaut +1 si `EMA[i] > EMA[i - pente_ema_barres]`, -1 si `<`, et 0 sinon. Elle vaut aussi 0 pendant l'échauffement, c'est-à-dire tant que i < 3 × `ema_periode`. À un instant t, la tendance est la dernière valeur dont la clôture H1 est ≤ t (0 s'il n'y en a aucune).

**FVG M15** (`detecter_fvg`). Soit c1, c2, c3 trois bougies M15 consécutives, c3 la plus récente, et un FVG confirmé à la clôture de c3.

- Long : il faut `low(c3) > high(c1)` et un vide `low(c3) - high(c1) ≥ fvg_ecart_min`. Le vide est la zone `[high(c1), low(c3)]`. L'entrée est `high(c1)` en mode `bord`, ou `(high(c1) + low(c3)) / 2` en mode `milieu`. Le SL vaut `min(low c1, c2, c3) - (spread(c3) × point + sl_marge_fixe)`.
- Short (symétrique) : il faut `high(c3) < low(c1)`. L'entrée est `low(c1)` en mode `bord`, ou le milieu du vide en mode `milieu`. Le SL vaut `max(high c1, c2, c3) + spread(c3) × point + sl_marge_fixe`.
- c1, c2 et c3 doivent être contiguës, sans trou de données.
- `distance_sl = |entree - sl|`. Le FVG est rejeté (et journalisé) avec l'une des raisons suivantes, de la plus prioritaire à la moins prioritaire :
  1. `formation_hors_session` si c1 s'ouvre avant `debut_session`, car le motif entier doit se former hors session asiatique (décision du 2026-11-13) ;
  2. `ecart_trop_petit` si le vide est inférieur au minimum ;
  3. `sl_trop_loin` si `distance_sl > sl_plafond` ;
  4. `sl_trop_proche` si `distance_sl < stops_level_points × point`.
- `tp1 = entree + sens × tp1_r × distance_sl`.

**Filtre ADR** (`filtre_adr`). Le range journalier d'une date serveur vaut max(high) − min(low) des bougies H1 de ce jour. Pour le jour D, on n'utilise que les jours **antérieurs** à D : `ADR` = moyenne des `adr_periode` derniers ranges, `REF` = médiane des `adr_reference` derniers. Le jour est autorisé si `adr_ratio_min ≤ ADR/REF ≤ adr_ratio_max`. Avec un historique insuffisant, le jour est interdit.

**Sessions** (`sessions.py`). Une entrée est possible si le jour de la semaine est dans `jours_autorises` et si `debut_session ≤ heure < derniere_entree`. La clôture forcée a lieu dès que l'heure est ≥ `cloture_forcee`.

**Machine à setups** (`MoteurSignaux.sur_cloture_m15`). Elle est appelée à chaque clôture M15, à l'instant `t` (= open de la bougie + 15 min), et applique trois étapes dans cet ordre :

1. **Annulation du setup actif.** Raison `expire` si `t ≥ expire_a`, `tendance` si la tendance à t est différente de `sens`, `hors_session` si t n'est plus une heure d'entrée.
2. **Création d'un setup.** Il faut un FVG confirmé à t, non rejeté, avec `sens == tendance(t) ≠ 0`, un jour ADR autorisé, une heure d'entrée valide et **aucune position ouverte**. Le nouveau setup **remplace** l'éventuel setup actif (événement `remplace`). Ses champs sont `cree_a = t` et `expire_a = t + validite_setup_barres × 15 min`.
3. **Retour.** La méthode renvoie la liste des événements `(type, setup, raison)`, avec un type parmi `nouveau`, `annule`, `remplace`, `rejete`.

Le setup est retiré par `consommer()` quand l'exécution le remplit. Un seul setup et une seule position à la fois.

**Point d'entrée unique, pour le backtest comme pour le bot.** `preparer_signaux(m15, h1, cfg, spec) -> DataFrame`, entièrement vectorisé.

- L'index est l'**instant de clôture** de chaque bougie M15 (open + 15 min).
- Les colonnes :
  - `tendance` (int -1/0/1) ;
  - `adr_ok` (bool) ;
  - `heure_entree_ok` (bool) ;
  - `sens` (int : 0 s'il n'y a pas de FVG, ±1 sinon) ;
  - `entree`, `sl`, `tp1`, `distance_sl` (float, NaN sans FVG) ;
  - `rejet` (str, `""` si le FVG est valide).

Ensuite, `MoteurSignaux(cfg).sur_cloture_m15(t, ligne, position_ouverte) -> list[Evenement]` reçoit une ligne de ce tableau. Les attributs `setup_actif` et `consommer()` complètent l'interface. Un `Setup` est un dataclass gelé `(sens, entree, sl, tp1, distance_sl, cree_a, expire_a)`. Un `Evenement` est un dataclass `(type, instant, setup, raison)`.

## 4. Gestion du risque (`risk_manager.py`)

- `calculer_taille_lot(balance, cfg_risque, perte_par_lot, notionnel_par_lot, spec) -> ResultatTaille(accepte, lots, risque_montant, risque_pct, levier_effectif, raison)`. Les étapes :
  1. `perte_par_lot` est la perte pour 1 lot si le SL est touché, **glissement de stop attendu et commission inclus** : `(distance + glissement_stop) × taille_contrat + commission` (ajouté le 2026-11-13 après audit). `notionnel_par_lot` vaut prix × taille du contrat.
  2. Le lot brut vaut `min(balance × pct / 100 / perte_par_lot, levier_effectif_max × balance / notionnel_par_lot, volume_max)`.
  3. Il est arrondi **vers le bas** au `volume_pas`, de façon robuste aux flottants. On n'arrondit jamais vers le haut.
  4. Refus avec la raison `lot_inferieur_minimum` si le lot obtenu est inférieur à `volume_min`, et avec `lot_non_divisible` si `exiger_lot_divisible` est actif et le lot inférieur à 2 × `volume_min`.
  5. Toute entrée invalide (≤ 0, NaN, infini) donne `accepte=False` avec une raison explicite, jamais d'exception.
  6. Garantie testée : `lots × perte_par_lot ≤ risque_montant × (1 + 1e-9)`.
- `decouper_volume(lots, fraction, spec) -> (a_fermer, restant)` : arrondi vers le bas, les deux parts ≥ `volume_min`, et `(0.0, lots)` si c'est impossible.
- `GardeRisque(cfg_risque, balance_initiale)` :
  - `nouvelle_journee(date, balance)` fixe la référence du jour.
  - `mettre_a_jour(t, equity)` suit le pic d'equity. À un drawdown ≥ `drawdown_max_pct`, elle déclenche l'**arrêt définitif** (`arret_definitif=True`, `raison_arret`), qu'on ne lève qu'avec `reinitialiser_arret()`.
  - `peut_ouvrir(t, equity) -> (bool, raison)` refuse en cas d'arrêt définitif, ou si `(balance_debut_jour - equity) / balance_debut_jour ≥ perte_jour_max_pct`. Ce blocage dure jusqu'à la prochaine `nouvelle_journee`.

## 5. Modèle d'exécution du backtest (`backtest.py`)

La résolution d'exécution est M1 si les données M1 couvrent la période, M15 sinon (le rapport le signale). Les signaux utilisent toujours les fichiers M15 et H1 exportés de MT5. Les indicateurs sont calculés sur tout l'historique disponible, et la simulation porte sur la fenêtre demandée.

**Boucle.** Pour chaque bougie d'exécution d'ouverture `t`, on traite d'abord **toutes** les clôtures M15 ≤ t pas encore traitées (appel du moteur de signaux), puis la bougie elle-même. Une bougie manquante ne doit jamais faire sauter une clôture M15.

**Entrée.** L'entrée est gérée par le bot : il passe un ordre au marché quand le prix touche le niveau.

- Long : le niveau est touché si `low_bid + spread ≤ entree`. Le prix d'entrée vaut `min(entree, open_ask) + glissement_entree`.
- Short : le niveau est touché si `high_bid ≥ entree`. Le prix d'entrée vaut `max(entree, open_bid) - glissement_entree`.
- Conditions au moment du toucher :
  - si l'heure n'est plus une heure d'entrée, le setup est annulé ;
  - si le spread de la bougie dépasse `spread_max`, le setup est **annulé** (CDC §3.4 ; corrigé le 2026-11-13 après audit) ;
  - si `GardeRisque.peut_ouvrir` est faux, le setup est annulé ;
  - la taille est calculée sur la distance réelle `|prix d'entrée - sl|` ; si elle est refusée, le setup est annulé.

**Sorties** (dans cet ordre de priorité sur une même bougie, hypothèses prudentes) :

1. **Clôture forcée.** À la première bougie d'ouverture ≥ `cloture_forcee`, on sort à l'open, au Bid pour un long et à l'Ask pour un short, avec `glissement_entree` défavorable. Le setup actif est annulé.
2. **Stop.** Un long est touché si `low_bid ≤ sl`, avec une sortie à `min(sl, open_bid) - glissement_stop`. Un short est touché si `high_bid + spread ≥ sl`, avec une sortie à `max(sl, open_ask) + glissement_stop`.
3. **TP1.** Un long l'atteint si `high_bid ≥ tp1`, un short si `low_bid + spread ≤ tp1`. On ferme alors `decouper_volume(lots, tp1_fraction)` à `tp1` moins `glissement_entree` défavorable, puis le SL du reste passe au prix d'entrée réel (breakeven). Le runner n'a pas de TP et ne sort qu'au SL ou à 21h55.
- Si stop et TP1 sont possibles dans la même bougie, le **stop d'abord** s'applique. Sur la bougie de remplissage, le stop est vérifié mais pas le TP1.
- La commission vaut `commission_par_lot × lots`, comptée proportionnellement sur chaque sortie.
- `GardeRisque` : appeler `nouvelle_journee` à la première bougie de chaque date serveur, et `mettre_a_jour` à chaque bougie avec l'equity évaluée au prix du marché. Après un arrêt définitif, on ferme à l'open suivant et le compte ne trade plus.

**Sorties du moteur.** `executer_backtest(...)` renvoie un objet avec :

- `trades` : un DataFrame avec une ligne par trade, et pour colonnes `setup_cree_a, sens, entree_a, prix_entree, sl, tp1, lots, risque_montant, sorties` (détail), `pnl, r_multiple, raison_sortie, duree_min` ;
- `equity` : une Series ;
- `evenements` : un DataFrame avec les setups, les rejets et leurs raisons, et les refus de taille ;
- les paramètres utilisés.

## 6. Rapport et critères de décision (pré-enregistrés : ne pas les modifier après avoir vu les résultats)

**Mode évaluation (décision du 2026-11-13).** Les sections statistiques (base, IS/OOS, sensibilité) tournent avec `arret_definitif_actif=False`. L'arrêt à -15 % y est neutralisé, pour ne pas tronquer l'échantillon ni plafonner artificiellement le drawdown mesuré. Son franchissement est daté (`stats["date_franchissement_dd"]`) et fait échouer le critère 4. Le drawdown est mesuré **au pire prix de chaque bougie**, comparé au plus haut des clôtures précédentes, comme la garde du bot réel. La limite journalière reste active. Le bot réel, lui, s'arrête.

**Contenu du rapport.** Le rapport (`reports/<date>/rapport.md` + `trades.csv`, `equity.png`, `drawdown.png`) contient :

- la période, la résolution, la balance initiale (3000 $ par défaut), les coûts ;
- le nombre de trades, le taux de réussite, les gains et pertes moyens en R, l'espérance (R et $), le profit factor, le rendement total, le CAGR, le drawdown max et sa durée, la plus longue série perdante, le Sharpe journalier ;
- la ventilation par année, par mois, long/short, par heure d'entrée et par raison de sortie ;
- le nombre de setups rejetés par raison et le nombre de jours bloqués par le filtre ADR ;
- les comparaisons avec deux références :
  - **Buy & hold** de l'or sur la même période (rendement et drawdown).
  - **Tendance seule** : des entrées au marché à des clôtures M15 tirées au hasard, dans la session, dans le sens de la tendance H1, avec un SL tiré dans la distribution des `distance_sl` de la stratégie, les mêmes sorties et le même risque. 200 tirages. On indique le percentile de l'espérance de la stratégie.
- **IS/OOS** : les premiers 60 % de la période contre les 40 % finaux, côte à côte. Aucun paramètre n'est optimisé.
- **Sensibilité** (pour information, on ne choisit pas « le meilleur ») :
  - `sl_plafond` ∈ {3, 5, 8, 12} × `mode_entree` ∈ {bord, milieu} ;
  - `validite_setup_barres` ∈ {4, 8, 16} ;
  - `spread_max` ∈ {0.30, 0.50} ;
  - coûts doublés (les deux glissements × 2).
- **Monte Carlo** : 1000 permutations de la séquence des R, avec la distribution du drawdown max et du rendement final.

**Verdict.** Il est **GO** si **tous** les critères suivants sont remplis :

1. au moins 100 trades au total et au moins 40 en OOS ;
2. une espérance OOS ≥ +0,10 R par trade, après coûts ;
3. un profit factor OOS ≥ 1,2 ;
4. un drawdown max ≤ 15 % sur la période, et ≤ 25 % au 95e percentile du Monte Carlo ;
5. une espérance au-dessus du 90e percentile de la référence « tendance seule » ;
6. une espérance > 0 dans les deux moitiés IS et OOS, pour au moins 3 des 4 plafonds de SL (en mode `bord`) et avec les coûts doublés.

Il est **NO-GO** si l'espérance OOS est ≤ 0 ou sous le 75e percentile de la référence. Sinon, le verdict est **À CREUSER**. Le rapport affiche chaque critère avec sa valeur et OK/KO.

## 7. Modules et responsabilités

| Fichier | Rôle | Dépendances |
|---|---|---|
| `sentitrade/config.py` | paramètres, validation (fait) | stdlib |
| `sentitrade/data.py` | `charger_bougies(chemin)`, `reechantillonner(df, regle)` (agrégats : open first, high max, low min, close last, volumes sum, spread max) | pandas |
| `sentitrade/indicators.py` | `ema`, `ranges_journaliers`, `filtre_adr` | pandas, numpy |
| `sentitrade/sessions.py` | `est_heure_entree`, `doit_cloturer`, `est_jour_autorise` | stdlib |
| `sentitrade/strategy.py` | `tendance_h1`, `tendance_a`, `detecter_fvg`, `Setup`, `MoteurSignaux` | pandas, numpy |
| `sentitrade/risk_manager.py` | `calculer_taille_lot`, `decouper_volume`, `GardeRisque` | stdlib |
| `sentitrade/backtest.py` | moteur d'exécution (section 5) | cœur |
| `sentitrade/reporting.py` | métriques, références, IS/OOS, sensibilité, Monte Carlo, verdict | cœur, matplotlib |
| `sentitrade/synthetique.py` | données M1/M15/H1 synthétiques au format de la section 2 (marche aléatoire, volatilité intrajournalière, spread variable) | numpy, pandas |
| `scripts/backtest.py` | CLI : `--donnees data/mt5`, `--synthetique`, `--sortie reports/...`, sections activables | cœur |
| `scripts/exporter_donnees_mt5.py` | export MT5 (PC Windows) | MetaTrader5 |
| plus tard | `mt5_connector.py`, `market_data.py`, `trade_executor.py`, `bot_monitor.py`, `main.py` | MetaTrader5 |

## 8. Tests exigés (`unittest`, lancés par `python3 -m unittest discover -s tests -t . -v` depuis la racine)

- **Données** : chargement, validation (OHLC incohérent refusé), rééchantillonnage.
- **Stratégie** : FVG long et short sur des bougies écrites à la main, avec entrée, SL et rejets. Pour la tendance, un test d'**absence d'anticipation** : modifier une bougie future ne change aucune valeur passée. Pour l'ADR, le jour D n'utilise pas D. La machine à setups doit être testée sur expiration, remplacement, annulation par la tendance, hors session et position ouverte.
- **Risque** : taille connue à la main, arrondi vers le bas (cas flottants pièges, par exemple 0.07/0.01), refus sous le minimum, plafond de levier, garantie risque ≤ 1 %, découpage, garde journalière et arrêt définitif.
- **Backtest** :
  - des scénarios à réponse connue : gain TP1 + breakeven, perte SL, clôture à 21h55, stop et TP1 dans la même bougie, gap ;
  - un test sur marche aléatoire synthétique (au moins 300 trades) : l'espérance ne doit pas être significativement positive (t de Student < 2), sinon il y a un bug ou une anticipation ;
  - le temps d'exécution complet du rapport doit rester < 9 minutes sur 3 ans de M1 dans le sandbox (2 vCPU). Simuler chaque trade sur des tableaux numpy, sans parcourir la boucle complète pour les tirages aléatoires.
