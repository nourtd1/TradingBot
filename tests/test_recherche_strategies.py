"""Tests de sentitrade/recherche/strategies.py : paramètres figés, indicateurs, anti-anticipation.

Anti-anticipation par troncature : un signal calculé sur les données coupées à l'instant k doit
être IDENTIQUE au signal calculé sur toutes les données, pour toute bougie <= k. Le même test est
fait sur le moteur complet : les entrées antérieures à la coupure ne changent pas.
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.synthetique import generer_brut, generer_univers
from sentitrade.recherche.donnees import construire_univers


def _d1(n=600, graine=3):
    rng = np.random.default_rng(graine)
    idx = pd.bdate_range("2015-01-01", periods=n)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.concatenate([[100], c[:-1]])
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.003, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.003, n)))
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "tick_volume": 1, "spread": 1,
                         "real_volume": 0}, index=pd.DatetimeIndex(idx, name="time"))


class TestParametres(unittest.TestCase):
    def test_parametres_du_plan(self):
        b1 = st.strategie_base("S1").params
        self.assertEqual((b1.entree, b1.sortie, b1.stop_atr), (55, 20, 2.0))
        self.assertEqual([(v.params.entree, v.params.sortie, v.params.stop_atr) for v in st.variantes_voisines("S1")],
                         [(40, 15, 2.0), (80, 30, 2.0), (55, 20, 3.0)])
        b2 = st.strategie_base("S2").params
        self.assertEqual((b2.rendement_jours, b2.vol_cible, b2.vol_barres, b2.stop_atr, b2.seuil_reequilibrage,
                          b2.levier_max), (365, 0.10, 60, 4.0, 0.25, 10.0))
        self.assertEqual([v.params.rendement_jours for v in st.variantes_voisines("S2")], [182, 91])
        b3 = st.strategie_base("S3").params
        self.assertEqual((b3.sma_tendance, b3.rsi_periode, b3.rsi_seuil, b3.sma_sortie, b3.barres_max, b3.stop_atr),
                         (200, 2, 10.0, 5, 10, 3.0))
        self.assertEqual([(v.params.rsi_seuil, v.params.sma_sortie) for v in st.variantes_voisines("S3")],
                         [(5.0, 5), (20.0, 5), (10.0, 10)])
        self.assertEqual(st.strategie_base("S3").classes, ("indices",))
        b4 = st.strategie_base("S4").params
        self.assertEqual((b4.barres_range, b4.objectif_r, b4.filtre_spread), (4, None, 3.0))
        self.assertEqual([(v.params.barres_range, v.params.objectif_r) for v in st.variantes_voisines("S4")],
                         [(2, None), (4, 2.0)])
        self.assertEqual(set(st.SESSIONS_S4), {"XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "GER40"})
        self.assertEqual(st.SESSIONS_S4["US500"], ("16:30", "22:45"))
        self.assertEqual(st.SESSIONS_S4["GER40"], ("10:00", "22:45"))
        self.assertEqual(st.SESSIONS_S4["XAUUSD"], ("10:00", "21:55"))
        for c in ("S1", "S3", "S4"):
            self.assertEqual(st.strategie_base(c).risque_pct, 0.5)


class TestIndicateurs(unittest.TestCase):
    def test_atr_moyenne_simple_20(self):
        df = _d1(60)
        prev = df["close"].shift(1)
        tr = pd.Series(np.maximum.reduce([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()]))
        a = st.atr(df)
        self.assertTrue(a.iloc[:20].isna().all())
        self.assertAlmostEqual(a.iloc[20], tr.iloc[1:21].mean())
        self.assertAlmostEqual(a.iloc[45], tr.iloc[26:46].mean())

    def test_rsi_wilder_a_la_main(self):
        c = pd.Series([10.0, 11.0, 10.5, 10.0, 11.0, 11.5])
        # variations : +1, -0.5, -0.5, +1, +0.5 ; n = 2
        # init (indice 2) : gain (1+0)/2 = 0.5 ; perte (0+0.5)/2 = 0.25 -> RSI 66.67
        # indice 3 : g = 0.5 + (0-0.5)/2 = 0.25 ; p = 0.25 + (0.5-0.25)/2 = 0.375 -> RSI 40
        # indice 4 : g = 0.25 + (1-0.25)/2 = 0.625 ; p = 0.375/2 = 0.1875 -> RSI 76.92
        r = st.rsi_wilder(c, 2)
        self.assertTrue(r.iloc[:2].isna().all())
        self.assertAlmostEqual(r.iloc[2], 100 - 100 / 3)
        self.assertAlmostEqual(r.iloc[3], 40.0)
        self.assertAlmostEqual(r.iloc[4], 100 - 100 / (1 + 0.625 / 0.1875))

    def test_s1_plus_haut_des_55_precedentes(self):
        df = _d1(200)
        s = st.signaux_s1(df, st.ParamS1())
        i = 150
        attendu = df["close"].iloc[i] > df["high"].iloc[i - 55:i].max()
        self.assertEqual(bool(s["entree_long"].iloc[i]), bool(attendu))
        self.assertTrue((~s["entree_long"].iloc[:55]).all())

    def test_s2_rendement_365_jours_calendaires(self):
        df = _d1(600)
        s = st.signaux_s2(df, st.ParamS2(), crypto=False)
        i = 500                                    # valeurs « veille » : calculées à la bougie 499
        t = df.index[i - 1]
        ref = df["close"][df.index <= t - pd.Timedelta(days=365)].iloc[-1]
        self.assertEqual(s["signe"].iloc[i], np.sign(df["close"].iloc[i - 1] / ref - 1))
        vol = df["close"].pct_change().iloc[i - 60:i].std(ddof=1) * np.sqrt(252)
        self.assertAlmostEqual(s["vol"].iloc[i], vol)
        lundis = df.index[s["reequilibrer"].to_numpy()]
        self.assertTrue((lundis.weekday == 0).all())


class TestAntiAnticipation(unittest.TestCase):
    """Troncature : rien de ce qui est connu à l'instant k ne change si l'on retire le futur."""

    def _compare(self, f, df, coupures):
        complet = f(df)
        for k in coupures:
            tronque = f(df.iloc[:k + 1])
            pd.testing.assert_frame_equal(complet.iloc[:k + 1], tronque, check_dtype=False,
                                          obj=f"coupure {k}")

    def test_s1_s2_s3(self):
        df = _d1(700)
        coupures = [60, 260, 400, 699]
        self._compare(lambda d: st.signaux_s1(d, st.ParamS1()), df, coupures)
        self._compare(lambda d: st.signaux_s2(d, st.ParamS2(), False), df, coupures)
        self._compare(lambda d: st.signaux_s3(d, st.ParamS3()), df, coupures)
        for v in st.variantes_voisines("S1") + st.variantes_voisines("S3"):
            f = st.signaux_s1 if v.code == "S1" else st.signaux_s3
            self._compare(lambda d, v=v, f=f: f(d, v.params), df, [300])

    def test_s4_niveaux(self):
        brut = generer_brut(debut="2024-01-01", fin="2024-02-15", graine=5, symboles=["EURUSD"], annees_m15=0)
        m15 = brut["EURUSD"]["bougies"]["M15"]
        p50 = np.full(24, 0.0001)
        complet = st.niveaux_s4(m15, "EURUSD", st.ParamS4(), p50).set_index("jour")
        for coupure in ("2024-01-20 10:45", "2024-01-25 10:30", "2024-02-01 15:00"):
            tr = st.niveaux_s4(m15.loc[:coupure], "EURUSD", st.ParamS4(), p50).set_index("jour")
            connus = tr[tr["t_placement"] <= pd.Timestamp(coupure)]
            pd.testing.assert_frame_equal(complet.loc[connus.index], connus, obj=coupure)

    def test_moteur_par_troncature(self):
        """Simulation complète : les trades OUVERTS avant la coupure sont identiques (entrée, taille)."""
        u = generer_univers(debut="2016-01-01", fin="2021-06-30", graine=11,
                            symboles=["EURUSD", "USDJPY", "US500", "GER40", "XAUUSD"], annees_m15=1.5)
        coupure = pd.Timestamp("2020-06-15")
        # (S2 ajuste la taille et le prix moyen d'une position ouverte : seuls entrée, sens et stop initial
        # sont comparés pour les positions encore ouvertes à la coupure.)
        cols = ["symbole", "sens", "entree_a", "stop_initial"]
        tri = ["entree_a", "symbole"]
        for code in st.CODES:
            s = st.strategie_base(code)
            if code == "S3":
                s = s.avec_classes(("indices", "forex", "metaux"))
            if code == "S4":
                coupure_s = pd.Timestamp("2021-03-10 13:00")
            else:
                coupure_s = coupure
            complet = mo.simuler(u, s, journal_complet=False).trades
            tronque = mo.simuler(u.tronquer(coupure_s), s, journal_complet=False).trades
            a = complet[complet["entree_a"] <= coupure_s].sort_values(tri)[cols].reset_index(drop=True)
            b = tronque[tronque["entree_a"] <= coupure_s].sort_values(tri)[cols].reset_index(drop=True)
            self.assertGreater(len(a), 3, code)
            pd.testing.assert_frame_equal(a, b, obj=code)
            # trades fermés avant la coupure : identiques en entier (sortie et P&L compris)
            fa = complet[complet["sortie_a"] < coupure_s - pd.Timedelta(days=1)].sort_values(tri).reset_index(drop=True)
            fb = tronque[tronque["sortie_a"] < coupure_s - pd.Timedelta(days=1)].sort_values(tri).reset_index(drop=True)
            pd.testing.assert_frame_equal(fa, fb, obj=code + " (fermés)")


if __name__ == "__main__":
    unittest.main()
