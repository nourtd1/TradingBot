"""Chargement de l'univers multi-symboles et verrou du contrôle final (RECHERCHE_PLAN §1-2).

Format (contrat avec l'exporteur MT5) :
- `<dossier>/univers.json` : {"decalage_serveur_utc_heures", "symboles": {"<GENERIQUE>":
  {"nom_broker", "classe", "dossier", "timeframes": {...}}}, "absents": {...}} ;
- `<dossier>/<GENERIQUE>/D1.csv`, `H1.csv`, `M15.csv` (format de `sentitrade.data.charger_bougies` :
  Bid, heure serveur naïve, spread en points) ;
- `<dossier>/<GENERIQUE>/symbol_info.json` et `spread_stats.json`.

**Verrou du contrôle final (hold-out).** Par défaut, toute bougie dont l'ouverture est
postérieure à `FIN_DEVELOPPEMENT` (2025-11-13 23:59:59) est retirée DÈS le chargement, avant
toute autre opération : aucun code en aval ne peut la voir par accident. Seul
`controle_final=True` la garde (jusqu'à `FIN_CONTROLE`). Toute la construction d'un univers
passe par `construire_univers`, y compris l'univers synthétique généré en mémoire.

Limite signalée : `spread_stats.json` (10 derniers jours ouvrés) et les swaps de
`symbol_info.json` sont des valeurs ACTUELLES, donc mesurées dans la période de contrôle. Ce
sont des paramètres de coût, pas des prix ; ils sont utilisés pour tout l'historique, comme le
prévoit le plan §4, et le rapport le signale.

Conversion en USD (`Convertisseur`) : le taux d'une devise pendant le jour `d` est la clôture
D1 de la paire de conversion du DERNIER jour strictement antérieur à `d` (cours connu à tout
instant du jour `d` : aucune anticipation). USD vaut 1 ; une devise X se convertit par `XUSD`
(EUR, GBP, AUD, NZD, XAU...) ou par `USDX` inversé (JPY, CAD, CHF). Sans paire disponible, la
devise n'est pas convertible (`ErreurConversion`) et le symbole est exclu avec la raison.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from sentitrade.data import charger_bougies

FIN_DEVELOPPEMENT = pd.Timestamp("2025-11-13 23:59:59")
DEBUT_CONTROLE = pd.Timestamp("2025-11-14 00:00:00")
FIN_CONTROLE = pd.Timestamp("2026-11-13 23:59:59")

# Classes acceptées. « energies » et « matieres » : ajoutées par l'exporteur étendu (nouveau broker,
# plan cycle 2 §5). Les stratégies du cycle 1 gardent leurs propres classes (forex, métaux, indices,
# crypto) : un symbole d'une nouvelle classe est chargé (conversions) mais ne change pas S1-S4.
CLASSES = ("forex", "metaux", "indices", "crypto", "energies", "matieres")
UNIVERS_PLAN = {
    "EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex", "AUDUSD": "forex",
    "USDCAD": "forex", "USDCHF": "forex", "NZDUSD": "forex",
    "XAUUSD": "metaux", "XAGUSD": "metaux",
    "US500": "indices", "NAS100": "indices", "US30": "indices", "GER40": "indices",
    "UK100": "indices", "JP225": "indices",
    "BTCUSD": "crypto", "ETHUSD": "crypto",
}
SYMBOLES_M15 = ("XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "GER40")
TIMEFRAMES = ("D1", "H1", "M15")

# Champs de symbol_info.json indispensables au moteur (noms MT5).
CHAMPS_INFO_OBLIGATOIRES = ("digits", "point", "trade_contract_size", "volume_min", "volume_step",
                            "volume_max", "currency_profit", "swap_mode", "swap_long", "swap_short",
                            "swap_rollover3days")


class ErreurDonnees(ValueError):
    """Fichier ou univers inutilisable."""


class ErreurConversion(ValueError):
    """Devise de profit (ou de swap) non convertible en USD."""


@dataclass
class DonneesSymbole:
    """Données d'un symbole : bougies par timeframe (déjà verrouillées), symbol_info, spread_stats."""
    generique: str
    nom_broker: str
    classe: str
    info: dict
    spread_stats: dict
    bougies: Dict[str, pd.DataFrame] = field(default_factory=dict)

    def tf(self, nom: str) -> Optional[pd.DataFrame]:
        df = self.bougies.get(nom)
        return df if df is not None and len(df) else None


@dataclass
class Univers:
    """Univers chargé. `exclus` : symbole -> raison (données inutilisables) ; `absents` : chez le broker."""
    symboles: Dict[str, DonneesSymbole]
    exclus: Dict[str, str]
    absents: Dict[str, str]
    decalage_serveur_utc_heures: Optional[float]
    controle_final: bool
    borne_fin: pd.Timestamp
    source: str
    cache: dict = field(default_factory=dict, repr=False)

    def classe(self, s: str) -> str:
        return self.symboles[s].classe

    def tronquer(self, fin: pd.Timestamp) -> "Univers":
        """Copie limitée aux bougies d'ouverture <= `fin` (utilisée pour isoler le développement)."""
        fin = pd.Timestamp(fin)
        syms = {}
        for nom, d in self.symboles.items():
            nd = copy.copy(d)
            nd.bougies = {tf: df.loc[df.index <= fin] for tf, df in d.bougies.items()}
            syms[nom] = nd
        return Univers(syms, dict(self.exclus), dict(self.absents), self.decalage_serveur_utc_heures,
                       self.controle_final and fin > FIN_DEVELOPPEMENT, min(fin, self.borne_fin), self.source)

    def signature(self) -> dict:
        """Résumé déterministe des données (pour savoir si des résultats peuvent être réutilisés)."""
        out = {"source": self.source, "controle_final": self.controle_final, "borne_fin": str(self.borne_fin),
               "exclus": self.exclus, "symboles": {}}
        for nom in sorted(self.symboles):
            d = self.symboles[nom]
            out["symboles"][nom] = {
                tf: [int(len(df)), str(df.index[0]), str(df.index[-1]), float(df["close"].iloc[-1]),
                     float(df["close"].sum())] for tf, df in sorted(d.bougies.items()) if len(df)}
            out["symboles"][nom]["info"] = {k: d.info.get(k) for k in CHAMPS_INFO_OBLIGATOIRES}
            out["symboles"][nom]["spread_p50"] = (d.spread_stats.get("global") or {}).get("p50")
        return out


def verrouiller(df: pd.DataFrame, controle_final: bool) -> pd.DataFrame:
    """Applique le verrou du hold-out : bougies d'ouverture <= FIN_DEVELOPPEMENT, sauf contrôle final
    (alors <= FIN_CONTROLE)."""
    borne = FIN_CONTROLE if controle_final else FIN_DEVELOPPEMENT
    return df.loc[df.index <= borne]


def _verifier_info(info: dict) -> Optional[str]:
    manquants = [c for c in CHAMPS_INFO_OBLIGATOIRES if info.get(c) is None]
    if manquants:
        return f"symbol_info.json incomplet (champs manquants : {', '.join(manquants)})"
    for c in ("point", "trade_contract_size", "volume_min", "volume_step", "volume_max"):
        try:
            v = float(info[c])
        except (TypeError, ValueError):
            return f"symbol_info.json : '{c}' non numérique"
        if not np.isfinite(v) or v <= 0:
            return f"symbol_info.json : '{c}' doit être > 0"
    if float(info["volume_max"]) < float(info["volume_min"]):
        return "symbol_info.json : volume_max < volume_min"
    return None


def construire_univers(brut: Dict[str, dict], controle_final: bool = False, absents: Optional[dict] = None,
                       exclus: Optional[dict] = None, decalage: Optional[float] = None,
                       source: str = "") -> Univers:
    """Construit un `Univers` à partir de données brutes et APPLIQUE LE VERROU (point d'entrée unique).

    `brut[generique] = {"nom_broker", "classe", "info", "spread_stats", "bougies": {tf: DataFrame}}`.
    Un symbole sans D1 utilisable, de classe inconnue ou au symbol_info incomplet est exclu avec la raison.
    """
    exclus = dict(exclus or {})
    syms: Dict[str, DonneesSymbole] = {}
    for nom in sorted(brut):
        b = brut[nom]
        classe = b.get("classe")
        if classe not in CLASSES:
            exclus[nom] = f"classe inconnue : {classe!r}"
            continue
        raison = _verifier_info(b.get("info") or {})
        if raison:
            exclus[nom] = raison
            continue
        bougies = {tf: verrouiller(df, controle_final) for tf, df in (b.get("bougies") or {}).items()
                   if df is not None}
        if "D1" not in bougies or len(bougies["D1"]) == 0:
            exclus[nom] = "pas de bougies D1 dans la période autorisée"
            continue
        syms[nom] = DonneesSymbole(nom, b.get("nom_broker", nom), classe, dict(b["info"]),
                                   dict(b.get("spread_stats") or {}), bougies)
    return Univers(syms, exclus, dict(absents or {}), decalage, bool(controle_final),
                   FIN_CONTROLE if controle_final else FIN_DEVELOPPEMENT, source)


def retirer_jours_figes(bougies: Dict[str, pd.DataFrame]) -> tuple:
    """Retire les journées de remplissage (architecte, 14/11/2026 ; ex. DE40 fin 2024 : séance entière
    au même prix). Une date est « figée » si TOUTES ses bougies H1 (à défaut M15) ont high == low ; elle
    est retirée de tous les timeframes. Les bougies D1 avec high == low sont aussi retirées.
    Renvoie (bougies nettoyées, nombre de dates retirées)."""
    ref = bougies.get("H1") if bougies.get("H1") is not None else bougies.get("M15")
    figes = pd.DatetimeIndex([])
    if ref is not None and len(ref):
        plat = (ref["high"] == ref["low"]).groupby(ref.index.normalize()).all()
        figes = pd.DatetimeIndex(plat.index[plat.to_numpy()])
    d1 = bougies.get("D1")
    if d1 is not None and len(d1):
        figes = figes.union(pd.DatetimeIndex(d1.index[(d1["high"] == d1["low"]).to_numpy()]).normalize())
    if len(figes) == 0:
        return bougies, 0
    propres = {tf: df[~df.index.normalize().isin(figes)] for tf, df in bougies.items()}
    return propres, int(len(figes))


def charger_univers(dossier, controle_final: bool = False, timeframes: Iterable[str] = TIMEFRAMES,
                    symboles: Optional[Iterable[str]] = None) -> Univers:
    """Charge `dossier/univers.json` et les fichiers de chaque symbole, verrou du hold-out appliqué.

    Un fichier illisible ou refusé par `charger_bougies` exclut le symbole (raison détaillée) ;
    il ne bloque pas les autres. Un `univers.json` absent ou illisible lève `ErreurDonnees`.
    """
    dossier = Path(dossier)
    chemin = dossier / "univers.json"
    if not chemin.exists():
        raise ErreurDonnees(f"{chemin} introuvable")
    try:
        meta = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErreurDonnees(f"{chemin} illisible : {exc}") from exc
    voulus = set(symboles) if symboles is not None else None
    brut, exclus = {}, {}
    for nom, m in sorted((meta.get("symboles") or {}).items()):
        if voulus is not None and nom not in voulus:
            continue
        sous = dossier / (m.get("dossier") or nom)
        try:
            info = json.loads((sous / "symbol_info.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            exclus[nom] = f"symbol_info.json illisible ({exc})"
            continue
        try:
            stats = json.loads((sous / "spread_stats.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stats = {}
        bougies = {}
        erreur = None
        for tf in timeframes:
            f = sous / f"{tf}.csv"
            if not f.exists():
                continue
            try:
                bougies[tf] = charger_bougies(f)
            except (ValueError, OSError) as exc:
                erreur = f"{tf}.csv refusé : {exc}"
                break
        if erreur:
            exclus[nom] = erreur
            continue
        bougies, nb_figes = retirer_jours_figes(bougies)
        info = dict(info)
        info["jours_figes_retires"] = nb_figes
        from sentitrade.recherche.couts import PLANCHER_SPREAD_PRIX
        if nom in PLANCHER_SPREAD_PRIX and "spread_plancher_prix" not in info:
            info["spread_plancher_prix"] = PLANCHER_SPREAD_PRIX[nom]
        brut[nom] = {"nom_broker": m.get("nom_broker", nom), "classe": m.get("classe") or UNIVERS_PLAN.get(nom),
                     "info": info, "spread_stats": stats, "bougies": bougies}
    return construire_univers(brut, controle_final, absents=meta.get("absents") or {}, exclus=exclus,
                              decalage=meta.get("decalage_serveur_utc_heures"),
                              source=f"données MT5 ({dossier})")


# --------------------------------------------------------------------------- conversions

def jours(index: pd.DatetimeIndex) -> np.ndarray:
    """Numéro de jour (int64, jours depuis 1970-01-01) de chaque horodatage."""
    return (index.to_numpy(dtype="datetime64[ns]").astype("datetime64[D]")).astype(np.int64)


class Convertisseur:
    """Taux de conversion d'une devise vers l'USD, jour par jour, sans anticipation.

    `taux(devise, jours)` renvoie, pour chaque numéro de jour, la valeur en USD d'une unité de la
    devise : clôture D1 du dernier jour STRICTEMENT antérieur (NaN si aucune clôture antérieure).
    """

    def __init__(self, univers: Univers):
        self._series: Dict[str, tuple] = {}
        for nom, d in univers.symboles.items():
            d1 = d.tf("D1")
            if d1 is None:
                continue
            self._series[nom] = (jours(d1.index), d1["close"].to_numpy(dtype=float))

    def source(self, devise: str) -> tuple:
        """(symbole, inverse) utilisé pour convertir `devise` ; lève ErreurConversion."""
        devise = (devise or "").upper()
        if devise == "USD":
            return ("", False)
        if devise + "USD" in self._series:
            return (devise + "USD", False)
        if "USD" + devise in self._series:
            return ("USD" + devise, True)
        raise ErreurConversion(f"devise {devise or '?'} non convertible en USD (ni {devise}USD ni USD{devise} "
                               f"dans l'univers)")

    def taux(self, devise: str, jours_: np.ndarray) -> np.ndarray:
        sym, inverse = self.source(devise)
        jours_ = np.asarray(jours_, dtype=np.int64)
        if not sym:
            return np.ones(len(jours_))
        j, c = self._series[sym]
        pos = np.searchsorted(j, jours_, side="left") - 1      # dernier jour < d
        out = np.full(len(jours_), np.nan)
        ok = pos >= 0
        out[ok] = c[pos[ok]]
        return 1.0 / out if inverse else out
