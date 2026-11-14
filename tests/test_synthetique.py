"""Tests de sentitrade/synthetique.py : format exact de la spec §2, réalisme grossier, absence d'avantage."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from sentitrade.data import COLONNES, FORMAT_TIME, charger_bougies, reechantillonner, valider_bougies
from sentitrade.synthetique import generer_jeu, generer_m1


class TestSynthetique(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.m1 = generer_m1("2024-01-01", "2024-07-01", graine=11)

    def test_format_exact(self):
        m1 = self.m1
        self.assertEqual(list(m1.columns), COLONNES[1:])
        self.assertEqual(m1.index.name, "time")
        self.assertIsNone(m1.index.tz)
        self.assertTrue(m1.index.is_monotonic_increasing)
        self.assertFalse(m1.index.has_duplicates)
        for c in ("open", "high", "low", "close"):
            self.assertEqual(m1[c].dtype, np.float64)
            self.assertTrue(np.allclose(m1[c], m1[c].round(2), atol=1e-9, rtol=0))
        for c in ("tick_volume", "spread", "real_volume"):
            self.assertEqual(m1[c].dtype, np.int64)
        valider_bougies(m1, "synthetique")   # OHLC cohérents, prix > 0, entiers >= 0

    def test_aller_retour_csv_au_format_mt5(self):
        m1 = self.m1.iloc[:5000]
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "XAUUSD_M1.csv"
            m1.reset_index().to_csv(chemin, index=False, date_format=FORMAT_TIME, float_format="%.2f")
            relu = charger_bougies(chemin)
        pd.testing.assert_frame_equal(relu, m1, check_freq=False, atol=1e-9)

    def test_calendrier_et_heures_de_cotation(self):
        idx = self.m1.index
        self.assertTrue((idx.dayofweek < 5).all())
        minutes = idx.hour * 60 + idx.minute
        self.assertEqual(int(minutes.min()), 60)              # 01:00
        self.assertEqual(int(minutes.max()), 23 * 60 + 55)    # 23:55
        self.assertTrue((idx.second == 0).all())
        # quelques bougies manquantes, mais très peu
        jours = idx.normalize().nunique()
        self.assertLess(len(idx), jours * 1376)
        self.assertGreater(len(idx), jours * 1376 * 0.99)

    def test_volatilite_et_spread_realistes(self):
        m15 = reechantillonner(self.m1, "15min")
        etendue = m15["high"] - m15["low"]
        h = m15.index.hour + m15.index.minute / 60
        session = etendue[(h >= 9) & (h < 21)]
        self.assertGreater(session.median(), 3.0)
        self.assertLess(session.median(), 8.0)
        us = etendue[(h >= 15.5) & (h < 18)].median()
        matin = etendue[(h >= 10) & (h < 12)].median()
        nuit = etendue[(h >= 2) & (h < 5)].median()
        self.assertGreater(us, 1.3 * matin)
        self.assertGreater(matin, 1.5 * nuit)
        sp = self.m1["spread"]
        self.assertGreaterEqual(int(sp.min()), 15)
        self.assertGreater(((sp >= 15) & (sp <= 40)).mean(), 0.99)
        self.assertGreater(int(sp.max()), 40)                 # pics rares
        self.assertLess((sp > 40).mean(), 0.01)

    def test_marche_aleatoire_sans_memoire(self):
        # Rendements M1 non autocorrélés et dérive non significative : aucun avantage exploitable.
        c = self.m1["close"].to_numpy()
        r = np.diff(c)
        rho = np.corrcoef(r[:-1], r[1:])[0, 1]
        self.assertLess(abs(rho), 0.02)
        t = r.mean() / (r.std() / np.sqrt(len(r)))
        self.assertLess(abs(t), 4.0)
        # Les mèches font partie du chemin : open de la minute suivante = close précédente (à 1 centime près, hors trous).
        idx = self.m1.index
        contigu = (idx[1:] - idx[:-1]) == pd.Timedelta(minutes=1)
        ecart = np.abs(self.m1["open"].to_numpy()[1:] - c[:-1])[contigu]
        self.assertLessEqual(ecart.max(), 0.011)

    def test_reproductible(self):
        a = generer_m1("2024-03-04", "2024-03-09", graine=5)
        b = generer_m1("2024-03-04", "2024-03-09", graine=5)
        c = generer_m1("2024-03-04", "2024-03-09", graine=6)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a["close"].equals(c["close"]))
        self.assertAlmostEqual(a["open"].iloc[0], 3500.0, places=2)
        self.assertEqual(a.index.normalize().nunique(), 5)    # lundi -> vendredi, fin exclue

    def test_generer_jeu(self):
        m1, m15, h1 = generer_jeu("2024-03-04", "2024-03-09", graine=5)
        pd.testing.assert_frame_equal(m15, reechantillonner(m1, "15min"))
        pd.testing.assert_frame_equal(h1, reechantillonner(m1, "h"))
        self.assertEqual(list(m15.columns), COLONNES[1:])


if __name__ == "__main__":
    unittest.main()
