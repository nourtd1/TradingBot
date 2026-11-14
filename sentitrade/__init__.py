"""SentiTrade — stratégie Imbalance / FVG sur l'or (XAUUSD), MetaTrader 5.

Le cœur (config, data, indicators, sessions, strategy, risk_manager, backtest)
n'utilise que la bibliothèque standard, numpy et pandas : il tourne à
l'identique dans le backtest et dans le bot. Seuls les modules MT5 (plus tard)
dépendent du paquet MetaTrader5, disponible uniquement sous Windows.
"""
__version__ = "0.1.0"
