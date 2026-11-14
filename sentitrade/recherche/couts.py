"""Coûts d'exécution et de portage (RECHERCHE_PLAN §4).

Toutes les grandeurs sont en PRIX (pas en points), sauf à la frontière avec les fichiers MT5.

- **Spread effectif** d'une bougie = max(spread de la bougie, médiane horaire `par_heure[h].p50` de
  `spread_stats.json`) ; une heure sans médiane (None) prend la médiane globale `global.p50`.
  Les bougies sont en Bid ; un achat se fait à l'Ask = Bid + spread.
  * M15 : heure = heure d'ouverture de la bougie.
  * D1, exécution à l'OUVERTURE (signal de la veille) : l'ordre part au premier tick du jour, souvent
    dans un marché peu liquide. Interprétation prudente : max(spread de la bougie D1, spread de la
    PREMIÈRE bougie H1 du jour, médiane de l'heure de cette première bougie H1) ; sans H1 ce jour-là,
    on prend l'heure d'ouverture la plus fréquente du symbole ; à défaut, la médiane globale.
  * D1, touches intrabarre (stops) et valorisation : max(spread de la bougie, médiane globale), l'heure
    exacte étant inconnue.
- **Glissement** : 0,5 × la médiane globale du spread sur les ordres au marché, 1 × sur les stops
  touchés et les ordres stop d'entrée. Un objectif (ordre limite) est exécuté à son prix, sans glissement.
- **Swap** par lot et par nuit selon `swap_mode` (énumération MT5 ENUM_SYMBOL_SWAP_MODE) :
  0 désactivé ; 1 points (swap × point × contrat, devise de profit) ; 2 devise de base ; 3 devise de
  marge ; 4 devise de dépôt (compte en USD supposé : sinon exception) ; 5 intérêt annuel sur le prix
  courant ; 6 intérêt annuel sur le prix d'ouverture (année de 360 jours). Modes 7 et 8 (réouverture)
  et toute valeur inconnue : `ErreurSwap`, le symbole est exclu avec la raison.
  La nuit du jour `swap_rollover3days` (MT5 : 0 = dimanche ... 3 = mercredi) compte triple.
- **Coûts doublés** (robustesse) : spread et glissements × 2 ; swap × 2 seulement quand il est un
  COÛT (swap négatif). Un swap créditeur n'est pas doublé (doubler un gain ne serait pas prudent).
- **Commission** : 0 sur MetaQuotes-Demo ; paramètre par lot aller-retour (USD), prélevé en entier à
  l'entrée (prudent). Source : `commission_par_lot` de symbol_info.json s'il existe, sinon 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

MODES_SWAP = {0: "désactivé", 1: "points", 2: "devise de base", 3: "devise de marge", 4: "devise de dépôt",
              5: "intérêt (prix courant)", 6: "intérêt (prix d'ouverture)"}
MODES_CALCUL_GERES = {0: "Forex", 2: "CFD", 3: "CFD indice", 4: "CFD levier", 5: "Forex sans levier"}


class ErreurSwap(ValueError):
    """Mode de swap non géré : le calcul est bloqué pour ce symbole."""


# Spread minimal réaliste d'un compte de détail standard, en PRIX (architecte, 14/11/2026).
PLANCHER_SPREAD_PRIX = {
    "EURUSD": 0.00008, "GBPUSD": 0.00012, "USDJPY": 0.010, "AUDUSD": 0.00010, "USDCAD": 0.00015,
    "USDCHF": 0.00015, "NZDUSD": 0.00015, "XAUUSD": 0.20, "XAGUSD": 0.025, "US500": 0.50,
    "NAS100": 1.50, "US30": 2.0, "GER40": 1.0, "UK100": 1.0, "JP225": 10.0,
    # Nouveaux marchés du cycle 2 (fixés le 14/11/2026, avant tout export chez le nouveau broker)
    "BTCUSD": 20.0, "ETHUSD": 2.0, "LTCUSD": 0.20, "XRPUSD": 0.003, "SOLUSD": 0.20,
    "USOIL": 0.04, "UKOIL": 0.04, "NGAS": 0.006, "EU50": 2.0, "FRA40": 1.5, "AUS200": 1.5,
    "HK50": 10.0, "ESP35": 6.0, "US2000": 0.40, "XPTUSD": 2.0, "XPDUSD": 5.0, "COPPER": 0.003,
}


class ErreurCouts(ValueError):
    """Caractéristiques de coût inutilisables (mode de calcul, spread inconnu...)."""


@dataclass(frozen=True)
class ParametresCouts:
    facteur_spread: float = 1.0
    facteur_glissement: float = 1.0
    facteur_swap_cout: float = 1.0
    glissement_marche: float = 0.5       # × spread médian
    glissement_stop: float = 1.0         # × spread médian

    @classmethod
    def doubles(cls) -> "ParametresCouts":
        return cls(facteur_spread=2.0, facteur_glissement=2.0, facteur_swap_cout=2.0)

    def est_double(self) -> bool:
        return self.facteur_spread != 1.0


def _p50(d) -> Optional[float]:
    if not isinstance(d, dict):
        return None
    v = d.get("p50")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v >= 0 else None


def jour_mt5_vers_python(jour_mt5: int) -> int:
    """ENUM_DAY_OF_WEEK (0 = dimanche) -> datetime.weekday() (0 = lundi)."""
    return (int(jour_mt5) - 1) % 7


@dataclass
class CoutsSymbole:
    """Coûts d'un symbole, en prix. Construire avec `construire_couts`."""
    point: float
    contrat: float
    p50_global: float               # prix
    p50_heure: np.ndarray           # prix, 24 valeurs (heures sans tick -> p50_global)
    heure_sans_tick: np.ndarray     # bool, 24 valeurs
    params: ParametresCouts
    swap_mode: int
    swap_long: float
    swap_short: float
    jour_triple_py: int             # weekday() Python de la nuit triple
    devise_profit: str
    devise_base: str
    devise_marge: str
    commission_par_lot: float = 0.0

    # -- glissements (prix)
    @property
    def glissement_marche(self) -> float:
        return self.params.glissement_marche * self.p50_global * self.params.facteur_glissement

    @property
    def glissement_stop(self) -> float:
        return self.params.glissement_stop * self.p50_global * self.params.facteur_glissement

    # -- spreads (prix)
    def spread_heures(self, spread_points: np.ndarray, heures: np.ndarray) -> np.ndarray:
        """max(spread de la bougie, médiane de l'heure) × facteur, en prix."""
        s = np.asarray(spread_points, dtype=float) * self.point
        return np.maximum(s, self.p50_heure[np.asarray(heures, dtype=int)]) * self.params.facteur_spread

    def spread_global(self, spread_points: np.ndarray) -> np.ndarray:
        s = np.asarray(spread_points, dtype=float) * self.point
        return np.maximum(s, self.p50_global) * self.params.facteur_spread

    # -- swap
    def devise_swap(self) -> str:
        if self.swap_mode in (0, 1, 5, 6):
            return self.devise_profit
        if self.swap_mode == 2:
            return self.devise_base
        if self.swap_mode == 3:
            return self.devise_marge
        return "USD"

    def swap_par_lot(self, sens: int, prix_courant: float, prix_ouverture: float) -> float:
        """Swap d'UNE nuit pour 1 lot, dans `devise_swap()` (signe : + crédit, - débit), facteur de coût inclus."""
        taux = self.swap_long if sens > 0 else self.swap_short
        m = self.swap_mode
        if m == 0 or taux == 0:
            return 0.0
        if m == 1:
            v = taux * self.point * self.contrat
        elif m in (2, 3, 4):
            v = taux
        elif m == 5:
            v = self.contrat * prix_courant * taux / 100.0 / 360.0
        elif m == 6:
            v = self.contrat * prix_ouverture * taux / 100.0 / 360.0
        else:  # pragma: no cover - filtré à la construction
            raise ErreurSwap(f"swap_mode {m} non géré")
        return v * self.params.facteur_swap_cout if v < 0 else v

    def multiplicateur_nuit(self, weekday_py: int) -> int:
        return 3 if weekday_py == self.jour_triple_py else 1


def construire_couts(info: dict, spread_stats: dict, params: ParametresCouts = ParametresCouts(),
                     facteur_contrat: float = 1.0, devise_compte: str = "USD") -> CoutsSymbole:
    """Construit les coûts d'un symbole. Lève ErreurSwap / ErreurCouts si un élément n'est pas géré.

    `facteur_contrat` (compte « cent » : 0.01) réduit la taille du contrat ; les swaps exprimés en
    argent par lot (modes 2, 3, 4) sont réduits dans la même proportion.
    """
    try:
        mode = int(info.get("swap_mode"))
    except (TypeError, ValueError):
        raise ErreurSwap(f"swap_mode illisible : {info.get('swap_mode')!r}")
    if mode not in MODES_SWAP:
        raise ErreurSwap(f"swap_mode {mode} non géré (seuls {sorted(MODES_SWAP)} le sont)")
    if mode == 4 and (devise_compte or "USD").upper() != "USD":
        raise ErreurSwap("swap en devise de dépôt avec un compte non USD : non géré")
    calc = info.get("trade_calc_mode")
    if calc is not None and int(calc) not in MODES_CALCUL_GERES:
        raise ErreurCouts(f"trade_calc_mode {calc} non géré (formule de profit différente)")
    point = float(info["point"])
    glob = _p50(spread_stats.get("global"))
    if glob is None:
        # Sans médiane mesurée, les coûts seraient devinés : on n'évalue pas le symbole (prudent).
        raise ErreurCouts("spread_stats.json absent ou sans médiane globale : coûts inconnus")
    par_heure = spread_stats.get("par_heure") or {}
    # Plancher de spread (architecte, 14/11/2026, AVANT tout résultat sur données réelles) : le serveur
    # démo affiche une médiane de 0 point sur EURUSD/GBPUSD, irréaliste pour un compte de détail ;
    # sans plancher, spread ET glissements seraient nuls. Valeur en prix, fixée par l'appelant.
    plancher = float(info.get("spread_plancher_prix") or 0.0)
    if glob * point < plancher:
        glob = plancher / point
    p50h, sans = np.empty(24), np.zeros(24, dtype=bool)
    for h in range(24):
        v = _p50(par_heure.get(str(h)))
        sans[h] = v is None
        p50h[h] = max((glob if v is None else v) * point, plancher)
    contrat = float(info["trade_contract_size"]) * facteur_contrat
    sl, ss = float(info["swap_long"]), float(info["swap_short"])
    if mode in (2, 3, 4):
        sl, ss = sl * facteur_contrat, ss * facteur_contrat
    return CoutsSymbole(
        point=point, contrat=contrat, p50_global=glob * point, p50_heure=p50h, heure_sans_tick=sans,
        params=params, swap_mode=mode, swap_long=sl, swap_short=ss,
        jour_triple_py=jour_mt5_vers_python(int(info["swap_rollover3days"])),
        devise_profit=str(info.get("currency_profit") or "").upper(),
        devise_base=str(info.get("currency_base") or "").upper(),
        devise_marge=str(info.get("currency_margin") or info.get("currency_base") or "").upper(),
        commission_par_lot=float(info.get("commission_par_lot") or 0.0) * facteur_contrat)


def spreads_d1(d1: pd.DataFrame, h1: Optional[pd.DataFrame], couts: CoutsSymbole) -> tuple:
    """(spread à l'ouverture, spread intrabarre) des bougies D1, en prix (voir l'en-tête du module)."""
    s_d1 = d1["spread"].to_numpy(dtype=float) * couts.point
    jours_d1 = d1.index.normalize()
    heure_typique = None
    sp_h1 = pd.Series(np.nan, index=jours_d1)
    heure_h1 = pd.Series(np.nan, index=jours_d1)
    if h1 is not None and len(h1):
        j = h1.index.normalize()
        premier = ~pd.Index(j).duplicated(keep="first")
        prem = h1[premier]
        jp = prem.index.normalize()
        sp_h1 = pd.Series(prem["spread"].to_numpy(dtype=float) * couts.point, index=jp).reindex(jours_d1)
        heure_h1 = pd.Series(prem.index.hour.to_numpy(dtype=float), index=jp).reindex(jours_d1)
        if len(prem):
            heure_typique = int(pd.Series(prem.index.hour).mode().iloc[0])
    heures = heure_h1.to_numpy(dtype=float)
    if heure_typique is not None:
        heures = np.where(np.isnan(heures), heure_typique, heures)
        med = couts.p50_heure[heures.astype(int)]
    else:
        med = np.full(len(d1), couts.p50_global)
    sp_h1v = np.nan_to_num(sp_h1.to_numpy(dtype=float), nan=0.0)
    ouverture = np.maximum.reduce([s_d1, sp_h1v, med, np.full(len(d1), 0.0)]) * couts.params.facteur_spread
    barre = couts.spread_global(d1["spread"].to_numpy())
    return ouverture, barre


def pnl_usd(sens: int, lots: float, prix_entree: float, prix_sortie: float, contrat: float, taux: float) -> float:
    """P&L en USD : sens × (sortie - entrée) × contrat × lots, converti au taux (USD par unité de devise)."""
    return sens * (prix_sortie - prix_entree) * contrat * lots * taux
