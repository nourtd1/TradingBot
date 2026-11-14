"""Tests de sentitrade/strategy.py : tendance H1, FVG, point d'entrée unique, machine à setups.

Spec §3 et §8. Le test d'absence d'anticipation est la priorité : modifier ou
retirer des données postérieures à t ne doit changer aucune valeur <= t.
"""
from __future__ import annotations

import dataclasses
import time
import unittest

import numpy as np
import pandas as pd

from sentitrade.config import Config, SymboleSpec
from sentitrade.data import reechantillonner
from sentitrade.indicators import ema
from sentitrade.strategy import (COLONNES_FVG, COLONNES_SIGNAUX, Evenement, MoteurSignaux, Setup,
                                 detecter_fvg, preparer_signaux, tendance_a, tendance_h1)

T = pd.Timestamp
M15 = pd.Timedelta(minutes=15)
CFG = Config()
SPEC = SymboleSpec()  # point 0.01, stops_level 0


def bougies(lignes, debut="2024-01-02 10:00", pas="15min"):
    """lignes : (open, high, low, close, spread) ; ou (instant, open, high, low, close, spread)."""
    if lignes and isinstance(lignes[0][0], str):
        idx = pd.DatetimeIndex([l[0] for l in lignes], name="time")
        lignes = [l[1:] for l in lignes]
    else:
        idx = pd.date_range(debut, periods=len(lignes), freq=pas, name="time")
    a = np.asarray(lignes, dtype=float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3],
                         "tick_volume": np.ones(len(a), dtype=np.int64),
                         "spread": a[:, 4].astype(np.int64),
                         "real_volume": np.zeros(len(a), dtype=np.int64)}, index=idx)


# FVG haussier : low(c3) = 2002 > high(c1) = 2001, vide 1.00, spread(c3) = 20 points
LONG = [(2000.00, 2001.00, 1999.00, 2000.80, 15),
        (2000.80, 2003.50, 2000.50, 2003.20, 18),
        (2003.20, 2004.00, 2002.00, 2003.60, 20)]
# FVG baissier : high(c3) = 1998 < low(c1) = 1999, vide 1.00, spread(c3) = 25 points
SHORT = [(2000.00, 2001.00, 1999.00, 1999.20, 15),
         (1999.20, 1999.50, 1996.50, 1996.80, 18),
         (1996.80, 1998.00, 1995.50, 1996.00, 25)]


def marche_aleatoire(n, freq, debut="2024-01-01", graine=0, vol=1.0):
    rng = np.random.default_rng(graine)
    idx = pd.date_range(debut, periods=n, freq=freq, name="time")
    c = 2000 + np.cumsum(rng.normal(0, vol, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.exponential(0.4 * vol, n)
    l = np.minimum(o, c) - rng.exponential(0.4 * vol, n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c,
                         "tick_volume": rng.integers(1, 100, n).astype(np.int64),
                         "spread": rng.integers(10, 40, n).astype(np.int64),
                         "real_volume": np.zeros(n, dtype=np.int64)}, index=idx)


# --------------------------------------------------------------------------- FVG

class TestDetecterFvg(unittest.TestCase):
    def un_fvg(self, lignes, cfg=CFG, spec=SPEC):
        fvg = detecter_fvg(bougies(lignes), cfg, spec)
        self.assertEqual(len(fvg), 1)
        return fvg.iloc[0], fvg.index[0]

    def test_long_bord(self):
        f, t = self.un_fvg(LONG)
        self.assertEqual(t, T("2024-01-02 10:45"))  # clôture de c3 (ouverte à 10:30)
        self.assertEqual(f["sens"], 1)
        self.assertAlmostEqual(f["entree"], 2001.00, places=9)
        self.assertAlmostEqual(f["sl"], 1999.00 - 0.20, places=9)        # min des low - spread(c3) x point
        self.assertAlmostEqual(f["distance_sl"], 2.20, places=9)
        self.assertAlmostEqual(f["tp1"], 2001.00 + 2.20, places=9)
        self.assertEqual(f["rejet"], "")
        self.assertAlmostEqual(f["haut_vide"], 2002.00)
        self.assertAlmostEqual(f["bas_vide"], 2001.00)

    def test_formation_hors_session(self):
        # c1 ouverte à 08:15 (session asiatique), confirmation à 09:00 : rejeté
        fvg = detecter_fvg(bougies(LONG, debut="2024-01-02 08:15"), CFG, SPEC)
        self.assertEqual(fvg.iloc[0]["rejet"], "formation_hors_session")
        # c1 ouverte à 09:00 pile : valide
        fvg = detecter_fvg(bougies(LONG, debut="2024-01-02 09:00"), CFG, SPEC)
        self.assertEqual(fvg.iloc[0]["rejet"], "")
        # prioritaire sur les autres raisons
        fvg = detecter_fvg(bougies(LONG, debut="2024-01-02 08:45"), CFG.avec(sl_plafond=1.0), SPEC)
        self.assertEqual(fvg.iloc[0]["rejet"], "formation_hors_session")

    def test_long_milieu_et_marge(self):
        f, _ = self.un_fvg(LONG, CFG.avec(mode_entree="milieu"))
        self.assertAlmostEqual(f["entree"], 2001.50, places=9)
        self.assertAlmostEqual(f["distance_sl"], 2.70, places=9)
        self.assertAlmostEqual(f["tp1"], 2004.20, places=9)
        f, _ = self.un_fvg(LONG, CFG.avec(sl_marge_fixe=0.30, tp1_r=2.0))
        self.assertAlmostEqual(f["sl"], 1998.50, places=9)
        self.assertAlmostEqual(f["distance_sl"], 2.50, places=9)
        self.assertAlmostEqual(f["tp1"], 2006.00, places=9)

    def test_short_bord_et_milieu(self):
        f, t = self.un_fvg(SHORT)
        self.assertEqual(t, T("2024-01-02 10:45"))
        self.assertEqual(f["sens"], -1)
        self.assertAlmostEqual(f["entree"], 1999.00, places=9)
        self.assertAlmostEqual(f["sl"], 2001.00 + 0.25, places=9)        # max des high + spread(c3) x point
        self.assertAlmostEqual(f["distance_sl"], 2.25, places=9)
        self.assertAlmostEqual(f["tp1"], 1999.00 - 2.25, places=9)
        self.assertAlmostEqual(f["haut_vide"], 1999.00)
        self.assertAlmostEqual(f["bas_vide"], 1998.00)
        f, _ = self.un_fvg(SHORT, CFG.avec(mode_entree="milieu"))
        self.assertAlmostEqual(f["entree"], 1998.50, places=9)
        self.assertAlmostEqual(f["distance_sl"], 2.75, places=9)
        self.assertAlmostEqual(f["tp1"], 1995.75, places=9)

    def test_sl_trop_loin(self):
        lignes = [list(l) for l in LONG]
        lignes[0][2] = 1995.00                       # low(c1) -> SL 1994.80, distance 6.20 > 5
        f, _ = self.un_fvg(lignes)
        self.assertEqual(f["rejet"], "sl_trop_loin")
        self.assertAlmostEqual(f["distance_sl"], 6.20, places=9)
        lignes[0][2] = 1996.20                       # distance exactement 5.00 : acceptée
        f, _ = self.un_fvg(lignes)
        self.assertEqual(f["rejet"], "")
        lignes[0][2] = 1996.19                       # 5.01 : rejetée
        self.assertEqual(self.un_fvg(lignes)[0]["rejet"], "sl_trop_loin")
        short = [list(l) for l in SHORT]
        short[1][1] = 2004.00                        # high(c2) -> SL 2004.25, distance 5.25
        self.assertEqual(self.un_fvg(short)[0]["rejet"], "sl_trop_loin")

    def test_sl_trop_proche(self):
        f, _ = self.un_fvg(LONG, spec=dataclasses.replace(SPEC, stops_level_points=300))  # 3.00 > 2.20
        self.assertEqual(f["rejet"], "sl_trop_proche")
        f, _ = self.un_fvg(LONG, spec=dataclasses.replace(SPEC, stops_level_points=220))  # égalité acceptée
        self.assertEqual(f["rejet"], "")
        f, _ = self.un_fvg(SHORT, spec=dataclasses.replace(SPEC, stops_level_points=226))
        self.assertEqual(f["rejet"], "sl_trop_proche")

    def test_ecart_trop_petit(self):
        f, _ = self.un_fvg(LONG, CFG.avec(fvg_ecart_min=1.5))
        self.assertEqual(f["rejet"], "ecart_trop_petit")
        f, _ = self.un_fvg(LONG, CFG.avec(fvg_ecart_min=1.0))  # vide de 1.00 exactement
        self.assertEqual(f["rejet"], "")
        f, _ = self.un_fvg(SHORT, CFG.avec(fvg_ecart_min=1.01))
        self.assertEqual(f["rejet"], "ecart_trop_petit")
        # priorité : ecart_trop_petit avant sl_trop_loin
        lignes = [list(l) for l in LONG]
        lignes[0][2] = 1990.00
        f, _ = self.un_fvg(lignes, CFG.avec(fvg_ecart_min=1.5))
        self.assertEqual(f["rejet"], "ecart_trop_petit")

    def test_pas_de_fvg(self):
        lignes = [list(l) for l in LONG]
        lignes[2][2] = 2001.00                       # low(c3) == high(c1) : inégalité stricte
        self.assertEqual(len(detecter_fvg(bougies(lignes), CFG, SPEC)), 0)
        self.assertEqual(len(detecter_fvg(bougies(LONG[:2]), CFG, SPEC)), 0)
        # bougies non contiguës (trou entre c2 et c3) : pas un FVG
        trou = bougies([("2024-01-02 10:00", *LONG[0]), ("2024-01-02 10:15", *LONG[1]),
                        ("2024-01-02 10:45", *LONG[2])])
        self.assertEqual(len(detecter_fvg(trou, CFG, SPEC)), 0)
        vide = detecter_fvg(bougies(LONG[:2]), CFG, SPEC)
        self.assertEqual(list(vide.columns), COLONNES_FVG)

    def test_plusieurs_fvg_et_c2_dans_le_sl(self):
        # c2 a le plus bas : il fixe le SL du long
        lignes = [list(l) for l in LONG]
        lignes[1][2] = 1998.50
        lignes[1][0] = 1999.0
        f, _ = self.un_fvg(lignes)
        self.assertAlmostEqual(f["sl"], 1998.30, places=9)
        # long puis short à la suite
        seq = LONG + [(2003.60, 2003.70, 2001.50, 2001.60, 10), (2001.60, 2001.80, 1999.00, 1999.50, 30)]
        fvg = detecter_fvg(bougies(seq), CFG, SPEC)
        self.assertEqual(list(fvg["sens"]), [1, -1])
        self.assertEqual(fvg.index[1], T("2024-01-02 11:15"))


# --------------------------------------------------------------------------- tendance

class TestTendance(unittest.TestCase):
    CFG_COURT = CFG.avec(ema_periode=2, pente_ema_barres=1)   # échauffement : i < 6

    def h1(self, closes, debut="2024-01-02 00:00"):
        c = np.asarray(closes, dtype=float)
        return bougies([(x, x + 1, x - 1, x, 20) for x in c], debut=debut, pas="h")

    def test_signe_de_la_pente_et_echauffement(self):
        hausse = tendance_h1(self.h1(np.arange(20) + 2000.0), self.CFG_COURT)
        self.assertEqual(list(hausse), [0] * 6 + [1] * 14)
        baisse = tendance_h1(self.h1(2000.0 - np.arange(20)), self.CFG_COURT)
        self.assertEqual(list(baisse), [0] * 6 + [-1] * 14)
        plat = tendance_h1(self.h1(np.full(20, 2000.0)), self.CFG_COURT)
        self.assertEqual(list(plat), [0] * 20)
        self.assertEqual(hausse.dtype, np.int64)

    def test_valeurs_a_la_main_et_index_de_cloture(self):
        closes = [2000, 2001, 2003, 2002, 2005, 2004, 2001, 1999, 2000, 2006, 2007, 2003]
        h1 = self.h1(closes)
        cfg = CFG.avec(ema_periode=2, pente_ema_barres=2)
        tend = tendance_h1(h1, cfg)
        e = ema(pd.Series(closes, dtype=float), 2).to_numpy()
        attendu = [0 if i < 6 else int(np.sign(e[i] - e[i - 2])) for i in range(len(closes))]
        self.assertEqual(list(tend), attendu)
        self.assertIn(1, attendu)
        self.assertIn(-1, attendu)
        np.testing.assert_array_equal(tend.index, h1.index + pd.Timedelta(hours=1))

    def test_echauffement_par_defaut(self):
        tend = tendance_h1(self.h1(np.arange(200) + 2000.0), CFG)   # ema 50 -> 150 barres à 0
        self.assertTrue((tend.iloc[:150] == 0).all())
        self.assertTrue((tend.iloc[150:] == 1).all())

    def test_non_anticipation_tendance_h1(self):
        h1 = marche_aleatoire(400, "h", graine=4)
        cfg = CFG.avec(ema_periode=10, pente_ema_barres=3)
        base = tendance_h1(h1, cfg)
        self.assertTrue((base == 1).any() and (base == -1).any())
        for k in (31, 100, 250, 399):
            futur = h1.copy()
            futur.iloc[k:, :4] = futur.iloc[k:, :4] * 1.5 + 7.0
            pd.testing.assert_series_equal(tendance_h1(futur, cfg).iloc[:k], base.iloc[:k])
            pd.testing.assert_series_equal(tendance_h1(h1.iloc[:k], cfg), base.iloc[:k])

    def test_visible_seulement_a_la_cloture(self):
        h1 = self.h1(np.r_[np.arange(10) + 2000.0, 2009 - np.arange(1, 10)])
        tend = tendance_h1(h1, self.CFG_COURT)
        for i in range(1, len(h1)):
            ouverture = h1.index[i]
            # pendant la bougie i, on ne voit que la tendance de la bougie i-1
            for dt in (pd.Timedelta(0), pd.Timedelta(minutes=15), pd.Timedelta(minutes=59, seconds=59)):
                self.assertEqual(tendance_a(tend, ouverture + dt), tend.iloc[i - 1])
            self.assertEqual(tendance_a(tend, ouverture + pd.Timedelta(hours=1)), tend.iloc[i])
        self.assertEqual(tendance_a(tend, h1.index[0]), 0)                  # avant la 1re clôture
        self.assertEqual(tendance_a(tend, h1.index[0] - pd.Timedelta(days=3)), 0)

    def test_tendance_a_vectorise(self):
        s = pd.Series([1, -1, 0, 1], index=pd.DatetimeIndex(["2024-01-02 10:00", "2024-01-02 11:00",
                                                                 "2024-01-02 12:00", "2024-01-02 14:00"]))
        instants = pd.DatetimeIndex(["2024-01-02 09:59", "2024-01-02 10:00", "2024-01-02 10:59",
                                     "2024-01-02 11:00", "2024-01-02 13:30", "2024-01-02 23:00"])
        np.testing.assert_array_equal(tendance_a(s, instants), [0, 1, 1, -1, 0, 1])
        self.assertIsInstance(tendance_a(s, T("2024-01-02 11:30")), int)


# --------------------------------------------------------------------------- preparer_signaux

def _donnees_aleatoires(jours=40, graine=7):
    m15 = marche_aleatoire(jours * 96, "15min", debut="2024-01-01", graine=graine, vol=0.8)
    h1 = reechantillonner(m15, "h")
    return m15, h1


CFG_RAPIDE = CFG.avec(ema_periode=8, pente_ema_barres=3, adr_periode=3, adr_reference=7,
                      adr_ratio_min=0.9, adr_ratio_max=1.1)


class TestPreparerSignaux(unittest.TestCase):
    def test_colonnes_types_et_index(self):
        m15, h1 = _donnees_aleatoires(jours=20)
        s = preparer_signaux(m15, h1, CFG_RAPIDE, SPEC)
        self.assertEqual(list(s.columns), COLONNES_SIGNAUX)
        np.testing.assert_array_equal(s.index, m15.index + M15)
        self.assertEqual(s["tendance"].dtype, np.int64)
        self.assertEqual(s["sens"].dtype, np.int64)
        self.assertEqual(s["adr_ok"].dtype, bool)
        self.assertEqual(s["heure_entree_ok"].dtype, bool)
        sans = s["sens"] == 0
        self.assertTrue(s.loc[sans, ["entree", "sl", "tp1", "distance_sl"]].isna().all().all())
        self.assertTrue((s.loc[sans, "rejet"] == "").all())
        avec = ~sans
        self.assertTrue(avec.any())
        self.assertFalse(s.loc[avec, ["entree", "sl", "tp1", "distance_sl"]].isna().any().any())
        # cohérence avec detecter_fvg
        fvg = detecter_fvg(m15, CFG_RAPIDE, SPEC)
        pd.testing.assert_frame_equal(s.loc[avec, ["sens", "entree", "sl", "tp1", "distance_sl", "rejet"]],
                                      fvg[["sens", "entree", "sl", "tp1", "distance_sl", "rejet"]],
                                      check_names=False)
        # heure_entree_ok est évaluée à l'instant de clôture
        self.assertFalse(s.loc[T("2024-01-02 08:45"), "heure_entree_ok"])   # bougie 08:30
        self.assertTrue(s.loc[T("2024-01-02 09:00"), "heure_entree_ok"])    # bougie 08:45 -> clôture 09:00
        self.assertTrue(s.loc[T("2024-01-02 20:45"), "heure_entree_ok"])
        self.assertFalse(s.loc[T("2024-01-02 21:00"), "heure_entree_ok"])

    def test_date_adr_est_celle_de_l_ouverture(self):
        # ranges : 1er = 10, 2 = 10, 3 = 40 ; ADR 1 jour, REF médiane de 2 jours, ratio max 1.5
        h1 = bougies([("2024-01-01 12:00", 2000, 2010, 2000, 2005, 20),
                      ("2024-01-02 12:00", 2000, 2010, 2000, 2005, 20),
                      ("2024-01-03 12:00", 2000, 2040, 2000, 2005, 20)])
        m15 = bougies([("2024-01-03 23:45", 2000, 2001, 1999, 2000, 20),
                       ("2024-01-04 00:00", 2000, 2001, 1999, 2000, 20)])
        cfg = CFG.avec(adr_periode=1, adr_reference=2, adr_ratio_max=1.5)
        s = preparer_signaux(m15, h1, cfg, SPEC)
        # clôture du 4 à 00:00 = bougie du 3 : ADR 10 / REF 10 = 1 -> ok
        self.assertTrue(s.loc[T("2024-01-04 00:00"), "adr_ok"])
        # clôture du 4 à 00:15 = bougie du 4 : ADR 40 / REF 25 = 1.6 -> interdit
        self.assertFalse(s.loc[T("2024-01-04 00:15"), "adr_ok"])

    def test_non_anticipation(self):
        m15, h1 = _donnees_aleatoires(jours=40)
        base = preparer_signaux(m15, h1, CFG_RAPIDE, SPEC)
        # le test n'a de sens que si toutes les colonnes varient
        self.assertTrue(base["adr_ok"].any() and (~base["adr_ok"]).any())
        self.assertTrue((base["tendance"] == 1).any() and (base["tendance"] == -1).any())
        self.assertTrue((base["sens"] == 1).any() and (base["sens"] == -1).any())
        self.assertTrue(base["heure_entree_ok"].any())
        rng = np.random.default_rng(11)
        instants = [T("2024-01-20 00:00"), T("2024-01-20 00:15"), T("2024-01-25 10:00"),
                    T("2024-01-25 10:30"), T("2024-01-31 16:45"), T("2024-02-09 23:45")]
        for t in instants:
            with self.subTest(t=t):
                attendu = base.loc[:t]
                # 1. données postérieures à t (bougies clôturées après t) remplacées par du bruit
                m15_f, h1_f = m15.copy(), h1.copy()
                fut_m15 = m15_f.index + M15 > t
                fut_h1 = h1_f.index + pd.Timedelta(hours=1) > t
                for df, masque in ((m15_f, fut_m15), (h1_f, fut_h1)):
                    k = int(masque.sum())
                    choc = rng.normal(0, 30, k)
                    for c in ("open", "high", "low", "close"):
                        df.loc[masque, c] = df.loc[masque, c] + choc
                    df.loc[masque, "high"] += 5.0
                    df.loc[masque, "low"] -= 5.0
                    df.loc[masque, "spread"] = rng.integers(0, 200, k)
                modifie = preparer_signaux(m15_f, h1_f, CFG_RAPIDE, SPEC)
                pd.testing.assert_frame_equal(modifie.loc[:t], attendu)
                # 2. données postérieures à t retirées (situation du bot en direct)
                tronque = preparer_signaux(m15[~fut_m15], h1[~fut_h1], CFG_RAPIDE, SPEC)
                pd.testing.assert_frame_equal(tronque, attendu)

    def test_bougie_h1_en_formation_ignoree(self):
        # le bot peut recevoir la bougie H1 en cours : sa tendance ne doit pas apparaître avant sa clôture
        m15, h1 = _donnees_aleatoires(jours=20)
        t = T("2024-01-15 10:30")
        base = preparer_signaux(m15[m15.index + M15 <= t], h1[h1.index + pd.Timedelta(hours=1) <= t],
                                CFG_RAPIDE, SPEC)
        avec_formation = preparer_signaux(m15[m15.index + M15 <= t], h1[h1.index <= t], CFG_RAPIDE, SPEC)
        pd.testing.assert_frame_equal(avec_formation, base)

    def test_index_invalide_refuse(self):
        m15, h1 = _donnees_aleatoires(jours=3)
        with self.assertRaises(ValueError):
            preparer_signaux(m15.iloc[::-1], h1, CFG_RAPIDE, SPEC)
        with self.assertRaises(ValueError):
            preparer_signaux(pd.concat([m15, m15.iloc[-2:]]), h1, CFG_RAPIDE, SPEC)

    def test_performance(self):
        m15 = marche_aleatoire(150_000, "15min", debut="2019-01-01", graine=21)
        h1 = marche_aleatoire(40_000, "h", debut="2019-06-01", graine=22)
        debut = time.perf_counter()
        s = preparer_signaux(m15, h1, CFG, SPEC)
        duree = time.perf_counter() - debut
        print(f"\n[perf] preparer_signaux 150 000 M15 + 40 000 H1 : {duree:.2f} s")
        self.assertEqual(len(s), 150_000)
        self.assertLess(duree, 10.0)


# --------------------------------------------------------------------------- machine à setups

T0 = T("2024-01-02 10:45")


def ligne(tendance=1, adr_ok=True, heure_entree_ok=True, sens=0, rejet="",
          entree=np.nan, sl=np.nan, tp1=np.nan, distance_sl=np.nan):
    return {"tendance": tendance, "adr_ok": adr_ok, "heure_entree_ok": heure_entree_ok, "sens": sens,
            "entree": entree, "sl": sl, "tp1": tp1, "distance_sl": distance_sl, "rejet": rejet}


def fvg_long(**kw):
    d = dict(sens=1, entree=2001.0, sl=1998.8, tp1=2003.2, distance_sl=2.2)
    d.update(kw)
    return ligne(**d)


def fvg_short(**kw):
    d = dict(tendance=-1, sens=-1, entree=1999.0, sl=2001.25, tp1=1996.75, distance_sl=2.25)
    d.update(kw)
    return ligne(**d)


def types(evenements):
    return [(e.type, e.raison) for e in evenements]


class TestMoteurSignaux(unittest.TestCase):
    def setUp(self):
        self.m = MoteurSignaux(CFG)

    def test_creation(self):
        ev = self.m.sur_cloture_m15(T0, fvg_long(), False)
        self.assertEqual(types(ev), [("nouveau", "")])
        s = self.m.setup_actif
        self.assertEqual(ev[0].setup, s)
        self.assertEqual(ev[0].instant, T0)
        self.assertEqual(s, Setup(1, 2001.0, 1998.8, 2003.2, 2.2, T0, T0 + 8 * M15))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            s.sl = 0.0
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ev[0].type = "x"

    def test_conditions_de_creation(self):
        refus = {
            "contre_tendance": fvg_long(tendance=-1),
            "tendance_nulle": fvg_long(tendance=0),
            "adr": fvg_long(adr_ok=False),
            "hors_session": fvg_long(heure_entree_ok=False),
            "pas_de_fvg": ligne(),
        }
        for nom, l in refus.items():
            with self.subTest(nom):
                m = MoteurSignaux(CFG)
                self.assertEqual(m.sur_cloture_m15(T0, l, False), [])
                self.assertIsNone(m.setup_actif)
        m = MoteurSignaux(CFG)
        self.assertEqual(m.sur_cloture_m15(T0, fvg_long(), True), [])   # position ouverte
        self.assertIsNone(m.setup_actif)
        self.assertEqual(types(m.sur_cloture_m15(T0 + M15, fvg_short(), False)), [("nouveau", "")])

    def test_rejet(self):
        ev = self.m.sur_cloture_m15(T0, fvg_long(rejet="sl_trop_loin", distance_sl=6.2), False)
        self.assertEqual(types(ev), [("rejete", "sl_trop_loin")])
        self.assertIsNone(ev[0].setup)
        self.assertIsNone(self.m.setup_actif)
        # un rejet ne retire pas le setup actif
        self.m.sur_cloture_m15(T0 + M15, fvg_long(), False)
        actif = self.m.setup_actif
        ev = self.m.sur_cloture_m15(T0 + 2 * M15, fvg_long(rejet="sl_trop_proche"), False)
        self.assertEqual(types(ev), [("rejete", "sl_trop_proche")])
        self.assertIs(self.m.setup_actif, actif)
        # rejet non signalé si le FVG était de toute façon hors conditions
        self.assertEqual(self.m.sur_cloture_m15(T0 + 3 * M15, fvg_short(rejet="sl_trop_loin", tendance=1), False), [])

    def test_expiration(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        for k in range(1, 8):
            self.assertEqual(self.m.sur_cloture_m15(T0 + k * M15, ligne(), False), [])
            self.assertIsNotNone(self.m.setup_actif)
        ev = self.m.sur_cloture_m15(T0 + 8 * M15, ligne(), False)
        self.assertEqual(types(ev), [("annule", "expire")])
        self.assertEqual(ev[0].setup.cree_a, T0)
        self.assertIsNone(self.m.setup_actif)

    def test_expiration_apres_un_trou(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + 20 * M15, ligne(), False)
        self.assertEqual(types(ev), [("annule", "expire")])

    def test_expiration_puis_creation_meme_cloture(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + 8 * M15, fvg_long(entree=2010.0), False)
        self.assertEqual(types(ev), [("annule", "expire"), ("nouveau", "")])
        self.assertEqual(self.m.setup_actif.entree, 2010.0)

    def test_remplacement(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ancien = self.m.setup_actif
        ev = self.m.sur_cloture_m15(T0 + 2 * M15, fvg_long(entree=2005.0, sl=2003.0, tp1=2007.0, distance_sl=2.0),
                                    False)
        self.assertEqual(types(ev), [("remplace", "nouveau_fvg"), ("nouveau", "")])
        self.assertIs(ev[0].setup, ancien)
        self.assertEqual(ev[1].setup.entree, 2005.0)
        self.assertEqual(self.m.setup_actif.expire_a, T0 + 10 * M15)

    def test_annulation_par_la_tendance(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + M15, ligne(tendance=0), False)
        self.assertEqual(types(ev), [("annule", "tendance")])
        self.assertIsNone(self.m.setup_actif)
        # retournement + FVG dans le nouveau sens : annulation puis création, pas de "remplace"
        self.m.sur_cloture_m15(T0 + 2 * M15, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + 3 * M15, fvg_short(), False)
        self.assertEqual(types(ev), [("annule", "tendance"), ("nouveau", "")])
        self.assertEqual(self.m.setup_actif.sens, -1)

    def test_annulation_hors_session(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + M15, ligne(heure_entree_ok=False), False)
        self.assertEqual(types(ev), [("annule", "hors_session")])

    def test_ordre_des_raisons(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.sur_cloture_m15(T0 + 8 * M15, ligne(tendance=-1, heure_entree_ok=False), False)
        self.assertEqual(types(ev), [("annule", "expire")])
        m = MoteurSignaux(CFG)
        m.sur_cloture_m15(T0, fvg_long(), False)
        ev = m.sur_cloture_m15(T0 + M15, ligne(tendance=-1, heure_entree_ok=False), False)
        self.assertEqual(types(ev), [("annule", "tendance")])

    def test_position_ouverte(self):
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        actif = self.m.setup_actif
        # pas de remplacement tant qu'une position est ouverte ; les annulations s'appliquent toujours
        self.assertEqual(self.m.sur_cloture_m15(T0 + M15, fvg_long(entree=2005.0), True), [])
        self.assertIs(self.m.setup_actif, actif)
        self.assertEqual(types(self.m.sur_cloture_m15(T0 + 2 * M15, ligne(tendance=-1), True)),
                         [("annule", "tendance")])

    def test_consommer(self):
        with self.assertRaises(RuntimeError):
            self.m.consommer()
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        actif = self.m.setup_actif
        self.assertIs(self.m.consommer(), actif)
        self.assertIsNone(self.m.setup_actif)
        # après consommation, plus d'annulation de ce setup
        self.assertEqual(self.m.sur_cloture_m15(T0 + 8 * M15, ligne(), True), [])
        with self.assertRaises(RuntimeError):
            self.m.consommer()

    def test_annuler_depuis_l_execution(self):
        self.assertIsNone(self.m.annuler(T0, "taille_refusee"))
        self.m.sur_cloture_m15(T0, fvg_long(), False)
        ev = self.m.annuler(T0 + pd.Timedelta(minutes=3), "taille_refusee")
        self.assertEqual((ev.type, ev.raison), ("annule", "taille_refusee"))
        self.assertIsNone(self.m.setup_actif)

    def test_garde_fous(self):
        self.m.sur_cloture_m15(T0, ligne(), False)
        with self.assertRaises(ValueError):          # instant non croissant
            self.m.sur_cloture_m15(T0, ligne(), False)
        serie = pd.Series(ligne(), name=T0 + 2 * M15)
        with self.assertRaises(ValueError):          # ligne d'un autre instant
            self.m.sur_cloture_m15(T0 + M15, serie, False)
        with self.assertRaises(ValueError):          # FVG valide sans prix
            MoteurSignaux(CFG).sur_cloture_m15(T0, fvg_long(entree=np.nan), False)

    def test_validite_configurable(self):
        m = MoteurSignaux(CFG.avec(validite_setup_barres=2))
        m.sur_cloture_m15(T0, fvg_long(), False)
        self.assertEqual(m.sur_cloture_m15(T0 + M15, ligne(), False), [])
        self.assertEqual(types(m.sur_cloture_m15(T0 + 2 * M15, ligne(), False)), [("annule", "expire")])

    def test_integration_avec_preparer_signaux(self):
        m15, h1 = _donnees_aleatoires(jours=40)
        s = preparer_signaux(m15, h1, CFG_RAPIDE, SPEC)
        m_tuples, m_series = MoteurSignaux(CFG_RAPIDE), MoteurSignaux(CFG_RAPIDE)
        ev_tuples, ev_series = [], []
        for l in s.itertuples():
            ev_tuples += m_tuples.sur_cloture_m15(l.Index, l, False)
            if m_tuples.setup_actif is not None:
                self.assertLess(l.Index, m_tuples.setup_actif.expire_a)
                self.assertEqual(m_tuples.setup_actif.sens, l.tendance)
                self.assertTrue(l.heure_entree_ok)
        for t, l in s.iterrows():
            ev_series += m_series.sur_cloture_m15(t, l, False)
        self.assertEqual(ev_tuples, ev_series)
        nouveaux = [e for e in ev_tuples if e.type == "nouveau"]
        self.assertGreater(len(nouveaux), 5)
        for e in nouveaux:
            l = s.loc[e.instant]
            self.assertTrue(l["sens"] == l["tendance"] != 0 and l["adr_ok"] and l["heure_entree_ok"])
            self.assertEqual(l["rejet"], "")
            self.assertEqual((e.setup.sens, e.setup.entree, e.setup.sl, e.setup.tp1, e.setup.distance_sl),
                             (l["sens"], l["entree"], l["sl"], l["tp1"], l["distance_sl"]))
            self.assertIsInstance(e, Evenement)


if __name__ == "__main__":
    unittest.main()
