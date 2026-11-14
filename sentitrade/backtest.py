"""Moteur d'exécution du backtest (docs/SPEC_TECHNIQUE.md §5).

Principe : les signaux viennent TOUJOURS de `preparer_signaux` (fichiers M15 et
H1) et de `MoteurSignaux`, exactement comme dans le bot. Ce module ne décide
que de l'exécution : toucher du niveau, prix d'entrée, taille, sorties, coûts
et garde-fous du compte.

Boucle (événementielle, mais équivalente à une boucle bougie par bougie) :
pour chaque bougie d'exécution d'ouverture t, on traite d'abord toutes les
clôtures M15 <= t pas encore traitées, puis la bougie. On parcourt donc les
clôtures M15 dans l'ordre et, entre deux clôtures, les bougies d'exécution
dont l'ouverture est dans [clôture précédente, clôture suivante[. Une bougie
M1 manquante ne fait jamais sauter une clôture M15. Sans setup actif ni
position, il ne se passe rien sur une bougie : on ne la parcourt pas.

Une position ouverte est simulée d'un bloc par `simuler_trade`, fonction pure
sur tableaux numpy (réutilisée par la référence « tendance seule » du
rapport) : elle est causale (la sortie à la bougie j ne dépend que des bougies
<= j), ce qui permet de la tronquer si la garde de risque déclenche l'arrêt
définitif en cours de trade.

Modèle de prix (spec §1 et §5) : bougies en Bid, Ask = Bid + spread.
Long  : touché si low_bid + spread <= entree ; prix = min(entree, open_ask) + glissement_entree.
Short : touché si high_bid >= entree ; prix = max(entree, open_bid) - glissement_entree.
Sorties, par priorité sur une même bougie : clôture forcée (à l'open), stop,
puis TP1 (jamais sur la bougie de remplissage ; stop prioritaire si les deux
sont possibles). Après TP1 : fermeture partielle à tp1 -/+ glissement_entree,
SL du reste au prix d'entrée réel, runner sans TP jusqu'au stop ou 21h55.

Hypothèses ajoutées (prudentes, non écrites dans la spec, signalées dans le rapport) :
- le stop au breakeven posé à TP1 n'est actif qu'à partir de la bougie
  SUIVANTE (l'ordre de modification part après l'exécution de TP1) ;
- si, au toucher, le prix d'entrée réel est déjà au-delà du SL (gap) ou à
  moins de `stops_level` du SL, le setup est annulé (`sl_depasse_au_toucher`) :
  le broker refuserait l'ordre avec ce stop ;
- equity vue par la garde de risque : à chaque bougie d'une position, d'abord
  au prix le plus défavorable de la bougie (low Bid pour un long, high Ask pour
  un short), puis à la clôture ; sur la bougie de sortie finale, la balance
  réalisée. Les commissions encore dues sont déduites de l'equity latente ;
- `spread_plancher` (optionnel, en points par heure serveur) : le spread
  utilisé à l'exécution est max(spread de la bougie, plancher de l'heure).
  Le spread d'une bougie MT5 peut sous-estimer le spread réellement payé ;
- fin des données avec une position ouverte : sortie à la clôture de la
  dernière bougie (raison `fin_donnees`), au Bid/Ask, glissement d'entrée.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from sentitrade.risk_manager import GardeRisque, calculer_taille_lot, decouper_volume
from sentitrade.sessions import est_heure_entree
from sentitrade.strategy import MoteurSignaux, preparer_signaux

TOLERANCE_PRIX = 1e-9
NS_MINUTE = 60 * 10 ** 9
TOLERANCE_COUVERTURE = pd.Timedelta(days=3)   # M1 « couvre » la période à 3 jours près

COLONNES_TRADES = ["setup_cree_a", "sens", "entree_a", "prix_entree", "sl", "tp1", "lots",
                   "risque_montant", "sorties", "pnl", "r_multiple", "raison_sortie", "duree_min",
                   "sortie_a", "niveau_entree", "distance_sl_setup", "distance_sl_reelle",
                   "perte_par_lot", "budget_risque", "lots_tp1", "tp1_atteint", "commission",
                   "balance_avant", "balance_apres", "spread_entree"]
COLONNES_EVENEMENTS = ["instant", "type", "raison", "sens", "entree", "sl", "tp1", "setup_cree_a"]


# --------------------------------------------------------------------------- marché

@dataclass
class Marche:
    """Bougies d'exécution sous forme de tableaux numpy (fenêtre simulée)."""
    index: pd.DatetimeIndex
    temps: np.ndarray        # int64 ns, ouverture
    o: np.ndarray            # Bid
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    sp: np.ndarray           # spread en prix (après plancher éventuel)
    jour: np.ndarray         # int64, jours depuis l'époque (date serveur)
    cloture: np.ndarray      # bool, heure >= cloture_forcee
    heure_entree: np.ndarray  # bool, est_heure_entree(ouverture)
    i_cloture: np.ndarray    # int64, pour une entrée à i : 1re bougie j >= i de clôture forcée
    resolution: str
    duree: pd.Timedelta

    def __len__(self) -> int:
        return len(self.temps)


def preparer_marche(bougies: pd.DataFrame, cfg, spec, resolution: str = "m1",
                    spread_plancher=None) -> Marche:
    """Convertit des bougies (Bid, spread en points) en `Marche`.

    `spread_plancher` : None, ou 24 valeurs (liste/array/dict heure -> points)
    de spread minimal par heure serveur.
    """
    s = cfg.strategie
    idx = pd.DatetimeIndex(bougies.index)
    temps = idx.values.astype("datetime64[ns]").view(np.int64)
    sp_points = bougies["spread"].to_numpy(dtype=float)
    heures = np.asarray(idx.hour)
    if spread_plancher is not None:
        if isinstance(spread_plancher, dict):
            plancher = np.array([float(spread_plancher.get(h, spread_plancher.get(str(h), 0.0)) or 0.0)
                                 for h in range(24)])
        else:
            plancher = np.asarray(spread_plancher, dtype=float)
        if plancher.shape != (24,) or not np.isfinite(plancher).all():
            raise ValueError("spread_plancher : 24 valeurs finies attendues (points par heure)")
        sp_points = np.maximum(sp_points, plancher[heures])
    sp = sp_points * float(spec.point)
    jour = temps // (86400 * 10 ** 9)
    hc = s.heure("cloture_forcee")
    sec = np.asarray(idx.hour * 3600 + idx.minute * 60 + idx.second, dtype=np.int64)
    cloture = sec >= hc.hour * 3600 + hc.minute * 60
    n = len(temps)
    # prochaine bougie de clôture forcée (>= i) et première bougie du jour suivant
    pos = np.where(cloture, np.arange(n), n)
    prochaine = np.minimum.accumulate(pos[::-1])[::-1] if n else pos
    jour_suivant = np.searchsorted(jour, jour, side="right")
    i_cloture = np.minimum(prochaine, jour_suivant).astype(np.int64)
    return Marche(index=idx, temps=temps,
                  o=bougies["open"].to_numpy(dtype=float), h=bougies["high"].to_numpy(dtype=float),
                  l=bougies["low"].to_numpy(dtype=float), c=bougies["close"].to_numpy(dtype=float),
                  sp=sp, jour=jour, cloture=cloture,
                  heure_entree=np.asarray(est_heure_entree(idx, s), dtype=bool),
                  i_cloture=i_cloture, resolution=resolution,
                  duree=pd.Timedelta(minutes=1 if resolution == "m1" else 15))


def choisir_resolution(m1: Optional[pd.DataFrame], m15: Optional[pd.DataFrame], debut=None, fin=None,
                       resolution: str = "auto") -> str:
    """'m1' si les données M1 couvrent la période (à 3 jours près), sinon 'm15'."""
    if resolution in ("m1", "m15"):
        return resolution
    if resolution != "auto":
        raise ValueError(f"resolution inconnue : {resolution!r} (auto, m1, m15)")
    if m1 is None or len(m1) == 0:
        return "m15"
    if m15 is None or len(m15) == 0:
        return "m1"
    d = m15.index[0] if debut is None else max(pd.Timestamp(debut), m15.index[0])
    f = m15.index[-1] if fin is None else min(pd.Timestamp(fin), m15.index[-1])
    if m1.index[0] <= d + TOLERANCE_COUVERTURE and m1.index[-1] >= f - TOLERANCE_COUVERTURE:
        return "m1"
    return "m15"


def _fenetre(df: pd.DataFrame, debut, fin) -> pd.DataFrame:
    if debut is not None:
        df = df[df.index >= pd.Timestamp(debut)]
    if fin is not None:
        df = df[df.index < pd.Timestamp(fin)]
    return df


# --------------------------------------------------------------------------- simulation d'un trade

@dataclass
class ResultatSimulation:
    """Sorties d'un trade : liste de (indice de bougie, prix, volume, raison), dans l'ordre."""
    sorties: list
    j_fin: int               # bougie de la dernière sortie
    i_tp1: int               # bougie de TP1 (-1 si non atteint)


def prix_cloture_forcee(marche: Marche, j: int, sens: int, glissement: float) -> float:
    """Sortie au marché à l'open de j : Bid pour un long, Ask pour un short, glissement défavorable."""
    if sens > 0:
        return float(marche.o[j]) - glissement
    return float(marche.o[j] + marche.sp[j]) + glissement


def _premier(masque: np.ndarray, decalage: int, defaut: int) -> int:
    if masque.size and masque.any():
        return decalage + int(np.argmax(masque))
    return defaut


def simuler_trade(marche: Marche, i: int, sens: int, prix_entree: float, sl: float, tp1: float,
                  lots: float, lots_tp1: float, cfg, spec) -> ResultatSimulation:
    """Simule un trade rempli sur la bougie i (spec §5), sans la garde de risque.

    `lots_tp1` = volume fermé à TP1 (0 si le lot n'est pas divisible : on passe
    alors seulement le SL au breakeven). Le trade est clos au plus tard à la
    première bougie de clôture forcée (heure >= cloture_forcee ou date
    postérieure à celle de l'entrée), à son open ; s'il n'y en a pas, à la
    clôture de la dernière bougie (`fin_donnees`).
    """
    ex = cfg.execution
    ge, gs = float(ex.glissement_entree), float(ex.glissement_stop)
    n = len(marche)
    i_cl = int(marche.i_cloture[i])
    o, h, l, sp = marche.o, marche.h, marche.l, marche.sp
    sorties = []

    def sortie_finale(j_debut: int, stop: float, volume: float, raison_stop: str):
        if sens > 0:
            masque = l[j_debut:i_cl] <= stop
        else:
            masque = h[j_debut:i_cl] + sp[j_debut:i_cl] >= stop
        js = _premier(masque, j_debut, i_cl)
        if js < i_cl:
            if sens > 0:
                prix = min(stop, float(o[js])) - gs
            else:
                prix = max(stop, float(o[js] + sp[js])) + gs
            sorties.append((js, prix, volume, raison_stop))
            return js
        if i_cl < n:
            sorties.append((i_cl, prix_cloture_forcee(marche, i_cl, sens, ge), volume, "cloture_forcee"))
            return i_cl
        j = n - 1
        prix = float(marche.c[j]) - ge if sens > 0 else float(marche.c[j] + sp[j]) + ge
        sorties.append((j, prix, volume, "fin_donnees"))
        return j

    # Phase 1 : stop d'origine (dès la bougie de remplissage) et TP1 (à partir de i + 1).
    if sens > 0:
        m_stop = l[i:i_cl] <= sl
        m_tp = h[i + 1:i_cl] >= tp1
    else:
        m_stop = h[i:i_cl] + sp[i:i_cl] >= sl
        m_tp = l[i + 1:i_cl] + sp[i + 1:i_cl] <= tp1
    js = _premier(m_stop, i, i_cl)
    jt = _premier(m_tp, i + 1, i_cl)
    if js < i_cl and js <= jt:          # stop d'abord, y compris sur la même bougie que TP1
        j_fin = sortie_finale(i, sl, lots, "stop")
        return ResultatSimulation(sorties, j_fin, -1)
    if jt >= i_cl:
        j_fin = sortie_finale(i_cl, sl, lots, "stop")   # aucune bougie à scanner : clôture forcée
        return ResultatSimulation(sorties, j_fin, -1)
    # TP1 à la bougie jt
    restant = lots
    if lots_tp1 > 0:
        sorties.append((jt, tp1 - sens * ge, lots_tp1, "tp1"))
        restant = lots - lots_tp1
    j_fin = sortie_finale(jt + 1, prix_entree, restant, "stop_breakeven")
    return ResultatSimulation(sorties, j_fin, jt)


def pnl_sortie(sens: int, prix_entree: float, prix: float, volume: float, cfg, spec) -> float:
    """P&L d'une sortie (devise du compte) : Δprix × volume × taille_contrat − commission × volume."""
    return (sens * (prix - prix_entree) * volume * float(spec.taille_contrat)
            - float(cfg.execution.commission_par_lot) * volume)


# --------------------------------------------------------------------------- résultat

@dataclass
class ResultatBacktest:
    trades: pd.DataFrame
    equity: pd.Series                 # equity à la clôture de chaque bougie d'exécution
    evenements: pd.DataFrame
    parametres: dict
    resolution: str
    debut: Optional[pd.Timestamp]
    fin: Optional[pd.Timestamp]
    balance_initiale: float
    balance_finale: float
    arret_definitif: bool
    raison_arret: str
    historique_garde: list
    stats: dict = field(default_factory=dict)

    @property
    def equity_journaliere(self) -> pd.Series:
        """Equity à la dernière bougie de chaque date serveur."""
        if self.equity.empty:
            return self.equity
        e = self.equity.groupby(self.equity.index.normalize()).last()
        e.index.name = "date"
        return e


# --------------------------------------------------------------------------- moteur

class _Execution:
    """État de la simulation (interne)."""

    def __init__(self, marche: Marche, cfg, spec, balance_initiale: float, garde_complete: bool,
                 arret_definitif_actif: bool = True):
        self.m = marche
        self.cfg = cfg
        self.spec = spec
        self.balance = float(balance_initiale)
        # Mode évaluation (architecte, 2026-11-13) : l'arrêt définitif tronquerait l'échantillon
        # et plafonnerait artificiellement le drawdown mesuré. Il est neutralisé (seuil 99 %),
        # son franchissement est daté a posteriori sur la courbe d'equity ; la limite
        # journalière reste active car elle fait partie des règles de trading.
        cfg_garde = cfg.risque if arret_definitif_actif else dataclasses.replace(cfg.risque, drawdown_max_pct=99.0)
        self.garde = GardeRisque(cfg_garde, balance_initiale)
        self.moteur = MoteurSignaux(cfg)
        self.garde_complete = garde_complete
        self.evenements: list = []
        self.trades: list = []
        self.pnl_sorties: list = []          # (indice bougie, pnl)
        self.latents: list = []              # (i0, tableau latent par bougie)
        self.adverses: list = []             # (i0, equity au pire prix de chaque bougie de position)
        self.t_fin_position = -1
        self.jour_garde = None
        self.nb_spread_large = 0
        self.arret_instant = None

    # ---- journal
    def journaliser(self, type_, instant, raison="", setup=None):
        self.evenements.append({
            "instant": pd.Timestamp(instant), "type": type_, "raison": raison,
            "sens": None if setup is None else setup.sens,
            "entree": None if setup is None else setup.entree,
            "sl": None if setup is None else setup.sl,
            "tp1": None if setup is None else setup.tp1,
            "setup_cree_a": None if setup is None else setup.cree_a,
        })

    def journaliser_moteur(self, evs):
        for ev in evs:
            self.journaliser(ev.type, ev.instant, ev.raison, ev.setup)

    def annuler(self, j: int, raison: str):
        ev = self.moteur.annuler(pd.Timestamp(self.m.temps[j]), raison)
        if ev is not None:
            self.journaliser(ev.type, ev.instant, ev.raison, ev.setup)

    def _memoriser(self, i: int, lat, eq_adv) -> None:
        """Garde le latent de clôture (courbe d'equity) et l'equity au pire prix (drawdown)."""
        self.latents.append((i, lat))
        self.adverses.append((i, np.asarray(eq_adv, dtype=float).copy()))

    # ---- garde
    def journee(self, j: int, balance: float):
        jour = int(self.m.jour[j])
        if self.jour_garde is None or jour > self.jour_garde:
            self.jour_garde = jour
            self.garde.nouvelle_journee(pd.Timestamp(self.m.temps[j]).normalize(), balance)

    # ---- bougies entre deux clôtures M15
    def traiter(self, a: int, b: int) -> int:
        """Traite les bougies [a, b[ ; renvoie l'indice de la prochaine bougie à traiter."""
        setup = self.moteur.setup_actif
        if setup is None or a >= b:
            return b
        m, s = self.m, self.cfg.strategie
        if setup.sens > 0:
            touche = m.l[a:b] + m.sp[a:b] <= setup.entree + TOLERANCE_PRIX
        else:
            touche = m.h[a:b] >= setup.entree - TOLERANCE_PRIX
        for j in np.flatnonzero(touche) + a:
            j = int(j)
            t = pd.Timestamp(m.temps[j])
            if m.cloture[j] or not m.heure_entree[j]:
                self.annuler(j, "hors_session_au_toucher")
                return b
            if m.sp[j] > float(s.spread_max) + TOLERANCE_PRIX:
                # CDC §3.4 : spread trop large au moment du signal => on ANNULE l'entrée
                # (décision 2026-11-13, alignement sur le CDC ; plus prudent que d'attendre).
                self.nb_spread_large += 1
                self.annuler(j, "spread_trop_large")
                return b
            self.journee(j, self.balance)
            ok, raison = self.garde.peut_ouvrir(t, self.balance)
            if not ok:
                self.annuler(j, raison)
                return b
            return self.ouvrir(j, setup)
        return b

    def ouvrir(self, j: int, setup) -> int:
        m, cfg, spec = self.m, self.cfg, self.spec
        ex = cfg.execution
        ge = float(ex.glissement_entree)
        sens = setup.sens
        if sens > 0:
            prix = min(setup.entree, float(m.o[j] + m.sp[j])) + ge
        else:
            prix = max(setup.entree, float(m.o[j])) - ge
        distance = sens * (prix - setup.sl)
        if distance <= float(spec.stops_level_points) * float(spec.point) + TOLERANCE_PRIX:
            self.annuler(j, "sl_depasse_au_toucher")
            return j + 1
        contrat = float(spec.taille_contrat)
        # Audit 2026-11-13 : le glissement attendu sur un stop fait partie de la perte possible ;
        # sans lui, un stop touché coûtait jusqu'à 1,02 % au lieu de 1 %.
        perte_par_lot = (distance + float(ex.glissement_stop)) * contrat + float(ex.commission_par_lot)
        taille = calculer_taille_lot(self.balance, cfg.risque, perte_par_lot, prix * contrat, spec)
        if not taille.accepte:
            self.annuler(j, "refus_taille:" + taille.raison)
            return j + 1
        self.moteur.consommer()
        self.journaliser("entree", m.temps[j], taille.raison, setup)
        lots = taille.lots
        lots_tp1, _ = decouper_volume(lots, cfg.strategie.tp1_fraction, spec)
        sim = simuler_trade(m, j, sens, prix, setup.sl, setup.tp1, lots, lots_tp1, cfg, spec)
        sorties, j_fin, i_tp1 = self.suivre_garde(j, sens, prix, lots, sim)
        if i_tp1 >= 0 and lots_tp1 <= 0:
            self.journaliser("tp1_sans_partiel", m.temps[i_tp1], "lot_non_divisible", setup)
        balance_avant = self.balance
        pnl_total = 0.0
        commission = 0.0
        details = []
        for (k, p, v, r) in sorties:
            pnl = pnl_sortie(sens, prix, p, v, cfg, spec)
            self.pnl_sorties.append((k, pnl))
            pnl_total += pnl
            commission += float(ex.commission_par_lot) * v
            details.append(f"{pd.Timestamp(m.temps[k]):%Y-%m-%d %H:%M} {r} {v:g} lot @ {p:.2f} ({pnl:+.2f})")
        self.balance = balance_avant + pnl_total
        risque = lots * perte_par_lot
        entree_a = pd.Timestamp(m.temps[j])
        sortie_a = pd.Timestamp(m.temps[j_fin])
        self.trades.append({
            "setup_cree_a": setup.cree_a, "sens": sens, "entree_a": entree_a, "prix_entree": prix,
            "sl": setup.sl, "tp1": setup.tp1, "lots": lots, "risque_montant": risque,
            "sorties": " | ".join(details), "pnl": pnl_total,
            "r_multiple": pnl_total / risque if risque > 0 else float("nan"),
            "raison_sortie": sorties[-1][3], "duree_min": (sortie_a - entree_a).total_seconds() / 60.0,
            "sortie_a": sortie_a, "niveau_entree": setup.entree, "distance_sl_setup": setup.distance_sl,
            "distance_sl_reelle": distance, "perte_par_lot": perte_par_lot,
            "budget_risque": taille.risque_montant, "lots_tp1": lots_tp1, "tp1_atteint": i_tp1 >= 0,
            "commission": commission, "balance_avant": balance_avant, "balance_apres": self.balance,
            "spread_entree": float(m.sp[j]),
        })
        self.t_fin_position = int(m.temps[j_fin])
        if self.garde.arret_definitif and self.arret_instant is None:
            self.arret_instant = pd.Timestamp(m.temps[j_fin])
            self.journaliser("arret_definitif", self.arret_instant, self.garde.raison_arret)
        return j_fin + 1

    def _trajectoire(self, i: int, sens: int, prix: float, lots: float, sorties: list):
        """Equity défavorable et de clôture à chaque bougie [i, j_fin] (balance avant trade = self.balance)."""
        m, cfg, spec = self.m, self.cfg, self.spec
        j_fin = sorties[-1][0]
        nb = j_fin - i + 1
        contrat = float(spec.taille_contrat)
        comm = float(cfg.execution.commission_par_lot)
        vol_sortie = np.zeros(nb)
        pnl_bougie = np.zeros(nb)
        for (k, p, v, _) in sorties:
            vol_sortie[k - i] += v
            pnl_bougie[k - i] += pnl_sortie(sens, prix, p, v, cfg, spec)
        vol_apres = lots - np.cumsum(vol_sortie)
        vol_avant = vol_apres + vol_sortie
        real_apres = np.cumsum(pnl_bougie)
        real_avant = real_apres - pnl_bougie
        sl_ = slice(i, j_fin + 1)
        if sens > 0:
            adverse, marque = m.l[sl_], m.c[sl_]
        else:
            adverse, marque = m.h[sl_] + m.sp[sl_], m.c[sl_] + m.sp[sl_]
        lat_avant = sens * (adverse - prix) * vol_avant * contrat - comm * vol_avant
        lat_apres = sens * (marque - prix) * vol_apres * contrat - comm * vol_apres
        lat_apres[-1] = 0.0
        eq_adv = self.balance + real_avant + lat_avant
        eq_clo = self.balance + real_apres + lat_apres
        eq_adv[-1] = eq_clo[-1]          # bougie de sortie finale : balance réalisée seulement
        return eq_adv, eq_clo, real_avant, lat_apres

    def suivre_garde(self, i: int, sens: int, prix: float, lots: float, sim: ResultatSimulation):
        """Nourrit la garde de risque pendant le trade ; tronque le trade en cas d'arrêt définitif."""
        m, garde = self.m, self.garde
        sorties = list(sim.sorties)
        eq_adv, eq_clo, real_avant, lat = self._trajectoire(i, sens, prix, lots, sorties)
        j_fin = sorties[-1][0]
        rapide = (not self.garde_complete and int(m.jour[j_fin]) == self.jour_garde)
        if rapide:
            obs = np.empty(2 * len(eq_adv))
            obs[0::2], obs[1::2] = eq_adv, eq_clo
            pic = np.maximum(garde.pic_equity, np.maximum.accumulate(obs))
            seuil_dd = 1.0 - float(self.cfg.risque.drawdown_max_pct) / 100.0
            seuil_jour = garde.balance_debut_jour * (1.0 - float(self.cfg.risque.perte_jour_max_pct) / 100.0)
            marge = 1.0 + 1e-6
            risque_dd = bool((obs <= pic * seuil_dd * marge).any())
            risque_jour = (not garde.bloque_jour) and bool((obs <= seuil_jour * marge).any())
            if not (risque_dd or risque_jour):
                t_fin = pd.Timestamp(m.temps[j_fin])
                garde.mettre_a_jour(t_fin, float(obs.max()))
                garde.mettre_a_jour(t_fin, float(obs[-1]))
                self._memoriser(i, lat, eq_adv)
                return sorties, j_fin, sim.i_tp1
        # Chemin complet : une observation par bougie (défavorable puis clôture).
        for k in range(i, j_fin + 1):
            t = pd.Timestamp(m.temps[k])
            self.journee(k, self.balance + float(real_avant[k - i]))
            garde.mettre_a_jour(t, float(eq_adv[k - i]))
            if k == j_fin:
                break
            garde.mettre_a_jour(t, float(eq_clo[k - i]))
            if garde.arret_definitif:
                # Arrêt définitif en cours de trade : fermeture à l'open suivant.
                gardees = [x for x in sorties if x[0] <= k]
                vol = lots - sum(x[2] for x in gardees)
                if k + 1 < len(m):
                    p = prix_cloture_forcee(m, k + 1, sens, float(self.cfg.execution.glissement_entree))
                    gardees.append((k + 1, p, vol, "arret_definitif"))
                else:
                    ge = float(self.cfg.execution.glissement_entree)
                    p = float(m.c[k]) - ge if sens > 0 else float(m.c[k] + m.sp[k]) + ge
                    gardees.append((k, p, vol, "arret_definitif"))
                sorties = gardees
                eq_adv, eq_clo, real_avant, lat = self._trajectoire(i, sens, prix, lots, sorties)
                j_fin = sorties[-1][0]
                garde.mettre_a_jour(pd.Timestamp(m.temps[j_fin]), float(eq_clo[-1]))
                i_tp1 = sim.i_tp1 if 0 <= sim.i_tp1 <= k else -1
                self._memoriser(i, lat, eq_adv)
                return sorties, j_fin, i_tp1
        self._memoriser(i, lat, eq_adv)
        return sorties, j_fin, sim.i_tp1


def executer_backtest(m1: Optional[pd.DataFrame], m15: Optional[pd.DataFrame], h1: Optional[pd.DataFrame],
                      cfg, spec, balance_initiale: float = 3000.0, debut=None, fin=None,
                      resolution: str = "auto", *, signaux: Optional[pd.DataFrame] = None,
                      spread_plancher=None, garde_complete: bool = False,
                      arret_definitif_actif: bool = True) -> ResultatBacktest:
    """Backtest de la stratégie sur [debut, fin[ (spec §5).

    - `m1`, `m15`, `h1` : bougies MT5 (Bid). Les signaux sont calculés par
      `preparer_signaux(m15, h1)` sur TOUT l'historique fourni, puis la
      simulation porte sur les bougies d'exécution d'ouverture dans [debut, fin[.
    - `resolution` : "auto" (M1 si les M1 couvrent la période, sinon M15), "m1" ou "m15".
    - `signaux` : tableau de `preparer_signaux` déjà calculé (même historique),
      pour éviter de le recalculer (sensibilité, tests).
    - `spread_plancher` : spread minimal par heure serveur (points), voir le module.
    - `garde_complete` : True = observer la garde de risque à chaque bougie de
      position sans raccourci (plus lent, résultat identique ; utilisé par les tests).
    - `arret_definitif_actif` : True = comportement du bot réel (le compte s'arrête à
      -drawdown_max_pct). False = mode ÉVALUATION utilisé par le rapport : on continue
      à trader pour mesurer toute la période, et `stats["date_franchissement_dd"]` date
      le moment où l'arrêt se serait déclenché.
    """
    debut = None if debut is None else pd.Timestamp(debut)
    fin = None if fin is None else pd.Timestamp(fin)
    if signaux is None:
        signaux = preparer_signaux(m15, h1, cfg, spec)
    res = choisir_resolution(m1, m15, debut, fin, resolution)
    bougies = m1 if res == "m1" else m15
    if bougies is None:
        raise ValueError(f"executer_backtest : pas de bougies pour la résolution {res}")
    bougies = _fenetre(bougies, debut, fin)
    marche = preparer_marche(bougies, cfg, spec, res, spread_plancher)
    ex = _Execution(marche, cfg, spec, balance_initiale, garde_complete, arret_definitif_actif)

    sig = signaux
    if debut is not None:
        sig = sig[sig.index >= debut]
    if fin is not None:
        sig = sig[sig.index < fin]
    C = sig.index.values.astype("datetime64[ns]").view(np.int64)
    fin_segment = np.searchsorted(marche.temps, C, side="left")
    tendance = sig["tendance"].to_numpy()
    adr = sig["adr_ok"].to_numpy()
    hok = sig["heure_entree_ok"].to_numpy()
    sens = sig["sens"].to_numpy()
    entree, sl, tp1, dist = (sig[c].to_numpy(dtype=float) for c in ("entree", "sl", "tp1", "distance_sl"))
    rejet = sig["rejet"].to_numpy()

    pos = 0
    n = len(marche)
    for k in range(len(C)):
        if ex.garde.arret_definitif:
            break
        b = int(fin_segment[k])
        if pos < b:
            pos = max(pos, ex.traiter(pos, b))
            if ex.garde.arret_definitif:
                break
        # Audit 2026-11-13 : un setup créé à la clôture C ne doit jamais pouvoir être
        # rempli sur une bougie antérieure à C (même si traiter() s'est arrêté avant b).
        pos = max(pos, b)
        if C[k] <= ex.t_fin_position:
            continue                      # position ouverte à cette clôture : rien ne peut se créer
        if ex.moteur.setup_actif is None and sens[k] == 0:
            continue                      # aucun événement possible
        ligne = {"tendance": tendance[k], "adr_ok": adr[k], "heure_entree_ok": hok[k], "sens": sens[k],
                 "entree": entree[k], "sl": sl[k], "tp1": tp1[k], "distance_sl": dist[k], "rejet": rejet[k]}
        ex.journaliser_moteur(ex.moteur.sur_cloture_m15(pd.Timestamp(C[k]), ligne, False))
    if not ex.garde.arret_definitif and pos < n:
        ex.traiter(pos, n)
    if ex.garde.arret_definitif and ex.moteur.setup_actif is not None:
        ev = ex.moteur.annuler(ex.arret_instant, "arret_definitif")
        if ev is not None:
            ex.journaliser(ev.type, ev.instant, ev.raison, ev.setup)

    # Equity à la clôture de chaque bougie.
    realise = np.zeros(n)
    for (k, p) in ex.pnl_sorties:
        realise[k] += p
    equity = float(balance_initiale) + np.cumsum(realise)
    for (i0, lat) in ex.latents:
        equity[i0:i0 + len(lat)] += lat
    equity_s = pd.Series(equity, index=marche.index, name="equity")

    trades = pd.DataFrame(ex.trades, columns=COLONNES_TRADES)
    evenements = pd.DataFrame(ex.evenements, columns=COLONNES_EVENEMENTS)

    # Statistiques de contexte pour le rapport.
    stats = {"nb_attente_spread": ex.nb_spread_large, "nb_bougies": n}
    if n:
        jours = pd.DatetimeIndex(np.unique(marche.index.normalize()))
        jours = jours[np.isin(jours.dayofweek, list(cfg.strategie.jours_autorises))]
        adr_jour = sig["adr_ok"].groupby(sig.index.normalize()).any() if len(sig) else pd.Series(dtype=bool)
        adr_jour = adr_jour.reindex(jours).fillna(False).astype(bool)
        stats["jours_trades_possibles"] = int(len(jours))
        stats["jours_bloques_adr"] = int((~adr_jour).sum())
    hist = list(ex.garde.historique)
    stats["jours_bloques_perte_jour"] = sum(1 for d in hist if d.type == "perte_jour")
    stats["arret_definitif_actif"] = bool(arret_definitif_actif)
    stats["date_franchissement_dd"] = None
    stats["dd_max_adverse_pct"] = None
    if n:
        # Drawdown au PIRE prix de chaque bougie (comme la garde du bot réel), pic sur les clôtures.
        # Audit 2026-11-13 : mesuré aux seules clôtures, un creux intra-bougie de -15,3 % passait inaperçu.
        equity_adv = equity.copy()
        for (i0, adv) in ex.adverses:
            fin_adv = min(i0 + len(adv), n)
            equity_adv[i0:fin_adv] = np.minimum(equity_adv[i0:fin_adv], adv[:fin_adv - i0])
        pic = np.maximum.accumulate(np.maximum(equity, float(balance_initiale)))
        # Le creux d'une bougie est comparé au plus haut des clôtures PRÉCÉDENTES (l'ordre
        # creux/sommet à l'intérieur d'une bougie est inconnu) ; la clôture, à son propre pic.
        pic_avant = np.concatenate([[float(balance_initiale)], pic[:-1]])
        dd = np.maximum((pic_avant - equity_adv) / pic_avant, (pic - equity) / pic)
        stats["dd_max_adverse_pct"] = float(dd.max() * 100.0)
        franchi = dd >= float(cfg.risque.drawdown_max_pct) / 100.0 - 1e-12
        if franchi.any():
            stats["date_franchissement_dd"] = str(marche.index[int(np.argmax(franchi))])

    parametres = {"strategie": dict(vars(cfg.strategie)), "risque": dict(vars(cfg.risque)),
                  "execution": dict(vars(cfg.execution)), "symbole": dict(vars(spec)),
                  "spread_plancher": None if spread_plancher is None else
                  (dict(spread_plancher) if isinstance(spread_plancher, dict) else list(np.asarray(spread_plancher, dtype=float)))}
    return ResultatBacktest(
        trades=trades, equity=equity_s, evenements=evenements, parametres=parametres, resolution=res,
        debut=debut if debut is not None else (marche.index[0] if n else None),
        fin=fin if fin is not None else (marche.index[-1] + marche.duree if n else None),
        balance_initiale=float(balance_initiale), balance_finale=float(ex.balance),
        arret_definitif=bool(ex.garde.arret_definitif), raison_arret=ex.garde.raison_arret,
        historique_garde=hist, stats=stats)
