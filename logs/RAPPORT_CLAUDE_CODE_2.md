# Compte rendu Claude Code -> architecte, mission 2 (2026-11-14)

Mission : exporter l'historique de l'univers de recherche depuis MT5. Aucun ordre passé. `.env` n'a pas été lu. Aucun identifiant n'est écrit ici. `scripts/recherche.py` n'a pas été lancé.

Contexte : export lancé le **samedi 14/11/2026 vers 05 h UTC**, marché fermé (voir §6.1). Terminal build 6317, MetaQuotes-Demo, compte **démo** (vérifié par le script : « compte démo »). Python du venv : 3.13.17.

## 1. Tests sous Windows

`python -m unittest discover -s tests -t .` : **299 tests, OK** (0 échec, 0 erreur). Les `__pycache__` ont été supprimés après les tests et à la fin de la mission.

Mémoire avant l'export : 1,7 Go libre sur 8 Go, puis environ 2,1 Go après que l'utilisateur a fermé des programmes et les graphiques MT5. Aucun « Out of memory » bloquant. `symbol_select` renvoie toujours `False` (code 1 « Success »), mais la tolérance « déjà visible » a joué partout.

## 2. Correspondance générique -> broker

Liste complète : `logs/symboles_broker_20261114-045623.txt` (12 157 symboles). Catégories du serveur : `Forex` (126), `Indexes` (26), `Metals` (14) et `Nasdaq` (11 991 actions, ETF et warrants). **Aucune catégorie crypto.**

| Générique | Broker | path | Description | base/profit |
|---|---|---|---|---|
| EURUSD | EURUSD | Forex\EURUSD | Euro vs US Dollar | EUR/USD |
| GBPUSD | GBPUSD | Forex\GBPUSD | Pound Sterling vs US Dollar | GBP/USD |
| USDJPY | USDJPY | Forex\USDJPY | US Dollar vs Yen | USD/JPY |
| AUDUSD | AUDUSD | Forex\AUDUSD | Australian Dollar vs US Dollar | AUD/USD |
| USDCAD | USDCAD | Forex\USDCAD | US Dollar vs Canadian Dollar | USD/CAD |
| USDCHF | USDCHF | Forex\USDCHF | US Dollar vs Swiss Franc | USD/CHF |
| NZDUSD | NZDUSD | Forex\NZDUSD | New Zealand Dollar vs US Dollar | NZD/USD |
| XAUUSD | XAUUSD | Metals\XAUUSD | Gold vs US Dollar | XAU/USD |
| XAGUSD | XAGUSD | Metals\XAGUSD | Silver vs US Dollar | XAG/USD |
| US500 | US500 | Indexes\US500 | US SPX 500 Index | USD/USD |
| NAS100 | USTEC | Indexes\USTEC | US Tech 100 Index | USD/USD |
| US30 | US30 | Indexes\US30 | US Wall Street 30 Index | USD/USD |
| GER40 | DE40 | Indexes\DE40 | Germany 40 Index | USD/EUR (marge EUR) |
| UK100 | UK100 | Indexes\UK100 | FTSE 100 Index | GBP/GBP |
| JP225 | JPN225 | Indexes\JPN225 | Nikkei 225 | JPY/JPY |
| BTCUSD | absent | - | - | - |
| ETHUSD | absent | - | - | - |

- **`forcer` est resté vide** : la résolution automatique est correcte pour les 15 symboles trouvés. GOLD (`Nasdaq\Stock\GOLD`) et les SPX* (actions ou ETF) ont été rejetés comme prévu. Pour US500 et US30, ce sont les contrats standards qui ont été retenus, pas les « mini » (US500M, US30M).
- **Crypto** : aucun CFD crypto chez ce broker. Les seules lignes contenant BTC ou ETH sont des ETF ou trusts Nasdaq (BITO, ARKB, « Grayscale Bitcoin Mini Trust » au symbole `BTC`...). Elles n'ont pas été forcées, conformément à la règle « jamais un ETF ».
- **Important : les 6 indices ont `trade_mode` = désactivé** sur ce compte démo. Leur historique et leurs ticks sont lisibles, mais ils ne sont **pas tradables** ici, même en paper trading via MT5. Le forex et les métaux sont en mode « complet ».

## 3. Tableau par symbole

Spread médian = `global.p50` de `spread_stats.json`, en points, puis en devise de cotation entre parenthèses. Ticks du 02/11 au 13/11/2026, sauf UK100 (du 01/05 au 15/05/2026). Dernière bougie D1 : 12/11 partout, car le 13/11 a été retiré par prudence (décalage non fiable, voir §6.1).

| Générique | Classe | D1 (barres, période) | H1 (barres, période) | M15 (barres, période) | Spread médian | swap_mode |
|---|---|---|---|---|---|---|
| EURUSD | forex | 5192, 2006-11-15 -> 2026-11-12 | 123922, 2006-11-14 -> 2026-11-13 | 149138, 2020-11-13 -> 2026-11-13 | 0 (p90 1, p99 3) | POINTS |
| GBPUSD | forex | 5191, 2006-11-15 -> 2026-11-12 | 123896, 2006-11-14 -> 2026-11-13 | 149136, 2020-11-13 -> 2026-11-13 | 0 (p90 2, p99 4) | POINTS |
| USDJPY | forex | 5192, 2006-11-15 -> 2026-11-12 | 123903, 2006-11-14 -> 2026-11-13 | - | 2 (0,002 JPY) | POINTS |
| AUDUSD | forex | 5193, 2006-11-15 -> 2026-11-12 | 123921, 2006-11-14 -> 2026-11-13 | - | 1 | POINTS |
| USDCAD | forex | 5193, 2006-11-15 -> 2026-11-12 | 123929, 2006-11-14 -> 2026-11-13 | - | 1 | POINTS |
| USDCHF | forex | 5191, 2006-11-15 -> 2026-11-12 | 123884, 2006-11-14 -> 2026-11-13 | - | 1 | POINTS |
| NZDUSD | forex | 5191, 2006-11-15 -> 2026-11-12 | 123879, 2006-11-14 -> 2026-11-13 | - | 1 (p99 12) | POINTS |
| XAUUSD | métaux | 5149, 2006-11-15 -> 2026-11-12 | 116917, 2006-11-14 -> 2026-11-13 | 141068, 2020-11-13 -> 2026-11-13 | 13 (0,13 $) | POINTS |
| XAGUSD | métaux | 4642, 2008-11-07 -> 2026-11-12 | 105724, 2008-11-07 -> 2026-11-13 | - | 7 (0,007 $) | POINTS |
| US500 | indices | 3652, 2012-08-06 -> 2026-11-12 | 63976, 2012-08-06 -> 2026-11-13 | 137203, 2020-11-13 -> 2026-11-13 | 50 (0,50 $), fixe | CURRENCY_SYMBOL |
| NAS100 | indices | **1088, 2022-07-06** -> 2026-11-12 | 24701, 2022-07-06 -> 2026-11-13 | **98607, 2022-07-06** -> 2026-11-13 | 100 (1,00 $), fixe | CURRENCY_MARGIN |
| US30 | indices | 3653, 2012-08-06 -> 2026-11-12 | 63947, 2012-08-06 -> 2026-11-13 | - | 120 (1,20 $), fixe | CURRENCY_MARGIN |
| GER40 | indices | 3600, 2012-08-06 -> 2026-11-12 | 61858, 2012-08-06 -> 2026-11-13 | 130868, 2020-11-13 -> 2026-11-13 | 50 (0,50 EUR), p99 400 | CURRENCY_MARGIN |
| UK100 | indices | **47, 2026-03-06 -> 2026-05-14** | **absent** | - | 13 (1,3 GBP) | CURRENCY_MARGIN |
| JP225 | indices | **1957, 2019-04-29** -> 2026-11-12 | 43400, 2019-04-29 -> 2026-11-13 | - | 9 (9 JPY) | **DISABLED** (mais swap_long 294.231 / short -304.231) |

Pour chaque symbole, `symbol_info.json` contient `swap_mode`, `swap_mode_texte`, `swap_long` et `swap_short`. `spread_stats.json` est **présent pour les 15 symboles**.

Modes de swap rencontrés : `SYMBOL_SWAP_MODE_POINTS` (forex et métaux, triple swap le mercredi), `SYMBOL_SWAP_MODE_CURRENCY_SYMBOL` (US500), `SYMBOL_SWAP_MODE_CURRENCY_MARGIN` (USTEC, US30, DE40, UK100) et `SYMBOL_SWAP_MODE_DISABLED` (JPN225). Les indices ont leur triple swap le vendredi, sauf UK100 (mercredi).

Couverture par rapport au plan :

- D1 >= 8 ans : OK pour 12 symboles. **Insuffisant** pour NAS100 (4,4 ans), JP225 (7,5 ans) et UK100 (0,2 an).
- M15 sur 6 ans : OK pour XAUUSD, EURUSD, GBPUSD, US500 et GER40. **NAS100 ne couvre que 4,4 ans** : du 06/07/2022 au 13/11/2025, il y a **3,4 ans < 4 ans exigés** avant le hold-out pour la stratégie intraday.

## 4. Absents et inutilisables

- **BTCUSD et ETHUSD** : absents, aucun CFD crypto sur MetaQuotes-Demo (`absents` dans `univers.json`).
- **UK100** : exporté, mais **inutilisable**. L'historique se limite à 47 bougies D1, du 06/03 au 14/05/2026, et il n'y a aucune H1. Le dernier tick date du 15/05/2026 : l'instrument ne cote plus depuis mai. Ses données tombent entièrement dans la période de contrôle final. Deux relances seules (`--symboles UK100`, puis `--symboles EURUSD,UK100`) ont donné le même résultat : ce n'est pas un problème passager. Je propose de le traiter comme absent ; à toi de décider.

## 5. Contrôles de qualité

Prix récents (dernière clôture H1, 13/11/2026), avec le bon ordre de grandeur : EURUSD 1,1023, GBPUSD 1,3214, USDJPY 159,80, AUDUSD 0,6777, USDCAD 1,4266, USDCHF 0,8394, NZDUSD 0,5526, XAUUSD 3 874,97, XAGUSD 48,89, US500 7 556,3, USTEC 27 939,2, US30 52 313,1, DE40 26 771,3, JPN225 61 036. Dernière clôture D1 de UK100 : 10 352 (mai 2026).

Sur tous les CSV : aucun prix <= 0, aucune bougie incohérente (high < max(open, close) ou low > min(open, close)), aucun doublon, tri croissant.

Anomalies relevées :

1. **Trou de 7 à 8 semaines sur les indices** (repéré par le script) : du 16-17/07/2025 au 09/09/2025 sur US500, USTEC et US30 (environ 38 jours ouvrés), et du 23-24/07/2025 au 09/09/2025 sur DE40 (33 jours), en D1, H1 et M15. Le trou est en période de développement, juste avant le hold-out. Il n'y en a pas sur JPN225.
2. **DE40 : environ 20 journées « figées »**, d'octobre 2024 à janvier 2025, plus le 23/07/2025. Toute la séance (02:15 -> 22:45) affiche le même prix, high = low, avec un tick_volume identique d'un jour à l'autre (1243 en M15). Ce sont visiblement des bougies de remplissage. Jours en M15 : 2024-10-08, 10-30, 11-01, 11-04, 11-11, 11-20, 11-21, 11-25, 12-05, 12-06, 12-09, 12-16, 12-19, 12-23, 12-27, 12-30, 2025-01-02, 01-03, 01-06. Elles sont visibles aussi en H1 et en D1 (10 jours D1 avec high = low). Il faudrait les filtrer ou les exclure.
3. DE40 en H1 : 8 trous de plus de 3 jours autour de Noël (2012-2025), normaux.
4. Jours isolés avec high = low en D1 : jours fériés ou week-ends (EURUSD 01/01/2007, AUDUSD 01/01/2025, USDCAD 25/12/2006 et 31/10/2009, USDCHF 31/10/2009, US500 07/04/2018, US30 07-08/04/2018, JPN225 17/04/2021). Ils sont négligeables.
5. **Spreads** : médiane de **0 point sur EURUSD et GBPUSD**, ce qui est irréaliste pour un compte de détail. Les spreads des indices sont fixes (p50 = p90 = p99). Prévois des frais prudents plutôt que ces valeurs brutes.
6. JPN225 : `swap_mode` = DISABLED, mais `swap_long` et `swap_short` sont non nuls. À interpréter selon le mode, donc sans swap ; à confirmer.

Confidentialité : le login et le nom du titulaire ont été lus via `mt5.account_info()` dans un script temporaire (supprimé), puis recherchés en octets (UTF-8 et UTF-16, sans tenir compte de la casse) dans les **85 fichiers** de `data/` et `logs/`. **0 occurrence.** Les valeurs n'ont jamais été affichées.

## 6. Problèmes et remarques sur les scripts

Aucune correction n'a été apportée aux scripts. `config/univers_symboles.json` n'a pas été modifié (`forcer` vide).

1. **Décalage serveur non fiable** : export fait un samedi, marché fermé. `univers.json` indique `decalage_serveur_utc_heures = -6`, `decalage_fiable = false`. Cette valeur est **fausse**. La valeur mesurée en direct lors de la mission 1 (vendredi 13/11, XAUUSD) est **+2 h**. Conséquence : faute de décalage fiable, chaque symbole a retiré par prudence la bougie D1 du 13/11 (pourtant complète). Cela n'a aucun impact sur la période de développement. Relancer l'export un jour de semaine donnerait une valeur fiable.
2. **Défaut dans `mesurer_decalage`** (`scripts/exporter_univers_mt5.py`, vers la ligne 485) : quand aucun essai n'est fiable, c'est le **dernier** essai qui est gardé, pas le plus plausible. Avec `--symboles UK100` (puis `EURUSD,UK100`), la mesure s'est faite sur UK100, dont le dernier tick date de mai, et `univers.json` a reçu **-4383 h**. Je l'ai remis à une valeur cohérente en relançant `--symboles EURUSD,GBPUSD,XAUUSD` (essais limités à des symboles qui cotaient vendredi), sans modifier le code. Suggestions :
   - garder le premier essai, ou rejeter un décalage hors de [-12, +14] même quand il n'est pas fiable ;
   - lors d'un export partiel, ne pas remplacer un décalage déjà présent dans `univers.json` par un décalage moins fiable.
3. Les 6 indices ne sont **pas tradables** sur ce compte démo (`trade_mode` désactivé), voir §2. C'est un point à considérer avant tout paper trading sur les indices.
4. `symbol_select` renvoie `False` (code 1 « Success ») pour tous les symboles avec le vrai MT5. La tolérance « déjà visible » fonctionne.

Rapports d'export : `logs/export_univers_20261114-045657.txt` (export complet), puis `-053712` (UK100 seul), `-053858` (EURUSD, UK100) et `-054058` (EURUSD, GBPUSD, XAUUSD : état final de ces trois symboles et du décalage).
