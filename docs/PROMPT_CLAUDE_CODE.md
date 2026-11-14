# Mission pour Claude Code : installer l'environnement et exporter l'historique de l'or

Tu travailles sur le PC Windows 11 de l'utilisateur (annmh, francophone, pas développeur : parle-lui en français simple et tutoie-le). Un autre Claude, l'**architecte**, a écrit tout le code de ce projet dans un environnement séparé : un bac à sable Linux sans internet et sans MetaTrader 5. Il ne peut donc ni lancer de programme sur ce PC, ni parler au terminal MT5. Ton rôle est d'être ses mains sur le PC. Ta mission est volontairement limitée : **installer, vérifier, exporter les données, rendre compte**. L'analyse et le backtest reviennent ensuite à l'architecte.

## 1. Le projet

**SentiTrade** est un bot de trading sur l'or (XAUUSD) qui passe par MetaTrader 5 (MT5). Il cherche des « Fair Value Gaps » sur les bougies de 15 minutes, dans le sens de la tendance des bougies d'une heure. La stratégie n'est **pas encore validée**. Les données que tu vas exporter servent justement à la tester par backtest avant d'écrire le bot qui passera des ordres.

Le dossier du projet :

`C:\Users\annmh\AppData\Local\Claude-3p\local-agent-mode-sessions\c926e419\00000000\c14cc7f3\outputs\TradingBot`

Depuis PowerShell, c'est `$env:LOCALAPPDATA\Claude-3p\local-agent-mode-sessions\c926e419\00000000\c14cc7f3\outputs\TradingBot`.

Avant d'agir, lis :

- `CLAUDE.md` : environnements et conventions ;
- `docs/GARDE_FOUS.md` : règles de sécurité, prioritaires sur tout ;
- `docs/GUIDE_MT5.md` : les étapes destinées à l'utilisateur ;
- `INSTALLER.bat`, `VERIFIER.bat`, `EXPORTER_DONNEES.bat`, `requirements.txt`, `scripts/check_env.py`, `scripts/exporter_donnees_mt5.py`.

## 2. Ce qui est déjà fait

- Tout le code de la stratégie, du risque et du backtest existe. Les 201 tests unitaires passent sous Linux avec Python 3.10.
- MetaTrader 5 est installé. L'utilisateur a ouvert un **compte démo sur le serveur `MetaQuotes-Demo`** : compte « Hedge », 100 000 USD, levier 1:100.
- Le bouton **Algo Trading** est activé (vert), et le symbole **`XAUUSD`** est visible dans l'Observation du marché.

## 3. Règles absolues

1. **Ne passe aucun ordre.** N'ouvre, ne ferme et ne modifie aucune position, n'appelle jamais `order_send`, même sur la démo. Tu ne fais que lire des données.
2. **Ne demande jamais son mot de passe à l'utilisateur.** Ne le cherche pas et ne lis pas `%USERPROFILE%\.tradingbot\.env`. N'affiche ni n'écris nulle part le login, le nom ou le mot de passe du compte. Le script s'attache au terminal MT5 déjà ouvert et connecté : aucun identifiant n'est nécessaire.
3. **Ne modifie pas** `sentitrade/`, `tests/`, `config/config.json` ni les documents de `docs/` (sauf le fichier de compte rendu demandé en section 5).
   - Si un script de `scripts/` ou un `.bat` plante à cause d'une particularité de Windows ou de l'API MetaTrader5 réelle, tu peux faire une correction **minimale**.
   - Documente-la dans le compte rendu : fichier, ligne, avant/après, raison.
   - Relance ensuite les tests (étape 4.4).
4. Demande l'accord de l'utilisateur avant d'installer un logiciel, par exemple Python via winget.
5. Si le compte connecté est un compte **réel**, arrête-toi et préviens l'utilisateur. Cette phase se fait uniquement en démo.

## 4. Ce qu'il reste à faire, dans l'ordre

### 4.1 Régler l'historique illimité dans MT5

Par défaut, MT5 ne garde qu'un nombre limité de bougies par graphique, ce qui tronquerait l'historique. Fais faire ce réglage par l'utilisateur dans l'interface, en le guidant :

1. **Tools > Options**, onglet **Charts**, ligne **« Max bars in chart »** : choisir **Unlimited**, puis **OK**.
2. **Fermer complètement MT5, le rouvrir** et attendre qu'il se reconnecte : les prix doivent bouger.

Ne modifie pas les fichiers `.ini` du terminal toi-même. Tu vérifieras le résultat à l'étape 4.3 : `terminal_info().maxbars` doit être très grand.

### 4.2 Installer l'environnement Python

1. Vérifie qu'un Python 64 bits **3.12** est présent. 3.10 à 3.13 sont acceptés, 3.12 est préféré pour le paquet MetaTrader5. Utilise `py -0p`, ou regarde dans `%LOCALAPPDATA%\Programs\Python`.
2. S'il manque, propose à l'utilisateur `winget install --exact --id Python.Python.3.12` et attends son accord.
3. Lance `INSTALLER.bat` depuis le dossier du projet, **avec l'entrée standard redirigée** pour que les `pause` ne bloquent pas :
   - en PowerShell : `cmd /c "INSTALLER.bat < NUL"` ;
   - en Git Bash : `cmd //c "INSTALLER.bat < NUL"`.

   Le script effectue alors ces opérations :

   - il crée l'environnement virtuel `%USERPROFILE%\.tradingbot\venv` ;
   - il installe `requirements.txt` ;
   - il écrit `logs\requirements.lock.txt` ;
   - il copie `.env.example` vers `%USERPROFILE%\.tradingbot\.env` s'il n'existe pas ;
   - il crée un raccourci sur le Bureau ;
   - il lance `scripts\check_env.py`.
4. S'il bloque ou échoue, fais l'équivalent à la main avec le Python 3.12 trouvé :
   - `python -m venv %USERPROFILE%\.tradingbot\venv` ;
   - avec le Python du venv : `-m pip install --upgrade pip` puis `-m pip install -r requirements.txt` ;
   - `-m pip freeze > logs\requirements.lock.txt`.

   Lis `logs\installation.log` et `logs\pip.log` pour comprendre l'erreur.
5. Point incertain : la contrainte `MetaTrader5>=5.0.5200` n'a pas pu être vérifiée sans internet. Si pip refuse, regarde les versions disponibles avec `pip index versions MetaTrader5`. Ajuste alors la contrainte dans `requirements.txt` au minimum nécessaire (fichier en ASCII) et note-le dans le compte rendu.

### 4.3 Vérifier

Lance, avec le Python du venv (`%USERPROFILE%\.tradingbot\venv\Scripts\python.exe`) : `scripts\check_env.py`. Le rapport s'écrit dans `logs\check_env_windows_*.txt`.

Dans la section « Terminal MetaTrader 5 », il faut :

- connexion au serveur : oui ;
- Algo Trading : activé ;
- type de compte : démo ;
- symbole de l'or trouvé ;
- `maxbars` très grand.

Si `maxbars` reste petit, l'étape 4.1 n'a pas été appliquée ou MT5 n'a pas redémarré : refais-la avec l'utilisateur. Un `[!!]` purement réseau (Telegram, Discord bloqués) n'est pas bloquant.

### 4.4 Lancer les tests unitaires sous Windows

Ils n'ont jamais tourné sous Windows : c'est une vérification précieuse. Depuis la racine du projet, avec le Python du venv : `-m unittest discover -s tests -t .`

Le résultat attendu est 201 tests OK. Les tests MT5 utilisent un faux module, même si le vrai est installé. Pour chaque échec, note le nom du test et l'erreur exacte. **Ne corrige pas `sentitrade/` ni `tests/`** : l'architecte s'en chargera. Supprime ensuite les dossiers `__pycache__` créés.

### 4.5 Exporter l'historique de l'or

1. MT5 doit être ouvert et connecté. Nous sommes un jour de semaine, marché ouvert : c'est le meilleur moment.
2. Lance, avec le Python du venv : `scripts\exporter_donnees_mt5.py --annees 5`. Le lanceur équivalent est `EXPORTER_DONNEES.bat`, avec `< NUL`.
3. La première fois, MT5 télécharge l'historique chez le serveur, ce qui peut prendre jusqu'à 30 minutes. Prévois un délai d'exécution long et ne coupe pas le processus.
4. Résultats attendus dans `data\mt5\` :
   - `XAUUSD_M1.csv`, `XAUUSD_M15.csv`, `XAUUSD_H1.csv` ;
   - `symbol_info.json` ;
   - `spread_stats.json`.

   Le rapport s'écrit dans `logs\export_mt5_*.txt`.
5. Lis ce rapport et contrôle :
   - le nombre de bougies et les dates de début et de fin par unité de temps ;
   - les trous signalés ;
   - le décalage serveur/UTC ;
   - le message « historique TRONQUÉ » éventuel. S'il mentionne « Max bars », refais 4.1 puis relance l'export. Sinon, c'est simplement la limite du serveur : ce n'est pas bloquant, mais note-le.
6. Contrôle rapide d'un CSV :
   - en-tête exact `time,open,high,low,close,tick_volume,spread,real_volume` ;
   - format `YYYY-MM-DD HH:MM:SS` ;
   - un prix de l'or récent cohérent, autour de 3 800 à 3 900 $ ;
   - dans `symbol_info.json`, notes `digits`, `point` et `trade_contract_size`.
7. Vérifie qu'aucun fichier de `data\` ou de `logs\` ne contient le login ou le nom du titulaire du compte. Si tu en trouves, supprime-les et signale-le.

## 5. Compte rendu

Écris `logs\RAPPORT_CLAUDE_CODE.md`, en français, à destination de l'architecte. Il contient :

- la version de Python et celle du paquet MetaTrader5 installées ;
- le résultat de `check_env`, avec chaque `[!!]` ;
- le résultat des tests unitaires : nombre de OK et KO, et pour chaque échec le test et l'erreur exacte ;
- pour l'export : le symbole, la période couverte par timeframe, le nombre de bougies, `digits`, `point`, la taille du contrat, le spread médian, le décalage serveur/UTC, et les avertissements ;
- toute correction faite dans `scripts/` ou un `.bat`, avec l'avant/après et la raison ;
- les problèmes non résolus.

**Aucun identifiant dans ce fichier.**

Pour finir, dis à l'utilisateur en deux ou trois phrases simples ce qui a été fait. Termine par ce message : **« Retourne voir Claude (Cowork) et dis-lui : c'est fait, le rapport est dans logs\RAPPORT_CLAUDE_CODE.md. »** C'est l'architecte qui lancera le backtest et donnera le verdict. Ne lance pas `scripts\backtest.py` toi-même, et ne modifie aucun paramètre de la stratégie.
