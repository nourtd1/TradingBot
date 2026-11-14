"""Hypothèses S1 à S4 et leurs variantes voisines, paramètres FIGÉS (RECHERCHE_PLAN §3).

Ce module ne contient que des définitions et des fonctions de signal VECTORISÉES et causales :
la valeur à la bougie i n'utilise que des bougies <= i (S1, S3 : connues à la clôture de i,
exécutées à l'ouverture de i+1) ou <= i-1 (S2 : valeurs « veille » alignées sur la bougie
d'exécution i). La gestion des positions (stops, durée, OCO, plafonds) est dans `moteur.py`.

Aucun paramètre autre que ceux du plan. Les variantes voisines ne servent qu'à la robustesse.

Interprétations prudentes (signalées dans le rapport) :
- ATR20 = moyenne simple sur 20 bougies du true range ; la première bougie (sans clôture
  précédente) n'a pas de true range : l'ATR n'existe qu'à partir de la 21e bougie.
- S2, « dernière clôture D1 de la semaine » : on rééquilibre à l'ouverture de la PREMIÈRE bougie
  d'une nouvelle semaine ISO, avec les valeurs de la clôture précédente (la dernière de la semaine
  écoulée). C'est exactement « signal à la dernière clôture, exécution à l'ouverture suivante »,
  sans avoir à deviner à l'avance qu'une bougie sera la dernière de la semaine.
- S2, volatilité : écart-type (ddof = 1) des 60 derniers rendements simples clôture à clôture.
- S2, signe nul (rendement exactement 0) : pas de position.
- S3, RSI(2) de Wilder : moyennes des hausses et des baisses initialisées par la moyenne simple
  des 2 premières variations, puis lissage de Wilder ; baisses nulles => RSI 100 (50 si tout est nul).
- S4 : le range exige les 4 (ou 2) bougies M15 exactes de la session ; s'il en manque une, le jour
  est ignoré (« range_incomplet »). Les ordres sont valables sur les bougies ENTIÈREMENT antérieures
  à l'échéance (ouverture <= échéance - 15 min). Le filtre « range < 3 × spread médian de l'heure »
  prend la plus grande médiane horaire des bougies du range (spread non doublé : le filtre est une
  règle de la stratégie, pas un coût).

Cycle 2 (docs/RECHERCHE_PLAN_CYCLE2.md) : C1 et C2 sont définis en fin de module (paramètres figés
du plan cycle 2, voir le docstring de `signaux_c1` et `signaux_c2`). `CODES` reste celui du cycle 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import pandas as pd

CODES = ("S1", "S2", "S3", "S4")
ATR_PERIODE = 20
RISQUE_POSITION_PCT = 0.5          # S1, S3, S4 (plan §5)

SYMBOLES_S4 = ("XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "GER40")
# (ouverture de session, clôture forcée), heure serveur
SESSIONS_S4 = {
    "XAUUSD": ("10:00", "21:55"), "EURUSD": ("10:00", "21:55"), "GBPUSD": ("10:00", "21:55"),
    "GER40": ("10:00", "22:45"), "US500": ("16:30", "22:45"), "NAS100": ("16:30", "22:45"),
}
VALIDITE_AVANT_CLOTURE = pd.Timedelta(hours=3)
M15 = pd.Timedelta(minutes=15)


@dataclass(frozen=True)
class ParamS1:
    entree: int = 55
    sortie: int = 20
    stop_atr: float = 2.0


@dataclass(frozen=True)
class ParamS2:
    rendement_jours: int = 365
    vol_cible: float = 0.10
    vol_barres: int = 60
    stop_atr: float = 4.0
    seuil_reequilibrage: float = 0.25
    levier_max: float = 10.0


@dataclass(frozen=True)
class ParamS3:
    sma_tendance: int = 200
    rsi_periode: int = 2
    rsi_seuil: float = 10.0
    sma_sortie: int = 5
    barres_max: int = 10
    stop_atr: float = 3.0


@dataclass(frozen=True)
class ParamS4:
    barres_range: int = 4
    objectif_r: Optional[float] = None
    filtre_spread: float = 3.0


@dataclass(frozen=True)
class Strategie:
    code: str
    variante: str
    params: object
    timeframe: str
    risque_pct: Optional[float]
    description: str = ""
    classes: Tuple[str, ...] = ("forex", "metaux", "indices", "crypto")
    symboles: Optional[Tuple[str, ...]] = None

    @property
    def nom(self) -> str:
        return self.code if self.variante == "base" else f"{self.code} [{self.variante}]"

    def avec_classes(self, classes) -> "Strategie":
        return Strategie(self.code, self.variante, self.params, self.timeframe, self.risque_pct,
                         self.description, tuple(classes), self.symboles)


DESCRIPTIONS = {
    "S1": "Cassure de Donchian (suivi de tendance, D1), achat et vente, tous les symboles",
    "S2": "Momentum temporel (TSMOM, D1), ciblage de volatilité, rééquilibrage hebdomadaire",
    "S3": "Retour à la moyenne sur les indices (D1), achat uniquement",
    "S4": "Cassure du range d'ouverture (intraday, M15)",
    "C1": "Tournant du mois sur les indices (D1), achat uniquement",
    "C2": "Indices, métaux (et énergie, crypto) avec filtre de tendance SMA200, achat ou rien",
    "P": "Combinaison déclarée C1 + C2 + S3 (un tiers du capital chacune)",
}


def strategie_base(code: str) -> Strategie:
    if code in CODES_CYCLE2:
        return _strategie_base_cycle2(code)
    if code == "S1":
        return Strategie("S1", "base", ParamS1(), "D1", RISQUE_POSITION_PCT, DESCRIPTIONS["S1"])
    if code == "S2":
        return Strategie("S2", "base", ParamS2(), "D1", None, DESCRIPTIONS["S2"])
    if code == "S3":
        return Strategie("S3", "base", ParamS3(), "D1", RISQUE_POSITION_PCT, DESCRIPTIONS["S3"], ("indices",))
    if code == "S4":
        return Strategie("S4", "base", ParamS4(), "M15", RISQUE_POSITION_PCT, DESCRIPTIONS["S4"],
                         symboles=SYMBOLES_S4)
    raise ValueError(f"stratégie inconnue : {code}")


def variantes_voisines(code: str) -> list:
    """Variantes voisines du plan §3 (cycle 2 : plan cycle 2 §1), et seulement elles."""
    if code in CODES_CYCLE2:
        return _variantes_cycle2(code)
    b = strategie_base(code)

    def v(nom, params):
        return Strategie(b.code, nom, params, b.timeframe, b.risque_pct, b.description, b.classes, b.symboles)
    if code == "S1":
        return [v("40/15", ParamS1(40, 15, 2.0)), v("80/30", ParamS1(80, 30, 2.0)),
                v("stop 3 ATR", ParamS1(55, 20, 3.0))]
    if code == "S2":
        return [v("182 jours", ParamS2(rendement_jours=182)), v("91 jours", ParamS2(rendement_jours=91))]
    if code == "S3":
        return [v("RSI < 5", ParamS3(rsi_seuil=5.0)), v("RSI < 20", ParamS3(rsi_seuil=20.0)),
                v("sortie SMA10", ParamS3(sma_sortie=10))]
    if code == "S4":
        return [v("range 2 bougies", ParamS4(barres_range=2)), v("objectif 2R", ParamS4(objectif_r=2.0))]
    raise ValueError(f"stratégie inconnue : {code}")


# --------------------------------------------------------------------------- indicateurs

def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    tr[prev.isna()] = np.nan
    return tr


def atr(df: pd.DataFrame, n: int = ATR_PERIODE) -> pd.Series:
    return true_range(df).rolling(n, min_periods=n).mean()


def rsi_wilder(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).to_numpy(dtype=float)
    perte = (-delta).clip(lower=0.0).to_numpy(dtype=float)
    out = np.full(len(close), np.nan)
    if len(close) <= n:
        return pd.Series(out, index=close.index)

    def lisser(x):
        y = np.full(len(x), np.nan)
        y[n] = x[1:n + 1].mean()
        a = 1.0 / n
        for i in range(n + 1, len(x)):
            y[i] = y[i - 1] + a * (x[i] - y[i - 1])
        return y
    g, p = lisser(gain), lisser(perte)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = g / p
        out = 100.0 - 100.0 / (1.0 + rs)
    out = np.where((p == 0) & (g > 0), 100.0, out)
    out = np.where((p == 0) & (g == 0), 50.0, out)
    out[:n] = np.nan
    return pd.Series(out, index=close.index)


# --------------------------------------------------------------------------- signaux

def signaux_s1(df: pd.DataFrame, p: ParamS1) -> pd.DataFrame:
    """Valeurs connues à la CLÔTURE de chaque bougie (exécution à l'ouverture suivante)."""
    c = df["close"]
    haut_e = df["high"].rolling(p.entree, min_periods=p.entree).max().shift(1)
    bas_e = df["low"].rolling(p.entree, min_periods=p.entree).min().shift(1)
    haut_s = df["high"].rolling(p.sortie, min_periods=p.sortie).max().shift(1)
    bas_s = df["low"].rolling(p.sortie, min_periods=p.sortie).min().shift(1)
    a = atr(df)
    out = pd.DataFrame(index=df.index)
    out["entree_long"] = (c > haut_e).to_numpy()
    out["entree_court"] = (c < bas_e).to_numpy()
    out["sortie_long"] = (c < bas_s).to_numpy()
    out["sortie_court"] = (c > haut_s).to_numpy()
    out["atr"] = a
    out["pret"] = (haut_e.notna() & bas_e.notna() & a.notna()).to_numpy()
    out.loc[~out["pret"], ["entree_long", "entree_court"]] = False
    return out


def signaux_s2(df: pd.DataFrame, p: ParamS2, crypto: bool) -> pd.DataFrame:
    """Valeurs « veille » alignées sur la bougie d'exécution i (calculées avec les bougies <= i-1).

    Colonnes : reequilibrer (première bougie d'une nouvelle semaine ISO), signe, vol (annualisée),
    atr, pret.
    """
    c = df["close"].to_numpy(dtype=float)
    d = df.index.normalize().to_numpy(dtype="datetime64[ns]")
    cible = d - np.timedelta64(p.rendement_jours, "D")
    pos = np.searchsorted(d, cible, side="right") - 1        # dernière clôture de date <= t - 365 j
    ret = np.full(len(c), np.nan)
    ok = pos >= 0
    ret[ok] = c[ok] / c[pos[ok]] - 1.0
    signe = np.sign(ret)
    r = df["close"].pct_change()
    vol = r.rolling(p.vol_barres, min_periods=p.vol_barres).std(ddof=1).to_numpy() * np.sqrt(365.0 if crypto else 252.0)
    a = atr(df).to_numpy()
    iso = df.index.isocalendar()
    semaine = (iso["year"].to_numpy(dtype=np.int64) * 100 + iso["week"].to_numpy(dtype=np.int64))
    out = pd.DataFrame(index=df.index)
    nouvelle = np.zeros(len(c), dtype=bool)
    nouvelle[1:] = semaine[1:] != semaine[:-1]
    out["reequilibrer"] = nouvelle

    def veille(x):
        y = np.full(len(x), np.nan)
        y[1:] = x[:-1]
        return y
    out["signe"] = veille(signe)
    out["vol"] = veille(vol)
    out["atr"] = veille(a)
    out["pret"] = (np.isfinite(out["signe"]) & np.isfinite(out["vol"]) & (out["vol"] > 0)
                   & np.isfinite(out["atr"])).to_numpy()
    return out


def signaux_s3(df: pd.DataFrame, p: ParamS3) -> pd.DataFrame:
    """Valeurs connues à la CLÔTURE de chaque bougie (exécution à l'ouverture suivante)."""
    c = df["close"]
    sma = c.rolling(p.sma_tendance, min_periods=p.sma_tendance).mean()
    rsi = rsi_wilder(c, p.rsi_periode)
    sma_s = c.rolling(p.sma_sortie, min_periods=p.sma_sortie).mean()
    a = atr(df)
    out = pd.DataFrame(index=df.index)
    out["pret"] = (sma.notna() & rsi.notna() & a.notna() & sma_s.notna()).to_numpy()
    out["entree_long"] = ((c > sma) & (rsi < p.rsi_seuil)).to_numpy() & out["pret"].to_numpy()
    out["sortie_sma"] = (c > sma_s).to_numpy()
    out["atr"] = a
    return out


def _hm(texte: str) -> pd.Timedelta:
    h, m = texte.split(":")
    return pd.Timedelta(hours=int(h), minutes=int(m))


def niveaux_s4(m15: pd.DataFrame, symbole: str, p: ParamS4, p50_heure_prix: np.ndarray) -> pd.DataFrame:
    """Un enregistrement par jour de cotation : range, horaires et décision (placer ou ignorer).

    Colonnes : t_placement (ouverture de la dernière bougie du range : ordres posés à sa clôture),
    haut, bas, t_limite (dernière ouverture de bougie où les ordres sont valables), t_sortie
    (ouverture de la bougie qui contient l'heure de clôture forcée), placer (bool), raison.
    N'utilise que les bougies du range : causal.
    """
    ouverture, cloture = SESSIONS_S4[symbole]
    d_ouv, d_clo = _hm(ouverture), _hm(cloture)
    idx = m15.index
    jours_uniques = idx.normalize().unique()
    temps = set(idx.asi8.tolist())
    hauts = m15["high"].to_numpy(dtype=float)
    bas = m15["low"].to_numpy(dtype=float)
    lignes = []
    for j in jours_uniques:
        debut = j + d_ouv
        ts = [debut + k * M15 for k in range(p.barres_range)]
        t_sortie = (j + d_clo).floor("15min")
        t_limite = j + d_clo - VALIDITE_AVANT_CLOTURE - M15
        rec = {"jour": j, "t_placement": ts[-1], "haut": np.nan, "bas": np.nan, "t_limite": t_limite,
               "t_sortie": t_sortie, "placer": False, "raison": ""}
        if not all(t.value in temps for t in ts):
            rec["raison"] = "range_incomplet"
            lignes.append(rec)
            continue
        pos = idx.get_indexer(ts)
        h, l = float(hauts[pos].max()), float(bas[pos].min())
        rec["haut"], rec["bas"] = h, l
        med = max(float(p50_heure_prix[t.hour]) for t in ts)
        if h - l < p.filtre_spread * med:
            rec["raison"] = "range_trop_etroit"
        else:
            rec["placer"] = True
            rec["raison"] = "ok"
        lignes.append(rec)
    return pd.DataFrame(lignes, columns=["jour", "t_placement", "haut", "bas", "t_limite", "t_sortie",
                                         "placer", "raison"])


# =========================================================================== cycle 2
# docs/RECHERCHE_PLAN_CYCLE2.md §1 : paramètres FIGÉS, variantes voisines du plan et rien d'autre.

CODES_CYCLE2 = ("C1", "C2")
CLASSES_C1 = ("indices",)
# Plan cycle 2 : indices et métaux, plus les marchés de même nature du nouveau broker ; l'architecte
# précise (14/11/2026) : classes « energies » et « crypto » si elles existent. Jamais de forex ; la classe
# « matieres » (si l'exporteur l'ajoute) n'est PAS citée par le plan : elle n'est pas incluse.
CLASSES_C2 = ("indices", "metaux", "energies", "crypto")


@dataclass(frozen=True)
class ParamC1:
    entree_avant_j: int = 0          # 0 : entrée à l'ouverture de J ; 1 : à l'ouverture de J-1
    jour_sortie: int = 4             # sortie à l'ouverture du 4e jour de cotation du nouveau mois
    stop_atr: float = 3.0
    toujours_long: bool = False      # référence du critère 7 (PAS une variante, voir moteur.py)


@dataclass(frozen=True)
class ParamC2:
    sma: int = 200
    frequence: str = "semaine"       # "semaine" (base) ou "mois" (variante)
    vol_cible: float = 0.10
    vol_barres: int = 60
    stop_atr: float = 4.0
    seuil_reequilibrage: float = 0.25
    levier_max: float = 10.0
    toujours_long: bool = False      # référence du critère 7 (signal forcé à 1)


def _strategie_base_cycle2(code: str) -> Strategie:
    if code == "C1":
        return Strategie("C1", "base", ParamC1(), "D1", RISQUE_POSITION_PCT, DESCRIPTIONS["C1"], CLASSES_C1)
    if code == "C2":
        return Strategie("C2", "base", ParamC2(), "D1", None, DESCRIPTIONS["C2"], CLASSES_C2)
    raise ValueError(f"stratégie inconnue : {code}")


def _variantes_cycle2(code: str) -> list:
    b = _strategie_base_cycle2(code)

    def v(nom, params):
        return Strategie(b.code, nom, params, b.timeframe, b.risque_pct, b.description, b.classes, b.symboles)
    if code == "C1":
        return [v("entrée J-1", ParamC1(entree_avant_j=1)), v("sortie 3e jour", ParamC1(jour_sortie=3)),
                v("stop 4 ATR", ParamC1(stop_atr=4.0))]
    if code == "C2":
        return [v("SMA150", ParamC2(sma=150)), v("SMA250", ParamC2(sma=250)),
                v("évaluation mensuelle", ParamC2(frequence="mois"))]
    raise ValueError(f"stratégie inconnue : {code}")


def reference_toujours_long(code: str) -> Strategie:
    """Référence du critère 7 du cycle 2 : « même méthode, toujours acheteuse » (mêmes symboles, même taille,
    même stop). C1 : toujours long au même risque (voir `moteur.py`) ; C2 : signal forcé à 1."""
    b = _strategie_base_cycle2(code)
    if code == "C1":
        p = ParamC1(toujours_long=True)
    else:
        p = ParamC2(toujours_long=True)
    return Strategie(b.code, "référence toujours long", p, b.timeframe, b.risque_pct, b.description, b.classes,
                     b.symboles)


def restreindre(strategie: Strategie, symboles) -> Strategie:
    """Même stratégie, limitée à une liste de symboles (test des nouveaux marchés, plan cycle 2 §5)."""
    return Strategie(strategie.code, strategie.variante, strategie.params, strategie.timeframe,
                     strategie.risque_pct, strategie.description, strategie.classes, tuple(sorted(symboles)))


def _jours_d(df: pd.DataFrame) -> np.ndarray:
    return df.index.normalize().to_numpy(dtype="datetime64[ns]").astype("datetime64[D]")


def jour_ouvre_suivant(d: np.ndarray) -> np.ndarray:
    """Premier lundi-vendredi STRICTEMENT après chaque date (datetime64[D])."""
    return np.busday_offset(np.asarray(d, dtype="datetime64[D]") + np.timedelta64(1, "D"), 0, roll="forward")


def dernier_jour_ouvre_du_mois(d: np.ndarray) -> np.ndarray:
    """J : dernier lundi-vendredi du mois calendaire de chaque date (jours fériés ignorés, plan cycle 2)."""
    m = np.asarray(d, dtype="datetime64[D]").astype("datetime64[M]")
    fin = (m + 1).astype("datetime64[D]") - np.timedelta64(1, "D")
    return np.busday_offset(fin, 0, roll="backward")


def signaux_c1(df: pd.DataFrame, p: ParamC1) -> pd.DataFrame:
    """C1, tournant du mois. Valeurs connues à la CLÔTURE de chaque bougie i (exécution à l'ouverture suivante).

    - `jour_prevu` : prochain jour ouvré (lundi-vendredi) après la date de la bougie, en jours depuis 1970 ;
    - `entree` : vrai si ce prochain jour ouvré est J (dernier lundi-vendredi de SON mois), ou J-1 pour la
      variante « entrée J-1 » (plan : « l'ordre part à la clôture de la veille, si le jour ouvré suivant est
      J »), et si l'ATR20 existe ;
    - `mois` (année × 12 + mois) et `rang_mois` : rang de la bougie parmi les bougies D1 REÇUES de son mois
      (1 = première). Le moteur sort à l'ouverture qui suit la clôture de la (jour_sortie - 1)-ième bougie
      du mois suivant celui de l'entrée : « 4e jour de cotation, après 3 bougies terminées ».

    Interprétations prudentes (signalées dans le rapport) :
    - l'ordre d'entrée ne vaut QUE pour l'ouverture du jour prévu : si la bougie suivante reçue n'est pas
      datée de ce jour (férié, donnée manquante), il est annulé et compté ; on n'entre jamais en retard ;
    - si la veille de J manque dans les données, aucune clôture n'a « J pour jour ouvré suivant » : pas
      d'entrée ce mois-là (deviner un férié à l'avance serait une anticipation) ;
    - les jours de cotation du nouveau mois sont comptés sur les bougies réellement reçues (une bougie de
      week-end, si le broker en fournit, compte comme un jour de cotation).
    Tout est causal : la valeur en i n'utilise que la date et les bougies <= i.
    """
    d = _jours_d(df)
    nb = jour_ouvre_suivant(d)
    j_mois = dernier_jour_ouvre_du_mois(nb)
    cible = np.busday_offset(j_mois, -int(p.entree_avant_j), roll="backward") if p.entree_avant_j else j_mois
    a = atr(df)
    mois_dt = d.astype("datetime64[M]")
    mois = mois_dt.astype(np.int64)
    rang = pd.Series(mois).groupby(mois).cumcount().to_numpy() + 1
    out = pd.DataFrame(index=df.index)
    out["pret"] = a.notna().to_numpy()
    out["entree"] = (nb == cible) & out["pret"].to_numpy()
    out["jour_prevu"] = nb.astype(np.int64)
    out["atr"] = a.to_numpy()
    out["mois"] = mois
    out["rang_mois"] = rang.astype(np.int64)
    return out


def signaux_c2(df: pd.DataFrame, p: ParamC2, crypto: bool) -> pd.DataFrame:
    """C2, filtre de tendance achat-ou-rien, même format que `signaux_s2` (valeurs « veille » alignées sur la
    bougie d'exécution i, calculées avec les bougies <= i-1) pour réutiliser la mécanique de S2 du moteur.

    - `signe` : 1 si la clôture est STRICTEMENT au-dessus de la SMA (200 ; variantes 150, 250), 0 sinon ;
      jamais -1 (jamais de vente à découvert). Référence « toujours long » : 1 dès que la SMA existe (même
      période d'évaluation et même N que C2) ;
    - `reequilibrer` : première bougie d'une nouvelle semaine ISO (base) ou d'un nouveau mois calendaire
      (variante « évaluation mensuelle ») : décision à la dernière clôture de la semaine (du mois),
      exécution à l'ouverture suivante, comme S2 ;
    - `vol` : écart-type (ddof = 1) des 60 derniers rendements × √252 (× √365 pour la crypto) ; `atr` : ATR20.
    """
    c = df["close"]
    sma = c.rolling(p.sma, min_periods=p.sma).mean()
    ok_sma = sma.notna().to_numpy()
    if p.toujours_long:
        signe = np.where(ok_sma, 1.0, np.nan)
    else:
        signe = np.where(ok_sma, (c > sma).to_numpy().astype(float), np.nan)
    r = c.pct_change()
    vol = r.rolling(p.vol_barres, min_periods=p.vol_barres).std(ddof=1).to_numpy() * np.sqrt(365.0 if crypto else 252.0)
    a = atr(df).to_numpy()
    if p.frequence == "semaine":
        iso = df.index.isocalendar()
        periode = iso["year"].to_numpy(dtype=np.int64) * 100 + iso["week"].to_numpy(dtype=np.int64)
    elif p.frequence == "mois":
        periode = df.index.year.to_numpy(dtype=np.int64) * 100 + df.index.month.to_numpy(dtype=np.int64)
    else:
        raise ValueError(f"fréquence inconnue : {p.frequence}")
    nouvelle = np.zeros(len(c), dtype=bool)
    nouvelle[1:] = periode[1:] != periode[:-1]

    def veille(x):
        y = np.full(len(x), np.nan)
        y[1:] = np.asarray(x, dtype=float)[:-1]
        return y
    out = pd.DataFrame(index=df.index)
    out["reequilibrer"] = nouvelle
    out["signe"] = veille(signe)
    out["vol"] = veille(vol)
    out["atr"] = veille(a)
    out["pret"] = (np.isfinite(out["signe"]) & np.isfinite(out["vol"]) & (out["vol"] > 0)
                   & np.isfinite(out["atr"])).to_numpy()
    return out
