"""Moteur de portefeuille multi-symboles par barres (RECHERCHE_PLAN §3-5).

Boucle : un CALENDRIER UNIFIÉ (toutes les ouvertures de bougies des symboles, triées) est parcouru
instant par instant. Pour chaque instant t, sur les symboles qui ont une bougie en t :

1. **Ouverture** : valorisation à l'ouverture ; S4 : sortie forcée ; ordres au marché décidés à la
   clôture précédente (d'abord TOUTES les sorties, puis les entrées dans l'ordre alphabétique des
   symboles) ; S2 : rééquilibrage de la première bougie de la semaine.
2. **Intrabarre** : S4 : échéance puis déclenchement des ordres stop d'entrée (OCO) ; stops et
   objectifs des positions ouvertes.
3. **Clôture** : valorisation à la clôture, equity au pire prix, garde de risque, décisions de la
   stratégie (exécutées à l'ouverture SUIVANTE du symbole).

Au changement de jour serveur : enregistrement de l'equity du jour (clôture et pire prix), swaps de
la nuit, nouvelle journée de la garde.

Modèle de prix : bougies en Bid ; Ask = Bid + spread effectif (`couts.py`).
- Achat au marché : Ask d'ouverture + glissement marché ; vente : Bid d'ouverture - glissement.
- Stop d'un long (vente) : si l'ouverture est déjà sous le stop (gap), sortie à l'ouverture - glissement
  stop ; sinon si le plus bas touche le stop, sortie au stop - glissement stop. Symétrique pour un
  short (déclenché quand l'Ask touche le stop).
- Objectif (S4 variante 2R) : ordre limite exécuté à son prix, jamais sur la bougie de remplissage
  (l'ordre intrabarre est inconnu : on suppose que l'objectif a été atteint AVANT l'entrée) ; si stop
  et objectif sont possibles dans la même bougie, le stop passe en premier.
- Ordres stop d'entrée de S4 : achat-stop déclenché quand l'Ask atteint le haut du range, rempli au
  max(niveau, Ask d'ouverture) + glissement stop (vente-stop symétrique au Bid). Si les deux niveaux
  sont atteints dans la même bougie, hypothèse défavorable : le premier ordre est rempli puis la
  position est stoppée de l'autre côté dans la même bougie.
- Barres D1 : l'ordre des prix dans la bougie est inconnu ; l'entrée à l'ouverture précède tout ;
  un stop touché dans la bougie d'entrée est exécuté ; l'equity « au pire prix » prend le plus bas
  (long) / le plus haut + spread (short) de chaque bougie, pour toutes les positions en même temps.

Taille et plafonds (plan §5) :
- S1, S3, S4 : 0,5 % de l'equity au moment de l'entrée, perte au stop glissement compris
  (`risk_manager.calculer_taille_lot`, arrondi vers le bas au pas, refus sous le minimum) ; levier
  restant = 10 × equity - notionnel déjà ouvert (et des ordres S4 en attente) ; refus si la somme des
  risques ouverts (risque initial en USD des positions, + ordres S4 en attente) dépasserait 4 %.
- S2 : taille = (10 %/√N) × equity / (notionnel d'un lot × vol annualisée). Interprétations prudentes
  (signalées) : DÉCISION DE L'ARCHITECTE (13/11/2026, avant toute donnée réelle) : le plafond de
  risque ouvert de 4 % ne s'applique PAS à S2 (plan §5 : « S2 suit sa propre cible de volatilité ») ;
  l'appliquer ramenait la volatilité cible de 10 % à environ 3 % et changeait la stratégie
  pré-enregistrée. S2 reste bornée par le levier (10) et jugée sur le drawdown (critère 4). N = nombre de symboles dont le signal est calculable
  à cette date ; le stop reste celui posé à l'ouverture de la position (un ajustement de taille ne
  le déplace pas) ; une position stoppée reste à plat jusqu'au rééquilibrage suivant.
- Garde de risque (`risk_manager.GardeRisque`, -3 %/jour et -15 %) en MODE ÉVALUATION : la limite
  journalière bloque les nouvelles positions et les augmentations jusqu'au lendemain (et annule les
  ordres S4 en attente) ; l'arrêt à -15 % est daté (`date_arret`) mais n'arrête pas la simulation.
  La garde observe l'equity au pire prix de chaque bougie puis à la clôture. Interprétation signalée :
  la référence de la perte du jour est l'equity à minuit (et non la balance) ; pour des positions de
  plusieurs jours, une perte latente antérieure n'est pas une perte du jour. Pour S4 (à plat à minuit),
  les deux sont égales.
- Swaps : chaque nuit d'un jour où le symbole a coté et où la position est encore ouverte à la
  clôture ; ×3 la nuit de `swap_rollover3days`. Pour la crypto, toutes les nuits sont comptées ET
  la nuit triple aussi (double compte possible du week-end : prudent).
- Conversion : P&L et swaps convertis en USD au taux du jour (clôture de la veille de la paire de
  conversion, `donnees.Convertisseur`). Sans taux, aucune entrée (refus « conversion_indisponible »).
- Fin de période : les positions encore ouvertes sont fermées à la dernière clôture, au marché.

Cycle 2 (docs/RECHERCHE_PLAN_CYCLE2.md) :
- C1 : entrée au marché (comme S3) à l'ouverture du jour prévu, risque 0,5 %, stop 3 ATR20 (4 en variante)
  sous le prix d'entrée, plafonds de risque ouvert (4 %) et de levier ; l'ordre est ANNULÉ (compteur
  `annulation:jour_entree_absent`) si la bougie suivante reçue n'est pas datée du jour prévu ; sortie à
  l'ouverture qui suit la clôture de la (jour_sortie - 1)-ième bougie reçue du mois suivant celui de
  l'entrée (raison « fin_tournant »). Une position stoppée attend le mois suivant.
  Référence « toujours long » (critère 7) : même symboles, même taille (0,5 %) et même stop ; on achète
  dès que possible, on rachète à l'ouverture qui suit un stop, et la position est RENOUVELÉE chaque mois
  au moment exact où C1 entre (sortie puis nouvelle entrée à la même ouverture, au même risque de
  0,5 % de l'equity du moment et avec un nouveau stop) : sans ce renouvellement, la taille fixée des
  années plus tôt ne serait plus « le même risque ». Le coût d'un aller-retour par mois est le même que
  celui de C1 : seule la durée de détention (et donc les swaps) diffère, c'est ce que le critère juge.
- C2 : exactement la mécanique de S2 (ciblage de volatilité 10 %/√N, levier 10, rééquilibrage au-delà de
  25 %, stop 4 ATR, à plat jusqu'au rééquilibrage suivant, plafond de risque ouvert NON appliqué), avec
  un signal 0/1 : le signal 0 ferme la position (« reequilibrage_sortie »), il n'y a jamais de vente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, Decimal
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from sentitrade.recherche.couts import (ErreurCouts, ErreurSwap, ParametresCouts, construire_couts,
                                        spreads_d1)
from sentitrade.recherche.donnees import Convertisseur, ErreurConversion, Univers, jours
from sentitrade.recherche import strategies as st
from sentitrade.risk_manager import DECL_DRAWDOWN_MAX, GardeRisque, calculer_taille_lot

CAPITAL_INITIAL = 10_000.0
PLAFOND_RISQUE_OUVERT_PCT = 4.0
APPLIQUER_PLAFOND_RISQUE_S2 = False   # décision architecte 13/11/2026 (voir docstring)
LEVIER_MAX = 10.0
PERTE_JOUR_MAX_PCT = 3.0
DRAWDOWN_ARRET_PCT = 15.0
NS_JOUR = 86_400 * 10 ** 9
TOL = 1e-9

COLONNES_TRADES = ["strategie", "symbole", "classe", "sens", "entree_a", "prix_entree", "lots", "stop_initial",
                   "objectif", "risque_usd", "risque_pct", "equity_entree", "sortie_a", "prix_sortie",
                   "raison_sortie", "barres", "ajustements", "pnl_prix_usd", "swaps_usd", "commissions_usd",
                   "couts_execution_usd", "pnl_net_usd", "r_multiple"]
COLONNES_EVENEMENTS = ["instant", "symbole", "type", "raison", "detail"]
COLONNES_TENTATIVES = ["instant", "symbole", "perte_par_lot_usd", "notionnel_par_lot_usd", "volume_min",
                       "accepte", "raison"]


# --------------------------------------------------------------------------- préparation

@dataclass
class Serie:
    nom: str
    classe: str
    t: list
    jour: list
    o: list
    h: list
    l: list
    c: list
    spr_o: list
    spr_b: list
    taux: list
    taux_swap: list
    couts: object
    vmin: float
    vpas: float
    vmax: float
    sig: Dict[str, list]
    premier_pret: Optional[int]       # ns du premier instant où la stratégie peut décider


@dataclass
class _Spec:
    volume_min: float
    volume_pas: float
    volume_max: float


@dataclass
class _CfgRisque:
    risque_par_trade_pct: float
    levier_effectif_max: float
    exiger_lot_divisible: bool = False
    perte_jour_max_pct: float = PERTE_JOUR_MAX_PCT
    drawdown_max_pct: float = DRAWDOWN_ARRET_PCT


def symboles_strategie(univers: Univers, strategie: st.Strategie) -> list:
    noms = []
    for nom in sorted(univers.symboles):
        d = univers.symboles[nom]
        if strategie.symboles is not None and nom not in strategie.symboles:
            continue
        if d.classe not in strategie.classes:
            continue
        noms.append(nom)
    return noms


def preparer_series(univers: Univers, strategie: st.Strategie, params_couts: ParametresCouts = ParametresCouts(),
                    facteur_contrat: float = 1.0, fin: Optional[pd.Timestamp] = None) -> tuple:
    """(liste de Serie, exclus {symbole: raison}, jours S4 ignorés {raison: nombre})."""
    conv = univers.cache.get("convertisseur")
    if conv is None:
        conv = univers.cache["convertisseur"] = Convertisseur(univers)
    series, exclus, ignores = [], {}, {}
    for nom in symboles_strategie(univers, strategie):
        d = univers.symboles[nom]
        try:
            couts = construire_couts(d.info, d.spread_stats, params_couts, facteur_contrat,
                                     (d.info.get("compte") or {}).get("currency", "USD"))
        except (ErreurSwap, ErreurCouts) as exc:
            exclus[nom] = str(exc)
            continue
        df = d.tf(strategie.timeframe)
        if df is None:
            exclus[nom] = f"pas de bougies {strategie.timeframe}"
            continue
        if fin is not None:
            df = df.loc[df.index <= fin]
            if not len(df):
                exclus[nom] = "aucune bougie dans la période"
                continue
        if strategie.timeframe == "D1":
            cle = ("spreads_d1", nom, params_couts, fin)
            if cle not in univers.cache:
                h1 = d.tf("H1")
                univers.cache[cle] = spreads_d1(df, h1, couts)
            spr_o, spr_b = univers.cache[cle]
        else:
            s = couts.spread_heures(df["spread"].to_numpy(), df.index.hour.to_numpy())
            spr_o = spr_b = s
        j = jours(df.index)
        try:
            taux = conv.taux(couts.devise_profit, j)
            taux_swap = conv.taux(couts.devise_swap(), j) if couts.swap_mode != 0 else np.ones(len(j))
        except ErreurConversion as exc:
            exclus[nom] = str(exc)
            continue
        p = strategie.params
        if strategie.code == "S1":
            sig = st.signaux_s1(df, p)
        elif strategie.code == "S2":
            sig = st.signaux_s2(df, p, d.classe == "crypto")
        elif strategie.code == "S3":
            sig = st.signaux_s3(df, p)
        elif strategie.code == "C1":
            sig = st.signaux_c1(df, p)
        elif strategie.code == "C2":
            sig = st.signaux_c2(df, p, d.classe == "crypto")
        else:
            niv = st.niveaux_s4(df, nom, p, couts.p50_heure)
            for r in niv.loc[~niv["placer"], "raison"]:
                ignores[r] = ignores.get(r, 0) + 1
            niv = niv[niv["placer"]]
            # On ne garde que les bougies utiles : de la dernière bougie du range à la fin du jour.
            pos_place = df.index.get_indexer(pd.DatetimeIndex(niv["t_placement"]))
            jour_place = dict(zip(niv["jour"].to_numpy(dtype="datetime64[ns]").astype(np.int64) // NS_JOUR,
                                  pos_place))
            prem = np.array([jour_place.get(int(x), -1) for x in j])
            garder = (prem >= 0) & (np.arange(len(df)) >= prem)
            sig = pd.DataFrame(index=df.index)
            sig["placer"] = False
            sig["haut"] = np.nan
            sig["bas"] = np.nan
            sig["t_limite"] = 0
            sig["t_sortie"] = 0
            sig.iloc[pos_place, sig.columns.get_loc("placer")] = True
            sig.iloc[pos_place, sig.columns.get_loc("haut")] = niv["haut"].to_numpy()
            sig.iloc[pos_place, sig.columns.get_loc("bas")] = niv["bas"].to_numpy()
            sig.iloc[pos_place, sig.columns.get_loc("t_limite")] = pd.DatetimeIndex(niv["t_limite"]).asi8
            sig.iloc[pos_place, sig.columns.get_loc("t_sortie")] = pd.DatetimeIndex(niv["t_sortie"]).asi8
            sig["pret"] = sig["placer"]
            df, sig = df[garder], sig[garder]
            spr_o, spr_b = spr_o[garder], spr_b[garder]
            j, taux, taux_swap = j[garder], taux[garder], taux_swap[garder]
            if not len(df):
                exclus[nom] = "aucun jour de range exploitable"
                continue
        pret = sig["pret"].to_numpy(dtype=bool)
        premier = int(df.index.asi8[pret.argmax()]) if pret.any() else None
        series.append(Serie(
            nom=nom, classe=d.classe, t=df.index.asi8.tolist(), jour=list(map(int, j)),
            o=df["open"].tolist(), h=df["high"].tolist(), l=df["low"].tolist(), c=df["close"].tolist(),
            spr_o=list(map(float, spr_o)), spr_b=list(map(float, spr_b)),
            taux=list(map(float, taux)), taux_swap=list(map(float, taux_swap)), couts=couts,
            vmin=float(d.info["volume_min"]), vpas=float(d.info["volume_step"]), vmax=float(d.info["volume_max"]),
            sig={k: sig[k].tolist() for k in sig.columns}, premier_pret=premier))
    return series, exclus, ignores


def plancher_lots(x: float, pas: float) -> float:
    """Arrondi vers le bas au pas, en décimal exact (jamais vers le haut)."""
    if not (x > 0) or not math.isfinite(x):
        return 0.0
    d_pas = Decimal(repr(float(pas)))
    n = (Decimal(repr(float(x))) / d_pas).to_integral_value(rounding=ROUND_FLOOR)
    return float(n * d_pas)


# --------------------------------------------------------------------------- moteur

@dataclass
class Position:
    sym: int
    sens: int
    lots: float
    prix_entree: float
    stop: float
    objectif: Optional[float]
    entree_ns: int
    risque_usd: float
    equity_entree: float
    stop_initial: float
    t_sortie: Optional[int] = None
    barre_entree: int = -1
    barres: int = 0
    pnl_prix: float = 0.0
    swaps: float = 0.0
    commissions: float = 0.0
    couts_exec: float = 0.0
    ajustements: int = 0


@dataclass
class ResultatSimulation:
    strategie: str
    variante: str
    capital_initial: float
    equity: pd.DataFrame
    trades: pd.DataFrame
    evenements: pd.DataFrame
    tentatives: pd.DataFrame
    compteurs: dict
    exclus: dict
    symboles: dict                # nom -> classe (symboles simulés)
    debut_eval: Optional[pd.Timestamp]
    date_arret: Optional[pd.Timestamp]
    nb_reequilibrages: int = 0


class _Moteur:
    def __init__(self, series: List[Serie], strategie: st.Strategie, capital: float,
                 debut_ns: Optional[int], journal_complet: bool = True):
        self.series = series
        self.strat = strategie
        self.code = strategie.code
        self.p = strategie.params
        self.capital = float(capital)
        self.debut_ns = debut_ns if debut_ns is not None else -(2 ** 62)
        self.balance = float(capital)
        self.positions: Dict[int, Position] = {}
        self.attente: Dict[int, list] = {}
        self.jour_prevu: Dict[int, int] = {}      # C1 : jour (n° depuis 1970) pour lequel l'ordre est valable
        self.oco: Dict[int, dict] = {}
        n = len(series)
        self.mk_bid = [math.nan] * n
        self.mk_spr = [0.0] * n
        self.mk_taux = [math.nan] * n
        self.mk_i = [-1] * n
        self.jour_derniere = [None] * n
        self.garde = GardeRisque(_CfgRisque(0.5, LEVIER_MAX), capital)
        self.jour = None
        self.pire_jour = math.inf
        self.lignes_equity = []
        self.trades = []
        self.evenements = []
        self.tentatives = []
        self.compteurs: Dict[str, int] = {}
        self.nb_reequilibrages = 0
        self.journal_complet = journal_complet

    # ---- outils
    def _compter(self, cle: str, n: int = 1):
        self.compteurs[cle] = self.compteurs.get(cle, 0) + n

    def _evt(self, t, s, type_, raison, detail=""):
        self._compter(f"{type_}:{raison}")
        if self.journal_complet:
            self.evenements.append((t, self.series[s].nom if s is not None else "", type_, raison, detail))

    def _latent(self, s: int, pos: Position, bid: float, spr: float) -> float:
        px = bid if pos.sens > 0 else bid + spr
        return pos.sens * (px - pos.prix_entree) * pos.lots * self.series[s].couts.contrat * self.mk_taux[s]

    def equity(self) -> float:
        e = self.balance
        for s, pos in self.positions.items():
            e += self._latent(s, pos, self.mk_bid[s], self.mk_spr[s])
        return e

    def _notionnel(self) -> float:
        tot = 0.0
        for s, pos in self.positions.items():
            tot += pos.lots * self.series[s].couts.contrat * self.mk_bid[s] * self.mk_taux[s]
        for s, o in self.oco.items():
            tot += o["lots"] * self.series[s].couts.contrat * o["haut"] * self.mk_taux[s]
        return tot

    def _risque_ouvert(self) -> float:
        return sum(p.risque_usd for p in self.positions.values()) + sum(o["risque_usd"] for o in self.oco.values())

    def _marquer(self, s: int, i: int, bid: float, spr: float):
        ser = self.series[s]
        self.mk_bid[s], self.mk_spr[s], self.mk_i[s] = bid, spr, i
        tx = ser.taux[i]
        if tx == tx:  # pas NaN : sinon on garde le dernier taux connu
            self.mk_taux[s] = tx

    # ---- exécutions
    def _executer_entree(self, s, i, t, sens, lots, prix, stop, objectif, cout_prix, equity, perte_lot,
                         raison_taille="ok", t_sortie=None):
        ser = self.series[s]
        com = ser.couts.commission_par_lot * lots
        self.balance -= com
        pos = Position(sym=s, sens=sens, lots=lots, prix_entree=prix, stop=stop, objectif=objectif, entree_ns=t,
                       risque_usd=lots * perte_lot, equity_entree=equity, stop_initial=stop, t_sortie=t_sortie,
                       barre_entree=i)
        pos.commissions = com
        pos.couts_exec = cout_prix * lots * ser.couts.contrat * self.mk_taux[s]
        self.positions[s] = pos
        if raison_taille != "ok":
            self._compter(f"taille_reduite:{raison_taille}")
        return pos

    def _fermer(self, s, t, prix, raison, cout_prix, lots=None):
        pos = self.positions[s]
        ser = self.series[s]
        l = pos.lots if lots is None else min(lots, pos.lots)
        pnl = pos.sens * (prix - pos.prix_entree) * ser.couts.contrat * l * self.mk_taux[s]
        self.balance += pnl
        pos.pnl_prix += pnl
        pos.couts_exec += cout_prix * l * ser.couts.contrat * self.mk_taux[s]
        if lots is not None and l < pos.lots - TOL:
            pos.risque_usd *= (pos.lots - l) / pos.lots
            pos.lots = plancher_lots(pos.lots - l + 1e-12, ser.vpas) if ser.vpas else pos.lots - l
            pos.ajustements += 1
            return
        net = pos.pnl_prix + pos.swaps - pos.commissions
        self.trades.append({
            "strategie": self.strat.nom, "symbole": ser.nom, "classe": ser.classe, "sens": pos.sens,
            "entree_a": pd.Timestamp(pos.entree_ns), "prix_entree": pos.prix_entree, "lots": pos.lots,
            "stop_initial": pos.stop_initial, "objectif": pos.objectif, "risque_usd": pos.risque_usd,
            "risque_pct": pos.risque_usd / pos.equity_entree * 100 if pos.equity_entree > 0 else math.nan,
            "equity_entree": pos.equity_entree, "sortie_a": pd.Timestamp(t), "prix_sortie": prix,
            "raison_sortie": raison, "barres": pos.barres, "ajustements": pos.ajustements,
            "pnl_prix_usd": pos.pnl_prix, "swaps_usd": pos.swaps, "commissions_usd": pos.commissions,
            "couts_execution_usd": pos.couts_exec, "pnl_net_usd": net,
            "r_multiple": net / pos.risque_usd if pos.risque_usd > 0 else math.nan})
        del self.positions[s]

    def _sortie_marche(self, s, i, t, raison, a_l_ouverture=True, lots=None):
        ser = self.series[s]
        pos = self.positions[s]
        bid = ser.o[i] if a_l_ouverture else ser.c[i]
        spr = ser.spr_o[i] if a_l_ouverture else ser.spr_b[i]
        g = ser.couts.glissement_marche
        if pos.sens > 0:
            self._fermer(s, t, bid - g, raison, g, lots)
        else:
            self._fermer(s, t, bid + spr + g, raison, spr + g, lots)

    def _tentative(self, t, s, perte_lot, notion_lot, accepte, raison):
        self.tentatives.append((t, self.series[s].nom, perte_lot, notion_lot, self.series[s].vmin, accepte, raison))
        if not accepte:
            self._compter(f"refus:{raison}")
            if self.journal_complet:
                self.evenements.append((t, self.series[s].nom, "refus", raison, ""))

    def _dimensionner(self, s, i, t, perte_lot, notion_lot):
        """(lots, raison_taille) ou (0, raison du refus). Applique garde, levier, risque, minimum."""
        E = self.equity()
        self.garde.mettre_a_jour(t, E)
        if not (perte_lot > 0 and notion_lot > 0 and math.isfinite(perte_lot) and math.isfinite(notion_lot)):
            return 0.0, "conversion_indisponible", E
        if self.garde.bloque_jour:
            return 0.0, "perte_jour_max", E
        if E <= 0:
            return 0.0, "equity_negative", E
        lev = (LEVIER_MAX * E - self._notionnel()) / E
        if lev <= TOL:
            return 0.0, "plafond_levier", E
        ser = self.series[s]
        res = calculer_taille_lot(E, _CfgRisque(self.strat.risque_pct, min(lev, LEVIER_MAX)), perte_lot, notion_lot,
                                  _Spec(ser.vmin, ser.vpas, ser.vmax))
        if not res.accepte:
            return 0.0, res.raison, E
        if self._risque_ouvert() + res.lots * perte_lot > PLAFOND_RISQUE_OUVERT_PCT / 100.0 * E * (1 + TOL):
            return 0.0, "plafond_risque_ouvert", E
        return res.lots, res.raison, E

    def _entree_marche(self, s, i, t, sens, atr, k_stop):
        """Entrée au marché à l'ouverture de la bougie i (S1, S3)."""
        ser = self.series[s]
        if not (atr == atr and atr > 0):
            return
        g, gs = ser.couts.glissement_marche, ser.couts.glissement_stop
        tx = ser.taux[i]
        if sens > 0:
            prix, cout = ser.o[i] + ser.spr_o[i] + g, ser.spr_o[i] + g
            stop = prix - k_stop * atr
        else:
            prix, cout = ser.o[i] - g, g
            stop = prix + k_stop * atr
        perte_lot = (abs(prix - stop) + gs) * ser.couts.contrat * tx + ser.couts.commission_par_lot
        notion_lot = ser.o[i] * ser.couts.contrat * tx
        lots, raison, E = self._dimensionner(s, i, t, perte_lot, notion_lot)
        self._tentative(t, s, perte_lot, notion_lot, lots > 0, raison if lots <= 0 else "ok")
        if lots > 0:
            self._executer_entree(s, i, t, sens, lots, prix, stop, None, cout, E, perte_lot, raison)

    def _verifier_sorties(self, s, i, t, pos: Position, depuis_ouverture=True):
        ser = self.series[s]
        o, h, l = ser.o[i], ser.h[i], ser.l[i]
        so, sb = ser.spr_o[i], ser.spr_b[i]
        gs = ser.couts.glissement_stop
        if pos.sens > 0:
            if depuis_ouverture and o <= pos.stop:
                self._fermer(s, t, o - gs, "stop_gap", gs)
            elif l <= pos.stop:
                self._fermer(s, t, pos.stop - gs, "stop", gs)
            elif pos.objectif is not None and h >= pos.objectif:
                self._fermer(s, t, pos.objectif, "objectif", 0.0)
        else:
            if depuis_ouverture and o + so >= pos.stop:
                self._fermer(s, t, o + so + gs, "stop_gap", so + gs)
            elif h + sb >= pos.stop:
                self._fermer(s, t, pos.stop + gs, "stop", sb + gs)
            elif pos.objectif is not None and l + sb <= pos.objectif:
                self._fermer(s, t, pos.objectif, "objectif", sb)

    # ---- journée
    def _changer_jour(self, nouveau: int):
        if self.jour is not None:
            if self.code == "S4":
                for s in list(self.positions):
                    i = self.mk_i[s]
                    self._sortie_marche(s, i, self.series[s].t[i], "fin_journee", a_l_ouverture=False)
                self.oco.clear()
            self._enregistrer_jour()
            wd = (self.jour + 3) % 7      # 1970-01-01 était un jeudi (weekday 3)
            for s, pos in self.positions.items():
                if self.jour_derniere[s] != self.jour:
                    continue
                ser = self.series[s]
                i = self.mk_i[s]
                montant = ser.couts.swap_par_lot(pos.sens, self.mk_bid[s], pos.prix_entree) * pos.lots \
                    * ser.couts.multiplicateur_nuit(wd) * ser.taux_swap[i]
                if montant == montant:
                    self.balance += montant
                    pos.swaps += montant
        self.jour = nouveau
        self.pire_jour = math.inf
        # Référence de la perte du jour : equity à minuit (interprétation signalée : pour des positions
        # de plusieurs jours, une perte latente d'avant minuit n'est pas une perte du jour).
        self.garde.nouvelle_journee(nouveau, self.equity())

    def _enregistrer_jour(self):
        if self.jour is None or (self.jour + 1) * NS_JOUR <= self.debut_ns:
            return
        e = self.equity()
        self.lignes_equity.append((self.jour, e, min(self.pire_jour, e), self.balance))

    # ---- S2
    def _reequilibrer_s2(self, t, membres):
        groupe = [(s, i) for s, i in membres if self.series[s].sig["reequilibrer"][i]]
        if not groupe:
            return
        self.nb_reequilibrages += 1
        p: st.ParamS2 = self.p
        n_dispo = 0
        for s, ser in enumerate(self.series):
            k = self.mk_i[s]
            if k >= 0 and ser.sig["pret"][k]:
                n_dispo += 1
        E = self.equity()
        self.garde.mettre_a_jour(t, E)
        cibles = {}
        noms_groupe = set()
        notion_g = risque_g = 0.0
        for s, i in groupe:
            ser = self.series[s]
            noms_groupe.add(s)
            sg = ser.sig
            tx = ser.taux[i]
            if not sg["pret"][i] or sg["signe"][i] == 0 or not (tx == tx) or n_dispo == 0 or E <= 0:
                cibles[s] = (0, 0.0, 0.0, 0.0, i)
                continue
            notion_lot = ser.o[i] * ser.couts.contrat * tx
            risque_lot = (p.stop_atr * sg["atr"][i] + ser.couts.glissement_stop) * ser.couts.contrat * tx \
                + ser.couts.commission_par_lot
            brut = p.vol_cible / math.sqrt(n_dispo) * E / (notion_lot * sg["vol"][i])
            cibles[s] = (int(sg["signe"][i]), brut, notion_lot, risque_lot, i)
            notion_g += brut * notion_lot
            risque_g += brut * risque_lot
        notion_a = sum(pos.lots * self.series[s].couts.contrat * self.mk_bid[s] * self.mk_taux[s]
                       for s, pos in self.positions.items() if s not in noms_groupe)
        risque_a = sum(pos.risque_usd for s, pos in self.positions.items() if s not in noms_groupe)
        k = 1.0
        if notion_g > 0 and notion_a + notion_g > p.levier_max * E:
            k = min(k, max(0.0, p.levier_max * E - notion_a) / notion_g)
            self._evt(t, None, "reduction", "plafond_levier", f"facteur {k:.3f}")
        if APPLIQUER_PLAFOND_RISQUE_S2 and risque_g > 0 and risque_a + risque_g > PLAFOND_RISQUE_OUVERT_PCT / 100 * E:
            k2 = max(0.0, PLAFOND_RISQUE_OUVERT_PCT / 100 * E - risque_a) / risque_g
            if k2 < k:
                k = k2
            self._evt(t, None, "reduction", "plafond_risque_ouvert", f"facteur {k:.3f}")
        final = {}
        for s, (sens, brut, notion_lot, risque_lot, i) in cibles.items():
            ser = self.series[s]
            lots = plancher_lots(min(brut * k, ser.vmax), ser.vpas) if sens != 0 else 0.0
            if sens != 0:
                ok = lots >= ser.vmin - TOL
                self._tentative(t, s, risque_lot, notion_lot, ok, "ok" if ok else "lot_inferieur_minimum")
                if not ok:
                    lots = 0.0
            final[s] = (sens, lots, risque_lot, i)
        # 1) sorties et réductions
        for s in sorted(final, key=lambda x: self.series[x].nom):
            sens, lots, risque_lot, i = final[s]
            pos = self.positions.get(s)
            if pos is None:
                continue
            if lots <= 0 or pos.sens != sens:
                self._sortie_marche(s, i, t, "retournement" if lots > 0 else "reequilibrage_sortie")
            elif lots < pos.lots and (pos.lots - lots) > p.seuil_reequilibrage * pos.lots + TOL:
                self._sortie_marche(s, i, t, "reduction", lots=pos.lots - lots)
        # 2) ouvertures et augmentations
        for s in sorted(final, key=lambda x: self.series[x].nom):
            sens, lots, risque_lot, i = final[s]
            if lots <= 0:
                continue
            ser = self.series[s]
            pos = self.positions.get(s)
            augmenter = pos is not None and pos.sens == sens and lots > pos.lots \
                and (lots - pos.lots) > p.seuil_reequilibrage * pos.lots + TOL
            if pos is not None and not augmenter:
                continue
            if self.garde.bloque_jour:
                self._evt(t, s, "refus", "perte_jour_max", "rééquilibrage S2")
                continue
            g = ser.couts.glissement_marche
            if sens > 0:
                prix, cout = ser.o[i] + ser.spr_o[i] + g, ser.spr_o[i] + g
            else:
                prix, cout = ser.o[i] - g, g
            if pos is None:
                atr = ser.sig["atr"][i]
                stop = prix - sens * p.stop_atr * atr
                perte_lot = (abs(prix - stop) + ser.couts.glissement_stop) * ser.couts.contrat * ser.taux[i] \
                    + ser.couts.commission_par_lot
                self._executer_entree(s, i, t, sens, lots, prix, stop, None, cout, E, perte_lot)
            else:
                dl = plancher_lots(lots - pos.lots + 1e-12, ser.vpas)
                if dl < ser.vmin - TOL:
                    continue
                com = ser.couts.commission_par_lot * dl
                self.balance -= com
                pos.commissions += com
                pos.prix_entree = (pos.prix_entree * pos.lots + prix * dl) / (pos.lots + dl)
                pos.lots = pos.lots + dl
                pos.couts_exec += cout * dl * ser.couts.contrat * self.mk_taux[s]
                pos.risque_usd = pos.lots * ((abs(pos.prix_entree - pos.stop) + ser.couts.glissement_stop)
                                             * ser.couts.contrat * self.mk_taux[s] + ser.couts.commission_par_lot)
                pos.ajustements += 1

    # ---- C1
    def _decider_c1(self, s, i, pos, sg):
        """Décision à la clôture de la bougie i (exécution à l'ouverture suivante, voir l'en-tête)."""
        p: st.ParamC1 = self.p
        if pos is not None:
            if p.toujours_long:
                if sg["entree"][i]:
                    self.attente[s] = [("sortie", "renouvellement_mensuel"), ("entree", 1, sg["atr"][i])]
                    self.jour_prevu[s] = int(sg["jour_prevu"][i])
            elif sg["mois"][i] > sg["mois"][pos.barre_entree] and sg["rang_mois"][i] >= p.jour_sortie - 1:
                self.attente[s] = [("sortie", "fin_tournant")]
            return
        if not sg["pret"][i]:
            return
        if sg["entree"][i]:
            self.attente[s] = [("entree", 1, sg["atr"][i])]
            self.jour_prevu[s] = int(sg["jour_prevu"][i])
        elif p.toujours_long:
            self.attente[s] = [("entree", 1, sg["atr"][i])]

    # ---- S4
    def _placer_s4(self, s, i, t):
        ser = self.series[s]
        sg = ser.sig
        H, L = sg["haut"][i], sg["bas"][i]
        gs = ser.couts.glissement_stop
        tx = ser.taux[i]
        perte_lot = (H - L + 2 * gs) * ser.couts.contrat * tx + ser.couts.commission_par_lot
        notion_lot = H * ser.couts.contrat * tx
        if s in self.positions or s in self.oco:
            return
        lots, raison, E = self._dimensionner(s, i, t, perte_lot, notion_lot)
        self._tentative(t, s, perte_lot, notion_lot, lots > 0, raison if lots <= 0 else "ok")
        if lots <= 0:
            return
        if raison != "ok":
            self._compter(f"taille_reduite:{raison}")
        r = self.p.objectif_r
        self.oco[s] = {"haut": H, "bas": L, "lots": lots, "risque_usd": lots * perte_lot, "perte_lot": perte_lot,
                       "t_limite": int(sg["t_limite"][i]), "t_sortie": int(sg["t_sortie"][i]), "equity": E,
                       "obj_long": (H + r * (H - L)) if r else None, "obj_court": (L - r * (H - L)) if r else None}

    def _intrabarre_s4(self, s, i, t) -> bool:
        """Traite l'OCO du symbole ; True si une position a été ouverte (et éventuellement fermée) ici."""
        o_ = self.oco.get(s)
        if o_ is None:
            return False
        if t > o_["t_limite"]:
            del self.oco[s]
            self._evt(t, s, "annulation", "echeance")
            return False
        if self.garde.bloque_jour:
            del self.oco[s]
            self._evt(t, s, "annulation", "perte_jour_max")
            return False
        ser = self.series[s]
        o, h, l = ser.o[i], ser.h[i], ser.l[i]
        so, sb = ser.spr_o[i], ser.spr_b[i]
        gs = ser.couts.glissement_stop
        H, L = o_["haut"], o_["bas"]
        gap_l, gap_c = o + so >= H, o <= L
        tl = gap_l or (h + sb >= H)
        tc = gap_c or (l <= L)
        if not (tl or tc):
            return False
        del self.oco[s]
        args = dict(equity=o_["equity"], perte_lot=o_["perte_lot"], t_sortie=o_["t_sortie"])
        if tl and (not tc or not gap_c or gap_l):
            prix = max(H, o + so) + gs
            self._executer_entree(s, i, t, 1, o_["lots"], prix, L, o_["obj_long"], (so if gap_l else sb) + gs,
                                  **args)
            if tc:
                self._fermer(s, t, L - gs, "stop_meme_bougie", gs)
        else:
            prix = min(L, o) - gs
            self._executer_entree(s, i, t, -1, o_["lots"], prix, H, o_["obj_court"], gs, **args)
            if tl:
                self._fermer(s, t, H + gs, "stop_meme_bougie", sb + gs)
        return True

    # ---- boucle principale
    def executer(self):
        ser = self.series
        if not ser:
            return
        tt = np.concatenate([np.asarray(x.t, dtype=np.int64) for x in ser])
        ss = np.concatenate([np.full(len(x.t), k, dtype=np.int64) for k, x in enumerate(ser)])
        ii = np.concatenate([np.arange(len(x.t), dtype=np.int64) for x in ser])
        ordre = np.lexsort((ss, tt))
        tt, ss, ii = tt[ordre], ss[ordre], ii[ordre]
        coupures = np.flatnonzero(np.diff(tt)) + 1
        debuts = np.concatenate([[0], coupures]).tolist()
        fins = np.concatenate([coupures, [len(tt)]]).tolist()
        tt_l, ss_l, ii_l = tt.tolist(), ss.tolist(), ii.tolist()
        code = self.code
        k_stop = getattr(self.p, "stop_atr", None)
        for a, b in zip(debuts, fins):
            t = tt_l[a]
            membres = list(zip(ss_l[a:b], ii_l[a:b]))
            j = t // NS_JOUR
            if j != self.jour:
                self._changer_jour(j)
            actif = t >= self.debut_ns
            # 1. ouverture
            for s, i in membres:
                self._marquer(s, i, ser[s].o[i], ser[s].spr_o[i])
            if code == "C1":
                for s, i in membres:
                    jp = self.jour_prevu.pop(s, None)
                    if jp is not None and s in self.attente and ser[s].jour[i] != jp:
                        del self.attente[s]
                        if actif:
                            self._evt(t, s, "annulation", "jour_entree_absent", str(pd.Timestamp(jp * NS_JOUR).date()))
            if actif:
                if code == "S4":
                    for s, i in membres:
                        pos = self.positions.get(s)
                        if pos is not None and t >= pos.t_sortie:
                            self._sortie_marche(s, i, t, "cloture_forcee")
                for s, i in membres:
                    for ordre_ in self.attente.get(s, ()):
                        if ordre_[0] == "sortie" and s in self.positions:
                            self._sortie_marche(s, i, t, ordre_[1])
                if code in ("S2", "C2"):
                    self._reequilibrer_s2(t, membres)
                for s, i in membres:
                    for ordre_ in self.attente.get(s, ()):
                        if ordre_[0] == "entree" and s not in self.positions:
                            self._entree_marche(s, i, t, ordre_[1], ordre_[2], k_stop)
            for s, _ in membres:          # un ordre en attente ne vit que jusqu'à l'ouverture suivante
                self.attente.pop(s, None)
            # 2. intrabarre
            for s, i in membres:
                rempli = code == "S4" and actif and self._intrabarre_s4(s, i, t)
                pos = self.positions.get(s)
                if pos is not None and not rempli:
                    self._verifier_sorties(s, i, t, pos, depuis_ouverture=pos.entree_ns != t)
            # 3. clôture
            pire = self.balance
            dans_groupe = set()
            for s, i in membres:
                dans_groupe.add(s)
                self._marquer(s, i, ser[s].c[i], ser[s].spr_b[i])
                self.jour_derniere[s] = j
                pos = self.positions.get(s)
                if pos is not None:
                    pos.barres += 1
            for s, pos in self.positions.items():
                i = self.mk_i[s]
                x = ser[s]
                if s in dans_groupe:
                    bid, spr = (x.l[i], x.spr_b[i]) if pos.sens > 0 else (x.h[i], x.spr_b[i])
                else:
                    bid, spr = self.mk_bid[s], self.mk_spr[s]
                pire += self._latent(s, pos, bid, spr)
            eq = self.equity()
            if actif:
                self.garde.mettre_a_jour(t, pire)
                self.garde.mettre_a_jour(t, eq)
                self.pire_jour = min(self.pire_jour, pire, eq)
            # décisions de clôture
            for s, i in membres:
                x = ser[s]
                sg = x.sig
                pos = self.positions.get(s)
                if code == "S1":
                    if not sg["pret"][i]:
                        continue
                    if pos is not None:
                        if pos.sens > 0 and sg["sortie_long"][i]:
                            o_ = [("sortie", "signal_sortie")]
                            if sg["entree_court"][i]:
                                o_.append(("entree", -1, sg["atr"][i]))
                            self.attente[s] = o_
                        elif pos.sens < 0 and sg["sortie_court"][i]:
                            o_ = [("sortie", "signal_sortie")]
                            if sg["entree_long"][i]:
                                o_.append(("entree", 1, sg["atr"][i]))
                            self.attente[s] = o_
                    elif sg["entree_long"][i]:
                        self.attente[s] = [("entree", 1, sg["atr"][i])]
                    elif sg["entree_court"][i]:
                        self.attente[s] = [("entree", -1, sg["atr"][i])]
                elif code == "S3":
                    if pos is not None:
                        if sg["sortie_sma"][i]:
                            self.attente[s] = [("sortie", "signal_sma")]
                        elif pos.barres >= self.p.barres_max:
                            self.attente[s] = [("sortie", "duree_max")]
                    elif sg["entree_long"][i]:
                        self.attente[s] = [("entree", 1, sg["atr"][i])]
                elif code == "S4":
                    if actif and sg["placer"][i]:
                        self._placer_s4(s, i, t)
                elif code == "C1":
                    self._decider_c1(s, i, pos, sg)
            if code == "S4" and self.garde.bloque_jour and self.oco:
                for s in list(self.oco):
                    del self.oco[s]
                    self._evt(t, s, "annulation", "perte_jour_max")
        # fin de période
        for s in list(self.positions):
            i = self.mk_i[s]
            self._sortie_marche(s, i, ser[s].t[i], "fin_periode", a_l_ouverture=False)
        self._enregistrer_jour()

    def resultat(self, exclus, debut_eval, ignores) -> ResultatSimulation:
        eq = pd.DataFrame(self.lignes_equity, columns=["jour", "equity", "equity_pire", "balance"])
        eq.index = pd.to_datetime(eq.pop("jour").to_numpy() * NS_JOUR)
        eq.index.name = "date"
        if debut_eval is not None and len(eq):
            eq = eq[eq.index >= debut_eval.normalize()]
        tr = pd.DataFrame(self.trades, columns=COLONNES_TRADES)
        ev = pd.DataFrame(self.evenements, columns=COLONNES_EVENEMENTS)
        if len(ev):
            ev["instant"] = pd.to_datetime(ev["instant"])
        te = pd.DataFrame(self.tentatives, columns=COLONNES_TENTATIVES)
        if len(te):
            te["instant"] = pd.to_datetime(te["instant"])
        date_arret = None
        for d in self.garde.historique:
            if d.type == DECL_DRAWDOWN_MAX:
                date_arret = pd.Timestamp(d.instant)
                break
        compteurs = dict(self.compteurs)
        for r, n in ignores.items():
            compteurs[f"jour_ignore:{r}"] = n
        return ResultatSimulation(self.strat.code, self.strat.variante, self.capital, eq, tr, ev, te, compteurs,
                                  exclus, {x.nom: x.classe for x in self.series}, debut_eval, date_arret,
                                  self.nb_reequilibrages)


def simuler(univers: Univers, strategie: st.Strategie, capital: float = CAPITAL_INITIAL,
            params_couts: ParametresCouts = ParametresCouts(), facteur_contrat: float = 1.0,
            debut: Optional[pd.Timestamp] = None, fin: Optional[pd.Timestamp] = None,
            journal_complet: bool = True) -> ResultatSimulation:
    """Simule une stratégie sur l'univers (données déjà verrouillées par `donnees`).

    `debut` : aucun ordre n'est exécuté avant (les indicateurs utilisent l'historique antérieur) ;
    `fin` : bougies d'ouverture <= fin seulement. L'equity est enregistrée à partir du premier jour
    où la stratégie peut décider (`debut_eval`), et au plus tôt à `debut`.
    """
    series, exclus, ignores = preparer_series(univers, strategie, params_couts, facteur_contrat, fin)
    debut_ns = pd.Timestamp(debut).value if debut is not None else None
    premiers = [x.premier_pret for x in series if x.premier_pret is not None]
    debut_eval = pd.Timestamp(min(premiers)) if premiers else None
    if debut is not None:
        debut_eval = max(debut_eval, pd.Timestamp(debut)) if debut_eval is not None else pd.Timestamp(debut)
    m = _Moteur(series, strategie, capital, debut_ns, journal_complet)
    m.executer()
    return m.resultat(exclus, debut_eval, ignores)


def combiner(resultats: list, nom: str) -> ResultatSimulation:
    """Portefeuille combiné (ex. S1 + S2 à parts égales de risque) : chaque stratégie est simulée sur
    sa part du capital et les equity sont additionnées jour par jour (dernière valeur connue reportée ;
    avant son premier jour, une part vaut son capital initial)."""
    dates = resultats[0].equity.index
    for r in resultats[1:]:
        dates = dates.union(r.equity.index)
    eq = None
    for r in resultats:
        e = r.equity.reindex(dates).ffill().fillna(r.capital_initial)
        eq = e if eq is None else eq + e
    compteurs: Dict[str, int] = {}
    for r in resultats:
        for k, v in r.compteurs.items():
            compteurs[k] = compteurs.get(k, 0) + v
    debuts = [r.debut_eval for r in resultats if r.debut_eval is not None]
    arrets = [r.date_arret for r in resultats if r.date_arret is not None]
    return ResultatSimulation(
        nom, "base", sum(r.capital_initial for r in resultats), eq,
        pd.concat([r.trades for r in resultats], ignore_index=True),
        pd.concat([r.evenements for r in resultats], ignore_index=True),
        pd.concat([r.tentatives for r in resultats], ignore_index=True), compteurs,
        {k: v for r in resultats for k, v in r.exclus.items()},
        {k: v for r in resultats for k, v in r.symboles.items()},
        min(debuts) if debuts else None, min(arrets) if arrets else None,
        sum(r.nb_reequilibrages for r in resultats))


COMPOSANTES_P = ("C1", "C2", "S3")


def combiner_rendements(resultats: list, nom: str, capital: float) -> ResultatSimulation:
    """Combinaison P du cycle 2 : rendement journalier = MOYENNE des rendements journaliers des composantes.

    Méthode (la plus fidèle au plan « un tiers du capital chacune, jugée sur la somme des rendements
    journaliers ») : chaque composante est simulée SÉPARÉMENT sur un tiers du capital (taille des lots,
    lot minimum et plafonds réalistes pour ce tiers) ; le rendement de P un jour donné est la somme des
    rendements des composantes pondérés par 1/3, c'est-à-dire des poids constants (un compte unique où
    chaque composante dimensionne sur le tiers de l'equity TOTALE du moment). Un jour sans bougie pour une
    composante, ou avant son premier jour d'évaluation, son rendement vaut 0 (argent non investi).
    Pire prix : rendement « au pire prix » de chaque composante (equity au pire prix / equity de la veille),
    moyenné, comme si les pires instants étaient simultanés (prudent). L'arrêt -15 % est la première date
    d'arrêt de l'une des composantes (prudent)."""
    dates = resultats[0].equity.index
    for r in resultats[1:]:
        dates = dates.union(r.equity.index)
    k = len(resultats)
    somme = pd.Series(0.0, index=dates)
    somme_pire = pd.Series(0.0, index=dates)
    for r in resultats:
        e = r.equity["equity"].reindex(dates).ffill().fillna(r.capital_initial)
        veille = e.shift(1).fillna(r.capital_initial)
        pire = r.equity["equity_pire"].reindex(dates)
        pire = pire.where(pire.notna(), e)
        somme += e / veille - 1.0
        somme_pire += pire / veille - 1.0
    ret, ret_pire = somme / k, somme_pire / k
    eq = capital * (1.0 + ret).cumprod()
    veille = eq.shift(1).fillna(capital)
    eq_pire = np.minimum(veille * (1.0 + ret_pire), eq)
    df = pd.DataFrame({"equity": eq, "equity_pire": eq_pire, "balance": eq}, index=dates)
    df.index.name = "date"
    compteurs: Dict[str, int] = {}
    for r in resultats:
        for c, v in r.compteurs.items():
            compteurs[c] = compteurs.get(c, 0) + v
    debuts = [r.debut_eval for r in resultats if r.debut_eval is not None]
    arrets = [r.date_arret for r in resultats if r.date_arret is not None]
    def concat(frames, colonnes):
        pleins = [f for f in frames if len(f)]
        return pd.concat(pleins, ignore_index=True) if pleins else pd.DataFrame(columns=colonnes)
    return ResultatSimulation(
        nom, "base", float(capital), df,
        concat([r.trades for r in resultats], COLONNES_TRADES),
        concat([r.evenements for r in resultats], COLONNES_EVENEMENTS),
        concat([r.tentatives for r in resultats], COLONNES_TENTATIVES), compteurs,
        {f"{r.strategie}:{k_}": v for r in resultats for k_, v in r.exclus.items()},
        {k_: v for r in resultats for k_, v in r.symboles.items()},
        min(debuts) if debuts else None, min(arrets) if arrets else None,
        sum(r.nb_reequilibrages for r in resultats))


def strategies_p(remplacement: Optional[st.Strategie] = None, symboles=None) -> list:
    """Les trois composantes de P (C1, C2, S3 de base), l'une éventuellement remplacée par une variante
    (robustesse) ; `symboles` : restriction aux nouveaux marchés (plan cycle 2 §5)."""
    out = []
    for code in COMPOSANTES_P:
        s = remplacement if remplacement is not None and remplacement.code == code else st.strategie_base(code)
        if symboles is not None:
            s = st.restreindre(s, symboles)
        out.append(s)
    return out


def simuler_p(univers: Univers, capital: float = CAPITAL_INITIAL, remplacement: Optional[st.Strategie] = None,
              symboles=None, **kwargs) -> ResultatSimulation:
    """Combinaison P = C1 + C2 + S3, chacune simulée sur un tiers du capital (voir `combiner_rendements`)."""
    parts = [simuler(univers, s, capital / len(COMPOSANTES_P), **kwargs) for s in strategies_p(remplacement, symboles)]
    return combiner_rendements(parts, "P", capital)


def simuler_finaliste(univers: Univers, nom: str, capital: float = CAPITAL_INITIAL, **kwargs) -> ResultatSimulation:
    """`nom` = "S1".."S4" ou la combinaison prévue par le plan "S1+S2" (parts égales du capital) ;
    cycle 2 : "C1", "C2" ou la combinaison "P" (C1 + C2 + S3, un tiers chacune).

    Note : l'arrêt -15 % de la combinaison est la première date d'arrêt de l'une des parts (prudent)."""
    if nom == "P":
        return simuler_p(univers, capital, **kwargs)
    if nom == "S1+S2":
        parts = [simuler(univers, st.strategie_base(c), capital / 2, **kwargs) for c in ("S1", "S2")]
        return combiner(parts, nom)
    return simuler(univers, st.strategie_base(nom), capital, **kwargs)
