"""Indicateurs : EMA, ranges journaliers et filtre ADR (docs/SPEC_TECHNIQUE.md §3).

Tous les calculs sont causaux : la valeur à une position ne dépend que des
valeurs aux positions antérieures ou égales (EMA), ou strictement antérieures
(filtre ADR du jour D, qui n'utilise que les jours < D).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(serie: pd.Series, periode: int) -> pd.Series:
    """EMA récursive : serie.ewm(span=periode, adjust=False).mean().

    EMA[0] = serie[0], puis EMA[i] = a * serie[i] + (1 - a) * EMA[i-1] avec
    a = 2 / (periode + 1). Causale : EMA[i] ne dépend que de serie[:i+1].
    """
    if int(periode) < 1:
        raise ValueError("ema : periode doit être >= 1")
    return serie.astype(float).ewm(span=int(periode), adjust=False).mean()


def ranges_journaliers(h1: pd.DataFrame) -> pd.Series:
    """Range de chaque date serveur : max(high) - min(low) des bougies H1 du jour.

    Une bougie H1 appartient à la date de son OUVERTURE (la bougie 23:00 est
    dans le jour J, bien qu'elle clôture à 00:00 de J+1). Renvoie une Series
    float indexée par la date (Timestamp normalisé à minuit, index nommé
    "date"), triée. Seules les dates présentes dans les données apparaissent
    (pas de jour vide inventé). Le range du jour en cours, s'il est partiel,
    n'est jamais utilisé pour ce même jour par `filtre_adr`.
    """
    if not isinstance(h1.index, pd.DatetimeIndex):
        raise ValueError("ranges_journaliers : l'index doit être un DatetimeIndex")
    dates = h1.index.normalize()
    groupes = h1.groupby(dates)
    r = (groupes["high"].max() - groupes["low"].min()).astype(float)
    r.index = pd.DatetimeIndex(r.index, name="date")
    return r.sort_index()


def filtre_adr(ranges: pd.Series, periode: int, reference: int,
               ratio_min: float, ratio_max: float, dates=None) -> pd.Series:
    """Filtre ADR du jour D, sans utiliser D ni aucun jour postérieur.

    Pour chaque date D : on prend les ranges des dates de `ranges`
    strictement antérieures à D ; ADR = moyenne des `periode` derniers,
    REF = médiane des `reference` derniers. Le jour est autorisé (True) si
    ratio_min <= ADR / REF <= ratio_max (bornes incluses).

    Interdit (False) si l'historique antérieur compte moins de
    max(periode, reference) jours, si un range de la fenêtre est NaN, ou si
    REF <= 0 : en cas de doute, on ne trade pas.

    "Jours" = dates présentes dans `ranges` (jours de cotation), pas jours
    calendaires : un week-end ou un jour férié sans données ne compte pas.

    `dates` (extension optionnelle) : dates à évaluer, par défaut
    `ranges.index`. Une date absente de `ranges` est évaluée avec la même règle
    (jours < D), ce qui permet d'évaluer un jour M15 dont les bougies H1 ne
    sont pas encore disponibles.

    Renvoie une Series[bool] indexée par la date (Timestamp normalisé, "date").
    """
    periode, reference = int(periode), int(reference)
    if periode < 1 or reference < 1:
        raise ValueError("filtre_adr : periode et reference doivent être >= 1")
    if not isinstance(ranges.index, pd.DatetimeIndex):
        raise ValueError("filtre_adr : ranges doit être indexé par des dates (DatetimeIndex)")
    r = ranges.sort_index()
    if r.index.has_duplicates:
        raise ValueError("filtre_adr : dates en double dans ranges")
    jours = r.index.normalize()
    valeurs = pd.Series(r.to_numpy(dtype=float))
    # Statistiques sur la fenêtre se TERMINANT à la position k (incluse) ;
    # pour le jour D on lira la position du dernier jour < D.
    adr_fin = valeurs.rolling(periode, min_periods=periode).mean().to_numpy()
    ref_fin = valeurs.rolling(reference, min_periods=reference).median().to_numpy()

    if dates is None:
        cibles = pd.DatetimeIndex(jours)
    else:
        cibles = pd.DatetimeIndex(dates).normalize()
    pos = jours.searchsorted(cibles, side="left") - 1      # dernier jour strictement < D
    valide = pos >= 0
    pos_sure = np.where(valide, pos, 0)
    adr = np.where(valide, adr_fin[pos_sure] if len(adr_fin) else np.nan, np.nan)
    ref = np.where(valide, ref_fin[pos_sure] if len(ref_fin) else np.nan, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = adr / ref
    ok = valide & np.isfinite(ratio) & (ref > 0) & (ratio >= ratio_min) & (ratio <= ratio_max)
    return pd.Series(ok.astype(bool), index=pd.DatetimeIndex(cibles, name="date"), name="adr_ok")
