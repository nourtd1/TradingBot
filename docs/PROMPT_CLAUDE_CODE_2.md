# Mission 2 pour Claude Code : exporter l'historique de tout l'univers de recherche

Tu travailles sur le PC Windows 11 de l'utilisateur. Il s'appelle annmh, il est étudiant, francophone et n'est pas développeur : parle-lui en français simple, en le tutoyant. Comme pour la mission 1, tu es **les mains de l'architecte** : un autre Claude, qui écrit et teste le code dans un environnement sans internet ni MetaTrader 5.

Ta mission : **vérifier, exporter les données, rendre compte**. L'analyse des stratégies, elle, revient à l'architecte.

## 1. Où on en est

La stratégie FVG sur l'or a été rejetée par le backtest (NO-GO). L'architecte lance maintenant un **programme de recherche sur plusieurs marchés** : forex, métaux, indices et crypto, avec 4 familles de stratégies aux règles figées à l'avance.

Il lui faut l'historique de ces marchés depuis MetaTrader 5 :

- D1 et H1 : jusqu'à 20 ans ;
- M15 : 6 ans pour 6 symboles.

Ta mission 1 (installation et export de l'or) est terminée, voir `logs\RAPPORT_CLAUDE_CODE.md`. Tes remarques ont été corrigées depuis :

- la détection du symbole de l'or ne prend plus l'action « GOLD » ;
- la tolérance `symbol_select` est testée ;
- le test qui échouait sous Windows est réparé.

Le dossier du projet est `C:\Users\annmh\AppData\Local\Claude-3p\local-agent-mode-sessions\c926e419\00000000\c14cc7f3\outputs\TradingBot`. Dans PowerShell : `$env:LOCALAPPDATA\Claude-3p\...\outputs\TradingBot`.

Lis d'abord :

- `CLAUDE.md` ;
- `docs/GARDE_FOUS.md` ;
- `docs/RECHERCHE_PLAN.md`, surtout §1 (univers) et §2 (périodes) ;
- `config/univers_symboles.json` ;
- l'en-tête de `scripts/exporter_univers_mt5.py`.

## 2. Règles absolues

Ce sont les mêmes que pour la mission 1 :

1. **Aucun ordre.** Tu ne fais que lire des données.
2. **Aucun identifiant.** Ne demande pas de mot de passe et ne lis pas `%USERPROFILE%\.tradingbot\.env`. N'écris nulle part le login ni le nom du titulaire.
3. Ne modifie ni `sentitrade/`, ni `tests/`, ni `config/config.json`, ni `docs/`. Deux exceptions :
   - la section **`forcer`** de `config/univers_symboles.json`, voir 4.3 ;
   - une correction **minimale** d'un script de `scripts/` en cas de bug lié au vrai MT5 ou à Windows. Documente-la (fichier, avant/après, raison).
4. Le compte doit être le compte **démo**. Si c'est un compte réel, arrête-toi.
5. Pas d'installation de logiciel sans l'accord de l'utilisateur.

Le Python du projet est `%USERPROFILE%\.tradingbot\venv\Scripts\python.exe`. Lance tout depuis la racine du projet. Pour les `.bat`, utilise `cmd /c ".\NOM.bat < NUL"`, car `NoDefaultCurrentDirectoryInExePath` est actif dans ton environnement.

## 3. Avant l'export

1. **Tests sous Windows** : `-m unittest discover -s tests -t .`. Le résultat attendu est de **299 tests OK**. Note chaque échec avec le test et l'erreur exacte, sans rien corriger dans `tests/` ni `sentitrade/`. Supprime ensuite les `__pycache__`.
2. **Mémoire.** Lors de la mission 1, MT5 renvoyait « Out of memory » : le PC n'avait qu'environ 1 Go libre. Demande à l'utilisateur de fermer les programmes inutiles et, dans MT5, les fenêtres de graphiques ouvertes (EURUSD, GBPUSD, USDCHF, USDJPY). MT5 doit rester **ouvert et connecté**.

## 4. Export

### 4.1 Lister les symboles du broker

Lance `scripts\exporter_univers_mt5.py --lister`, puis lis `logs\symboles_broker_*.txt`. Ce fichier contient le nom, le chemin (`path`), la description et les devises de chaque symbole.

### 4.2 Vérifier la correspondance de chaque nom générique

Les noms génériques viennent de `RECHERCHE_PLAN.md` §1 :

- forex : EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, USDCHF, NZDUSD ;
- métaux : XAUUSD, XAGUSD ;
- indices : US500, NAS100, US30, GER40, UK100, JP225 ;
- crypto : BTCUSD, ETHUSD.

Pour chacun, vérifie dans la liste quel symbole du broker correspond **vraiment** :

- **Forex, métaux, crypto** : la devise de base et la devise de profit doivent être cohérentes, par exemple BTC et USD pour BTCUSD.
- **Indices** : il faut un **indice ou un CFD sur indice**, avec un chemin du type `Indexes\...`. Jamais une action, un ETF ou un future à échéance. Rappel : sur ce serveur, « GOLD » est l'action Barrick Gold.

### 4.3 Compléter `forcer` si besoin

Si les alias de `config/univers_symboles.json` ne trouvent pas le bon symbole, ou en trouvent un mauvais, ajoute dans `forcer` la paire `"GENERIQUE": "NomExactBroker"`, après avoir vérifié la description et le chemin.

**Dans le doute, ne force rien** : un symbole absent vaut mieux qu'un mauvais instrument. Note chaque choix dans le compte rendu.

### 4.4 Lancer l'export complet

Lance : `scripts\exporter_univers_mt5.py --annees 20 --annees-m15 6`.

L'option M15 sur **6 ans** est indispensable : la stratégie intraday exige au moins 4 ans de données avant le 13/11/2025.

L'export peut être **long**, potentiellement plus d'une heure, car MT5 télécharge l'historique. Utilise un délai d'exécution long, ou lance-le par groupes avec `--symboles EURUSD,GBPUSD,...`. Quand l'option `--symboles` est utilisée, les symboles déjà présents dans `univers.json` sont conservés.

### 4.5 Gérer les échecs par symbole

Un symbole en échec part dans `absents`, avec sa raison, sans arrêter les autres. Si l'échec ressemble à un problème passager (mémoire, téléchargement incomplet), relance-le seul avec `--symboles`.

## 5. Contrôles

Pour chaque symbole exporté, lis `logs\export_univers_*.txt` et `data\univers\univers.json`, puis vérifie :

- **Historique** : les dates de début et de fin par timeframe. D1 doit couvrir au moins 8 ans si le broker les a. M15 doit couvrir 6 ans pour XAUUSD, EURUSD, GBPUSD, US500, NAS100 et GER40. Note aussi les trous anormaux.
- **Prix plausibles** : contrôle visuellement un prix récent par symbole, avec le bon ordre de grandeur, sans zéro ni prix figés.
- **`spread_stats.json`** : il doit être présent pour **chaque** symbole. **Sans lui, le symbole est exclu de la recherche.** S'il manque, relance ce symbole seul ; pour la crypto, le week-end convient.
- **Swaps** : `symbol_info.json` doit contenir `swap_mode`, `swap_long` et `swap_short`. Note les modes de swap rencontrés (`swap_mode_texte`).
- **Confidentialité** : cherche, sans les afficher, le login et le nom du titulaire dans `data\` et `logs\`. Il ne doit y avoir aucune occurrence.

## 6. Compte rendu

Écris `logs\RAPPORT_CLAUDE_CODE_2.md` pour l'architecte. Il doit contenir :

- le résultat des tests ;
- la correspondance générique → nom broker, avec le chemin et la description, et la justification de chaque `forcer` ;
- un tableau par symbole : classe, barres et période pour D1, H1 et M15, spread médian, `swap_mode` ;
- les symboles absents et leur raison ;
- les corrections éventuelles apportées aux scripts ;
- les problèmes non résolus.

**Aucun identifiant dans ce rapport.**

Pour finir, dis à l'utilisateur en 2 ou 3 phrases simples ce qui a été fait, puis : **« Retourne voir Claude (Cowork) et dis-lui : export de l'univers terminé, le rapport est dans logs\RAPPORT_CLAUDE_CODE_2.md. »**

Ne lance **pas** `scripts\recherche.py`. L'utilisation des données des 12 derniers mois (contrôle final) est verrouillée et réservée à l'architecte.
