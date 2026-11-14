"""Données synthétiques M1/M15/H1 au format MT5 (docs/SPEC_TECHNIQUE.md §2).

À quoi ça sert : tester le moteur de backtest de bout en bout dans le sandbox,
sans données réelles. Le prix est une MARCHE ALÉATOIRE SANS AVANTAGE : aucune
stratégie ne doit y gagner de l'argent après coûts. Si un backtest y trouve une
espérance significativement positive, c'est un bug (anticipation, coût oublié).

Construction (prudente vis-à-vis des biais) :
- chaque minute est simulée par `sous_pas` sous-pas gaussiens (5 s par défaut) ;
  open = premier point, close = dernier, high/low = extrêmes du sous-chemin.
  Les mèches sont donc de vrais morceaux du chemin : on ne fabrique pas de
  mèches qui « reviennent » artificiellement (ce serait un retour à la moyenne
  exploitable par une entrée au toucher d'un niveau) ;
- la minute suivante repart exactement du dernier point (martingale) ;
- volatilité intrajournalière : calme la nuit, plus forte à l'ouverture de
  Londres, maximale 15h30-18h (heure serveur), plus un facteur journalier
  persistant (log-AR(1)) pour que l'ADR varie d'un jour à l'autre ;
- cotation du lundi au vendredi, de 01:00 à 23:55 heure serveur, avec un petit
  gap aléatoire (centré) à chaque réouverture ;
- prix Bid arrondis au centime (2 décimales), spread en points entiers,
  15-40 points selon l'heure, avec de rares pics ;
- quelques bougies M1 manquantes (taux réglable) pour exercer la robustesse.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sentitrade.data import COLONNES, reechantillonner

# Profil de volatilité par tranche de 30 minutes (48 valeurs, heure serveur) :
# multiplicateur de l'écart-type par minute.
_PROFIL_30MIN = np.array(
    [0.45, 0.45,                     # 00:00-01:00 (pas de cotation avant 01:00)
     0.55, 0.50, 0.45, 0.45, 0.45, 0.45, 0.50, 0.50, 0.55, 0.60, 0.65, 0.70,   # 01:00-07:00
     0.80, 0.85,                     # 07:00-08:00
     0.95, 1.00,                     # 08:00-09:00
     1.15, 1.10, 1.05, 1.00, 0.95, 0.95, 0.95, 0.95, 1.00, 1.05,   # 09:00-14:00
     1.10, 1.25, 1.35,               # 14:00-15:30
     1.85, 1.90, 1.80, 1.70, 1.60,   # 15:30-18:00
     1.30, 1.15, 1.05, 0.95, 0.85, 0.80, 0.75, 0.65, 0.55, 0.50,   # 18:00-23:00
     0.45, 0.45],                    # 23:00-24:00
    dtype=float)
assert len(_PROFIL_30MIN) == 48


def _jours_ouvres(debut, fin) -> pd.DatetimeIndex:
    jours = pd.date_range(pd.Timestamp(debut).normalize(), pd.Timestamp(fin).normalize(), freq="D")
    return jours[jours.dayofweek < 5]


def generer_m1(debut, fin, graine: int, prix_initial: float = 3500.0, *,
               vol_minute: float = 0.85, sous_pas: int = 12,
               persistance_vol: float = 0.97, choc_vol: float = 0.08,
               gap_reouverture: float = 3.0, taux_trous: float = 0.0005,
               premiere_minute: int = 60, derniere_minute: int = 23 * 60 + 55) -> pd.DataFrame:
    """Bougies M1 synthétiques (Bid) du jour de `debut` inclus au jour de `fin` exclu.

    Paramètres principaux :
    - `vol_minute` : écart-type d'une minute ($) pour un multiplicateur 1 ;
      la valeur par défaut donne des bougies M15 de 3 à 8 $ en session ;
    - `sous_pas` : nombre de points simulés par minute (12 = toutes les 5 s) ;
    - `premiere_minute`, `derniere_minute` : première et dernière bougie du jour
      (minutes depuis minuit ; 01:00 et 23:55 incluses) ;
    - `taux_trous` : proportion de bougies M1 supprimées au hasard.

    Renvoie un DataFrame indexé par `time` (naïf, heure serveur, ouverture de
    la bougie), colonnes exactes de la spec : open, high, low, close (float,
    2 décimales), tick_volume, spread (points), real_volume (int64).
    """
    rng = np.random.default_rng(int(graine))
    debut_ts, fin_ts = pd.Timestamp(debut), pd.Timestamp(fin)
    jours = _jours_ouvres(debut_ts, fin_ts - pd.Timedelta(days=1)) if fin_ts > debut_ts else pd.DatetimeIndex([])
    minutes = np.arange(int(premiere_minute), int(derniere_minute) + 1)
    n_jour, n_jours = len(minutes), len(jours)
    if n_jours == 0:
        return pd.DataFrame(columns=COLONNES[1:], index=pd.DatetimeIndex([], name="time"))

    # Facteur de volatilité journalier persistant (moyenne ~1).
    log_f = np.empty(n_jours)
    x = 0.0
    chocs = rng.normal(0.0, choc_vol, n_jours)
    for d in range(n_jours):
        x = persistance_vol * x + chocs[d]
        log_f[d] = x
    facteur_jour = np.exp(log_f - 0.5 * choc_vol ** 2 / (1 - persistance_vol ** 2))

    profil = _PROFIL_30MIN[minutes // 30]
    # Écart-type par sous-pas : la variance d'une minute vaut (vol × profil × f)².
    sigma_min = vol_minute * profil[None, :] * facteur_jour[:, None]          # (jours, minutes)
    sigma_sous = sigma_min / np.sqrt(sous_pas)

    o = np.empty((n_jours, n_jour))
    h = np.empty_like(o)
    l = np.empty_like(o)
    c = np.empty_like(o)
    prix = float(prix_initial)
    for d in range(n_jours):
        if d > 0:
            prix += rng.normal(0.0, gap_reouverture * facteur_jour[d])
        pas = rng.standard_normal((n_jour, sous_pas)) * sigma_sous[d][:, None]
        chemin = np.cumsum(pas, axis=1)                                          # relatif à l'open
        increments = chemin[:, -1]
        ouvertures = prix + np.concatenate(([0.0], np.cumsum(increments)[:-1]))
        o[d] = ouvertures
        c[d] = ouvertures + increments
        h[d] = ouvertures + np.maximum(chemin.max(axis=1), 0.0)
        l[d] = ouvertures + np.minimum(chemin.min(axis=1), 0.0)
        prix = c[d, -1]
        if prix <= 1.0:  # garde-fou numérique (n'arrive pas avec les réglages par défaut)
            raise ValueError("generer_m1 : prix devenu négatif, réduire vol_minute")

    # Spread (points) : plus large la nuit et autour de la réouverture, pics rares.
    heure = minutes / 60.0
    base = np.where((heure >= 8) & (heure < 22), 20.0, 28.0)
    base = np.where(heure < 2, 34.0, base)
    spread = base[None, :] + rng.normal(0.0, 3.0, (n_jours, n_jour))
    spread = np.clip(np.rint(spread), 15, 40)
    pics = rng.random((n_jours, n_jour)) < 0.002
    spread = np.where(pics, rng.integers(45, 151, (n_jours, n_jour)), spread).astype(np.int64)

    volume = np.maximum(1, np.rint(60 * profil[None, :] * facteur_jour[:, None]
                                   * rng.lognormal(0.0, 0.3, (n_jours, n_jour)))).astype(np.int64)

    temps = (jours.values.astype("datetime64[m]")[:, None]
             + minutes[None, :].astype("timedelta64[m]")).ravel()
    df = pd.DataFrame({
        "open": np.round(o.ravel(), 2),
        "high": np.round(h.ravel(), 2),
        "low": np.round(l.ravel(), 2),
        "close": np.round(c.ravel(), 2),
        "tick_volume": volume.ravel(),
        "spread": spread.ravel(),
        "real_volume": np.zeros(n_jours * n_jour, dtype=np.int64),
    }, index=pd.DatetimeIndex(temps.astype("datetime64[ns]"), name="time"))
    if taux_trous > 0:
        garder = rng.random(len(df)) >= taux_trous
        df = df[garder]
    return df[COLONNES[1:]]


def generer_jeu(debut, fin, graine: int, **kwargs):
    """(m1, m15, h1) synthétiques cohérents : M15 et H1 agrégés depuis les M1 (`reechantillonner`)."""
    m1 = generer_m1(debut, fin, graine, **kwargs)
    return m1, reechantillonner(m1, "15min"), reechantillonner(m1, "h")
