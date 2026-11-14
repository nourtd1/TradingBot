"""Stratégie FVG M15 filtrée par la tendance H1 (docs/SPEC_TECHNIQUE.md §3).

Point d'entrée unique, identique pour le backtest et le bot :

    signaux = preparer_signaux(m15, h1, cfg, spec)          # vectorisé
    moteur = MoteurSignaux(cfg)
    for t, ligne in signaux.iterrows():                    # une fois par clôture M15
        evenements = moteur.sur_cloture_m15(t, ligne, position_ouverte)

Absence d'anticipation (règle n°1) :
- une bougie est datée de son ouverture et n'est utilisable qu'à sa clôture ;
- `tendance_h1` est indexée par l'instant de CLÔTURE H1 (open + 1 h) et
  `tendance_a` fait un asof ARRIÈRE (dernière clôture <= t) ;
- `detecter_fvg` et `preparer_signaux` sont indexés par l'instant de clôture de
  la bougie M15 la plus récente utilisée ;
- l'ADR du jour D n'utilise que les jours < D.
Conséquence : une ligne d'index t de `preparer_signaux` ne dépend que de
bougies clôturées au plus tard à t. Le bot ne doit traiter que les lignes
d'index <= maintenant (une bougie en formation produit une ligne d'index futur).

Interprétations prudentes (non écrites explicitement dans la spec) :
- c1, c2, c3 doivent être CONTIGUËS dans le temps (open(c2) = open(c1) + 15 min,
  open(c3) = open(c2) + 15 min). Un triplet qui enjambe un trou de données
  (bougie manquante, pause quotidienne, week-end) n'est pas un FVG : ce
  « vide » serait un gap d'ouverture, pas une imbalance.
- Priorité des raisons de rejet quand plusieurs s'appliquent :
  `ecart_trop_petit` (partie de la définition du FVG), puis `sl_trop_loin`,
  puis `sl_trop_proche`.
- Comparaisons de prix avec une tolérance TOLERANCE_PRIX = 1e-9 $ pour que les
  erreurs d'arrondi binaire ne changent pas une décision : un SL à exactement
  `sl_plafond` est accepté, un vide d'exactement `fvg_ecart_min` est accepté.
  La condition de formation (low(c3) > high(c1)) reste STRICTE, sans tolérance.
- Les prix (entree, sl, tp1) ne sont pas arrondis au tick ici : l'arrondi est
  fait à la frontière MT5 (exécution), comme les conversions en points.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from sentitrade.indicators import ema, filtre_adr, ranges_journaliers
from sentitrade.sessions import est_heure_entree

DUREE_M15 = pd.Timedelta(minutes=15)
DUREE_H1 = pd.Timedelta(hours=1)
TOLERANCE_PRIX = 1e-9

REJET_SL_TROP_LOIN = "sl_trop_loin"
REJET_SL_TROP_PROCHE = "sl_trop_proche"
REJET_ECART_TROP_PETIT = "ecart_trop_petit"
# Décision de l'architecte (2026-11-13) : le motif entier doit se former en session.
# Le CDC exclut la session asiatique (22h-09h) pour ses faux signaux ; un FVG dont
# c1 s'ouvre avant debut_session (ex. 08:15-09:00) en serait issu. Prioritaire sur
# les autres raisons de rejet.
REJET_FORMATION_HORS_SESSION = "formation_hors_session"

COLONNES_FVG = ["sens", "entree", "sl", "tp1", "distance_sl", "rejet", "haut_vide", "bas_vide"]
COLONNES_SIGNAUX = ["tendance", "adr_ok", "heure_entree_ok", "sens", "entree", "sl", "tp1",
                    "distance_sl", "rejet"]


def _strategie(cfg):
    """Accepte un Config (on lit cfg.strategie) ou un StrategieConfig."""
    return getattr(cfg, "strategie", cfg)


def _verifier_index(df: pd.DataFrame, nom: str) -> None:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError(f"{nom} : l'index doit être un DatetimeIndex (heure d'ouverture)")
    if df.index.tz is not None:
        raise ValueError(f"{nom} : horodatages naïfs (heure serveur) attendus")
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError(f"{nom} : l'index doit être strictement croissant (trié, sans doublon)")


# --------------------------------------------------------------------------- tendance

def tendance_h1(h1: pd.DataFrame, cfg) -> pd.Series:
    """Tendance H1 : +1, -1 ou 0, indexée par l'instant de CLÔTURE (open + 1 h).

    EMA = close.ewm(span=ema_periode, adjust=False).mean(). Pour la bougie
    d'indice i : +1 si EMA[i] > EMA[i - pente_ema_barres], -1 si <, 0 sinon.
    0 pendant l'échauffement (i < 3 × ema_periode) et tant que
    i - pente_ema_barres < 0. L'indice i est la position dans les données
    fournies : l'échauffement court depuis la première bougie fournie.
    """
    s = _strategie(cfg)
    _verifier_index(h1, "tendance_h1")
    e = ema(h1["close"], s.ema_periode).to_numpy()
    n = len(e)
    pente = int(s.pente_ema_barres)
    tendance = np.zeros(n, dtype=np.int64)
    if n > pente:
        actuel, passe = e[pente:], e[:-pente]
        tendance[pente:] = np.where(actuel > passe, 1, np.where(actuel < passe, -1, 0))
    tendance[: min(n, 3 * int(s.ema_periode))] = 0
    return pd.Series(tendance, index=pd.DatetimeIndex(h1.index + DUREE_H1, name="cloture"),
                     name="tendance")


def tendance_a(serie_tendance: pd.Series, instants):
    """Tendance connue à chaque instant : dernière valeur d'index <= instant.

    `serie_tendance` est indexée par les instants de clôture (sortie de
    `tendance_h1`). Renvoie 0 avant la première clôture. Accepte un instant
    unique (-> int) ou une suite d'instants (-> np.ndarray[int64]).
    """
    idx = serie_tendance.index
    if not idx.is_monotonic_increasing:
        raise ValueError("tendance_a : la série de tendance doit être triée par instant de clôture")
    valeurs = serie_tendance.to_numpy(dtype=np.int64)
    scalaire = isinstance(instants, (pd.Timestamp, np.datetime64)) or not hasattr(instants, "__len__")
    cibles = pd.DatetimeIndex([instants] if scalaire else instants)
    pos = idx.searchsorted(cibles, side="right") - 1
    res = np.where(pos >= 0, valeurs[np.maximum(pos, 0)] if len(valeurs) else 0, 0).astype(np.int64)
    return int(res[0]) if scalaire else res


# --------------------------------------------------------------------------- FVG

def detecter_fvg(m15: pd.DataFrame, cfg, spec) -> pd.DataFrame:
    """Détecte les FVG M15 (règles exactes §3), de façon vectorisée.

    c1, c2, c3 = trois bougies M15 consécutives et contiguës, c3 la plus
    récente ; le FVG est confirmé à la clôture de c3 (index de la sortie).

    Long  : low(c3) > high(c1). Vide [high(c1), low(c3)].
            entree = high(c1) (bord) ou milieu du vide (milieu).
            sl = min(low c1, c2, c3) - (spread(c3) × point + sl_marge_fixe).
    Short : high(c3) < low(c1). Vide [high(c3), low(c1)].
            entree = low(c1) (bord) ou milieu du vide (milieu).
            sl = max(high c1, c2, c3) + spread(c3) × point + sl_marge_fixe.
    distance_sl = |entree - sl| ; tp1 = entree + sens × tp1_r × distance_sl.
    Rejet (colonne `rejet`, "" si valide) : `ecart_trop_petit` si le vide
    < fvg_ecart_min, sinon `sl_trop_loin` si distance_sl > sl_plafond, sinon
    `sl_trop_proche` si distance_sl < stops_level_points × point.

    Renvoie UNIQUEMENT les triplets formant un FVG (valide ou rejeté), indexés
    par l'instant de clôture de c3, colonnes COLONNES_FVG (sens int64, prix
    float64, rejet str, haut_vide/bas_vide = bornes du vide).
    """
    s = _strategie(cfg)
    _verifier_index(m15, "detecter_fvg")
    # nanosecondes quelle que soit la résolution de l'index (pandas 2 accepte s/ms/us)
    temps = m15.index.values.astype("datetime64[ns]").view(np.int64)
    h = m15["high"].to_numpy(dtype=float)
    l = m15["low"].to_numpy(dtype=float)
    sp = m15["spread"].to_numpy(dtype=float)
    n = len(m15)
    vide = pd.DataFrame({c: pd.Series(dtype=float) for c in COLONNES_FVG},
                        index=pd.DatetimeIndex([], name="cloture"))
    if n < 3:
        return _typer_fvg(vide)

    pas = DUREE_M15.value
    contigu = (temps[1:-1] - temps[:-2] == pas) & (temps[2:] - temps[1:-1] == pas)
    h1_, h2_, h3_ = h[:-2], h[1:-1], h[2:]
    l1_, l2_, l3_ = l[:-2], l[1:-1], l[2:]
    sp3 = sp[2:]

    est_long = contigu & (l3_ > h1_)
    est_short = contigu & (h3_ < l1_)
    garde = est_long | est_short
    if not garde.any():
        return _typer_fvg(vide)

    k = np.flatnonzero(garde)
    longs = est_long[k]
    sens = np.where(longs, 1, -1).astype(np.int64)
    haut_vide = np.where(longs, l3_[k], l1_[k])
    bas_vide = np.where(longs, h1_[k], h3_[k])
    ecart = haut_vide - bas_vide
    marge = sp3[k] * float(spec.point) + float(s.sl_marge_fixe)
    if s.mode_entree == "bord":
        entree = np.where(longs, h1_[k], l1_[k])
    elif s.mode_entree == "milieu":
        entree = (haut_vide + bas_vide) / 2.0
    else:
        raise ValueError(f"mode_entree inconnu : {s.mode_entree!r}")
    plus_bas = np.minimum(np.minimum(l1_[k], l2_[k]), l3_[k])
    plus_haut = np.maximum(np.maximum(h1_[k], h2_[k]), h3_[k])
    sl = np.where(longs, plus_bas - marge, plus_haut + marge)
    distance = np.abs(entree - sl)
    tp1 = entree + sens * float(s.tp1_r) * distance

    stops_min = float(spec.stops_level_points) * float(spec.point)
    rejet = np.full(len(k), "", dtype=object)
    rejet[distance < stops_min - TOLERANCE_PRIX] = REJET_SL_TROP_PROCHE
    rejet[distance > float(s.sl_plafond) + TOLERANCE_PRIX] = REJET_SL_TROP_LOIN
    rejet[ecart < float(s.fvg_ecart_min) - TOLERANCE_PRIX] = REJET_ECART_TROP_PETIT
    ouverture_c1 = m15.index[:-2][k]
    debut = s.heure("debut_session")
    minutes_c1 = np.asarray(ouverture_c1.hour * 60 + ouverture_c1.minute)
    rejet[minutes_c1 < debut.hour * 60 + debut.minute] = REJET_FORMATION_HORS_SESSION

    index = pd.DatetimeIndex(m15.index[2:][k] + DUREE_M15, name="cloture")
    res = pd.DataFrame({
        "sens": sens, "entree": entree, "sl": sl, "tp1": tp1, "distance_sl": distance,
        "rejet": rejet, "haut_vide": haut_vide, "bas_vide": bas_vide,
    }, index=index)
    return _typer_fvg(res)


def _typer_fvg(df: pd.DataFrame) -> pd.DataFrame:
    df = df[COLONNES_FVG].copy()
    df["sens"] = df["sens"].astype(np.int64)
    for c in ("entree", "sl", "tp1", "distance_sl", "haut_vide", "bas_vide"):
        df[c] = df[c].astype(float)
    df["rejet"] = df["rejet"].astype(object)
    return df


# --------------------------------------------------------------------------- point d'entrée unique

def preparer_signaux(m15: pd.DataFrame, h1: pd.DataFrame, cfg, spec) -> pd.DataFrame:
    """Tableau des signaux, une ligne par clôture M15 (spec §3, point d'entrée unique).

    Index : instant de clôture de chaque bougie M15 (open + 15 min), nommé "cloture".
    Colonnes :
      tendance (int64 -1/0/1) : tendance H1 connue à t (dernière clôture H1 <= t) ;
      adr_ok (bool) : filtre ADR de la date de l'OUVERTURE de la bougie (t - 15 min),
                      calculé avec les jours H1 strictement antérieurs ;
      heure_entree_ok (bool) : est_heure_entree(t) ;
      sens (int64) : 0 sans FVG confirmé à t, ±1 sinon ;
      entree, sl, tp1, distance_sl (float64, NaN sans FVG) ;
      rejet (str) : "" si pas de FVG ou FVG valide, sinon la raison.

    Toutes les valeurs de la ligne t ne dépendent que des bougies M15 et H1
    clôturées au plus tard à t. Les indicateurs utilisent tout l'historique
    fourni : passer l'historique complet, puis filtrer la fenêtre simulée.
    """
    s = _strategie(cfg)
    _verifier_index(m15, "preparer_signaux (m15)")
    _verifier_index(h1, "preparer_signaux (h1)")
    clotures = pd.DatetimeIndex(m15.index + DUREE_M15, name="cloture")

    tendance = tendance_a(tendance_h1(h1, s), clotures)

    dates = m15.index.normalize()
    jours = dates.unique()
    filtre = filtre_adr(ranges_journaliers(h1), s.adr_periode, s.adr_reference,
                        s.adr_ratio_min, s.adr_ratio_max, dates=jours)
    adr_ok = filtre.to_numpy()[jours.get_indexer(dates)]

    heure_ok = est_heure_entree(clotures, s)

    n = len(m15)
    sens = np.zeros(n, dtype=np.int64)
    entree = np.full(n, np.nan)
    sl = np.full(n, np.nan)
    tp1 = np.full(n, np.nan)
    distance = np.full(n, np.nan)
    rejet = np.full(n, "", dtype=object)
    fvg = detecter_fvg(m15, s, spec)
    if len(fvg):
        pos = clotures.get_indexer(fvg.index)
        if (pos < 0).any():  # impossible par construction ; garde-fou
            raise RuntimeError("preparer_signaux : FVG hors des clôtures M15")
        sens[pos] = fvg["sens"].to_numpy()
        entree[pos] = fvg["entree"].to_numpy()
        sl[pos] = fvg["sl"].to_numpy()
        tp1[pos] = fvg["tp1"].to_numpy()
        distance[pos] = fvg["distance_sl"].to_numpy()
        rejet[pos] = fvg["rejet"].to_numpy()

    return pd.DataFrame({
        "tendance": tendance.astype(np.int64),
        "adr_ok": np.asarray(adr_ok, dtype=bool),
        "heure_entree_ok": np.asarray(heure_ok, dtype=bool),
        "sens": sens, "entree": entree, "sl": sl, "tp1": tp1, "distance_sl": distance,
        "rejet": rejet,
    }, index=clotures)


# --------------------------------------------------------------------------- machine à setups

@dataclass(frozen=True)
class Setup:
    """Setup en attente d'exécution (niveau d'entrée à toucher)."""
    sens: int
    entree: float
    sl: float
    tp1: float
    distance_sl: float
    cree_a: pd.Timestamp
    expire_a: pd.Timestamp


@dataclass(frozen=True)
class Evenement:
    """Événement de la machine à setups.

    type : "nouveau" (setup = le nouveau), "remplace" (setup = l'ANCIEN,
    remplacé ; suivi d'un "nouveau"), "annule" (setup = l'annulé, raison
    "expire" / "tendance" / "hors_session", ou raison libre via `annuler`),
    "rejete" (setup = None, raison = raison du rejet du FVG).
    """
    type: str
    instant: pd.Timestamp
    setup: Optional[Setup]
    raison: str = ""


def _champ(ligne, nom):
    """Lit un champ d'une ligne : Series, dict ou namedtuple (itertuples)."""
    try:
        return ligne[nom]
    except (KeyError, TypeError, IndexError):
        return getattr(ligne, nom)


class MoteurSignaux:
    """Machine à setups (spec §3), appelée à chaque clôture M15.

    `sur_cloture_m15(t, ligne, position_ouverte)` applique dans cet ordre :
    1. Annulation du setup actif : "expire" si t >= expire_a, sinon "tendance"
       si ligne.tendance != sens, sinon "hors_session" si not ligne.heure_entree_ok.
    2. Création : FVG à t (sens != 0) non rejeté, sens == tendance != 0,
       adr_ok, heure_entree_ok, aucune position ouverte. Le nouveau setup
       remplace l'éventuel setup actif (événements "remplace" puis "nouveau").
       cree_a = t, expire_a = t + validite_setup_barres × 15 min.
       Un FVG REJETÉ qui remplissait toutes les autres conditions (sens ==
       tendance != 0, adr_ok, heure d'entrée, pas de position) produit un
       événement "rejete" avec sa raison ; le setup actif est conservé. Les
       FVG écartés par la tendance, l'ADR, la session ou une position ouverte
       ne produisent pas d'événement (ils sont visibles dans le tableau des
       signaux).
    3. Renvoie la liste des événements, dans l'ordre où ils se produisent.

    Garde-fous : t doit être strictement croissant d'un appel à l'autre ; si
    la ligne porte son instant (Series.name ou namedtuple.Index), il doit
    être égal à t ; un FVG valide sans prix finis lève ValueError.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self._s = _strategie(cfg)
        self.validite = int(self._s.validite_setup_barres) * DUREE_M15
        self.setup_actif: Optional[Setup] = None
        self.dernier_instant: Optional[pd.Timestamp] = None

    def sur_cloture_m15(self, t, ligne, position_ouverte: bool = False) -> list:
        t = pd.Timestamp(t)
        if self.dernier_instant is not None and t <= self.dernier_instant:
            raise ValueError(f"MoteurSignaux : instants non croissants ({t} après {self.dernier_instant})")
        instant_ligne = getattr(ligne, "name", None)
        if instant_ligne is None and hasattr(ligne, "_fields") and "Index" in ligne._fields:
            instant_ligne = ligne.Index
        if isinstance(instant_ligne, (pd.Timestamp, np.datetime64)) and pd.Timestamp(instant_ligne) != t:
            raise ValueError(f"MoteurSignaux : la ligne {instant_ligne} ne correspond pas à t={t}")
        self.dernier_instant = t

        tendance = int(_champ(ligne, "tendance"))
        heure_ok = bool(_champ(ligne, "heure_entree_ok"))
        adr_ok = bool(_champ(ligne, "adr_ok"))
        sens = int(_champ(ligne, "sens"))
        evenements: list = []

        # 1. Annulation du setup actif
        actif = self.setup_actif
        if actif is not None:
            raison = ""
            if t >= actif.expire_a:
                raison = "expire"
            elif tendance != actif.sens:
                raison = "tendance"
            elif not heure_ok:
                raison = "hors_session"
            if raison:
                evenements.append(Evenement("annule", t, actif, raison))
                self.setup_actif = None

        # 2. Création d'un setup
        if (sens != 0 and sens == tendance and adr_ok and heure_ok
                and not bool(position_ouverte)):
            rejet = _champ(ligne, "rejet")
            rejet = "" if rejet is None or (isinstance(rejet, float) and np.isnan(rejet)) else str(rejet)
            if rejet:
                evenements.append(Evenement("rejete", t, None, rejet))
            else:
                prix = [float(_champ(ligne, c)) for c in ("entree", "sl", "tp1", "distance_sl")]
                if not all(np.isfinite(prix)) or prix[3] <= 0:
                    raise ValueError(f"MoteurSignaux : FVG valide à {t} avec des prix invalides {prix}")
                nouveau = Setup(sens, prix[0], prix[1], prix[2], prix[3], t, t + self.validite)
                if self.setup_actif is not None:
                    evenements.append(Evenement("remplace", t, self.setup_actif, "nouveau_fvg"))
                self.setup_actif = nouveau
                evenements.append(Evenement("nouveau", t, nouveau, ""))

        return evenements

    def consommer(self) -> Setup:
        """Retire et renvoie le setup actif (rempli par l'exécution). RuntimeError s'il n'y en a pas."""
        if self.setup_actif is None:
            raise RuntimeError("MoteurSignaux.consommer : aucun setup actif")
        setup, self.setup_actif = self.setup_actif, None
        return setup

    def annuler(self, instant, raison: str) -> Optional[Evenement]:
        """Annule le setup actif depuis l'exécution (ex. heure dépassée ou taille refusée au toucher, §5).

        Renvoie l'événement "annule", ou None s'il n'y avait pas de setup.
        """
        if self.setup_actif is None:
            return None
        ev = Evenement("annule", pd.Timestamp(instant), self.setup_actif, str(raison))
        self.setup_actif = None
        return ev
