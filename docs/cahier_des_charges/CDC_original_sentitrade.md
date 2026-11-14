# CAHIER DES CHARGES : BOT DE TRADING ALGORITHMIQUE MT5 VIA CLAUDE AI

**Note de conception :** Ce document constitue le cahier des charges technique et fonctionnel complet (Master Specification Document) pour la création, le déploiement et la gestion d'un algorithme de trading automatisé sur MetaTrader 5, piloté par Python et généré via l'IA Claude. 
Il couvre l'infrastructure, la logique mathématique de la stratégie (Imbalance/FVG sur l'Or), le risk management, l'architecture du code Python, et les procédures de monitoring.

---

## 1. VUE D'ENSEMBLE DU PROJET (PROJECT OVERVIEW)

*   **Nom du Projet :** SentiTrade (Algorithme de Trading Haute Fréquence Assisté par IA)
*   **Objectif :** Automatiser une stratégie de trading basée sur la détection d'empreintes institutionnelles (Imbalances / Fair Value Gaps) sur le marché de l'Or (XAU/USD).
*   **Cible Technologique :** MetaTrader 5 (MT5), Python 3.10+, Environnement Windows (VPS).
*   **Méthodologie de Développement :** "AI-Driven Development" (Génération complète du code source par Claude AI via itérations séquentielles).

## 2. INFRASTRUCTURE ET ENVIRONNEMENT (INFRASTRUCTURE SETUP)

L'environnement de production doit être distinct de l'environnement de test. L'algorithme doit tourner 24h/24 et 7j/7 avec une latence minimale.

### 2.1. Spécifications du Serveur (VPS)
*   **Type d'hébergement :** Serveur Privé Virtuel (VPS) spécialisé Forex (ex: Forex VPS ou AWS EC2 Windows).
*   **Localisation :** Londres (Royaume-Uni) ou Francfort, pour être au plus proche des serveurs de liquidité des brokers (objectif : latence < 10ms).
*   **OS :** Windows Server 2022 (Obligatoire, car le terminal MetaTrader 5 et sa librairie Python native `MetaTrader5` requièrent un environnement Windows natif).
*   **Ressources minimales :** 2 vCPU, 4 GB RAM, 40 GB SSD.

### 2.2. Stack Technique et Dépendances (Requirements)
*   **Langage :** Python 3.10 ou supérieur.
*   **Plateforme de Trading :** MetaTrader 5 (Terminal installé sur le VPS).
*   **Compte :** Compte de Démonstration (Capital fictif : 3000$ à 5000$ pour simuler des conditions réelles de margin).
*   **Bibliothèques Python requises (`requirements.txt`) :**
    *   `MetaTrader5` (API officielle de connexion).
    *   `pandas` (Manipulation des dataframes et des séries temporelles).
    *   `numpy` (Calculs vectoriels pour les indicateurs).
    *   `pytz` (Gestion stricte des fuseaux horaires, critique en trading).
    *   `schedule` ou `time` (Gestion de la boucle d'exécution principale).

## 3. PARAMÈTRES DE LA STRATÉGIE DE TRADING (CORE LOGIC)

Cette section définit les règles mathématiques strictes que Claude devra implémenter. Il n'y a pas de place pour l'interprétation.

### 3.1. Actif et Temporalité
*   **Symbole (Ticker) :** `XAUUSD` (ou `XAUUSD.p`, `GOLD` selon le suffixe du broker).
*   **Unité de temps d'exécution (Timeframe) :** M15 (Bougies de 15 minutes).
*   **Unité de temps de tendance (Bias) :** H1 (Bougies de 1 heure).

### 3.2. Filtres Horaires (Time Filters)
*   **Heures de trading autorisées :** De 09h00 à 22h00 (Heure du serveur du broker).
*   **Jours autorisés :** Du Lundi au Vendredi.
*   **Sessions exclues :** Session asiatique (de 22h00 à 09h00) pour éviter les faux signaux liés au manque de liquidité et les spreads élargis.

### 3.3. Définition Technique du Signal d'Entrée (Imbalance / FVG)
L'algorithme doit identifier une "Fair Value Gap" (FVG) haussière ou baissière.
*   **Condition Haussière (Long) :**
    *   **Tendance H1 :** Haussière (ex: Moyenne Mobile 50 périodes orientée à la hausse).
    *   **Formation FVG M15 :** Le plus bas de la bougie 3 est supérieur au plus haut de la bougie 1. (Il y a un "trou" de cotation sur la bougie 2).
    *   **Trigger (Déclencheur) :** Le prix redescend et touche la zone de l'Imbalance (le plus haut de la bougie 1).
*   **Condition Baissière (Short) :**
    *   **Tendance H1 :** Baissière.
    *   **Formation FVG M15 :** Le plus haut de la bougie 3 est inférieur au plus bas de la bougie 1.
    *   **Trigger :** Le prix remonte et touche la zone de l'Imbalance (le plus bas de la bougie 1).

### 3.4. Filtres de Sécurité (Safety Checks)
*   **Spread Maximum :** Si le spread au moment du signal est supérieur à 30 points (3 pips), annuler l'entrée (protection contre la volatilité des annonces économiques).
*   **Volatilité (ADR) :** L'Average Daily Range ne doit pas être anormalement élevé ou plat.

## 4. GESTION DU RISQUE ET EXÉCUTION (RISK MANAGEMENT)

C'est le module le plus critique. Une stratégie moyenne avec un bon risk management sera rentable ; l'inverse détruira le compte.

| Paramètre | Valeur / Règle | Description |
| :--- | :--- | :--- |
| **Risque par Trade** | 1.0 % | Le bot doit calculer dynamiquement la taille du lot (Volume) pour que le Stop Loss représente exactement 1% du capital actuel (Balance). |
| **Stop Loss (SL)** | 50 Pips (5.0$) | Placé systématiquement derrière le point de structure opposé (Plus haut/bas précédent) avec un cap maximum de 50 pips. |
| **Take Profit 1 (TP1)** | 50 Pips (5.0$) | Ratio Risque/Récompense de 1:1. À ce niveau, clôturer 50% de la position et mettre le Stop Loss à Breakeven (Prix d'entrée). |
| **Take Profit 2 (TP2)** | Illimité (Runner) | Laisser courir les 50% restants de la position pour capturer les tendances exponentielles. |
| **Time Exit** | 21h55 | Clôture automatique (Force Close) de toutes les positions ouvertes (Runner TP2 inclus) avant la fermeture de la journée pour éviter le swap et les gaps de nuit. |

## 5. ARCHITECTURE DU CODE ET MODULES (CODE STRUCTURE)

L'architecture doit être modulaire (Clean Code) pour faciliter la maintenance et le débogage.

*   `config.json` : Fichier contenant les identifiants MT5, les lots de base, et les seuils de risque.
*   `mt5_connector.py` : Module gérant l'initialisation, le login, et le check de l'état du terminal.
*   `market_data.py` : Module chargé de récupérer les bougies (rates) et de calculer la tendance et les FVG.
*   `risk_manager.py` : Module mathématique pour le calcul du lot dynamique en fonction du SL et du solde du compte.
*   `trade_executor.py` : Module envoyant les requêtes d'ordres (`ORDER_TYPE_BUY`, `ORDER_TYPE_SELL`) et gérant les modifications (Breakeven, Partial Close).
*   `bot_monitor.py` : Script de surveillance qui envoie un statut toutes les 15 minutes (via logs ou webhook Discord/Telegram).
*   `main.py` : Le chef d'orchestre qui orchestre la boucle principale (`while True:` avec un `sleep` d'une minute).

---

## 6. SÉQUENCE DE PROMPTING POUR CLAUDE (MASTER PROMPTS)

Voici les prompts exacts à copier-coller un par un dans Claude pour générer l'architecture logicielle étape par étape.

### Prompt 1 : Connexion et Architecture de Base
> **Contexte pour Claude :**
> "Agis en tant qu'ingénieur logiciel quantitatif senior spécialisé en Python et MetaTrader 5. Je souhaite développer un robot de trading algorithmique robuste. Nous allons travailler de manière modulaire.
> 
> **Mission 1 :** Rédige un script Python nommé `mt5_connector.py` qui :
> 1. Importe la bibliothèque `MetaTrader5`.
> 2. Initialise la connexion au terminal MT5.
> 3. Tente de se connecter à un compte en utilisant des variables d'environnement (Login, Mot de passe, Serveur).
> 4. Vérifie que le terminal permet le trading automatisé (Algo Trading activé).
> 5. Affiche dans la console un résumé des informations du compte (Balance, Equity, Margin) si la connexion réussit.
> Ajoute un système complet de gestion d'erreurs (try/except) avec des logs explicites."

### Prompt 2 : Moteur de Données et Détection d'Imbalance (FVG)
> **Contexte pour Claude :**
> "Parfait, la connexion fonctionne. 
> 
> **Mission 2 :** Rédige un module `market_data.py`. 
> 1. Crée une fonction qui récupère les 100 dernières bougies sur le timeframe M15 et H1 pour l'actif XAUUSD, et retourne des DataFrames Pandas.
> 2. Crée une fonction `check_h1_trend(dataframe_h1)` qui détermine si la tendance est haussière ou baissière (utilise une moyenne mobile exponentielle 50).
> 3. Crée une fonction `detect_fvg(dataframe_m15)` qui scanne les 3 dernières bougies complètes.
>   - Pour une FVG Bullish : `Low(bougie 3) > High(bougie 1)`.
>   - Pour une FVG Bearish : `High(bougie 3) < Low(bougie 1)`.
> Retourne un dictionnaire indiquant si un signal FVG est présent, sa direction, et le prix d'entrée idéal (le comblement du vide)."

### Prompt 3 : Gestion du Risque (Position Sizing)
> **Contexte pour Claude :**
> "Excellent. Maintenant, sécurisons le capital.
> 
> **Mission 3 :** Rédige un module `risk_manager.py`.
> 1. Je veux risquer exactement 1% de ma `Balance` actuelle par trade.
> 2. Le Stop Loss fixe est de 500 points (50 pips) sur le XAUUSD.
> 3. Rédige une fonction `calculate_lot_size(account_balance, risk_percentage, stop_loss_points, tick_value)` qui retourne le volume exact de lot à ouvrir.
> 4. Assure-toi que le lot calculé respecte le volume minimal et maximal autorisé par le broker (utilise `mt5.symbol_info('XAUUSD').volume_min` et `volume_step`)."

### Prompt 4 : Exécution des Ordres et Logique Avancée
> **Contexte pour Claude :**
> "Le cœur du système. 
> 
> **Mission 4 :** Rédige le module `trade_executor.py`.
> 1. Crée une fonction pour ouvrir un ordre de marché (Buy ou Sell) avec un SL et un TP initiaux.
> 2. Le TP1 est placé à une distance égale au SL (Ratio 1:1). 
> 3. Crée une fonction de gestion de trade actif : si le prix atteint le TP1, le script doit :
>    - Envoyer une requête pour fermer 50% du volume de la position.
>    - Envoyer une requête pour modifier le SL du trade restant (Runner) en le plaçant au prix d'ouverture (Breakeven).
> 4. Implémente un filtre horaire strict : Aucune ouverture d'ordre en dehors de l'intervalle 09h00 - 22h00.
> 5. Crée une fonction `close_all_positions()` qui est appelée tous les jours à 21h55 précises pour fermer tous les trades ouverts."

### Prompt 5 : Assemblage (Main Loop) et Monitoring
> **Contexte pour Claude :**
> "Dernière étape. 
> 
> **Mission 5 :** Rédige le fichier `main.py` qui importe tous les modules précédents.
> 1. Implémente une boucle infinie `while True:` qui s'exécute à la fermeture de chaque bougie M15.
> 2. La séquence doit être : Check connexion -> Check Heure -> Fetch Data -> Check Tendance -> Check FVG -> Si Signal ET aucun trade en cours : Calcul du lot -> Ordre d'exécution.
> 3. En parallèle, à chaque tick ou chaque minute, vérifie les trades en cours pour la gestion du TP1 (Breakeven partial close).
> 4. Ajoute un logger robuste (utilisant la librairie `logging` de Python) qui écrit chaque action, chaque erreur, et l'état de la connexion dans un fichier `bot_logs.txt`.
> 5. Ajoute un petit script de "Heartbeat" (monitoring) qui affiche dans la console "Bot actif - Tendance actuelle H1: [Direction] - Trades en cours: [Nombre]" toutes les 15 minutes."

---

## 7. PLAN DE TEST ET DÉPLOIEMENT (QA & ROLLOUT)

Procédure stricte de déploiement pour s'assurer de la stabilité du système en conditions réelles.

### Phase 1 : Backtesting (Validation Mathématique)
Avant de lancer le bot, valider que la FVG sur l'Or est réellement profitable. 
*   Utiliser un script Python pour extraire 1 an d'historique de l'Or depuis MT5 (`mt5.copy_rates_from_pos`).
*   Créer un script de backtest rapide avec `pandas` pour simuler les entrées FVG et vérifier le Win Rate et le Drawdown.

### Phase 2 : Forward Testing (Démo)
*   Déployer le script complet sur le VPS (connecté à un compte de démonstration MetaTrader de 3000$).
*   Laisser tourner le bot sans **aucune** intervention manuelle pendant un minimum de 2 à 4 semaines.
*   **Objectif :** Traquer les bugs. Vérifier les logs : l'algorithme gère-t-il correctement les déconnexions intempestives du broker ? Ferme-t-il bien à 21h55 ? Gère-t-il bien les spreads explosifs lors des news économiques ?

### Phase 3 : Monitoring Temps Réel et Application Mobile
*   Installer l'application MetaTrader 5 sur smartphone.
*   Se connecter au compte de démonstration via l'application.
*   Dans l'onglet "Chat et messages" de MT5 Mobile, récupérer le MetaQuotes ID.
*   Dans MT5 sur le VPS (Outils -> Options -> Notifications), renseigner ce MetaQuotes ID. 
*   **Résultat :** À chaque fois que le bot Python prendra un trade, une notification push instantanée sera envoyée sur le mobile.

### Phase 4 : Passage en Réel (Live Trading)
*   Si le Forward Test est positif et sans bugs critiques (Crash de la boucle `while`), passage sur un petit compte réel (ex: 500$ ou compte de prop firm).
*   Conservation d'une approche de supervision humaine pour agir en cas de cygne noir sur les marchés.