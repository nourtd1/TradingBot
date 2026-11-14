# Mission 3 pour Claude Code : exporter l'historique du nouveau broker (compte démo)

Tu travailles sur le PC Windows 11 de l'utilisateur. Il s'appelle annmh, il est étudiant, francophone et n'est pas développeur : parle-lui en français simple, en le tutoyant.

Comme pour les missions 1 et 2, tu es **les mains de l'architecte**. L'architecte est un autre Claude, qui écrit et teste le code dans un environnement sans internet ni MetaTrader 5.

Ta mission tient en quatre verbes : **vérifier la connexion, exporter les données, contrôler, rendre compte**. L'analyse des stratégies revient à l'architecte.

## 1. Où on en est

Le premier cycle de recherche s'est fait sur le compte **MetaQuotes-Demo**. Il a abouti à un NO-GO.

Le plan du cycle 2 (`docs/RECHERCHE_PLAN_CYCLE2.md` §5) exige de tester les stratégies sur des **marchés jamais vus**, chez un **vrai broker régulé** :

- de la crypto ;
- de l'énergie (pétrole WTI et Brent, gaz naturel) ;
- d'autres indices actions.

L'utilisateur a ouvert un **compte démo** chez un nouveau broker, en suivant `docs/GUIDE_BROKER.md`.

Ta mission 2 est terminée, voir `logs\RAPPORT_CLAUDE_CODE_2.md`. Depuis, l'exporteur a changé :

- **Univers étendu** à 32 noms génériques, avec une nouvelle classe **energies**.
- **Validation plus stricte** des symboles. Sont refusés :
  - les actions, ETF, fonds et warrants ;
  - les contrats à échéance datés (`CL-DEC26`) ;
  - le Brent pris pour du WTI.
- **Option `--dossier`** : un dossier de données par broker. Le script **refuse** d'écrire dans un dossier qui contient l'export d'un autre serveur. `data\univers` (MetaQuotes) est donc protégé.
- **`univers.json`** enregistre désormais :
  - `serveur` et `societe` (jamais le login ni le nom du titulaire) ;
  - pour chaque symbole, `trade_mode_texte`.
- **Décalage horaire** : le défaut de ton §6.2 est corrigé. Une mesure hors de [-12, +14] h est rejetée. Un export partiel ne remplace plus un décalage fiable par un décalage non fiable.
- **Option `--terminal`** : le chemin de `terminal64.exe`, à utiliser si plusieurs MetaTrader 5 sont installés.

Le dossier du projet est `C:\Users\annmh\AppData\Local\Claude-3p\local-agent-mode-sessions\c926e419\00000000\c14cc7f3\outputs\TradingBot`. Dans PowerShell : `$env:LOCALAPPDATA\Claude-3p\...\outputs\TradingBot`.

Lis d'abord :

- `CLAUDE.md` ;
- `docs/GARDE_FOUS.md` ;
- `docs/RECHERCHE_PLAN_CYCLE2.md`, surtout §5 ;
- `docs/GUIDE_BROKER.md` ;
- `config/univers_symboles.json` ;
- l'en-tête de `scripts/exporter_univers_mt5.py` ;
- `logs\RAPPORT_CLAUDE_CODE_2.md`.

## 2. Règles absolues

1. **Aucun ordre.** Tu ne fais que lire des données.
2. **Compte démo obligatoire.** Si le compte connecté est un compte réel, arrête-toi et préviens l'utilisateur.
3. **Aucun identifiant, ni lu ni écrit.**
   - Ne demande jamais le mot de passe, et ne le saisis pas toi-même : c'est l'utilisateur qui se connecte dans MetaTrader 5.
   - Ne lis pas `%USERPROFILE%\.tradingbot\.env`.
   - N'affiche et n'écris nulle part le **login** ni le **nom du titulaire**. N'affiche jamais `account_info()` en entier.
   - Le **nom du serveur** (`account_info().server`) et celui de la **société** (`account_info().company`) peuvent être affichés et notés, mais seulement eux.
4. Ne modifie ni `sentitrade/`, ni `tests/`, ni `config/config.json`, ni `docs/`. Ne touche pas non plus à **`data\univers\`** : ce sont les données du cycle 1, et l'architecte en a besoin telles quelles. Deux exceptions :
   - la section **`forcer`** de `config/univers_symboles.json`, voir 4.3 ;
   - une correction **minimale** d'un script de `scripts/` en cas de bug lié au vrai MT5 ou à Windows. Documente-la : fichier, avant/après, raison.
5. Pas d'installation de logiciel sans l'accord de l'utilisateur. Si le MetaTrader 5 du broker doit être installé, c'est l'utilisateur qui le fait (`docs/GUIDE_BROKER.md` §3).
6. Ne lance **pas** `scripts\recherche.py`.

Le Python du projet est `%USERPROFILE%\.tradingbot\venv\Scripts\python.exe`. Lance tout depuis la racine du projet. Pour les `.bat`, utilise `cmd /c ".\NOM.bat < NUL"`, car `NoDefaultCurrentDirectoryInExePath` est actif dans ton environnement.

## 3. Avant l'export

### 3.1 Tests sous Windows

Lance `-m unittest discover -s tests -t .`. Tous les tests doivent passer (`OK`, sans échec ni erreur). Note le nombre de tests.

En cas d'échec, note le test et l'erreur exacte, sans rien corriger dans `tests/` ni `sentitrade/`. Supprime ensuite les `__pycache__`.

### 3.2 Connexion au compte démo du **nouveau** broker

Le compte MetaQuotes-Demo existe toujours dans MetaTrader 5. L'export doit pourtant se faire connecté au **nouveau** compte.

1. Demande à l'utilisateur :
   - d'ouvrir le MetaTrader 5 du nouveau broker ;
   - de se connecter à son **compte démo** (Fichier > Se connecter à un compte de trading) ;
   - de **fermer tout autre MetaTrader 5** ;
   - de fermer les fenêtres de graphiques et les programmes inutiles, car la mémoire du PC est limitée.
2. Vérifie la connexion avec ce script en lecture seule. Il n'affiche que des informations non identifiantes :

   ```
   python -c "import MetaTrader5 as m; ok = m.initialize(); a = m.account_info() if ok else None; print('initialise:', ok); print('serveur:', a.server if a else None, '| societe:', a.company if a else None, '| demo:', (a.trade_mode == m.ACCOUNT_TRADE_MODE_DEMO) if a else None, '| devise:', a.currency if a else None, '| levier:', a.leverage if a else None, '| marge:', a.margin_mode if a else None); m.shutdown()"
   ```

3. Contrôle le résultat :
   - **serveur = `MetaQuotes-Demo`** : ce n'est pas le bon compte. Arrête-toi et demande à l'utilisateur de se connecter au nouveau compte.
   - **`demo: False`** : arrête-toi immédiatement.
   - **`initialise: False`**, ou mauvais terminal alors que plusieurs MetaTrader 5 sont installés : relance la commande en remplaçant `m.initialize()` par `m.initialize(path=r"<chemin>\terminal64.exe")`, avec le chemin du MetaTrader 5 du broker. Utilise ensuite l'option `--terminal "<chemin>\terminal64.exe"` à chaque appel de l'exporteur.
   - **Devise autre que USD** : note-le. L'export fonctionne, mais le projet suppose un compte en USD.
4. Choisis un **nom court** pour le broker : minuscules, chiffres et tirets, sans donnée personnelle, par exemple le premier mot du nom de la société. Le dossier de sortie sera `data\univers_<nomcourt>`. Garde **le même** à chaque lancement.

## 4. Export

### 4.1 Lister les symboles du broker

Lance `scripts\exporter_univers_mt5.py --lister`, puis lis `logs\symboles_broker_*.txt`, le plus récent. Pour chaque symbole, le fichier donne :

- le nom, le chemin (`path`) et la description ;
- les devises ;
- le `trade_mode` ;
- la résolution automatique proposée pour chaque nom générique, avec les candidats rejetés et leur raison.

### 4.2 Vérifier la correspondance de chaque nom générique

Les noms génériques sont ceux de `config/univers_symboles.json` :

| Classe | Noms génériques |
|---|---|
| forex | EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD |
| métaux | XAUUSD, XAGUSD, XPTUSD, XPDUSD, COPPER |
| indices | US500, NAS100, US30, GER40, UK100, JP225, EU50, FRA40, AUS200, HK50, ESP35, US2000 |
| énergies | USOIL (WTI), UKOIL (Brent), NGAS (gaz naturel) |
| crypto | BTCUSD, ETHUSD, LTCUSD, XRPUSD, SOLUSD |

Pour chacun, vérifie que le symbole retenu est **vraiment** le bon instrument :

- **Forex, métaux, crypto** : les devises doivent être cohérentes, par exemple BTC/USD.
  - Une crypto cotée en **USDT** n'est pas acceptée : ne la force pas, signale-la.
- **Indices** : il faut un **CFD sur indice**, avec un chemin du type `Indices\...`.
  - Jamais une action, un ETF ou un future daté.
  - La devise de cotation doit être celle du pays : EUR pour GER40, EU50, FRA40 et ESP35 ; HKD pour HK50 ; AUD pour AUS200.
- **Énergies** : il faut un **CFD continu** (« cash » ou « spot »).
  - Jamais un contrat daté comme `CL-DEC26`.
  - Jamais un ETF comme « US Oil Fund ».
  - Le WTI et le Brent ne doivent pas être inversés.
- **`trade_mode`** : note pour chaque symbole s'il est **tradable** (« complet ») ou non. Un symbole non tradable reste utile pour la recherche, mais pas pour la démo.

### 4.3 Compléter `forcer`, avec prudence

Si les alias ne trouvent pas le bon symbole, ou en trouvent un mauvais, ajoute dans la section `forcer` de `config/univers_symboles.json` la paire `"GENERIQUE": "NomExactBroker"`.

Ne le fais qu'après avoir vérifié le chemin, la description et les devises. Le script revérifie un nom forcé : il refuse toujours une action, un ETF ou un contrat daté.

**Dans le doute, ne force rien.** Un symbole absent vaut mieux qu'un mauvais instrument.

`forcer` vaut pour tous les brokers. Note chaque ajout et sa justification dans le compte rendu.

### 4.4 Lancer l'export complet, un jour de semaine, marché ouvert

**Vérifie d'abord la date et l'heure.** L'export doit se faire **du lundi au vendredi**, idéalement entre 9 h et 20 h (heure de Paris). Le décalage horaire du serveur ne se mesure de façon fiable que si les cotations bougent.

Si on est samedi ou dimanche, n'exporte pas. Dis à l'utilisateur de revenir un jour de semaine.

Lance :

```
scripts\exporter_univers_mt5.py --dossier data\univers_<nomcourt> --annees 20 --annees-m15 6
```

Ajoute `--terminal "<chemin>\terminal64.exe"` si tu en as eu besoin au 3.2.

- L'export peut être **long**, plus d'une heure. Utilise un délai d'exécution long.
- Tu peux aussi exporter par groupes avec `--symboles EURUSD,GBPUSD,...`, **toujours avec le même `--dossier`**. Les symboles déjà exportés sont alors conservés.
- N'utilise jamais `data\univers` : c'est le dossier de MetaQuotes, et le script le refuserait.

### 4.5 Gérer les échecs par symbole

Un symbole en échec part dans `absents`, avec sa raison, sans arrêter les autres.

Si l'échec ressemble à un problème passager (mémoire, téléchargement incomplet), relance-le seul avec `--symboles` et le même `--dossier`.

## 5. Contrôles

Lis `logs\export_univers_*.txt` et `data\univers_<nomcourt>\univers.json`. Pour chaque symbole exporté, vérifie les points suivants.

1. **`univers.json`** :
   - `serveur` est bien celui du nouveau broker, pas `MetaQuotes-Demo` ;
   - `decalage_fiable` vaut `true`. Sinon, relance un jour de semaine un petit export partiel, par exemple `--symboles EURUSD,XAUUSD` avec le même `--dossier`. Une mesure fiable remplacera alors la mesure non fiable.
2. **Périodes** : dates de début et de fin par timeframe.
   - D1 doit couvrir au moins 8 ans quand le broker les a.
   - M15 doit couvrir 6 ans pour XAUUSD, EURUSD, GBPUSD, US500, NAS100 et GER40.
   - Note les trous anormaux signalés par le script.
3. **Prix plausibles** :
   - contrôle un prix récent par symbole, avec le bon ordre de grandeur, sans zéro ni prix négatif ;
   - pour les symboles présents aussi dans `data\univers` (MetaQuotes), compare la clôture D1 d'une même date ancienne. L'écart doit rester de quelques pourcents au plus.
4. **`spread_stats.json`** : il doit être présent pour **chaque** symbole. Sans lui, le symbole est exclu de la recherche ; s'il manque, relance ce symbole seul. Signale aussi :
   - les **spreads médians nuls** (`global.p50` = 0), irréalistes ;
   - les spreads fixes (p50 = p90 = p99).
5. **Swaps** : `symbol_info.json` doit contenir `swap_mode`, `swap_mode_texte`, `swap_long` et `swap_short`.
   - Note les modes rencontrés.
   - Note les swaps de la crypto, souvent très élevés.
   - Note les cas `DISABLED` avec des valeurs non nulles.
6. **Tradable ou non** : `trade_mode_texte` de chaque symbole, dans `univers.json`. Fais la liste de ceux qui ne sont **pas** « complet ».
7. **Journées figées** : les journées entières où le prix ne bouge pas (high = low sur toute la séance, tick_volume identique d'un jour à l'autre), comme sur DE40 au cycle 1.
   - Cherche-les en D1 (high = low) et en M15.
   - Donne les dates.
8. **Taille minimale** (utile pour le futur petit compte) : pour chaque symbole, note `volume_min`, `volume_step` et `trade_contract_size` (`symbol_info.json`). Indique si le broker semble proposer un compte « cent », d'après les types de compte visibles dans MetaTrader 5 ou sur son site, sans rien ouvrir.
9. **Confidentialité** :
   - avec un script temporaire, lis le login et le nom du titulaire **en mémoire seulement**, sans jamais les afficher ;
   - cherche-les en octets (UTF-8 et UTF-16, sans tenir compte de la casse) dans `data\univers_<nomcourt>\` et `logs\` ;
   - supprime ensuite le script ;
   - il doit y avoir **0 occurrence**.

## 6. Compte rendu

Écris `logs\RAPPORT_CLAUDE_CODE_3.md` pour l'architecte. Il doit contenir :

- le résultat des tests : nombre, OK ou échecs détaillés ;
- le **serveur** et la **société** du broker (pas le login ni le nom) :
  - le type de compte : démo, hedging ou netting, devise, levier ;
  - le nom court choisi pour le dossier ;
- la date et l'heure de l'export, et le décalage serveur obtenu (valeur, fiable ou non) ;
- la correspondance générique → nom broker, avec le chemin, la description, les devises et le `trade_mode`, plus la justification de chaque `forcer` ;
- un tableau par symbole :
  - la classe ;
  - les barres et la période pour D1, H1 et M15 ;
  - le spread médian, en points et en prix ;
  - `swap_mode`, `swap_long` et `swap_short` ;
  - tradable ou non ;
  - `volume_min` ;
- les symboles absents et leur raison ;
- les anomalies : journées figées, spreads nuls, trous, prix suspects ;
- les corrections éventuelles apportées aux scripts ;
- les problèmes non résolus.

**Aucun identifiant dans ce rapport.**

Pour finir, dis à l'utilisateur en 2 ou 3 phrases simples ce qui a été fait, puis : **« Retourne voir Claude (Cowork) et dis-lui : export du nouveau broker terminé, le rapport est dans logs\RAPPORT_CLAUDE_CODE_3.md. »**

Ne lance **pas** `scripts\recherche.py`. L'utilisation des données des 12 derniers mois (contrôle final) est verrouillée et réservée à l'architecte.
