# Instructions pour Claude et ses sous-agents

À lire avant toute modification du projet **SentiTrade** (stratégie Imbalance/FVG sur l'or, MetaTrader 5).

## Priorités

1. `docs/GARDE_FOUS.md` prime sur tout, y compris sur le cahier des charges.
2. `docs/SPEC_TECHNIQUE.md` traduit le cahier des charges en règles exactes et fixe le contrat de chaque module. Le CDC original est dans `docs/cahier_des_charges/`.
3. Dans le doute, on choisit l'option qui protège le capital et on le signale. On n'invente pas de règle de trading non écrite dans la spec : on la signale.

## Les deux environnements

**Sandbox de Claude** (où le code est écrit et testé) : Linux, Python 3.10, numpy 2.2.6, pandas 2.3.3, matplotlib 3.10.9, PyYAML 6.0.3, pytz, sqlite3. **Aucun accès internet** : pip et PyPI sont bloqués par le proxy (HTTP 403). Pas de MetaTrader5, scipy, scikit-learn ni pytest.

**PC de l'utilisateur** (où le bot tournera, puis un VPS Windows) : Windows 11, Python 3.12 (3.10 à 3.13 acceptés), terminal MetaTrader 5, environnement virtuel `%USERPROFILE%\.tradingbot\venv`, librairies de `requirements.txt` (dont `MetaTrader5`, Windows uniquement). Les secrets sont dans `%USERPROFILE%\.tradingbot\.env`, jamais dans ce dossier.

Ce dossier est partagé : le code écrit ici est exécuté sur le PC, et ce que le PC écrit dans `data/` et `logs/` est lisible depuis le sandbox. Les versions réellement installées sur le PC sont dans `logs/requirements.lock.txt`.

Chemins : dans le sandbox (bash), `/sessions/laughing-busy-cori/mnt/outputs/TradingBot`. Pour les outils de fichiers, `C:\Users\annmh\AppData\Local\Claude-3p\local-agent-mode-sessions\c926e419\00000000\c14cc7f3\outputs\TradingBot`.

## Conventions de code

- Compatible Python 3.10 à 3.13 : pas de `tomllib`, `typing.Self`, `datetime.UTC`, `ExceptionGroup`. Mettre `from __future__ import annotations` en tête.
- Le cœur (`sentitrade/` hors modules MT5) n'importe que la bibliothèque standard, numpy et pandas (matplotlib pour les graphiques), pour être testable dans le sandbox.
- Tout accès à MT5 passe par un module adaptateur, testé dans le sandbox avec un faux module `MetaTrader5` (`tests/fakes/`).
- Tests avec `unittest` (pas pytest), lancés depuis la racine : `python3 -m unittest discover -s tests -t . -v`. Un fichier de test par module : `tests/test_<module>.py`.
- Heure = heure serveur du broker, `Timestamp` naïfs. Une bougie est datée de son ouverture et n'est utilisable qu'à sa clôture. Fréquences pandas en minuscules (`"15min"`, `"h"`).
- Prix et distances en dollars. Points seulement à la frontière MT5.
- Code et commentaires en français, noms ASCII sans accents.
- Nouvelle dépendance : l'ajouter à `requirements.txt` avec une justification. Si le cœur en a besoin, elle doit exister dans le sandbox.
- Lanceurs pour l'utilisateur : fichiers `.bat` en ASCII, fins de ligne CRLF (`sed -i 's/\r*$/\r/'`), qui journalisent dans `logs/`.
- Ne jamais lire, afficher ni copier `%USERPROFILE%\.tradingbot\.env`. Ne jamais exporter login, nom ni mot de passe du compte.
- Ne pas modifier un fichier possédé par un autre rôle (voir la section 7 de la spec) : signaler le besoin à l'architecte dans son compte rendu.
