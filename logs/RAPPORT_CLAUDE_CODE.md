# Compte rendu Claude Code -> architecte (2026-11-13)

Mission : installer l'environnement, vérifier, exporter l'historique de l'or. Aucun ordre passé, aucun identifiant lu dans `.env` ni écrit.

## 1. Environnement

- Python : **3.13.17** 64 bits (déjà présent : `%LOCALAPPDATA%\Programs\Python\Python313`). L'utilisateur a choisi de garder 3.13 plutôt qu'installer 3.12 ; aucun logiciel installé.
- Venv : `%USERPROFILE%\.tradingbot\venv`, créé par `INSTALLER.bat` sans erreur.
- Paquet **MetaTrader5 5.0.6231** (la contrainte `>=5.0.5200` est passée telle quelle, `requirements.txt` non modifié).
- Versions exactes dans `logs/requirements.lock.txt` (numpy 2.2.6, pandas 2.3.3, matplotlib 3.10.9, PyYAML 6.0.3, requests 2.34.2, python-dotenv 1.2.4).
- Terminal MT5 build 6317, serveur MetaQuotes-Demo, compte **démo**, USD, levier 1:100, hedging.

Remarque Windows : sur ce PC, la variable `NoDefaultCurrentDirectoryInExePath=1` est définie dans l'environnement de Claude Code, d'où l'échec de `cmd /c "INSTALLER.bat < NUL"` (« not recognized »). Il a fallu lancer `cmd /c ".\INSTALLER.bat < NUL"`. Le double-clic de l'utilisateur n'est pas concerné. Aucun `.bat` n'a été modifié.

## 2. check_env (`logs/check_env_windows_20261113-164935.txt`)

**TOUT EST OK, aucun `[!!]`.** Librairies 7/7, internet 3/3 (PyPI, Telegram, Discord), connecté, Algo Trading activé, compte démo, `maxbars = 100000000` (Unlimited déjà en place : l'étape 4.1 n'était plus nécessaire).

**Problème important, sans `[!!]`** : `choisir_symbole_or` a retenu **`GOLD`**. Sur MetaQuotes-Demo, ce symbole est l'**action Barrick Gold** (`path = Nasdaq\Stock\GOLD`, contrat 1, volume min 1 lot, pas de cotation), pas l'or. Le bon symbole est **`XAUUSD`** (`Metals\XAUUSD`, « Gold vs US Dollar »). Le choix automatique ne regarde pas le `path` ni `currency_base == "XAU"`. À corriger par l'architecte (check_env et le futur bot). L'export a été lancé avec `--symbole XAUUSD`.

## 3. Tests unitaires sous Windows

`python -m unittest discover -s tests -t .` : **201 tests, 200 OK, 1 KO**. Résultat identique avant et après la correction de la section 5.

- `tests.test_check_env.TestLibrairies.test_mt5_present`
  ```
  File "tests\test_check_env.py", line 152, in test_mt5_present
    self.assertTrue(any(l.startswith("[OK] MetaTrader5") and "5.0.5200" in l for l in r.lignes))
  AssertionError: False is not true
  ```
  Cause probable : `check_env._version()` lit d'abord `importlib.metadata.version("MetaTrader5")`. Le vrai paquet étant installé, il renvoie 5.0.6231 au lieu du `__version__` (5.0.5200) du faux module. Le test n'est pas hermétique quand le vrai paquet est présent. Il faudrait aussi simuler `metadata.version` dans le test. Rien n'a été modifié dans `tests/` ni `sentitrade/`.

Les dossiers `__pycache__` ont été supprimés.

## 4. Export (`logs/export_mt5_20261113-165140.txt`, code retour 0)

Symbole **XAUUSD**. Décalage heure serveur - UTC : **+2 h** (fiable, cotations en direct). Aucun historique tronqué, aucun trou anormal.

| TF | Bougies | Première | Dernière (heure serveur) |
|---|---|---|---|
| M1 | 1 758 514 | 2021-11-15 01:05 | 2026-11-13 18:50 |
| M15 | 117 551 | 2021-11-15 01:00 | 2026-11-13 18:30 |
| H1 | 29 416 | 2021-11-15 01:00 | 2026-11-13 17:00 |

Pour chaque TF, la bougie en cours de formation a été retirée.

- `digits` 2, `point` 0.01, `trade_contract_size` **100** oz, volume min 0.01, pas 0.01, max 100, tick value 0.1 $, `trade_stops_level` 0, `filling_mode` 3, swaps long -12.6 / short -4.6.
- Spread (3 669 650 ticks, 2026-11-02 au 2026-11-13) : **médiane 13 points (0,13 $)**, p90 40, p99 59. Il est plus large à 01h (médiane 21, p99 661) et à 22h (médiane 21) heure serveur. Le détail par heure est dans `spread_stats.json`.
- Contrôle des CSV : en-tête exact `time,open,high,low,close,tick_volume,spread,real_volume`, dates `YYYY-MM-DD HH:MM:SS`, dernier cours 3 880,73 $ (cohérent). `real_volume` vaut 0, la colonne `spread` est en points.
- Fichiers : `data/mt5/XAUUSD_M1.csv` (~105 Mo), `XAUUSD_M15.csv`, `XAUUSD_H1.csv`, `symbol_info.json`, `spread_stats.json`.
- Contrôle de confidentialité : `data/` et `logs/` ont été parcourus à la recherche du numéro et du nom du titulaire du compte (sans les afficher). **Aucune occurrence.**

## 5. Correction faite dans `scripts/`

Fichier `scripts/exporter_donnees_mt5.py`, fonction `_choisir_symbole` (vers la ligne 422).

Raison : avec le vrai MT5 (build 6317), `mt5.symbol_select("XAUUSD", True)` renvoie `False`, avec `last_error() = (-3, 'Terminal: Out of memory')`, et cela de façon systématique. Pourtant, `symbol_info("XAUUSD").visible` vaut `True`, et `copy_rates_*` / `copy_ticks_range` fonctionnent normalement. Le PC a 8 Go de RAM, dont environ 1 Go libre. Le premier export s'est donc arrêté sur « impossible de sélectionner le symbole » (rapport de ce premier essai supprimé, remplacé par le suivant).

Avant :
```python
    if not mt5.symbol_select(symbole, True):
        _, candidats, _ = choisir_symbole_or(mt5)
```
Après :
```python
    if not mt5.symbol_select(symbole, True):
        # MT5 réel (build 6317) : symbol_select peut renvoyer False ("Out of memory")
        # alors que le symbole est déjà dans l'Observation du marché. Dans ce cas, on continue.
        info_sel = mt5.symbol_info(symbole)
        if info_sel is not None and bool(getattr(info_sel, "visible", False)):
            r.ecrire(f"[--] symbol_select({symbole}) a échoué ({erreur_mt5(mt5)}), "
                     f"mais le symbole est déjà visible : on continue")
            return symbole
        _, candidats, _ = choisir_symbole_or(mt5)
```
Tests relancés après la correction : 200 OK, même unique échec qu'avant (section 3). Cette tolérance n'a pas de test dédié, il serait utile d'en ajouter un.

## 6. Problèmes non résolus

1. Choix automatique du symbole de l'or : `GOLD` (action) est retenu au lieu de `XAUUSD`. Ce problème concerne check_env, l'export sans `--symbole` et sans doute le futur bot.
2. Test `test_mt5_present` non hermétique quand le vrai paquet MetaTrader5 est installé.
3. `symbol_select` renvoie « Out of memory » sur ce terminal. Le contournement est en place pour l'export, mais le bot devra le gérer aussi.
4. `EXPORTER_DONNEES.bat` lancé sans argument utiliserait `GOLD` : en attendant la correction du point 1, il faut passer `--symbole XAUUSD`.
