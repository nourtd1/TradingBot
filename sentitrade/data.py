"""Chargement et rééchantillonnage des bougies MT5 (docs/SPEC_TECHNIQUE.md §1-2).

Format des fichiers (section 2 de la spec) :
    time,open,high,low,close,tick_volume,spread,real_volume
avec `time` au format "YYYY-MM-DD HH:MM:SS" en heure SERVEUR du broker.

Conventions :
- l'index `time` est un DatetimeIndex NAÏF (heure serveur, jamais converti en UTC) ;
- une bougie est datée de son OUVERTURE et n'est utilisable qu'à sa clôture ;
- prix en float64, `tick_volume`, `spread` (points) et `real_volume` en int64.

Politique de validation (prudente) : tout fichier douteux est REFUSÉ (ValueError
avec le détail) plutôt que corrigé en silence. Seules exceptions, signalées par
`warnings.warn` : les doublons de `time` (on garde la DERNIÈRE occurrence du
fichier) et un fichier non trié (on le trie).
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

COLONNES = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
COLONNES_PRIX = ["open", "high", "low", "close"]
COLONNES_ENTIERES = ["tick_volume", "spread", "real_volume"]
FORMAT_TIME = "%Y-%m-%d %H:%M:%S"

# Agrégats du rééchantillonnage (spec §7) : open first, high max, low min,
# close last, volumes sum, spread max.
AGREGATS = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "tick_volume": "sum",
    "spread": "max",
    "real_volume": "sum",
}

_MAX_EXEMPLES = 5


def _exemples(index: pd.Index, masque: np.ndarray) -> str:
    """Liste lisible des premiers horodatages fautifs."""
    fautifs = index[masque]
    texte = ", ".join(str(x) for x in fautifs[:_MAX_EXEMPLES])
    if len(fautifs) > _MAX_EXEMPLES:
        texte += f", ... ({len(fautifs)} au total)"
    return texte


def valider_bougies(df: pd.DataFrame, source: str = "bougies") -> None:
    """Vérifie un DataFrame de bougies déjà typé (index `time`).

    Refuse (ValueError avec détail) : NaN ou infini, prix <= 0, OHLC incohérent
    (high < max(open, close, low) ou low > min(open, close)), spread ou volumes
    négatifs. Ne vérifie ni l'ordre ni les doublons.
    """
    prix = df[COLONNES_PRIX].to_numpy(dtype=float)
    non_finis = ~np.isfinite(prix).all(axis=1)
    if non_finis.any():
        raise ValueError(f"{source} : prix manquant ou infini aux instants {_exemples(df.index, non_finis)}")
    non_positifs = (prix <= 0).any(axis=1)
    if non_positifs.any():
        raise ValueError(f"{source} : prix <= 0 aux instants {_exemples(df.index, non_positifs)}")
    o, h, l, c = (prix[:, i] for i in range(4))
    incoherent = (h < np.maximum(o, c)) | (l > np.minimum(o, c)) | (h < l)
    if incoherent.any():
        premier = df.index[incoherent][0]
        ligne = df.loc[premier, COLONNES_PRIX]
        if isinstance(ligne, pd.DataFrame):
            ligne = ligne.iloc[0]
        raise ValueError(
            f"{source} : OHLC incohérent (il faut low <= open, close <= high) sur "
            f"{int(incoherent.sum())} bougie(s), instants {_exemples(df.index, incoherent)} ; "
            f"première : open={ligne['open']}, high={ligne['high']}, low={ligne['low']}, close={ligne['close']}"
        )
    for col in COLONNES_ENTIERES:
        if col in df.columns:
            negatif = df[col].to_numpy() < 0
            if negatif.any():
                raise ValueError(f"{source} : '{col}' négatif aux instants {_exemples(df.index, negatif)}")


def charger_bougies(chemin: Path | str) -> pd.DataFrame:
    """Charge un fichier de bougies MT5 exporté (spec §2) et le valide.

    Renvoie un DataFrame indexé par `time` (DatetimeIndex naïf, heure serveur,
    nommé "time"), trié, sans doublon, avec les colonnes
    open, high, low, close (float64), tick_volume, spread, real_volume (int64).

    Lève ValueError si : le fichier est vide, les colonnes ne sont pas
    exactement celles de la spec, une date n'est pas au format
    "YYYY-MM-DD HH:MM:SS", une valeur est manquante ou non numérique, une
    colonne entière contient un nombre non entier, ou si `valider_bougies`
    échoue (OHLC incohérent, prix <= 0, valeurs négatives). La validation porte
    sur TOUTES les lignes du fichier, y compris les doublons écartés : une ligne
    corrompue fait refuser le fichier entier.

    Doublons de `time` : on garde la dernière occurrence du fichier et on le
    signale par `warnings.warn`. Fichier non trié : on trie et on le signale.
    """
    chemin = Path(chemin)
    brut = pd.read_csv(chemin, dtype=str, keep_default_na=False)
    source = chemin.name
    colonnes = list(brut.columns)
    if sorted(colonnes) != sorted(COLONNES):
        manquantes = sorted(set(COLONNES) - set(colonnes))
        en_trop = sorted(set(colonnes) - set(COLONNES))
        raise ValueError(f"{source} : colonnes attendues {COLONNES} ; manquantes {manquantes}, en trop {en_trop}")
    if brut.empty:
        raise ValueError(f"{source} : aucune bougie")

    try:
        temps = pd.to_datetime(brut["time"].str.strip(), format=FORMAT_TIME)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{source} : colonne 'time' hors du format {FORMAT_TIME} ({exc})") from exc

    df = pd.DataFrame(index=pd.DatetimeIndex(temps, name="time"))
    for col in COLONNES_PRIX + COLONNES_ENTIERES:
        texte = brut[col].str.strip()
        valeurs = pd.to_numeric(texte.where(texte != "", None), errors="coerce").to_numpy(dtype=float)
        manquant = np.isnan(valeurs)
        if manquant.any():
            raise ValueError(f"{source} : '{col}' manquant ou non numérique aux instants "
                             f"{_exemples(df.index, manquant)}")
        if col in COLONNES_ENTIERES:
            if not np.isfinite(valeurs).all() or (valeurs != np.round(valeurs)).any():
                fautif = ~np.isfinite(valeurs) | (valeurs != np.round(valeurs))
                raise ValueError(f"{source} : '{col}' doit être entier, instants {_exemples(df.index, fautif)}")
            df[col] = valeurs.astype(np.int64)
        else:
            df[col] = valeurs
    df = df[COLONNES[1:]]
    valider_bougies(df, source)

    doublons = df.index.duplicated(keep="last")
    if doublons.any():
        warnings.warn(
            f"{source} : {int(doublons.sum())} doublon(s) de 'time' ignoré(s) (dernière occurrence gardée), "
            f"instants {_exemples(df.index, doublons)}",
            stacklevel=2,
        )
        df = df[~doublons]
    if not df.index.is_monotonic_increasing:
        warnings.warn(f"{source} : fichier non trié par 'time', tri appliqué", stacklevel=2)
        df = df.sort_index(kind="mergesort")
    return df


def reechantillonner(df: pd.DataFrame, regle: str) -> pd.DataFrame:
    """Agrège des bougies vers une unité plus grande ("15min", "h", "D"...).

    Agrégats : open first, high max, low min, close last, tick_volume et
    real_volume sum, spread max. Comme MT5, chaque période est fermée à gauche
    et étiquetée par son début : la bougie H1 de 10:00 couvre [10:00, 11:00).
    Les périodes sans aucune bougie source sont supprimées (pas de bougie
    inventée). Seules les colonnes connues sont acceptées (ValueError sinon) ;
    les colonnes de volume/spread absentes sont simplement omises.

    Attention : une période partiellement couverte (début ou fin des données,
    bougies manquantes) donne une bougie agrégée partielle ; c'est à l'appelant
    de ne pas utiliser une bougie qui n'est pas encore clôturée.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("reechantillonner : l'index doit être un DatetimeIndex")
    if df.index.tz is not None:
        raise ValueError("reechantillonner : horodatages naïfs (heure serveur) attendus")
    inconnues = sorted(set(df.columns) - set(AGREGATS))
    if inconnues:
        raise ValueError(f"reechantillonner : colonne(s) inconnue(s) {inconnues}")
    manquantes = [c for c in COLONNES_PRIX if c not in df.columns]
    if manquantes:
        raise ValueError(f"reechantillonner : colonne(s) de prix manquante(s) {manquantes}")
    if not df.index.is_monotonic_increasing:
        df = df.sort_index(kind="mergesort")
    agregats = {c: a for c, a in AGREGATS.items() if c in df.columns}
    res = df.resample(regle, label="left", closed="left").agg(agregats)
    res = res[df["open"].resample(regle, label="left", closed="left").count() > 0]
    for col in COLONNES_ENTIERES:
        if col in res.columns:
            res[col] = res[col].astype(np.int64)
    res.index.name = df.index.name if df.index.name is not None else "time"
    return res[list(agregats)]
