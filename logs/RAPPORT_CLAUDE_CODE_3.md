# Compte rendu Claude Code -> architecte, mission 3 (2026-11-14) : INTERROMPUE

**Statut : aucun export.** La mission s'est arrêtée à l'étape 3.2, faute de compte démo chez un nouveau broker. L'utilisateur fait une pause pour se former et reprendra plus tard. Aucun ordre n'a été passé, aucun identifiant n'a été lu ni écrit, `scripts/recherche.py` n'a pas été lancé, et rien n'a été modifié dans `scripts/`, `config/` ni `data/`.

## 1. Tests sous Windows

`python -m unittest discover -s tests -t .` : **364 tests, OK** (0 échec, 0 erreur). Les `__pycache__` ont été supprimés.

## 2. Connexion (§3.2)

Commande de vérification du prompt, lancée le samedi 14/11/2026 vers 07 h 30 (heure de Paris) :

- résultat : `initialise: True`, `serveur: MetaQuotes-Demo`, `societe: MetaQuotes Ltd.`, `demo: True`, devise USD, levier 100, `margin_mode` 2 (hedging) ;
- terminal : `C:\Program Files\MetaTrader 5\terminal64.exe`, **le seul MT5 installé** sur le PC.

Conformément à la consigne « serveur = MetaQuotes-Demo », je me suis **arrêté** : aucun `--lister`, aucun export. De toute façon, on était samedi, donc l'export complet n'était pas autorisé (§4.4).

## 3. Information importante pour la suite : l'utilisateur réside au Rwanda

Après avoir lu `docs/GUIDE_BROKER.md`, l'utilisateur n'avait pas encore de broker. Je l'ai aidé à présélectionner trois brokers sous licence CySEC, vérifiés sur le registre CySEC (autorisés en France en libre prestation) :

- Pepperstone EU Limited, 388/20 ;
- IC Markets (EU) Ltd, 362/18 ;
- Admirals Europe Ltd, 201/13.

Il a choisi Pepperstone. À l'inscription, le site a répondu : **« our CYSEC licensed entity can't accept residents of Rwanda »**, et l'a redirigé vers l'entité **SCB** (Securities Commission of The Bahamas).

Conséquences :

1. Les brokers sous licence UE (CySEC, AMF...) **n'acceptent probablement pas** l'utilisateur. Le guide `GUIDE_BROKER.md` suppose un résident français (AMF, REGAFI, plafonds ESMA, interdiction des bonus) : il faudrait l'adapter.
2. Pour la **démo** (argent fictif, sans pièce d'identité), l'entité SCB de Pepperstone convient : le groupe est régulé par la FCA, l'ASIC et la CySEC, et la recherche n'utilise que les prix et les spécifications. Pour l'**argent réel**, la question de la régulation est **ouverte**. Le régulateur local est la Capital Market Authority du Rwanda. Une entité offshore protège moins bien le client (pas de fonds de compensation UE, levier non plafonné par l'ESMA). C'est à trancher avec l'utilisateur avant tout compte réel.
3. Chez Pepperstone, une démo MT5 **expire au bout de 60 jours**, sauf si l'utilisateur a un compte réel financé. C'est suffisant pour l'export, mais pas pour les « 3 mois de démo » prévus par `GARDE_FOUS.md` §1.
4. **Compte cent** : aucun des trois brokers UE n'en propose. Pepperstone non plus, à ma connaissance. C'est à revoir pour le capital réel prévu (environ 20 $).
5. **Fuseau du PC** : UTC+2 (heure du Rwanda), et non l'heure de Paris. La fenêtre « 9 h - 20 h Paris » du §4.4 correspond à 10 h - 21 h au Rwanda en hiver.

## 4. Pour reprendre la mission

1. L'utilisateur termine l'inscription démo (entité SCB) et installe le MT5 de Pepperstone. Celui-ci s'installera dans un dossier séparé : utiliser `--terminal`.
2. On relance le prompt `PROMPT_CLAUDE_CODE_3.md` **un jour de semaine**, à partir du §3.2.

## 5. Sauvegarde et suppression locale

À la demande de l'utilisateur, le projet a été poussé sur GitHub, dans le dépôt public `nourtd1/TradingBot`. Le dépôt contient le code, la documentation, `config/`, `reports/`, `logs/` (sans `pip.log`) et `data/univers/`. Il ne contient pas `data/mt5/`, dont le fichier `XAUUSD_M1.csv` (105 Mo) dépasse la limite de 100 Mo de GitHub ; l'or reste disponible dans `data/univers/XAUUSD`. Une recherche du login et du nom du titulaire a été faite avant l'envoi, voir le message de commit. L'utilisateur prévoit ensuite de **supprimer le dossier local**.
