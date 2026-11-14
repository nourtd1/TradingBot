"""Univers synthétique multi-symboles au format EXACT de l'exporteur (tests et démonstration).

Marche aléatoire log-normale dont le PRIX est une martingale par défaut (dérive du log
-σ²/2 : ni la stratégie ni l'achat-conservation n'ont d'avantage), aux horaires de cotation de chaque classe (heure serveur) :
forex 24 h du lundi au vendredi ; métaux 01:00-24:00 ; indices 01:00-23:00 ; crypto 24 h / 7 j.
Tout l'historique est tiré en H1 (puis agrégé en D1) ; pour les symboles M15, la fenêtre M15 (les
`annees_m15` dernières années) est tirée en M15 et agrégée en H1 et D1.
Chaque bougie est tirée à partir de sous-pas (3 par M15, 4 par H1) ; plus haut et plus bas en
découlent, plus une petite excursion. Le spread de chaque bougie (points) fluctue autour d'une
valeur de base, plus large à minuit pour le forex.

`tendance` (optionnel) : dérive annuelle (en log) qui change de signe toutes les `periode_jours`
avec une phase propre à chaque symbole ; sert à prouver que le moteur DÉTECTE un vrai avantage.
Clé optionnelle `derive_moyenne` : dérive annuelle (en log) constante ajoutée (marché haussier à long
terme avec des régimes de baisse : cas du filtre de tendance C2 du cycle 2).

`tournant_mois` (optionnel, cycle 2) : rendement (en log) ajouté chaque jour de J (dernier lundi-vendredi
du mois) et des 3 premiers lundis-vendredis du mois suivant, pour les INDICES seulement ; sert à prouver
que le moteur détecte l'effet « tournant du mois » (C1) quand il existe.

`SPECS_SUPPLEMENTAIRES` : symboles absents du plan du cycle 1 (énergie, autre indice) pour simuler un
nouveau broker (plan cycle 2 §5) ; ils ne sont générés que si on les demande dans `symboles`.

API :
- `generer_brut(...)` -> dict au format de `donnees.construire_univers` ;
- `generer_univers(...)` -> `Univers` (verrou du hold-out appliqué comme au chargement) ;
- `ecrire_univers(brut, dossier)` -> écrit univers.json, <SYM>/D1.csv, H1.csv, M15.csv,
  symbol_info.json, spread_stats.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from sentitrade.data import COLONNES, reechantillonner
from sentitrade.recherche.donnees import SYMBOLES_M15, UNIVERS_PLAN, construire_univers

# prix initial, vol annuelle, chiffres, contrat, lots (min, pas, max), devises (base, profit),
# swap (mode, long, short, jour triple MT5), spread de base (points), début des données
SPECS = {
    "EURUSD": (1.10, 0.08, 5, 100000, (0.01, 0.01, 100), ("EUR", "USD"), (1, -7.0, 2.0, 3), 8, None),
    "GBPUSD": (1.30, 0.09, 5, 100000, (0.01, 0.01, 100), ("GBP", "USD"), (1, -5.0, -1.0, 3), 12, None),
    "USDJPY": (110.0, 0.09, 3, 100000, (0.01, 0.01, 100), ("USD", "JPY"), (1, 8.0, -20.0, 3), 10, None),
    "AUDUSD": (0.75, 0.10, 5, 100000, (0.01, 0.01, 100), ("AUD", "USD"), (1, -3.0, -2.0, 3), 12, None),
    "USDCAD": (1.30, 0.07, 5, 100000, (0.01, 0.01, 100), ("USD", "CAD"), (1, 1.0, -6.0, 3), 15, None),
    "USDCHF": (0.95, 0.08, 5, 100000, (0.01, 0.01, 100), ("USD", "CHF"), (1, 4.0, -10.0, 3), 15, None),
    "NZDUSD": (0.70, 0.10, 5, 100000, (0.01, 0.01, 100), ("NZD", "USD"), (1, -2.0, -3.0, 3), 18, None),
    "XAUUSD": (1300.0, 0.15, 2, 100, (0.01, 0.01, 100), ("XAU", "USD"), (1, -12.6, -4.6, 3), 25, None),
    "XAGUSD": (18.0, 0.25, 3, 5000, (0.01, 0.01, 100), ("XAG", "USD"), (1, -6.0, -2.0, 3), 30, None),
    "US500": (2000.0, 0.17, 2, 1, (0.1, 0.1, 100), ("USD", "USD"), (5, -5.0, -1.0, 5), 50, None),
    "NAS100": (4000.0, 0.22, 2, 1, (0.1, 0.1, 100), ("USD", "USD"), (5, -5.0, -1.0, 5), 150, None),
    "US30": (17000.0, 0.16, 2, 1, (0.1, 0.1, 100), ("USD", "USD"), (5, -5.0, -1.0, 5), 300, None),
    "GER40": (10000.0, 0.20, 2, 1, (0.1, 0.1, 100), ("EUR", "EUR"), (5, -4.0, -1.5, 5), 150, None),
    "UK100": (6500.0, 0.15, 2, 1, (0.1, 0.1, 100), ("GBP", "GBP"), (5, -4.5, -1.0, 5), 150, None),
    "JP225": (18000.0, 0.20, 2, 1, (0.1, 0.1, 100), ("JPY", "JPY"), (5, -3.0, -1.0, 5), 1000, None),
    "BTCUSD": (1000.0, 0.70, 2, 1, (0.01, 0.01, 10), ("BTC", "USD"), (5, -20.0, -10.0, 5), 300, "2014-01-01"),
    "ETHUSD": (100.0, 0.85, 2, 1, (0.01, 0.01, 100), ("ETH", "USD"), (5, -20.0, -10.0, 5), 30, "2016-01-01"),
}


# Symboles d'un « nouveau broker » (non générés par défaut : le cycle 1 reste identique).
SPECS_SUPPLEMENTAIRES = {
    "XTIUSD": (60.0, 0.35, 2, 100, (0.01, 0.01, 100), ("USD", "USD"), (5, -6.0, -2.0, 5), 4, "2012-01-01"),
    "AUS200": (5000.0, 0.15, 1, 1, (0.1, 0.1, 100), ("AUD", "AUD"), (5, -4.0, -1.0, 5), 20, None),
}
CLASSES_SUPPLEMENTAIRES = {"XTIUSD": "energies", "AUS200": "indices"}


def _classe(nom: str) -> str:
    return UNIVERS_PLAN.get(nom) or CLASSES_SUPPLEMENTAIRES[nom]


def _spec(nom: str):
    return SPECS[nom] if nom in SPECS else SPECS_SUPPLEMENTAIRES[nom]


def jours_tournant(jours: np.ndarray) -> np.ndarray:
    """Vrai pour J (dernier lundi-vendredi du mois) et les 3 premiers lundis-vendredis du mois suivant."""
    d = np.asarray(jours, dtype="datetime64[D]")
    m = d.astype("datetime64[M]")
    fin = (m + 1).astype("datetime64[D]") - np.timedelta64(1, "D")
    j = np.busday_offset(fin, 0, roll="backward")
    debut = m.astype("datetime64[D]")
    ouvre = np.is_busday(d)
    rang = np.busday_count(debut, d) + 1
    return ouvre & ((d == j) | (rang <= 3))


def _horaires(classe: str, idx: pd.DatetimeIndex) -> np.ndarray:
    wd = idx.weekday.to_numpy()
    h = idx.hour.to_numpy()
    if classe == "crypto":
        return np.ones(len(idx), dtype=bool)
    semaine = wd < 5
    if classe == "forex":
        return semaine
    if classe in ("metaux", "energies"):
        return semaine & (h >= 1)
    return semaine & (h >= 1) & (h < 23)


def _bougies(idx: pd.DatetimeIndex, prix0: float, vol: float, pas_bougie_h: float, heures_an: float,
             sous_pas: int, digits: int, spread: int, classe: str, rng: np.random.Generator,
             derive: Optional[np.ndarray]) -> pd.DataFrame:
    n = len(idx)
    sig_sous = vol * np.sqrt(pas_bougie_h / heures_an / sous_pas)
    inc = rng.standard_normal((n, sous_pas)) * sig_sous - 0.5 * sig_sous ** 2   # prix martingale
    if derive is not None:
        inc += (derive * pas_bougie_h / heures_an / sous_pas)[:, None]
    chemin = np.cumsum(inc.ravel()).reshape(n, sous_pas)
    fin = chemin[:, -1]
    debut = np.concatenate([[0.0], fin[:-1]])
    pts = np.concatenate([debut[:, None], chemin], axis=1)
    exc = np.abs(rng.standard_normal((n, 2))) * sig_sous * 0.5
    hi = pts.max(axis=1) + exc[:, 0]
    lo = pts.min(axis=1) - exc[:, 1]
    o, c = prix0 * np.exp(debut), prix0 * np.exp(fin)
    h, l = prix0 * np.exp(hi), prix0 * np.exp(lo)
    o, c, h, l = (np.round(x, digits) for x in (o, c, h, l))
    h = np.maximum.reduce([h, o, c])
    l = np.minimum.reduce([l, o, c])
    sp = np.maximum(1, np.round(spread * (1 + 0.3 * rng.random(n)))).astype(np.int64)
    if classe == "forex":
        sp = np.where(idx.hour.to_numpy() == 0, sp * 3, sp)
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                       "tick_volume": rng.integers(50, 500, n).astype(np.int64), "spread": sp,
                       "real_volume": np.zeros(n, dtype=np.int64)}, index=idx)
    df.index.name = "time"
    return df


def _info(nom: str, spec) -> dict:
    prix, vol, digits, contrat, (vmin, vpas, vmax), (base, profit), (mode, sl, ss, triple), spread, _ = spec
    point = 10.0 ** -digits
    return {"name": nom, "digits": digits, "point": point, "trade_contract_size": float(contrat),
            "volume_min": vmin, "volume_step": vpas, "volume_max": float(vmax), "trade_stops_level": 0,
            "trade_tick_size": point, "currency_base": base, "currency_profit": profit, "currency_margin": base,
            "spread": spread, "trade_calc_mode": 0 if _classe(nom) == "forex" else 2,
            "swap_mode": mode, "swap_long": sl, "swap_short": ss, "swap_rollover3days": triple,
            "description": f"{nom} synthétique"}


def _stats(nom: str, spec) -> dict:
    classe = _classe(nom)
    spread = float(spec[7])
    point = 10.0 ** -spec[2]
    idx = pd.date_range("2026-11-02", periods=24, freq="h")
    actif = _horaires(classe, idx)
    par_heure = {}
    for h in range(24):
        if not actif[h]:
            par_heure[str(h)] = {"p50": None, "p90": None, "p99": None, "moyenne": None, "max": None, "nb_ticks": 0}
        else:
            v = spread * (3 if classe == "forex" and h == 0 else 1)
            par_heure[str(h)] = {"p50": v, "p90": v * 2, "p99": v * 4, "moyenne": v * 1.2, "max": v * 10,
                                 "nb_ticks": 1000}
    return {"symbole": nom, "unite": "points", "point": point, "jours": [], "nb_jours": 10, "nb_ticks": 24000,
            "global": {"p50": spread, "p90": spread * 2, "p99": spread * 4, "moyenne": spread * 1.2,
                       "max": spread * 10, "nb_ticks": 24000},
            "par_heure": par_heure}


def generer_brut(debut="2008-01-01", fin="2026-11-13 23:59", graine: int = 1,
                 symboles: Optional[Iterable[str]] = None, tendance: Optional[dict] = None,
                 annees_m15: float = 5.0, h1: bool = True, tournant_mois: Optional[float] = None) -> dict:
    """Données brutes (non verrouillées) au format de `construire_univers`."""
    rng = np.random.default_rng(graine)
    noms = list(symboles) if symboles is not None else list(SPECS)
    debut, fin = pd.Timestamp(debut), pd.Timestamp(fin)
    brut = {}
    for nom in noms:
        spec = _spec(nom)
        classe = _classe(nom)
        d0 = max(debut, pd.Timestamp(spec[8])) if spec[8] else debut
        m15 = nom in SYMBOLES_M15
        heures_semaine = {"crypto": 168, "forex": 120, "metaux": 115}.get(classe, 110)
        heures_an = heures_semaine * 52.0
        phase = rng.uniform(0, 2 * np.pi)

        def derive_de(idx):
            d = None
            if tendance:
                t_jours = (idx - d0).total_seconds().to_numpy() / 86400.0
                d = tendance["amplitude"] * np.sign(np.sin(2 * np.pi * t_jours / tendance["periode_jours"] + phase))
                d[d == 0] = tendance["amplitude"]
                d = d + float(tendance.get("derive_moyenne", 0.0))
            if tournant_mois and classe == "indices":
                # rendement journalier r réparti sur les heures du jour : dérive annuelle r × heures_an / heures_jour
                bonus = jours_tournant(idx.normalize().to_numpy(dtype="datetime64[ns]").astype("datetime64[D]"))
                extra = bonus * float(tournant_mois) * heures_an / (heures_semaine / 5.0)
                d = extra if d is None else d + extra
            return d
        # H1 sur tout l'historique ; pour les symboles M15, la fenêtre M15 (fin - annees_m15) est tirée
        # en M15 à partir du dernier cours H1, et le H1 de cette fenêtre est l'agrégat du M15.
        debut_m15 = (fin - pd.Timedelta(days=round(365.25 * annees_m15)) if annees_m15 else d0) if m15 else fin
        debut_m15 = max(debut_m15.normalize(), d0)
        idx_h1 = pd.date_range(d0, fin, freq="h")
        idx_h1 = idx_h1[_horaires(classe, idx_h1) & (idx_h1 < debut_m15)]
        bougies = {}
        morceaux = []
        prix = spec[0]
        if len(idx_h1):
            h1a = _bougies(idx_h1, prix, spec[1], 1.0, heures_an, 4, spec[2], spec[7], classe, rng, derive_de(idx_h1))
            morceaux.append(h1a)
            prix = float(h1a["close"].iloc[-1])
        if m15:
            idx15 = pd.date_range(debut_m15, fin, freq="15min")
            idx15 = idx15[_horaires(classe, idx15)]
            df15 = _bougies(idx15, prix, spec[1], 0.25, heures_an, 3, spec[2], spec[7], classe, rng, derive_de(idx15))
            bougies["M15"] = df15
            morceaux.append(reechantillonner(df15, "h"))
        df_h1 = pd.concat(morceaux) if len(morceaux) > 1 else morceaux[0]
        if h1:
            bougies["H1"] = df_h1
        bougies["D1"] = reechantillonner(df_h1, "D")
        brut[nom] = {"nom_broker": nom, "classe": classe, "info": _info(nom, spec), "spread_stats": _stats(nom, spec),
                     "bougies": bougies}
    return brut


def generer_univers(controle_final: bool = False, **kwargs):
    """Univers synthétique en mémoire, verrou du hold-out appliqué comme pour des fichiers."""
    brut = generer_brut(**kwargs)
    return construire_univers(brut, controle_final, decalage=2,
                              source=f"données synthétiques (marche aléatoire, graine {kwargs.get('graine', 1)}"
                                     + (", tendance injectée" if kwargs.get("tendance") else "")
                                     + (", effet tournant du mois injecté sur les indices" if kwargs.get("tournant_mois")
                                        else "") + ")")


def ecrire_univers(brut: dict, dossier) -> Path:
    """Écrit l'univers au format exact de l'exporteur MT5."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    meta = {"genere_le_utc": "synthétique", "decalage_serveur_utc_heures": 2, "decalage_fiable": True,
            "symboles": {}, "absents": {}}
    for nom, b in brut.items():
        sous = dossier / nom
        sous.mkdir(exist_ok=True)
        tfs = {}
        for tf, df in b["bougies"].items():
            sortie = df.reset_index()
            sortie["time"] = sortie["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
            sortie[COLONNES].to_csv(sous / f"{tf}.csv", index=False)
            tfs[tf] = {"barres": int(len(df)), "premiere": str(df.index[0]), "derniere": str(df.index[-1])}
        (sous / "symbol_info.json").write_text(json.dumps(b["info"], indent=1), encoding="utf-8")
        (sous / "spread_stats.json").write_text(json.dumps(b["spread_stats"], indent=1), encoding="utf-8")
        meta["symboles"][nom] = {"nom_broker": b["nom_broker"], "classe": b["classe"], "dossier": nom,
                                 "timeframes": tfs}
    (dossier / "univers.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return dossier
