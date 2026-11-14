"""Fenêtres horaires de trading (docs/SPEC_TECHNIQUE.md §3 « Sessions »).

Heures = heure SERVEUR du broker (horodatages naïfs). Chaque fonction accepte :
- un instant unique (pd.Timestamp ou datetime.datetime) -> bool ;
- un DatetimeIndex (ou tout ce que pd.DatetimeIndex accepte, sauf Series) -> np.ndarray[bool] ;
- une pd.Series de dates -> pd.Series[bool] de même index.

`cfg` peut être un `Config` (on lit `cfg.strategie`) ou directement un
`StrategieConfig`.

Règles :
- jour autorisé : jour de la semaine (lundi = 0) dans `jours_autorises` ;
- heure d'entrée : jour autorisé ET debut_session <= heure < derniere_entree ;
- clôture forcée : heure >= cloture_forcee (quel que soit le jour).
L'heure est comparée à la seconde près (09:00:00 est une heure d'entrée,
08:59:59 non).
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def _strategie(cfg):
    return getattr(cfg, "strategie", cfg)


def _secondes(nom: str, s) -> int:
    h = s.heure(nom)
    return h.hour * 3600 + h.minute * 60


def _est_scalaire(t) -> bool:
    return isinstance(t, (pd.Timestamp, datetime, np.datetime64))


def _vers_index(t) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(t)
    if idx.tz is not None:
        raise ValueError("sessions : horodatages naïfs (heure serveur) attendus")
    return idx


def _secondes_du_jour(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(idx.hour * 3600 + idx.minute * 60 + idx.second, dtype=np.int64)


def _scalaire(t) -> pd.Timestamp:
    ts = t if isinstance(t, pd.Timestamp) else pd.Timestamp(t)
    if ts.tz is not None:
        raise ValueError("sessions : horodatage naïf (heure serveur) attendu")
    return ts


def _appliquer(t, calcul):
    """Applique `calcul(DatetimeIndex) -> ndarray[bool]` à une entrée vectorielle."""
    if isinstance(t, pd.Series):
        return pd.Series(calcul(_vers_index(t)), index=t.index)
    return calcul(_vers_index(t))


def _jour_ok(idx: pd.DatetimeIndex, s) -> np.ndarray:
    return np.isin(np.asarray(idx.dayofweek), np.asarray(list(s.jours_autorises), dtype=np.int64))


def est_jour_autorise(t, cfg):
    """Vrai si le jour de la semaine de `t` (lundi = 0) est dans `jours_autorises`."""
    s = _strategie(cfg)
    if _est_scalaire(t):
        return _scalaire(t).weekday() in s.jours_autorises
    return _appliquer(t, lambda idx: _jour_ok(idx, s))


def est_heure_entree(t, cfg):
    """Vrai si une entrée est permise à `t` : jour autorisé et debut_session <= heure < derniere_entree."""
    s = _strategie(cfg)
    debut, fin = _secondes("debut_session", s), _secondes("derniere_entree", s)

    def calcul(idx):
        sec = _secondes_du_jour(idx)
        return _jour_ok(idx, s) & (sec >= debut) & (sec < fin)

    if _est_scalaire(t):
        ts = _scalaire(t)
        sec = ts.hour * 3600 + ts.minute * 60 + ts.second
        return ts.weekday() in s.jours_autorises and debut <= sec < fin
    return _appliquer(t, calcul)


def doit_cloturer(t, cfg, depuis=None):
    """Vrai si l'heure de `t` est >= cloture_forcee (tout jour confondu).

    `depuis` (extension optionnelle, prudente) : instant d'ouverture de la
    position. S'il est donné et que `t` tombe à une date serveur POSTÉRIEURE à
    celle de `depuis`, on renvoie aussi True : l'heure de clôture forcée du
    jour d'ouverture est forcément passée (cas d'un trou de données qui
    sauterait la bougie de 21:55). Sans `depuis`, règle stricte de la spec.
    """
    s = _strategie(cfg)
    limite = _secondes("cloture_forcee", s)
    jour_depuis = None if depuis is None else pd.Timestamp(depuis).normalize()

    def calcul(idx):
        res = _secondes_du_jour(idx) >= limite
        if jour_depuis is not None:
            res = res | np.asarray(idx.normalize() > jour_depuis)
        return res

    if _est_scalaire(t):
        ts = _scalaire(t)
        if ts.hour * 3600 + ts.minute * 60 + ts.second >= limite:
            return True
        return jour_depuis is not None and ts.normalize() > jour_depuis
    return _appliquer(t, calcul)
