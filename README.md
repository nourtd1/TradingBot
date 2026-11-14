# SentiTrade

Bot de trading sur l'or (XAUUSD) via MetaTrader 5. Il entre sur les « imbalances » (Fair Value Gaps M15) dans le sens de la tendance H1.

**Statut au 13/11/2026 :** le backtest sur 5 ans de données réelles de l'or donne **NO-GO** : la stratégie FVG du cahier des charges perd de l'argent, même sans frais. Le bot de trading n'est donc pas construit. Explication dans [reports/2026-11-13_XAUUSD/VERDICT_EXPLIQUE.md](reports/2026-11-13_XAUUSD/VERDICT_EXPLIQUE.md). Les outils (export MT5, backtest, gestion du risque, 205 tests) restent prêts pour tester une autre idée.

**14/11/2026 :** la recherche sur 14 marchés (forex, métaux, indices) avec 4 méthodes reconnues donne aussi **NO-GO** : aucune ne passe les critères fixés à l'avance. Voir [reports/recherche_2026-11-14/VERDICT_EXPLIQUE.md](reports/recherche_2026-11-14/VERDICT_EXPLIQUE.md). Les 12 derniers mois de données restent sous clé, intacts.

Pour réexporter les données : `EXPORTER_DONNEES.bat` choisit désormais correctement `XAUUSD` (et non l'action « GOLD »).

## Ce que tu as à faire maintenant

1. Suis **[docs/GUIDE_MT5.md](docs/GUIDE_MT5.md)** : installer MetaTrader 5, ouvrir un compte démo, régler l'historique illimité.
2. Double-clique sur **`INSTALLER.bat`** (une seule fois).
3. MetaTrader 5 ouvert et connecté, double-clique sur **`EXPORTER_DONNEES.bat`**.
4. Dis-le à Claude. Il lira les données dans `data/mt5/`, lancera le backtest et te présentera le verdict (GO, NO-GO ou À CREUSER).

## Comment on travaille

Claude écrit et teste le code dans son environnement, qui n'a pas internet. Ton PC exécute : MetaTrader 5, l'export des données, puis le bot. Ce dossier sert de pont entre les deux.

Le plan complet, les décisions prises et les points ouverts sont dans [docs/cahier_des_charges/ANALYSE_ET_PLAN.md](docs/cahier_des_charges/ANALYSE_ET_PLAN.md). Les règles de sécurité qui priment sur tout sont dans [docs/GARDE_FOUS.md](docs/GARDE_FOUS.md).

## Où sont les choses

| Emplacement | Contenu |
|---|---|
| `config/config.json` | tous les réglages de la stratégie et du risque |
| `docs/` | cahier des charges, plan, règles exactes (`SPEC_TECHNIQUE.md`), garde-fous, guide MT5 |
| `sentitrade/` | le code : stratégie, risque, backtest, rapport |
| `scripts/` | vérification de l'installation, export MT5, lancement du backtest |
| `data/mt5/` | l'historique exporté depuis MetaTrader 5 |
| `reports/` | les rapports de backtest (`_demo_synthetique` = exemple sur des prix inventés) |
| `logs/` | les journaux, que Claude lit pour diagnostiquer |
| `%USERPROFILE%\.tradingbot\` | l'environnement Python et **tes identifiants** (`.env`), volontairement hors de ce dossier |
