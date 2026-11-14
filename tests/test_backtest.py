"""Tests de sentitrade/backtest.py (spec §5 et §8 « Backtest »).

Scénarios à réponse connue construits à la main en M1 : les montants attendus
sont calculés à la main dans les commentaires (XAUUSD : 1 lot = 100 onces,
point 0.01, glissement d'entrée 0.05 $, glissement de stop 0.10 $).

Pour isoler l'exécution, les signaux sont fournis directement (tableau au
format de `preparer_signaux`) : un FVG valide est placé à une clôture M15
choisie. Les tests sur données synthétiques passent, eux, par toute la chaîne.
"""
from __future__ import annotations

import dataclasses
import unittest

import numpy as np
import pandas as pd

from sentitrade.backtest import (choisir_resolution, executer_backtest, preparer_marche, simuler_trade)
from sentitrade.config import Config, SymboleSpec
from sentitrade.data import reechantillonner
from sentitrade.sessions import est_heure_entree
from sentitrade.strategy import COLONNES_SIGNAUX
from sentitrade.synthetique import generer_jeu

T = pd.Timestamp
CFG = Config()
SPEC = SymboleSpec()
LUNDI = "2025-01-06"
MARDI = "2025-01-07"


# --------------------------------------------------------------------------- outils

def bougies_m1(jour, fond, speciales, debut="09:00", fin="22:10", spread=20, absentes=()):
    """Bougies M1 de `debut` à `fin` (exclue) le jour donné.

    fond : liste de (heure "HH:MM" de début, prix) — prix plat (o=h=l=c) à partir de cette heure ;
    speciales : {"HH:MM": (o, h, l, c[, spread])} ; absentes : heures "HH:MM" supprimées.
    """
    idx = pd.date_range(f"{jour} {debut}", f"{jour} {fin}", freq="1min", inclusive="left", name="time")
    prix = np.full(len(idx), np.nan)
    for heure, p in fond:
        prix[idx >= T(f"{jour} {heure}")] = p
    o, h, l, c = prix.copy(), prix.copy(), prix.copy(), prix.copy()
    sp = np.full(len(idx), spread, dtype=np.int64)
    for heure, val in speciales.items():
        k = idx.get_loc(T(f"{jour} {heure}"))
        o[k], h[k], l[k], c[k] = val[:4]
        if len(val) > 4:
            sp[k] = val[4]
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "tick_volume": np.ones(len(idx), dtype=np.int64),
                       "spread": sp, "real_volume": np.zeros(len(idx), dtype=np.int64)}, index=idx)
    garder = ~idx.isin([T(f"{jour} {a}") for a in absentes])
    return df[garder]


def signaux_manuels(jours, fvgs, tendance=1, tendances=None):
    """Tableau de signaux : clôtures M15 de 08:15 à 22:00 ; fvgs = {"AAAA-MM-JJ HH:MM": (sens, entree, sl, tp1)}.

    tendances : {"AAAA-MM-JJ HH:MM": valeur} pour changer la tendance à partir d'une clôture.
    """
    idx = pd.DatetimeIndex(np.concatenate([
        pd.date_range(f"{j} 08:15", f"{j} 22:00", freq="15min").values for j in jours]), name="cloture")
    tend = np.full(len(idx), tendance, dtype=np.int64)
    for quand, v in (tendances or {}).items():
        tend[idx >= T(quand)] = v
    df = pd.DataFrame({
        "tendance": tend, "adr_ok": True, "heure_entree_ok": est_heure_entree(idx, CFG),
        "sens": np.zeros(len(idx), dtype=np.int64), "entree": np.nan, "sl": np.nan, "tp1": np.nan,
        "distance_sl": np.nan, "rejet": ""}, index=idx)
    df["rejet"] = df["rejet"].astype(object)
    for quand, (sens, entree, sl, tp1) in fvgs.items():
        k = idx.get_loc(T(quand))
        df.iloc[k, df.columns.get_loc("sens")] = sens
        for col, v in (("entree", entree), ("sl", sl), ("tp1", tp1), ("distance_sl", abs(entree - sl))):
            df.iloc[k, df.columns.get_loc(col)] = v
    return df[COLONNES_SIGNAUX]


def lancer(m1, sig, cfg=CFG, balance=3000.0, **kw):
    return executer_backtest(m1, None, None, cfg, SPEC, balance, resolution="m1", signaux=sig,
                             garde_complete=kw.pop("garde_complete", True), **kw)


LONG = {f"{LUNDI} 10:00": (1, 3500.00, 3497.00, 3503.00)}
SHORT = {f"{LUNDI} 10:00": (-1, 3500.00, 3503.00, 3497.00)}
# Toucher du long à 10:05 : low 3499.70 + spread 0.20 = 3499.90 <= 3500 ; open Ask 3501.20 > 3500
# => prix d'entrée = 3500.00 + 0.05 = 3500.05 ; distance réelle 3.05 ; perte par lot (3.05 + 0.10 glissement stop) × 100 = 315 $.
# Taille (3000 $) : risque 30 / 315 = 0.095 lot ; levier 10 × 3000 / 350005 = 0.0857 lot => 0.08 lot (plafond levier).
# Découpage à TP1 : 0.04 / 0.04.
TOUCHER_LONG = {"10:05": (3501.00, 3501.00, 3499.70, 3500.50)}
RISQUE_LONG = 0.08 * 315.0          # 25.20 $


class TestScenariosLong(unittest.TestCase):

    def test_gain_tp1_puis_breakeven(self):
        # TP1 à 10:20 (high 3503.10 >= 3503) : 0.04 lot fermé à 3503 - 0.05 = 3502.95 => +2.90 × 4 = +11.60 $.
        # SL du reste au prix d'entrée 3500.05 ; touché à 10:40 (low 3499.90) : sortie min(3500.05, open 3502) - 0.10
        # = 3499.95 => -0.10 × 4 = -0.40 $. Total +11.20 $ ; R = 11.20 / 25.20.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:21", 3502.80), ("10:41", 3500.00)],
                        {**TOUCHER_LONG, "10:20": (3500.50, 3503.10, 3500.40, 3502.80),
                         "10:40": (3502.00, 3502.00, 3499.90, 3500.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual(t["entree_a"], T(f"{LUNDI} 10:05"))
        self.assertAlmostEqual(t["prix_entree"], 3500.05, places=9)
        self.assertAlmostEqual(t["lots"], 0.08)
        self.assertAlmostEqual(t["lots_tp1"], 0.04)
        self.assertTrue(t["tp1_atteint"])
        self.assertEqual(t["raison_sortie"], "stop_breakeven")
        self.assertAlmostEqual(t["pnl"], 11.20, places=6)
        self.assertAlmostEqual(t["risque_montant"], RISQUE_LONG, places=9)
        self.assertAlmostEqual(t["r_multiple"], 11.20 / 25.20, places=9)
        self.assertEqual(t["sortie_a"], T(f"{LUNDI} 10:40"))
        self.assertAlmostEqual(r.balance_finale, 3011.20, places=6)
        self.assertAlmostEqual(r.equity.iloc[-1], 3011.20, places=6)
        # Equity latente à la clôture de 10:30 : 3000 + 11.60 + (3502.80 - 3500.05) × 4 = 3022.60.
        self.assertAlmostEqual(r.equity.loc[T(f"{LUNDI} 10:30")], 3022.60, places=6)

    def test_perte_au_stop_avec_glissement(self):
        # Stop à 10:30 (low 3496.50 <= 3497) : sortie min(3497, open 3499) - 0.10 = 3496.90
        # => (3496.90 - 3500.05) × 0.08 × 100 = -25.20 $ ; R = -25.20 / 25.20 = -1 exactement (glissement inclus dans le risque).
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:31", 3496.80)],
                        {**TOUCHER_LONG, "10:30": (3499.00, 3499.00, 3496.50, 3496.80)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertAlmostEqual(t["pnl"], -25.20, places=6)
        self.assertAlmostEqual(t["r_multiple"], -1.0, places=9)
        self.assertFalse(t["tp1_atteint"])

    def test_cloture_forcee_2155(self):
        # Ni stop ni TP1 : sortie à l'open Bid de 21:55 (3501.50) - 0.05 = 3501.45 => +1.40 × 8 = +11.20 $.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("21:55", 3501.50)], TOUCHER_LONG)
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "cloture_forcee")
        self.assertEqual(t["sortie_a"], T(f"{LUNDI} 21:55"))
        self.assertAlmostEqual(t["pnl"], 11.20, places=6)
        self.assertAlmostEqual(t["duree_min"], (T(f"{LUNDI} 21:55") - T(f"{LUNDI} 10:05")).total_seconds() / 60)

    def test_stop_et_tp1_dans_la_meme_bougie_stop_dabord(self):
        # 10:30 : high 3503.50 >= TP1 et low 3496 <= SL => stop d'abord : 3496.90, -25.20 $.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:31", 3500.00)],
                        {**TOUCHER_LONG, "10:30": (3500.50, 3503.50, 3496.00, 3500.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertFalse(t["tp1_atteint"])
        self.assertAlmostEqual(t["pnl"], -25.20, places=6)

    def test_pas_de_tp1_sur_la_bougie_de_remplissage(self):
        # 10:05 : toucher puis high 3503.20 >= TP1 dans la même bougie : TP1 ignoré ; ensuite clôture forcée.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3501.00)],
                        {"10:05": (3501.00, 3503.20, 3499.70, 3501.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertFalse(t["tp1_atteint"])
        self.assertEqual(t["raison_sortie"], "cloture_forcee")

    def test_stop_verifie_sur_la_bougie_de_remplissage(self):
        # 10:05 : toucher (entrée 3500.05) et low 3496.80 <= SL dans la même bougie => stop à 3496.90.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3497.00)],
                        {"10:05": (3501.00, 3501.00, 3496.80, 3497.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertEqual(t["sortie_a"], T(f"{LUNDI} 10:05"))
        self.assertAlmostEqual(t["pnl"], -25.20, places=6)

    def test_gap_a_travers_le_stop_sortie_a_lopen(self):
        # 10:30 ouvre à 3495.00 sous le SL 3497 : sortie à l'open - 0.10 = 3494.90 => -5.15 × 8 = -41.20 $.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:31", 3495.00)],
                        {**TOUCHER_LONG, "10:30": (3495.00, 3495.50, 3494.00, 3495.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertAlmostEqual(t["pnl"], -41.20, places=6)
        self.assertAlmostEqual(t["r_multiple"], -41.20 / 25.20, places=9)

    def test_entree_a_lopen_si_le_prix_saute_sous_le_niveau(self):
        # 10:05 ouvre à 3499.00 (Ask 3499.20 < 3500) : entrée = 3499.20 + 0.05 = 3499.25 ; distance 2.25.
        # Taille : risque 30/235 = 0.128 ; levier 30000/349925 = 0.0857 => 0.08. Clôture 21:55 à 3499.00 - 0.05.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:05", 3499.00)], {})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        t = r.trades.iloc[0]
        self.assertAlmostEqual(t["prix_entree"], 3499.25, places=9)
        self.assertAlmostEqual(t["distance_sl_reelle"], 2.25, places=9)
        self.assertAlmostEqual(t["pnl"], (3498.95 - 3499.25) * 8, places=6)

    def test_spread_trop_large_au_toucher_annule_le_setup(self):
        # CDC §3.4 : 10:05 low 3499.00 + spread 0.60 = 3499.60 <= 3500 (touché) mais 0.60 > spread_max 0.30
        # => entrée ANNULÉE. Le nouveau toucher de 10:07 (spread normal) ne donne donc aucun trade.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00)],
                        {"10:05": (3501.00, 3501.00, 3499.00, 3501.00, 60),
                         "10:07": (3500.80, 3500.80, 3499.70, 3500.20)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        self.assertEqual(len(r.trades), 0)
        ann = r.evenements[r.evenements["type"] == "annule"]
        self.assertEqual(list(ann["instant"]), [T(f"{LUNDI} 10:05")])
        self.assertEqual(list(ann["raison"]), ["spread_trop_large"])
        self.assertEqual(r.stats["nb_attente_spread"], 1)

    def test_commission(self):
        # Commission 7 $/lot : perte par lot 315 + 7 = 322 ; taille 0.08 (levier) ; risque 0.08 × 322 = 25.76 $.
        # Perte au stop : -25.20 - 7 × 0.08 = -25.76 $ ; R = -1 exactement.
        cfg = CFG.avec(commission_par_lot=7.0)
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:31", 3496.80)],
                        {**TOUCHER_LONG, "10:30": (3499.00, 3499.00, 3496.50, 3496.80)})
        t = lancer(m1, signaux_manuels([LUNDI], LONG), cfg).trades.iloc[0]
        self.assertAlmostEqual(t["perte_par_lot"], 322.0, places=9)
        self.assertAlmostEqual(t["pnl"], -25.76, places=6)
        self.assertAlmostEqual(t["commission"], 0.56, places=9)
        self.assertAlmostEqual(t["r_multiple"], -1.0, places=9)
        # Avec TP1 + breakeven : (11.60 - 0.28) + (-0.40 - 0.28) = 10.64 $ (commission au prorata de chaque sortie).
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:21", 3502.80), ("10:41", 3500.00)],
                        {**TOUCHER_LONG, "10:20": (3500.50, 3503.10, 3500.40, 3502.80),
                         "10:40": (3502.00, 3502.00, 3499.90, 3500.00)})
        t = lancer(m1, signaux_manuels([LUNDI], LONG), cfg).trades.iloc[0]
        self.assertAlmostEqual(t["pnl"], 10.64, places=6)
        self.assertAlmostEqual(t["r_multiple"], 10.64 / 25.76, places=9)


class TestScenarioShort(unittest.TestCase):

    def test_short_symetrique(self):
        # Short : niveau 3500, SL 3503, TP1 3497. Toucher à 10:05 (high Bid 3500.30 >= 3500) :
        # entrée = max(3500, open 3499) - 0.05 = 3499.95 ; distance 3503 - 3499.95 = 3.05 ; 0.08 lot.
        # TP1 à 10:20 (low 3496.70 + 0.20 = 3496.90 <= 3497) : 0.04 lot racheté à 3497.05 => +2.90 × 4 = +11.60 $.
        # Breakeven touché à 10:40 (high 3499.90 + 0.20 >= 3499.95) : rachat max(3499.95, 3498.20) + 0.10 = 3500.05
        # => -0.40 $. Total +11.20 $, R identique au long (11.20 / 25.20).
        m1 = bougies_m1(LUNDI, [("09:00", 3499.00), ("10:06", 3499.50), ("10:21", 3497.50), ("10:41", 3499.00)],
                        {"10:05": (3499.00, 3500.30, 3498.90, 3499.50),
                         "10:20": (3499.50, 3499.60, 3496.70, 3497.00),
                         "10:40": (3498.00, 3499.90, 3497.90, 3499.00)})
        r = lancer(m1, signaux_manuels([LUNDI], SHORT, tendance=-1))
        t = r.trades.iloc[0]
        self.assertEqual(t["sens"], -1)
        self.assertAlmostEqual(t["prix_entree"], 3499.95, places=9)
        self.assertAlmostEqual(t["lots"], 0.08)
        self.assertTrue(t["tp1_atteint"])
        self.assertEqual(t["raison_sortie"], "stop_breakeven")
        self.assertAlmostEqual(t["pnl"], 11.20, places=6)
        self.assertAlmostEqual(t["r_multiple"], 11.20 / 25.20, places=9)

    def test_short_stop_au_ask(self):
        # Stop short si high Bid + spread >= SL : 10:30 high 3502.85 + 0.20 = 3503.05 >= 3503
        # => rachat max(3503, open Ask 3500.20) + 0.10 = 3503.10 ; -3.15 × 8 = -25.20 $.
        m1 = bougies_m1(LUNDI, [("09:00", 3499.00), ("10:06", 3499.50)],
                        {"10:05": (3499.00, 3500.30, 3498.90, 3499.50),
                         "10:30": (3500.00, 3502.85, 3499.90, 3502.00)})
        t = lancer(m1, signaux_manuels([LUNDI], SHORT, tendance=-1)).trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "stop")
        self.assertAlmostEqual(t["pnl"], -25.20, places=6)


class TestGardeRisque(unittest.TestCase):

    def test_perte_journaliere_bloque_la_journee(self):
        # 100 000 $, risque 2 % : niveau 3500, SL 3490 => distance réelle 10.05, perte par lot (10.05 + 0.10) × 100 = 1015 $.
        # Trade 1 : 2000 / 1015 = 1.97 lot ; stop à 3489.90 => -10.15 × 197 = -1999.55 $ (balance 98 000.45).
        # Trade 2 : 1960.009 / 1015 = 1.93 lot ; -10.15 × 193 = -1958.95 $ (balance 96 041.50) : perte du jour
        # 3.96 % >= 3 % => plus d'entrée ce lundi. Le setup de 12:00, touché à 12:05, est annulé (perte_jour_max).
        # Mardi : nouvelle journée, l'entrée est permise : 1920.83 / 1015 = 1.89 lot.
        cfg = CFG.avec(risque_par_trade_pct=2.0)
        fvg = lambda j, h: {f"{j} {h}": (1, 3500.00, 3490.00, 3510.00)}
        sig = signaux_manuels([LUNDI, MARDI], {**fvg(LUNDI, "10:00"), **fvg(LUNDI, "11:00"),
                                               **fvg(LUNDI, "12:00"), **fvg(MARDI, "10:00")})
        stop = {"10:05": (3501.0, 3501.0, 3499.7, 3500.5), "10:30": (3495.0, 3495.0, 3489.5, 3492.0),
                "11:05": (3501.0, 3501.0, 3499.7, 3500.5), "11:30": (3495.0, 3495.0, 3489.5, 3492.0),
                "12:05": (3501.0, 3501.0, 3499.7, 3500.5)}
        lundi = bougies_m1(LUNDI, [("09:00", 3501.0), ("10:06", 3500.5), ("10:31", 3501.0), ("11:06", 3500.5),
                                   ("11:31", 3501.0), ("12:06", 3500.5)], stop)
        mardi = bougies_m1(MARDI, [("09:00", 3501.0), ("10:06", 3500.5)], {"10:05": stop["10:05"]})
        r = lancer(pd.concat([lundi, mardi]), sig, cfg, balance=100000.0)
        tr = r.trades
        self.assertEqual(len(tr), 3)
        self.assertEqual(list(tr["lots"]), [1.97, 1.93, 1.89])
        self.assertAlmostEqual(tr.iloc[0]["pnl"], -1999.55, places=4)
        self.assertAlmostEqual(tr.iloc[1]["pnl"], -1958.95, places=4)
        self.assertEqual(tr.iloc[2]["entree_a"], T(f"{MARDI} 10:05"))
        ann = r.evenements[(r.evenements["type"] == "annule")]
        self.assertEqual(list(ann["raison"]), ["perte_jour_max"])
        self.assertEqual(list(ann["instant"]), [T(f"{LUNDI} 12:05")])
        self.assertEqual(r.stats["jours_bloques_perte_jour"], 1)
        self.assertFalse(r.arret_definitif)

    def test_arret_definitif_ferme_a_lopen_suivant(self):
        # 100 000 $, risque 2 % : 2000 / 1015 = 1.97 lot, découpage 0.98 / 0.99. TP1 3510 à 10:20 : 0.98 × 9.90 × 100 = +970.20 $.
        # 10:30 : envolée, clôture 3720 => equity 100 970.20 + (3720 - 3500.05) × 99 = 122 745.25 (plus haut).
        # 10:31 : low 3530 => equity 103 935.25, soit -15.32 % depuis le plus haut => ARRÊT DÉFINITIF.
        # Fermeture du runner à l'open de 10:32 (3536.00) - 0.05 = 3535.95 => 35.90 × 99 = +3554.10 $. Total +4524.30 $.
        # Plus aucun trade ensuite, même le mardi.
        cfg = CFG.avec(risque_par_trade_pct=2.0)
        sig = signaux_manuels([LUNDI, MARDI], {f"{LUNDI} 10:00": (1, 3500.00, 3490.00, 3510.00),
                                               f"{MARDI} 10:00": (1, 3600.00, 3590.00, 3610.00)})
        lundi = bougies_m1(LUNDI, [("09:00", 3501.0), ("10:06", 3500.5), ("10:21", 3509.0), ("10:32", 3536.0)],
                           {"10:05": (3501.0, 3501.0, 3499.7, 3500.5), "10:20": (3500.5, 3510.2, 3500.4, 3509.0),
                            "10:30": (3510.0, 3720.0, 3509.0, 3720.0), "10:31": (3720.0, 3720.0, 3530.0, 3535.0)})
        mardi = bougies_m1(MARDI, [("09:00", 3601.0)], {"10:05": (3601.0, 3601.0, 3599.7, 3600.5)})
        r = lancer(pd.concat([lundi, mardi]), sig, cfg, balance=100000.0)
        self.assertTrue(r.arret_definitif)
        self.assertIn("drawdown_max", r.raison_arret)
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual(t["raison_sortie"], "arret_definitif")
        self.assertEqual(t["sortie_a"], T(f"{LUNDI} 10:32"))
        self.assertAlmostEqual(t["pnl"], 4524.30, places=4)
        self.assertAlmostEqual(r.balance_finale, 104524.30, places=4)
        self.assertAlmostEqual(r.equity.loc[T(f"{LUNDI} 10:30")], 122745.25, places=4)
        self.assertTrue((r.evenements["type"] == "arret_definitif").any())
        # Equity plate après l'arrêt.
        self.assertTrue(np.allclose(r.equity[r.equity.index > T(f"{LUNDI} 10:32")], 104524.30))

    def test_mode_evaluation_continue_et_date_le_franchissement(self):
        # Même scénario, arrêt définitif neutralisé : le runner vit jusqu'à 21:55, le trade
        # du mardi a lieu, et le franchissement de -15 % est daté à 10:31 : au PIRE prix de la bougie
        # (low 3530) l'equity vaut 103 935.25 contre un plus haut de 122 745.25, soit -15.32 % ; à la seule
        # clôture (3535) elle vaudrait 104 430.25 (-14.92 %) et le franchissement serait manqué.
        cfg = CFG.avec(risque_par_trade_pct=2.0)
        sig = signaux_manuels([LUNDI, MARDI], {f"{LUNDI} 10:00": (1, 3500.00, 3490.00, 3510.00),
                                               f"{MARDI} 10:00": (1, 3600.00, 3590.00, 3610.00)})
        lundi = bougies_m1(LUNDI, [("09:00", 3501.0), ("10:06", 3500.5), ("10:21", 3509.0), ("10:32", 3536.0)],
                           {"10:05": (3501.0, 3501.0, 3499.7, 3500.5), "10:20": (3500.5, 3510.2, 3500.4, 3509.0),
                            "10:30": (3510.0, 3720.0, 3509.0, 3720.0), "10:31": (3720.0, 3720.0, 3530.0, 3535.0)})
        mardi = bougies_m1(MARDI, [("09:00", 3601.0)], {"10:05": (3601.0, 3601.0, 3599.7, 3600.5)})
        r = lancer(pd.concat([lundi, mardi]), sig, cfg, balance=100000.0, arret_definitif_actif=False)
        self.assertFalse(r.arret_definitif)
        self.assertEqual(len(r.trades), 2)
        self.assertEqual(r.trades.iloc[0]["raison_sortie"], "cloture_forcee")
        self.assertEqual(r.stats["date_franchissement_dd"], str(T(f"{LUNDI} 10:31")))
        self.assertFalse(r.stats["arret_definitif_actif"])
        from sentitrade.reporting import resumer_resultat
        res = resumer_resultat(r)
        self.assertTrue(res["arret_definitif"] and res["mode_evaluation"])
        self.assertEqual(res["date_arret"], str(T(f"{LUNDI} 10:31")))

    def test_refus_de_taille_annule_le_setup(self):
        # 300 $ de capital : 1 % = 3 $ ; 3 / 305 = 0.0098 lot < 0.01 => refus, setup annulé, aucun trade.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50)], TOUCHER_LONG)
        r = lancer(m1, signaux_manuels([LUNDI], LONG), balance=300.0)
        self.assertEqual(len(r.trades), 0)
        ann = r.evenements[r.evenements["type"] == "annule"]
        self.assertEqual(list(ann["raison"]), ["refus_taille:lot_inferieur_minimum"])


class TestBougiesManquantes(unittest.TestCase):

    def test_setup_cree_pendant_un_trou_m1(self):
        # Aucune bougie M1 de 09:50 à 10:11 : la clôture M15 de 10:00 (création du setup) est quand même traitée.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:13", 3500.50)],
                        {"10:12": (3501.00, 3501.00, 3499.70, 3500.50)},
                        absentes=[f"{h}:{m:02d}" for h, rng in (("09", range(50, 60)), ("10", range(0, 12)))
                                  for m in rng])
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        self.assertEqual(len(r.trades), 1)
        self.assertEqual(r.trades.iloc[0]["entree_a"], T(f"{LUNDI} 10:12"))

    def test_annulation_pendant_un_trou_m1(self):
        # La tendance devient baissière à la clôture de 10:15 alors qu'aucune bougie M1 n'existe de 10:10 à 10:20 :
        # le setup doit être annulé (clôture traitée) et le toucher de 10:21 ne doit PAS ouvrir de position.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:22", 3500.50)],
                        {"10:21": (3501.00, 3501.00, 3499.70, 3500.50)},
                        absentes=[f"10:{m:02d}" for m in range(10, 21)])
        sig = signaux_manuels([LUNDI], LONG, tendances={f"{LUNDI} 10:15": -1})
        r = lancer(m1, sig)
        self.assertEqual(len(r.trades), 0)
        ann = r.evenements[r.evenements["type"] == "annule"]
        self.assertEqual(list(ann["raison"]), ["tendance"])
        self.assertEqual(list(ann["instant"]), [T(f"{LUNDI} 10:15")])

    def test_signal_utilisable_seulement_apres_la_cloture(self):
        # Un toucher à 09:59 (avant la clôture 10:00 qui crée le setup) ne doit pas ouvrir de position.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00)], {"09:59": (3501.00, 3501.00, 3499.70, 3501.00)})
        r = lancer(m1, signaux_manuels([LUNDI], LONG))
        self.assertEqual(len(r.trades), 0)


class TestResolution(unittest.TestCase):

    def test_choix_auto(self):
        m15 = pd.DataFrame({"open": 1.0}, index=pd.date_range("2024-01-01", "2024-12-31", freq="15min"))
        m1_complet = pd.DataFrame({"open": 1.0}, index=pd.date_range("2024-01-01", "2024-12-31", freq="1h"))
        m1_partiel = pd.DataFrame({"open": 1.0}, index=pd.date_range("2024-06-01", "2024-12-31", freq="1h"))
        self.assertEqual(choisir_resolution(m1_complet, m15), "m1")
        self.assertEqual(choisir_resolution(m1_partiel, m15), "m15")
        self.assertEqual(choisir_resolution(m1_partiel, m15, debut="2024-07-01"), "m1")
        self.assertEqual(choisir_resolution(None, m15), "m15")
        self.assertEqual(choisir_resolution(m1_partiel, m15, resolution="m1"), "m1")

    def test_execution_m15(self):
        # Même scénario TP1 + breakeven, agrégé en M15. Bougie 10:00 : toucher (pas de TP1 sur cette bougie) ;
        # bougie 10:15 : TP1 ; bougie 10:30 : rien (BE actif seulement après la bougie de TP1) ; 10:45 : BE touché.
        m1 = bougies_m1(LUNDI, [("09:00", 3501.00), ("10:06", 3500.50), ("10:21", 3502.80), ("10:46", 3500.00)],
                        {**TOUCHER_LONG, "10:20": (3500.50, 3503.10, 3500.40, 3502.80),
                         "10:45": (3502.00, 3502.00, 3499.90, 3500.00)})
        m15 = reechantillonner(m1, "15min")
        r = executer_backtest(None, m15, None, CFG, SPEC, 3000.0, resolution="m15",
                              signaux=signaux_manuels([LUNDI], LONG))
        self.assertEqual(r.resolution, "m15")
        t = r.trades.iloc[0]
        self.assertEqual(t["entree_a"], T(f"{LUNDI} 10:00"))
        self.assertAlmostEqual(t["prix_entree"], 3500.05, places=9)
        self.assertAlmostEqual(t["pnl"], 11.20, places=6)


# --------------------------------------------------------------------------- données synthétiques

class _Synthetique:
    jeu = None

    @classmethod
    def donnees(cls):
        if cls.jeu is None:
            cls.jeu = generer_jeu("2023-08-01", "2026-07-01", 3)
        return cls.jeu


class TestSynthetique(unittest.TestCase):

    def test_marche_aleatoire_sans_esperance_positive(self):
        # Au moins 300 trades sur marche aléatoire : t de Student de l'espérance en R < 2, sinon bug / anticipation.
        # Capital et limites élargis pour que la garde ne coupe pas l'échantillon (le R ne dépend pas du capital).
        m1, m15, h1 = _Synthetique.donnees()
        cfg = CFG.avec(risque_par_trade_pct=0.25, drawdown_max_pct=30.0)
        r = executer_backtest(m1, m15, h1, cfg, SPEC, 100000.0, debut="2024-01-02")
        self.assertEqual(r.resolution, "m1")
        self.assertFalse(r.arret_definitif)
        R = r.trades["r_multiple"].to_numpy()
        self.assertGreaterEqual(len(R), 300)
        t = R.mean() / (R.std(ddof=1) / np.sqrt(len(R)))
        self.assertLess(t, 2.0, f"espérance {R.mean():+.3f} R, t = {t:.2f} sur {len(R)} trades")
        # Garde-fou dans l'autre sens : les coûts ne doivent pas être absurdes.
        self.assertGreater(R.mean(), -0.5)
        # Cohérence comptable : balance finale = initiale + somme des P&L = dernière equity.
        self.assertAlmostEqual(r.balance_finale, 100000.0 + r.trades["pnl"].sum(), places=4)
        self.assertAlmostEqual(r.equity.iloc[-1], r.balance_finale, places=4)
        # Garantie de risque : perte au stop prévue <= budget.
        self.assertTrue((r.trades["risque_montant"] <= r.trades["budget_risque"] * (1 + 1e-9)).all())

    def test_absence_danticipation_troncature(self):
        # Tronquer toutes les données à l'instant t (seules les bougies CLÔTURÉES à t restent) ne change aucun
        # trade clôturé avant t.
        m1, m15, h1 = _Synthetique.donnees()
        debut = T("2024-01-02")
        fin_courte = T("2024-10-01")
        m1, m15, h1 = (x[x.index < fin_courte] for x in (m1, m15, h1))
        complet = executer_backtest(m1, m15, h1, CFG, SPEC, 3000.0, debut=debut, resolution="m1",
                                    garde_complete=False).trades
        for t in (T("2024-03-14 15:07"), T("2024-06-05 11:43"), T("2024-09-02 16:21")):
            tm1 = m1[m1.index < t]
            tm15 = m15[m15.index + pd.Timedelta(minutes=15) <= t]
            th1 = h1[h1.index + pd.Timedelta(hours=1) <= t]
            tronque = executer_backtest(tm1, tm15, th1, CFG, SPEC, 3000.0, debut=debut, resolution="m1").trades
            avant = lambda df: df[df["sortie_a"] + pd.Timedelta(minutes=1) <= t].reset_index(drop=True)
            a, b = avant(complet), avant(tronque)
            self.assertGreater(len(a), 0)
            pd.testing.assert_frame_equal(a, b, check_exact=True)

    def test_raccourci_de_garde_identique_au_chemin_complet(self):
        m1, m15, h1 = _Synthetique.donnees()
        rapide = executer_backtest(m1, m15, h1, CFG, SPEC, 3000.0, debut="2024-01-02", fin="2025-01-01")
        complet = executer_backtest(m1, m15, h1, CFG, SPEC, 3000.0, debut="2024-01-02", fin="2025-01-01",
                                    garde_complete=True)
        self.assertGreater(len(rapide.trades), 20)
        pd.testing.assert_frame_equal(rapide.trades, complet.trades, check_exact=True)
        np.testing.assert_array_equal(rapide.equity.to_numpy(), complet.equity.to_numpy())
        self.assertEqual(rapide.arret_definitif, complet.arret_definitif)


class TestSimulerTrade(unittest.TestCase):

    def test_sans_garde_et_lot_indivisible(self):
        # lots_tp1 = 0 : à TP1 rien n'est fermé, le SL de toute la position passe au breakeven.
        m1 = bougies_m1(LUNDI, [("09:00", 3500.50), ("10:21", 3502.80), ("10:41", 3500.00)],
                        {"10:20": (3500.50, 3503.10, 3500.40, 3502.80),
                         "10:40": (3502.00, 3502.00, 3499.90, 3500.00)})
        marche = preparer_marche(m1, CFG, SPEC)
        i = int(np.searchsorted(marche.temps, T(f"{LUNDI} 10:05").value))
        sim = simuler_trade(marche, i, 1, 3500.05, 3497.0, 3503.0, 0.01, 0.0, CFG, SPEC)
        self.assertEqual(len(sim.sorties), 1)
        j, prix, vol, raison = sim.sorties[0]
        self.assertEqual(raison, "stop_breakeven")
        self.assertAlmostEqual(prix, 3499.95, places=9)
        self.assertEqual(marche.index[sim.i_tp1], T(f"{LUNDI} 10:20"))


if __name__ == "__main__":
    unittest.main()
