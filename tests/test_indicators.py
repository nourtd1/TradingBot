"""Tests de sentitrade/indicators.py : EMA, ranges journaliers, filtre ADR (spec §3, §8)."""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from sentitrade.indicators import ema, filtre_adr, ranges_journaliers


def _ranges(valeurs, debut="2024-01-01"):
    return pd.Series(np.asarray(valeurs, dtype=float),
                     index=pd.date_range(debut, periods=len(valeurs), freq="D", name="date"))


class TestEma(unittest.TestCase):
    def test_recursion_manuelle(self):
        x = pd.Series([10.0, 11.0, 13.0, 12.0, 15.0])
        a = 2 / (3 + 1)
        attendu = [10.0]
        for v in x.iloc[1:]:
            attendu.append(a * v + (1 - a) * attendu[-1])
        np.testing.assert_allclose(ema(x, 3).to_numpy(), attendu, rtol=0, atol=1e-12)

    def test_causale(self):
        rng = np.random.default_rng(1)
        x = pd.Series(rng.normal(size=300).cumsum())
        y = x.copy()
        y.iloc[200:] += 50.0
        np.testing.assert_array_equal(ema(x, 20).to_numpy()[:200], ema(y, 20).to_numpy()[:200])


class TestRangesJournaliers(unittest.TestCase):
    def test_par_date_serveur(self):
        idx = pd.DatetimeIndex(["2024-01-02 22:00", "2024-01-02 23:00", "2024-01-03 00:00", "2024-01-03 01:00"])
        h1 = pd.DataFrame({"open": [10, 10, 10, 10.0], "high": [12, 15, 11, 13.0],
                           "low": [9, 8, 7, 10.0], "close": [10, 10, 10, 10.0]}, index=idx)
        r = ranges_journaliers(h1)
        self.assertEqual(list(r.index), [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")])
        # la bougie de 23:00 (clôture à 00:00 le 3) appartient au 2
        self.assertEqual(r.loc["2024-01-02"], 15 - 8)
        self.assertEqual(r.loc["2024-01-03"], 13 - 7)


class TestFiltreAdr(unittest.TestCase):
    def test_exemple_a_la_main(self):
        r = _ranges([10, 20, 30, 40, 100])
        f = filtre_adr(r, periode=2, reference=3, ratio_min=0.5, ratio_max=2.0)
        # jours 1 à 3 : moins de 3 jours antérieurs -> interdit
        self.assertEqual(list(f.iloc[:3]), [False, False, False])
        # jour 4 (index 3) : ADR = moy(20, 30) = 25, REF = méd(10, 20, 30) = 20 -> 1.25 ok
        self.assertTrue(f.iloc[3])
        # jour 5 (index 4) : ADR = moy(30, 40) = 35, REF = méd(20, 30, 40) = 30 -> ok ; le 100 du jour n'est pas utilisé
        self.assertTrue(f.iloc[4])
        self.assertEqual(f.dtype, bool)
        self.assertEqual(f.index.name, "date")

    def test_ratio_hors_bornes_et_bornes_incluses(self):
        # ADR = moy(40, 40) = 40, REF = méd(10, 20, 40, 40) -> 30 ; ratio 1.333
        r = _ranges([10, 20, 40, 40, 0])
        self.assertFalse(filtre_adr(r, 2, 4, 0.5, 1.3).iloc[4])
        self.assertTrue(filtre_adr(r, 2, 4, 0.5, 1.34).iloc[4])
        # ratio exactement égal à la borne -> autorisé
        r = _ranges([10, 10, 10, 20, 0])  # ADR = moy(10, 20) = 15, REF = méd(10,10,10,20) = 10 -> 1.5
        self.assertTrue(filtre_adr(r, 2, 4, 0.5, 1.5).iloc[4])
        r = _ranges([10, 10, 10, 5, 0])  # ADR = 7.5, REF = 10 -> 0.75
        self.assertTrue(filtre_adr(r, 2, 4, 0.75, 2.0).iloc[4])
        self.assertFalse(filtre_adr(r, 2, 4, 0.76, 2.0).iloc[4])

    def test_jour_d_n_utilise_pas_d(self):
        rng = np.random.default_rng(2)
        r = _ranges(rng.uniform(10, 30, 200))
        base = filtre_adr(r, 14, 100, 0.5, 2.0)
        for k in (120, 150, 199):
            modifie = r.copy()
            modifie.iloc[k] = 1e6  # range absurde le jour D
            f = filtre_adr(modifie, 14, 100, 0.5, 2.0)
            self.assertEqual(f.iloc[k], base.iloc[k], f"le jour {k} a utilisé son propre range")
            if k + 1 < len(r):
                self.assertFalse(f.iloc[k + 1])  # ... mais le lendemain le voit bien

    def test_non_anticipation(self):
        rng = np.random.default_rng(3)
        r = _ranges(rng.uniform(10, 30, 250))
        base = filtre_adr(r, 14, 100, 0.5, 2.0)
        for k in (101, 130, 249):
            futur = r.copy()
            futur.iloc[k:] = rng.uniform(0, 1000, len(r) - k)
            f = filtre_adr(futur, 14, 100, 0.5, 2.0)
            pd.testing.assert_series_equal(f.iloc[:k + 1], base.iloc[:k + 1])
            tronque = filtre_adr(r.iloc[:k], 14, 100, 0.5, 2.0, dates=r.index[:k + 1])
            pd.testing.assert_series_equal(tronque, base.iloc[:k + 1])

    def test_historique_insuffisant(self):
        r = _ranges(np.full(100, 20.0))
        f = filtre_adr(r, 14, 100, 0.5, 2.0)
        self.assertFalse(f.any())  # le jour 100 n'a que 99 jours antérieurs
        f = filtre_adr(_ranges(np.full(101, 20.0)), 14, 100, 0.5, 2.0)
        self.assertFalse(f.iloc[:100].any())
        self.assertTrue(f.iloc[100])

    def test_nan_et_reference_nulle_interdits(self):
        r = _ranges([10, np.nan, 10, 10, 10])
        f = filtre_adr(r, 2, 3, 0.5, 2.0)
        self.assertFalse(f.iloc[3])  # fenêtre REF contient le NaN
        r = _ranges([0, 0, 0, 0, 0])
        self.assertFalse(filtre_adr(r, 2, 3, 0.5, 2.0).any())

    def test_dates_absentes_des_ranges(self):
        r = _ranges([10, 20, 30, 40])  # 1er au 4 janvier
        dates = pd.DatetimeIndex(["2024-01-04", "2024-01-05 13:00", "2024-01-10", "2023-12-01"])
        f = filtre_adr(r, 2, 3, 0.5, 2.0, dates=dates)
        # le 4 : jours 1-3 -> ADR 25, REF 20 ; le 5 et le 10 : jours 1-4 -> ADR 35, REF 30 ; 2023 : aucun historique
        self.assertEqual(list(f), [True, True, True, False])
        self.assertEqual(f.index[1], pd.Timestamp("2024-01-05"))


if __name__ == "__main__":
    unittest.main()
