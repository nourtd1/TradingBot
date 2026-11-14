# Guide : choisir un broker pour la démo, puis (beaucoup plus tard) pour un petit compte

Le compte démo actuel (serveur **MetaQuotes-Demo**) a servi au premier cycle de recherche. Il a deux gros défauts :

- il n'a ni crypto, ni pétrole, ni gaz ;
- ses indices ne sont **pas tradables**, même en démo.

Le plan de recherche (cycle 2, §5) demande donc un **compte démo chez un vrai broker régulé**. Ce guide t'aide à le choisir et à l'ouvrir.

On parle ici d'une **démo** : argent fictif, aucun risque. L'argent réel ne viendra que **beaucoup plus tard**, après au moins 3 mois de démo concluants et **ton accord explicite** (`GARDE_FOUS.md` §1).

Je ne te recommande **aucun broker par son nom**. Compare deux ou trois candidats avec les critères ci-dessous.

---

## 1. Les critères, dans l'ordre

### 1.1 Une régulation sérieuse, vérifiée à la source

Le broker doit être autorisé par une autorité reconnue, par exemple :

- **FCA** (Royaume-Uni) ;
- **CySEC** (Chypre, valable dans toute l'Union européenne) ;
- **ASIC** (Australie) ;
- **AMF** (France) ou **BaFin** (Allemagne).

**Ne te contente pas du logo sur le site du broker.** Fais ces trois vérifications :

1. Va sur le **registre officiel** du régulateur. Tape toi-même l'adresse du régulateur dans le navigateur, sans passer par un lien du broker.
2. Cherche la société par son nom ou son numéro de licence. Vérifie que la licence est **active**.
3. Vérifie que **l'adresse du site** inscrite au registre est bien celle du site où tu es. Des escrocs copient les sites de vrais brokers : ce sont des « clones ».

En France, l'AMF publie aussi des **listes noires** de sites non autorisés : vérifie que le broker n'y figure pas.

Évite les brokers régulés seulement dans de petits territoires offshore. Ces régulations protègent très peu le client.

### 1.2 MetaTrader 5

Le broker doit proposer **MetaTrader 5**, pas seulement MetaTrader 4 ou sa propre plateforme. Le bot et les scripts d'export ne fonctionnent qu'avec MT5.

### 1.3 Crypto, pétrole et indices tradables **en démo**

C'est le but de ce changement de broker. Sur sa page « instruments » ou « conditions de trading », vérifie qu'il propose en **CFD** :

- de la **crypto** : Bitcoin (BTCUSD), Ethereum (ETHUSD), et si possible d'autres ;
- de l'**énergie** : pétrole WTI (souvent XTIUSD, USOIL ou WTI), pétrole Brent (XBRUSD, UKOIL ou BRENT), gaz naturel (XNGUSD, NGAS) ;
- des **indices** au-delà des américains : Europe 50, CAC 40, Australie 200, Hong Kong 50, Espagne 35, Russell 2000, etc. ;
- les marchés déjà étudiés : forex, or, argent, S&P 500, Nasdaq, Dow Jones, DAX.

Il faut des **CFD « cash » ou « spot »**, à cotation continue. Évite les contrats à échéance (« futures » avec une date dans le nom, par exemple `CL-DEC26`).

Point important : **ces marchés doivent être tradables en démo**. Sur MetaQuotes-Demo, les indices s'affichent mais sont bloqués. Pour le vérifier dans MetaTrader 5 :

1. clic droit sur le symbole dans l'Observation du marché ;
2. **Spécification** ;
3. la ligne **« Mode de trading »** (Trade) doit indiquer **« Complet »** (Full access), et non « Désactivé » (Disabled) ou « Clôture seule » (Close only).

Le script d'export le vérifie aussi, symbole par symbole.

### 1.4 Un compte « cent » ou des micro-lots

C'est le critère le plus important pour la suite, avec un capital réel prévu d'environ **20 $**.

La règle du projet est de risquer **1 à 2 % du capital par trade**. Avec 20 $, cela fait **0,20 à 0,40 $** de perte maximale si le stop est touché.

Or, chez un broker classique, la plus petite position est de **0,01 lot**. Exemples :

- **Or** : 0,01 lot correspond à 1 once. Un stop placé 15 $ plus bas coûte **15 $**, soit 75 % du capital.
- **EUR/USD** : 0,01 lot correspond à 1 000 €. Un stop de 50 pips coûte **5 $**, soit 25 % du capital.

Les règles de risque deviennent alors impossibles à respecter. Et le bot ne contourne jamais la règle : si le lot minimal dépasse le risque autorisé, **il refuse le trade** (`GARDE_FOUS.md` §2).

Deux solutions existent :

- **Compte « cent »** : le solde est compté en cents. Tes 20 $ s'affichent comme 2 000 cents, et 0,01 lot y vaut 100 fois moins. Le même stop de 15 $ sur l'or coûte alors **0,15 $**, et 50 pips sur l'EUR/USD **0,05 $**. Avec 20 $, c'est en pratique **la seule façon de respecter 1 à 2 % de risque**.
- **Micro-lots** : certains brokers acceptent des tailles de **0,001 lot**. C'est mieux que 0,01, mais souvent encore trop gros pour 20 $ sur l'or ou les indices.

Vérifie donc que le broker propose un **compte cent en réel**, ou au minimum des micro-lots, même si tu commences en démo standard. Certains brokers n'ont pas de démo « cent ». Ce n'est pas grave : la démo standard sert à la recherche, et on reproduira les tailles du compte cent par calcul.

### 1.5 Des coûts visibles

Les coûts d'un CFD sont :

- le **spread** : l'écart entre le prix d'achat et le prix de vente ;
- la **commission**, sur certains comptes ;
- le **swap** : les frais payés pour chaque nuit où une position reste ouverte.

Un broker sérieux publie ces trois coûts par instrument. Les swaps sont aussi visibles dans MetaTrader 5 (Spécification, lignes « Swap long » et « Swap short »).

Méfie-toi d'un broker qui affiche partout « spread 0 » sans dire comment il se rémunère. C'est souvent une commission cachée, ou un spread qui s'écarte fortement aux moments importants.

### 1.6 Pas de bonus agressif

Un « bonus de 100 % sur ton dépôt » ou « 50 $ offerts pour commencer » est un **signal d'alarme**. Ces bonus s'accompagnent souvent de conditions qui bloquent les retraits.

Dans l'Union européenne, les régulateurs interdisent ce genre de bonus aux particuliers sur les CFD. Un broker qui en propose à un résident français n'est donc probablement pas régulé en Europe.

### 1.7 Les autres bons signes

- **Protection contre le solde négatif** : tu ne peux pas perdre plus que ce que tu as déposé. Elle est obligatoire dans l'UE pour les particuliers.
- **Avertissement de risque affiché**, du type « 74 % des comptes de particuliers perdent de l'argent ». En Europe, il est obligatoire. Ce chiffre est la réalité des CFD : prends-le au sérieux.
- **Compte « hedging »** proposé (plusieurs positions possibles sur un même symbole). Un compte « netting » fonctionne aussi.

---

## 2. Ouvrir la démo

1. Sur le site du broker, choisis **« Compte démo »**. En général, une adresse e-mail suffit. Ne donne **aucun document d'identité** pour une démo.
2. Choisis la plateforme **MetaTrader 5**.
3. Paramètres :
   - **Devise : USD** (le projet compte tout en dollars).
   - **Levier : modeste**, entre **1:30 et 1:100**. En Europe, il est de toute façon plafonné, par exemple à 1:30 sur le forex et 1:2 sur la crypto. Le levier du compte ne change pas le risque du bot : c'est la taille de position qui le contrôle.
   - **Solde fictif : entre 1 000 et 5 000 $**.
   - Type de compte : le type standard. Si le choix existe, prends une variante **hedging**.
4. Le broker t'envoie par e-mail :
   - un **numéro de compte** (login) ;
   - un **mot de passe** ;
   - le **nom du serveur** démo, souvent de la forme `NomDuBroker-Demo`.

   Garde-les pour toi : ni dans le projet, ni dans une conversation avec Claude.

## 3. Te connecter dans MetaTrader 5

### Cas 1 : le serveur du broker apparaît dans ton MetaTrader 5 actuel

1. Ouvre MetaTrader 5.
2. Menu **Fichier > Se connecter à un compte de trading**. Selon la version, le menu s'appelle « Connexion au compte de trading » (File > Login to Trade Account).
3. Saisis le login et le mot de passe, puis choisis le **serveur démo du broker** dans la liste. S'il n'y est pas, tape le nom du broker dans le champ pour le chercher.
4. Coche « Enregistrer le mot de passe » si tu veux. Il est alors gardé par MetaTrader 5, pas par le projet.
5. En bas à droite de MetaTrader 5, l'indicateur de connexion doit afficher un débit (par exemple « 12/1 kb ») et non « Pas de connexion ».

### Cas 2 : le serveur n'apparaît pas

1. Télécharge MetaTrader 5 **depuis le site du broker** : sa version connaît déjà ses serveurs.
2. Installe-le. Il s'installe dans un dossier séparé, à côté de l'autre MetaTrader 5.
3. Connecte-toi comme dans le cas 1.

**Garde un seul MetaTrader 5 ouvert pendant les exports.** Ferme celui de MetaQuotes avant de lancer un script. S'il y a un doute sur le terminal utilisé, Claude Code peut indiquer au script le bon terminal (option `--terminal`).

### Vérifier qu'on est sur la démo

Dans MetaTrader 5, ouvre la fenêtre **Navigateur** (Ctrl+N), puis **Comptes**. Le compte du nouveau broker doit y figurer, avec la mention **démo** (Demo). Le compte MetaQuotes-Demo existe toujours : il ne faut pas les confondre.

Les scripts du projet vérifient aussi que le compte est une démo et affichent le nom du serveur.

---

## 4. Prudence : les règles qui protègent ton argent

- **Ne partage jamais ton mot de passe**, ni avec Claude, ni avec un « conseiller », ni avec le support du broker. Les scripts du projet n'en ont pas besoin : ils utilisent le MetaTrader 5 déjà connecté.
- **Un démarcheur qui t'appelle, t'écrit sur WhatsApp, Telegram ou Instagram pour « gérer ton compte », « doubler ton capital » ou te faire « investir dans un robot gagnant », c'est une arnaque.** Raccroche. Un broker sérieux ne te démarche pas pour gérer ton argent.
- N'installe **jamais** un logiciel de prise en main à distance (AnyDesk, TeamViewer...) à la demande d'un inconnu.
- Ne paie jamais de « frais de déblocage » ou de « taxe » pour retirer de l'argent : c'est la marque des faux brokers.
- **Pas d'argent réel maintenant.** Le dépôt réel viendra bien plus tard, après :
  1. une stratégie validée par le plan de recherche ;
  2. **au moins 3 mois de démo** chez ce broker ;
  3. la comparaison de la démo avec le backtest ;
  4. **ton accord explicite**.

  Ce jour-là, on commencera petit (`GARDE_FOUS.md` §1), sur un compte cent si possible.
- À l'ouverture d'un compte **réel**, un broker régulé te demandera une pièce d'identité et un justificatif de domicile. C'est normal. Envoie-les **uniquement** via l'espace client sécurisé de son site officiel, jamais à quelqu'un qui te contacte.

---

## 5. Et ensuite ?

Une fois connecté au compte démo du nouveau broker :

1. ouvre Claude Code sur ton PC ;
2. donne-lui le prompt de `docs/PROMPT_CLAUDE_CODE_3.md`.

Il vérifiera la connexion (démo, nouveau serveur), listera les symboles du broker et exportera l'historique dans `data/univers_<nom du broker>`, **un jour de semaine, marché ouvert**. Il te rendra ensuite un compte rendu.
