# Guide : préparer MetaTrader 5 et exporter les données

Ce guide te mène, étape par étape, d'un PC sans MetaTrader 5 jusqu'aux fichiers de données dont le backtest a besoin. Compte environ une heure, dont une bonne partie d'attente pendant les téléchargements.

On travaille **uniquement sur un compte démo** (argent fictif). Aucun ordre n'est passé pendant cette phase : l'export ne fait que lire l'historique des prix.

Les noms de menus sont donnés en français, avec l'anglais entre parenthèses quand la traduction peut varier selon la version de MetaTrader 5.

---

## 1. Choisir un broker

MetaTrader 5 (MT5) est un logiciel. Les prix, le compte et l'exécution des ordres viennent d'un **broker** (courtier). Le choix du broker compte : le spread (l'écart entre prix d'achat et de vente), les horaires et même les bougies diffèrent d'un broker à l'autre.

Critères à vérifier sur le site du broker :

1. **Régulé par une autorité sérieuse** : par exemple la FCA (Royaume-Uni), la CySEC (Chypre, Union européenne), l'ASIC (Australie) ou l'AMF (France). Vérifie le numéro de licence sur le site de l'autorité elle-même, pas seulement sur celui du broker. Évite les brokers régulés uniquement dans de petits territoires offshore.
2. **Propose MetaTrader 5** (pas seulement MetaTrader 4).
3. **Propose l'or contre dollar** (souvent appelé `XAUUSD`, parfois `GOLD` ou `XAUUSD.p`, `XAUUSDm`, etc.) avec un **spread serré** : idéalement 30 points (0,30 $) ou moins aux heures actives. Regarde la page « conditions de trading » ou « spreads » du broker.
4. **Compte démo en USD**.
5. Idéalement, un compte de type **« hedging »** (plusieurs positions possibles sur le même symbole). Un compte « netting » fonctionne aussi, mais le hedging est plus souple pour la suite.

**Important : ouvre la démo chez le broker que tu utiliserais en réel.** Le spread, les horaires de cotation et les données diffèrent d'un broker à l'autre. Un backtest fait avec les données d'un broker A ne dit pas grand-chose de ce que donnerait le broker B.

Je ne te recommande pas de broker précis : compare deux ou trois brokers régulés avec ces critères.

## 2. Installer MetaTrader 5

1. Télécharge MetaTrader 5 **depuis le site de ton broker** (la version du broker est déjà configurée pour ses serveurs). À défaut, depuis le site officiel de MetaQuotes : https://www.metatrader5.com
2. Lance l'installation et accepte les options par défaut.
3. Ouvre MetaTrader 5.

## 3. Ouvrir un compte démo

1. Dans MetaTrader 5 : **Fichier > Ouvrir un compte** (File > Open an Account).
2. Cherche le nom de ton broker dans la liste et choisis son serveur **démo** (le nom contient souvent « Demo »).
3. Choisis **« Ouvrir un compte démo »** (Open a demo account) et remplis le formulaire :
   - **Type de compte** : le type standard du broker. Si le choix existe, prends une variante « hedging ».
   - **Devise** : **USD**.
   - **Dépôt** : entre **3 000 et 5 000 $**.
   - **Levier** : par exemple **1:100**. Le levier du compte n'est pas le risque : c'est la taille des positions, calculée par le bot, qui contrôle le risque.
4. Coche l'acceptation des conditions et valide.
5. MetaTrader 5 affiche ton **identifiant (login)** et ton **mot de passe**. Note-les dans un endroit sûr, **pas dans le dossier du projet** et **ne les donne jamais à Claude** (ni dans une conversation, ni dans un fichier).

Certains brokers font ouvrir le compte démo sur leur site web : dans ce cas, ils t'envoient l'identifiant, le mot de passe et le nom du serveur par e-mail.

## 4. Se connecter au compte démo

1. **Fichier > Connexion au compte de trading** (File > Login to Trade Account).
2. Saisis l'identifiant, le mot de passe et choisis le serveur démo. Coche **« Enregistrer le mot de passe »** (Save password) pour que la connexion se refasse toute seule.
3. En bas à droite de la fenêtre, tu dois voir une vitesse de connexion (par exemple `35 / 2 Kb`) et non « Pas de connexion » (No connection).
4. Dans la fenêtre **Boîte à outils** (Toolbox, menu Affichage / View si elle n'est pas visible), l'onglet **Trading** doit afficher un solde de 3 000 à 5 000 $.

## 5. Activer le bouton « Algo Trading »

Dans la barre d'outils en haut, clique sur le bouton **Algo Trading** (il s'appelait « AutoTrading » dans les anciennes versions). Il doit passer au **vert** (icône « play »).

Pour l'export des données, ce bouton n'est pas indispensable. Il le sera pour le bot. La vérification (`VERIFIER.bat`) le signale s'il est désactivé.

## 6. Régler le nombre maximal de barres sur « Unlimited »

Par défaut, MetaTrader 5 ne garde qu'un nombre limité de bougies par graphique. Avec ce réglage, on n'obtiendrait que quelques semaines de bougies d'une minute au lieu de plusieurs années.

1. **Outils > Options** (Tools > Options), onglet **Graphiques** (Charts).
2. Ligne **« Nombre max de barres dans le graphique »** (Max bars in chart) : choisis **Unlimited** (illimité) dans la liste.
3. Clique sur **OK**.
4. **Ferme complètement MetaTrader 5, puis rouvre-le.** Le réglage ne s'applique qu'au redémarrage.

## 7. Ajouter l'or dans l'« Observation du marché »

1. Ouvre la fenêtre **Observation du marché** (Market Watch) : menu **Affichage > Observation du marché** (View > Market Watch), ou `Ctrl+M`.
2. Si l'or n'y est pas : clic droit dans la fenêtre > **Symboles** (Symbols). Cherche « XAU » ou « GOLD », sélectionne le symbole **or contre dollar** (par exemple `XAUUSD`) et clique sur **Afficher le symbole** (Show Symbol), puis **OK**.
3. Vérifie que le prix de l'or bouge (pendant les heures d'ouverture : du lundi au vendredi).

Si ton broker propose plusieurs variantes (par exemple `XAUUSD` et `XAUUSD.p`), garde affichée celle que tu utiliserais pour trader. Le script choisit automatiquement la variante visible et tradable, et l'écrit dans son rapport.

## 8. Installer l'environnement Python (si ce n'est pas déjà fait)

Dans le dossier du projet, double-clique sur **`INSTALLER.bat`** et suis les instructions. À la fin, une vérification complète s'affiche. Elle contrôle aussi MetaTrader 5 : laisse donc MT5 **ouvert et connecté** pendant ce temps.

Si l'environnement est déjà installé, double-clique simplement sur **`VERIFIER.bat`** (MetaTrader 5 ouvert et connecté). La section « Terminal MetaTrader 5 » doit afficher :

- `[OK] connexion au serveur du broker : oui`
- `[OK] bouton Algo Trading : activé`
- `[OK] type de compte : démo`
- `[OK] symbole de l'or trouvé : ...`

Réinstalle aussi avec `INSTALLER.bat` si tu l'avais lancé avant ce guide : la liste des librairies a changé (ajout du module MetaTrader5).

## 9. Exporter les données

1. MetaTrader 5 est **ouvert et connecté** au compte démo. Laisse-le ouvert pendant tout l'export.
2. Double-clique sur **`EXPORTER_DONNEES.bat`**.
3. Patiente. La première fois, MetaTrader 5 doit télécharger plusieurs années d'historique chez le broker : cela peut prendre de quelques minutes à une demi-heure. Ne ferme pas la fenêtre noire.
4. À la fin, la fenêtre affiche « EXPORT TERMINE - tout est OK » ou « points à regarder ». Appuie sur une touche pour la fermer.

Le script crée :

- dans `data\mt5\` : les bougies de 1 minute, 15 minutes et 1 heure de l'or (`..._M1.csv`, `..._M15.csv`, `..._H1.csv`), les caractéristiques du symbole (`symbol_info.json`) et les statistiques de spread des 10 derniers jours ouvrés (`spread_stats.json`) ;
- dans `logs\` : un rapport lisible (`export_mt5_<date>.txt`).

Aucun identifiant, nom ni mot de passe n'est écrit dans ces fichiers.

Conseil : lance l'export **pendant l'ouverture du marché** (du lundi au vendredi, en journée). Le script mesure alors le décalage entre l'heure du serveur du broker et l'heure UTC. Le week-end, cette mesure est marquée comme non fiable (les données, elles, restent bonnes).

## 10. Si ça ne marche pas

Pas d'inquiétude : **dis simplement à Claude « l'export a échoué »** (ou « il y a des points à regarder »). Claude lit directement les rapports dans `logs\` (`export_mt5_*.txt`, `export_donnees.log`, `check_env_*.txt`) et t'explique quoi faire.

Les cas les plus fréquents :

| Message | Que faire |
|---|---|
| « impossible de joindre le terminal MetaTrader 5 » | Ouvre MetaTrader 5, connecte-toi au compte démo, puis relance `EXPORTER_DONNEES.bat`. |
| « pas connecté au serveur du broker » | **Fichier > Connexion au compte de trading** (File > Login to Trade Account), puis relance. |
| « historique TRONQUÉ » avec « Max bars in chart » | Refais l'étape 6 (Unlimited), **redémarre MetaTrader 5**, puis relance l'export. |
| « historique TRONQUÉ » sans « Max bars » | Le broker ne fournit pas plus d'historique en bougies d'une minute. Ce n'est pas bloquant : si les bougies d'une minute ne couvrent pas la période testée, le backtest travaille avec les bougies de 15 minutes et son rapport le signale. |
| « aucun symbole or/dollar trouvé » | Refais l'étape 7. Si le nom est inhabituel, lance l'export avec le nom exact (Claude t'indiquera comment). |
| « Compte RÉEL détecté » | Déconnecte-toi et connecte-toi au **compte démo** : cette phase se fait uniquement en démo. |
| « le module MetaTrader5 est absent » | Relance `INSTALLER.bat`. |
