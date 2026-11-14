"""Faux module MetaTrader5 pour les tests du sandbox (le vrai n'existe que sous Windows).

Imite les retours du paquet officiel :
- namedtuples TerminalInfo, AccountInfo, SymbolInfo, Tick (mêmes champs, même ordre) ;
- tableaux numpy structurés pour copy_rates_* (time, open, high, low, close,
  tick_volume, spread, real_volume) et copy_ticks_* (time, bid, ask, last,
  volume, time_msc, flags, volume_real) ;
- None + last_error() en cas d'échec ;
- l'heure serveur encodée comme un epoch : bar.time = heure serveur "vue comme UTC".

Usage dans un test :
    faux = FauxMT5(maintenant_utc=datetime(2026, 11, 11, 14, tzinfo=timezone.utc))
    with mock.patch.dict(sys.modules, {"MetaTrader5": faux}):
        ...

Le faux impose les conventions du projet : les dates passées à copy_*_range
doivent être des datetime avec fuseau (UTC), et le symbole doit avoir été
sélectionné (symbol_select) avant toute demande de données.
"""
from __future__ import annotations

import fnmatch
import math
import types
from collections import namedtuple
from datetime import datetime, timezone

import numpy as np

# --------------------------------------------------------------------------- #
# Structures (champs du paquet MetaTrader5 officiel)
# --------------------------------------------------------------------------- #
TerminalInfo = namedtuple("TerminalInfo", [
    "community_account", "community_connection", "connected", "dlls_allowed", "trade_allowed",
    "tradeapi_disabled", "email_enabled", "ftp_enabled", "notifications_enabled", "mqid", "build",
    "maxbars", "codepage", "ping_last", "community_balance", "retransmission", "company", "name",
    "language", "path", "data_path", "commondata_path"])

AccountInfo = namedtuple("AccountInfo", [
    "login", "trade_mode", "leverage", "limit_orders", "margin_so_mode", "trade_allowed", "trade_expert",
    "margin_mode", "currency_digits", "fifo_close", "balance", "credit", "profit", "equity", "margin",
    "margin_free", "margin_level", "margin_so_call", "margin_so_so", "margin_initial", "margin_maintenance",
    "assets", "liabilities", "commission_blocked", "name", "server", "currency", "company"])

SymbolInfo = namedtuple("SymbolInfo", [
    "custom", "chart_mode", "select", "visible", "session_deals", "session_buy_orders",
    "session_sell_orders", "volume", "volumehigh", "volumelow", "time", "digits", "spread",
    "spread_float", "ticks_bookdepth", "trade_calc_mode", "trade_mode", "start_time", "expiration_time",
    "trade_stops_level", "trade_freeze_level", "trade_exemode", "swap_mode", "swap_rollover3days",
    "margin_hedged_use_leg", "expiration_mode", "filling_mode", "order_mode", "order_gtc_mode",
    "option_mode", "option_right", "bid", "bidhigh", "bidlow", "ask", "askhigh", "asklow", "last",
    "lasthigh", "lastlow", "volume_real", "volumehigh_real", "volumelow_real", "option_strike", "point",
    "trade_tick_value", "trade_tick_value_profit", "trade_tick_value_loss", "trade_tick_size",
    "trade_contract_size", "trade_accrued_interest", "trade_face_value", "trade_liquidity_rate",
    "volume_min", "volume_max", "volume_step", "volume_limit", "swap_long", "swap_short",
    "margin_initial", "margin_maintenance", "session_volume", "session_turnover", "session_interest",
    "session_buy_orders_volume", "session_sell_orders_volume", "session_open", "session_close",
    "session_aw", "session_price_settlement", "session_price_limit_min", "session_price_limit_max",
    "margin_hedged", "price_change", "price_volatility", "price_theoretical", "price_greeks_delta",
    "price_greeks_theta", "price_greeks_gamma", "price_greeks_vega", "price_greeks_rho",
    "price_greeks_omega", "price_sensitivity", "basis", "category", "currency_base", "currency_profit",
    "currency_margin", "bank", "description", "exchange", "formula", "isin", "name", "page", "path"])

Tick = namedtuple("Tick", ["time", "bid", "ask", "last", "volume", "time_msc", "flags", "volume_real"])

DTYPE_RATES = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
                        ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")])
DTYPE_TICKS = np.dtype([("time", "<i8"), ("bid", "<f8"), ("ask", "<f8"), ("last", "<f8"), ("volume", "<u8"),
                        ("time_msc", "<i8"), ("flags", "<u4"), ("volume_real", "<f8")])

# Identité fictive : les tests vérifient qu'elle n'apparaît JAMAIS dans les sorties.
LOGIN_FICTIF = 98765432
NOM_FICTIF = "Jean Dupont-Secret"

JOUR = 86400
DUREES = {1: 60, 15: 900, 16385: 3600, 16408: 86400}


def _epoch(d) -> int:
    if isinstance(d, datetime):
        if d.tzinfo is None:
            raise AssertionError("le faux MT5 exige des datetime avec fuseau UTC (convention du projet)")
        return int(d.timestamp())
    return int(d)


def _jour_ouvre(t: np.ndarray) -> np.ndarray:
    """Lundi-vendredi dans le calendrier serveur (1970-01-01 = jeudi)."""
    return ((t // JOUR) + 3) % 7 < 5


def prix_fictif(t) -> np.ndarray:
    """Prix Bid déterministe : identique quel que soit le découpage des demandes."""
    t = np.asarray(t, dtype="float64")
    return 2000.0 + 30.0 * np.sin(2 * math.pi * t / (5 * JOUR)) + 5.0 * np.sin(2 * math.pi * t / (3 * 3600))


def spread_tick_fictif(heure) -> np.ndarray:
    """Spread (points) des ticks : 10 + heure serveur."""
    return 10 + np.asarray(heure)


def symbole_fictif(name: str, **champs) -> SymbolInfo:
    base = {f: 0 for f in SymbolInfo._fields}
    base.update(dict(
        custom=False, select=False, visible=False, digits=2, spread=25, spread_float=True, trade_mode=4,
        trade_calc_mode=2, trade_stops_level=0, trade_freeze_level=0, trade_exemode=2, filling_mode=3,
        order_mode=127, point=0.01, trade_tick_value=1.0, trade_tick_value_profit=1.0,
        trade_tick_value_loss=1.0, trade_tick_size=0.01, trade_contract_size=100.0, volume_min=0.01,
        volume_max=100.0, volume_step=0.01, volume_limit=0.0, swap_long=-50.0, swap_short=20.0,
        margin_hedged=50.0, currency_base="XAU", currency_profit="USD", currency_margin="USD",
        description="Gold vs US Dollar", path=f"Metals\\{name}", bank="", exchange="", formula="",
        isin="", page="", category="", basis="", name=name))
    base.update(champs)
    return SymbolInfo(**base)


def symboles_broker_etendu() -> list:
    """Broker régulé fictif : forex, métaux (dont platine, palladium, cuivre), indices (dont
    STOXX 50, CAC 40, ASX 200, Hang Seng, IBEX 35 non tradable, Russell 2000), énergies (WTI,
    Brent, gaz naturel) et crypto. Avec des pièges : l'ETF « US Oil Fund ETF » au nom USOIL,
    le contrat daté CL-DEC26, un « OILCash » qui est en fait du Brent, un WTI à échéance
    sans date dans le nom, un trust Bitcoin coté en bourse, SOLUSDT coté en USDT."""
    def fx(nom, base, profit, **c):
        d = dict(currency_base=base, currency_profit=profit, currency_margin=base, digits=5, point=0.00001,
                 trade_tick_size=0.00001, trade_contract_size=100000.0, trade_calc_mode=0,
                 description=f"{base} vs {profit}", path=f"Forex\\{nom}", swap_mode=1)
        d.update(c)
        return symbole_fictif(nom, **d)

    def cfd(nom, base, profit, description, chemin, **c):
        d = dict(currency_base=base, currency_profit=profit, currency_margin=profit, digits=2, point=0.01,
                 trade_contract_size=1.0, trade_calc_mode=2, description=description, path=chemin)
        d.update(c)
        return symbole_fictif(nom, **d)

    vis = dict(visible=True, select=True)
    return [
        fx("EURUSD", "EUR", "USD", **vis), fx("GBPUSD", "GBP", "USD"), fx("USDJPY", "USD", "JPY", digits=3),
        fx("AUDUSD", "AUD", "USD"), fx("USDCAD", "USD", "CAD"), fx("USDCHF", "USD", "CHF"), fx("NZDUSD", "NZD", "USD"),
        fx("USDHKD", "USD", "HKD"),
        symbole_fictif("XAUUSD", **vis),
        cfd("XAGUSD", "XAG", "USD", "Silver vs US Dollar", "Metals\\XAGUSD", digits=3, point=0.001),
        cfd("XPTUSD", "XPT", "USD", "Platinum vs US Dollar", "Metals\\XPTUSD"),
        cfd("XPDUSD", "XPD", "USD", "Palladium vs US Dollar", "Metals\\XPDUSD"),
        cfd("COPPER", "USD", "USD", "Copper Cash", "Commodities\\COPPER", digits=4, point=0.0001),
        cfd("US500", "USD", "USD", "US 500 Cash Index", "Indices\\US500"),
        cfd("USTEC", "USD", "USD", "US Tech 100 Index", "Indices\\USTEC"),
        cfd("US30", "USD", "USD", "Wall Street 30 Index", "Indices\\US30"),
        cfd("DE40", "EUR", "EUR", "Germany 40 Index", "Indices\\DE40"),
        cfd("UK100", "GBP", "GBP", "UK 100 Index", "Indices\\UK100"),
        cfd("JPN225", "JPY", "JPY", "Japan 225 Index", "Indices\\JPN225"),
        cfd("STOXX50", "EUR", "EUR", "Euro Stoxx 50 Index", "Indices\\STOXX50"),
        cfd("FRA40", "EUR", "EUR", "France 40 Index", "Indices\\FRA40"),
        cfd("AUS200", "AUD", "AUD", "Australia 200 Index", "Indices\\AUS200"),
        cfd("HK50", "HKD", "HKD", "Hong Kong 50 Index", "Indices\\HK50"),
        cfd("SPA35", "EUR", "EUR", "Spain 35 Index", "Indices\\SPA35", trade_mode=0),
        cfd("US2000", "USD", "USD", "US Small Cap 2000", "Indices\\US2000"),
        cfd("XTIUSD", "XTI", "USD", "US Crude Oil (WTI) Cash", "Energies\\XTIUSD", **vis),
        cfd("XBRUSD", "XBR", "USD", "Brent Crude Oil Cash", "Energies\\XBRUSD"),
        cfd("XNGUSD", "XNG", "USD", "Natural Gas Cash", "Energies\\XNGUSD", digits=3, point=0.001),
        cfd("OILCash", "USD", "USD", "Brent Crude Oil Cash", "Energies\\OILCash"),
        cfd("WTI.f", "USD", "USD", "WTI Crude Oil Futures", "Futures\\Energy\\WTI.f", trade_calc_mode=1,
            expiration_time=1797379200),
        cfd("CL-DEC26", "USD", "USD", "Crude Oil Light Futures Dec 2026", "Futures\\Energy\\CL-DEC26",
            trade_calc_mode=1, expiration_time=1797379200),
        cfd("USOIL", "USD", "USD", "United States Oil Fund ETF", "NYSE\\USOIL", volume_min=1.0, volume_step=1.0),
        cfd("BTCUSD", "BTC", "USD", "Bitcoin vs US Dollar", "Crypto\\BTCUSD", **vis),
        cfd("ETHUSD", "ETH", "USD", "Ethereum vs US Dollar", "Crypto\\ETHUSD"),
        cfd("LTCUSD", "LTC", "USD", "Litecoin vs US Dollar", "Crypto\\LTCUSD"),
        cfd("XRPUSD", "XRP", "USD", "Ripple vs US Dollar", "Crypto\\XRPUSD", digits=5, point=0.00001),
        cfd("SOLUSDT", "SOL", "USDT", "Solana vs Tether", "Crypto\\SOLUSDT"),
        cfd("BITCOIN.US", "USD", "USD", "Grayscale Bitcoin Trust", "NYSE\\Shares\\GBTC", trade_calc_mode=32),
    ]


class FauxMT5(types.ModuleType):
    """Terminal MetaTrader 5 simulé, configurable pour chaque scénario de test."""

    __version__ = "5.0.5200"

    # Constantes (valeurs de la documentation MetaQuotes)
    TIMEFRAME_M1, TIMEFRAME_M15, TIMEFRAME_H1, TIMEFRAME_D1 = 1, 15, 16385, 16408
    COPY_TICKS_ALL, COPY_TICKS_INFO, COPY_TICKS_TRADE = -1, 1, 2
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_CONTEST, ACCOUNT_TRADE_MODE_REAL = 0, 1, 2
    ACCOUNT_MARGIN_MODE_RETAIL_NETTING, ACCOUNT_MARGIN_MODE_EXCHANGE, ACCOUNT_MARGIN_MODE_RETAIL_HEDGING = 0, 1, 2
    SYMBOL_TRADE_MODE_DISABLED, SYMBOL_TRADE_MODE_LONGONLY, SYMBOL_TRADE_MODE_SHORTONLY = 0, 1, 2
    SYMBOL_TRADE_MODE_CLOSEONLY, SYMBOL_TRADE_MODE_FULL = 3, 4
    RES_S_OK, RES_E_FAIL, RES_E_INVALID_PARAMS, RES_E_NO_MEMORY, RES_E_NOT_FOUND = 1, -1, -2, -3, -4
    RES_E_INTERNAL_FAIL_INIT, RES_E_NO_CONNECTION = -10003, -10004

    def __init__(self, *, maintenant_utc: datetime, decalage_h: int = 2, terminal_ouvert: bool = True,
                 connecte: bool = True, algo_trading: bool = True, trade_mode: int = 0, margin_mode: int = 2,
                 devise: str = "USD", symboles=None, jours_historique: int = 100, maxbars: int = 100_000_000,
                 telechargement_lent: bool = False, marche_ouvert: bool = True, pas_tick_s: int = 60,
                 select_en_echec=(), rates_en_echec=(), serveur: str = "BrokerExemple-Demo",
                 societe: str = "Broker Exemple Ltd", cotent_toujours=(), ticks_figes=None):
        super().__init__("MetaTrader5")
        self.maintenant_serveur = int(maintenant_utc.timestamp()) + decalage_h * 3600
        self.debut_historique = self.maintenant_serveur - jours_historique * JOUR
        self.terminal_ouvert, self.connecte, self.algo_trading = terminal_ouvert, connecte, algo_trading
        self.trade_mode, self.margin_mode, self.devise = trade_mode, margin_mode, devise
        self.maxbars, self.telechargement_lent = maxbars, telechargement_lent
        self.marche_ouvert, self.pas_tick_s = marche_ouvert, pas_tick_s
        # MT5 réel (build 6317) : symbol_select renvoie False « Out of memory » pour ces symboles
        self.select_en_echec = set(select_en_echec)
        # symboles dont copy_rates_range échoue toujours (None + last_error)
        self.rates_en_echec = set(rates_en_echec)
        self.serveur, self.societe = serveur, societe
        # symboles qui cotent même quand le marché est fermé (crypto le week-end)
        self.cotent_toujours = set(cotent_toujours)
        # {symbole: âge du dernier tick en secondes} : symbole qui ne cote plus (dernier tick figé)
        self.ticks_figes = dict(ticks_figes or {})
        if symboles is None:
            symboles = [symbole_fictif("XAUUSD", visible=True, select=True), symbole_fictif(
                "XAUEUR", visible=True, select=True, currency_profit="EUR", description="Gold vs Euro")]
        self.symboles = {s.name: s for s in symboles}
        self.selectionnes = {s.name for s in symboles if s.select}
        self.initialise = False
        self.erreur = (self.RES_S_OK, "Success")
        self.appels: list[tuple] = []
        self._cache_barres: dict = {}
        self._appels_par_tf: dict = {}
        self._compteur_tick = 0

    # ----------------------------------------------------------------- outils
    def _noter(self, nom, *args):
        self.appels.append((nom,) + args)

    def _echec(self, code, message):
        self.erreur = (code, message)
        return None

    def _pret(self) -> bool:
        if not self.initialise:
            self._echec(self.RES_E_NO_CONNECTION, "No IPC connection")
            return False
        return True

    def _toutes_barres(self, timeframe: int) -> np.ndarray:
        if timeframe not in self._cache_barres:
            d = DUREES[timeframe]
            debut = -(-self.debut_historique // d) * d
            t = np.arange(debut, self.maintenant_serveur + 1, d, dtype="int64")
            t = t[_jour_ouvre(t)]
            if t.size > self.maxbars:  # limite "Max bars in chart" du terminal
                t = t[-self.maxbars:]
            self._cache_barres[timeframe] = t
        return self._cache_barres[timeframe]

    # ------------------------------------------------------------ connexion
    def initialize(self, *args, **kwargs):
        self._noter("initialize")
        if not self.terminal_ouvert:
            self._echec(self.RES_E_INTERNAL_FAIL_INIT, "IPC initialize failed, MetaTrader 5 x64 not found")
            return False
        self.initialise = True
        self.erreur = (self.RES_S_OK, "Success")
        return True

    def shutdown(self):
        self._noter("shutdown")
        self.initialise = False
        return True

    def last_error(self):
        return self.erreur

    def version(self):
        return (500, 5200, "01 Nov 2026") if self._pret() else None

    def terminal_info(self):
        self._noter("terminal_info")
        if not self._pret():
            return None
        return TerminalInfo(
            community_account=False, community_connection=False, connected=self.connecte, dlls_allowed=False,
            trade_allowed=self.algo_trading, tradeapi_disabled=False, email_enabled=False, ftp_enabled=False,
            notifications_enabled=False, mqid=False, build=5200, maxbars=self.maxbars, codepage=1252,
            ping_last=35000, community_balance=0.0, retransmission=0.0, company="MetaQuotes Ltd.",
            name="MetaTrader 5", language="French",
            path=f"C:\\Users\\{NOM_FICTIF}\\MetaTrader 5",
            data_path=f"C:\\Users\\{NOM_FICTIF}\\AppData\\Roaming\\MetaQuotes\\Terminal\\ABC",
            commondata_path=f"C:\\Users\\{NOM_FICTIF}\\AppData\\Roaming\\MetaQuotes\\Terminal\\Common")

    def account_info(self):
        self._noter("account_info")
        if not self._pret():
            return None
        if not self.connecte:
            return self._echec(self.RES_E_FAIL, "Terminal: Call failed")
        return AccountInfo(
            login=LOGIN_FICTIF, trade_mode=self.trade_mode, leverage=100, limit_orders=200, margin_so_mode=0,
            trade_allowed=True, trade_expert=True, margin_mode=self.margin_mode, currency_digits=2,
            fifo_close=False, balance=5000.0, credit=0.0, profit=0.0, equity=5000.0, margin=0.0,
            margin_free=5000.0, margin_level=0.0, margin_so_call=100.0, margin_so_so=50.0,
            margin_initial=0.0, margin_maintenance=0.0, assets=0.0, liabilities=0.0, commission_blocked=0.0,
            name=NOM_FICTIF, server=self.serveur, currency=self.devise, company=self.societe)

    # ------------------------------------------------------------- symboles
    def symbols_get(self, group=None):
        self._noter("symbols_get", group)
        if not self._pret():
            return None
        if group is None:
            return tuple(self.symboles.values())
        motifs = [m.strip().upper() for m in str(group).split(",") if m.strip()]
        res = []
        for nom, s in self.symboles.items():
            garde = False
            for m in motifs:
                if m.startswith("!"):
                    if fnmatch.fnmatchcase(nom.upper(), m[1:]):
                        garde = False
                elif fnmatch.fnmatchcase(nom.upper(), m):
                    garde = True
            if garde:
                res.append(s)
        return tuple(res)

    def symbol_select(self, symbol, enable=None):
        self._noter("symbol_select", symbol, enable)
        if not self._pret():
            return False
        if symbol not in self.symboles:
            self._echec(self.RES_E_NOT_FOUND, "Terminal: Not found")
            return False
        if symbol in self.select_en_echec:
            self._echec(self.RES_E_NO_MEMORY, "Terminal: Out of memory")
            return False
        if enable is None or enable:
            self.selectionnes.add(symbol)
            self.symboles[symbol] = self.symboles[symbol]._replace(select=True, visible=True)
        else:
            self.selectionnes.discard(symbol)
        return True

    def _symbole_pret(self, symbol) -> bool:
        if not self._pret():
            return False
        if symbol not in self.symboles or symbol not in self.selectionnes:
            self._echec(self.RES_E_NOT_FOUND, "Terminal: Not found")
            return False
        return True

    def symbol_info(self, symbol):
        self._noter("symbol_info", symbol)
        return self.symboles[symbol] if self._symbole_pret(symbol) else None

    def symbol_info_tick(self, symbol):
        self._noter("symbol_info_tick", symbol)
        if not self._symbole_pret(symbol):
            return None
        if symbol in self.ticks_figes:  # ne cote plus : dernier tick figé
            t = self.maintenant_serveur - int(self.ticks_figes[symbol])
        elif self.marche_ouvert or symbol in self.cotent_toujours:
            self._compteur_tick += 1
            t = self.maintenant_serveur - 5 + self._compteur_tick
        else:  # marché fermé : dernier tick figé, vieux de 40 heures
            t = self.maintenant_serveur - 40 * 3600
        bid = round(float(prix_fictif(t)), 2)
        point = self.symboles[symbol].point
        ask = round(bid + float(spread_tick_fictif((t // 3600) % 24)) * point, 2)
        return Tick(time=t, bid=bid, ask=ask, last=0.0, volume=0, time_msc=t * 1000, flags=6, volume_real=0.0)

    # --------------------------------------------------------------- données
    def copy_rates_range(self, symbol, timeframe, date_from, date_to):
        self._noter("copy_rates_range", symbol, timeframe, date_from, date_to)
        if not self._symbole_pret(symbol):
            return None
        if timeframe not in DUREES:
            return self._echec(self.RES_E_INVALID_PARAMS, "Invalid params")
        if symbol in self.rates_en_echec:
            return self._echec(self.RES_E_FAIL, "Terminal: Call failed")
        a, b = _epoch(date_from), _epoch(date_to)
        t = self._toutes_barres(timeframe)
        t = t[(t >= a) & (t <= b)]
        n = self._appels_par_tf.get(timeframe, 0)
        self._appels_par_tf[timeframe] = n + 1
        if self.telechargement_lent and n == 0:  # 1er appel : historique en cours de téléchargement
            t = t[int(t.size * 0.7):]
        d = DUREES[timeframe]
        res = np.zeros(t.size, dtype=DTYPE_RATES)
        res["time"] = t
        ouverture = np.round(prix_fictif(t), 2)
        cloture = np.round(prix_fictif(t + d - 1), 2)
        res["open"], res["close"] = ouverture, cloture
        res["high"] = np.maximum(ouverture, cloture) + 0.35
        res["low"] = np.minimum(ouverture, cloture) - 0.25
        res["tick_volume"] = 100 + (t // d) % 50
        res["spread"] = 15 + ((t // 3600) % 24) % 5
        res["real_volume"] = 0
        return res

    def copy_ticks_range(self, symbol, date_from, date_to, flags):
        self._noter("copy_ticks_range", symbol, date_from, date_to, flags)
        if not self._symbole_pret(symbol):
            return None
        a, b = _epoch(date_from), _epoch(date_to)
        fin = min(b, self.maintenant_serveur - 5)
        debut = max(a, self.debut_historique)
        if fin <= debut:
            return np.zeros(0, dtype=DTYPE_TICKS)
        t = np.arange(-(-debut // self.pas_tick_s) * self.pas_tick_s, fin, self.pas_tick_s, dtype="int64")
        t = t[_jour_ouvre(t)]
        point = self.symboles[symbol].point
        res = np.zeros(t.size, dtype=DTYPE_TICKS)
        res["time"] = t
        res["bid"] = np.round(prix_fictif(t), 2)
        res["ask"] = np.round(res["bid"] + spread_tick_fictif((t // 3600) % 24) * point, 2)
        res["time_msc"] = t * 1000
        res["flags"] = 6  # TICK_FLAG_BID | TICK_FLAG_ASK
        return res

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        self._noter("copy_rates_from_pos", symbol, timeframe, start_pos, count)
        if not self._symbole_pret(symbol):
            return None
        t = self._toutes_barres(timeframe)
        fin = t.size - int(start_pos)
        debut = max(0, fin - int(count))
        if fin <= 0:
            return np.zeros(0, dtype=DTYPE_RATES)
        return self.copy_rates_range(symbol, timeframe, datetime.fromtimestamp(int(t[debut]), timezone.utc),
                                     datetime.fromtimestamp(int(t[fin - 1]), timezone.utc))
