"""Tests de sentitrade/data.py : chargement, validation, rééchantillonnage (spec §2, §7, §8)."""
from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from sentitrade.data import charger_bougies, reechantillonner

ENTETE = "time,open,high,low,close,tick_volume,spread,real_volume\n"


class _Fichiers(unittest.TestCase):
    def setUp(self):
        self._dossier = tempfile.TemporaryDirectory()
        self.dossier = Path(self._dossier.name)

    def tearDown(self):
        self._dossier.cleanup()

    def ecrire(self, lignes, entete=ENTETE, nom="XAUUSD_M15.csv"):
        chemin = self.dossier / nom
        chemin.write_text(entete + "".join(l + "\n" for l in lignes), encoding="utf-8")
        return chemin


class TestChargerBougies(_Fichiers):
    def test_chargement_types_et_index(self):
        chemin = self.ecrire([
            "2024-01-02 10:00:00,2050.10,2051.00,2049.50,2050.80,120,25,0",
            "2024-01-02 10:15:00,2050.80,2052.30,2050.70,2052.00,98,30,0",
        ])
        df = charger_bougies(chemin)
        self.assertEqual(list(df.columns), ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
        self.assertIsInstance(df.index, pd.DatetimeIndex)
        self.assertEqual(df.index.name, "time")
        self.assertIsNone(df.index.tz)
        self.assertEqual(df.index[0], pd.Timestamp("2024-01-02 10:00:00"))
        for c in ("open", "high", "low", "close"):
            self.assertEqual(df[c].dtype, np.float64)
        for c in ("tick_volume", "spread", "real_volume"):
            self.assertEqual(df[c].dtype, np.int64)
        self.assertEqual(df["spread"].iloc[1], 30)
        self.assertAlmostEqual(df["high"].iloc[1], 2052.30)

    def test_ohlc_incoherent_refuse_avec_detail(self):
        cas = {
            "high_sous_close": "2024-01-02 10:15:00,2050.00,2050.50,2049.00,2051.00,1,20,0",
            "low_sur_open": "2024-01-02 10:15:00,2050.00,2052.00,2050.50,2051.00,1,20,0",
            "high_sous_low": "2024-01-02 10:15:00,2050.00,2049.00,2051.00,2050.00,1,20,0",
        }
        for nom, ligne in cas.items():
            with self.subTest(nom):
                chemin = self.ecrire(["2024-01-02 10:00:00,2050.00,2051.00,2049.00,2050.50,1,20,0", ligne])
                with self.assertRaises(ValueError) as ctx:
                    charger_bougies(chemin)
                self.assertIn("OHLC", str(ctx.exception))
                self.assertIn("2024-01-02 10:15:00", str(ctx.exception))

    def test_valeurs_invalides_refusees(self):
        cas = {
            "prix_manquant": "2024-01-02 10:00:00,2050.00,,2049.00,2050.50,1,20,0",
            "prix_texte": "2024-01-02 10:00:00,abc,2051.00,2049.00,2050.50,1,20,0",
            "prix_nul": "2024-01-02 10:00:00,0,2051.00,0,2050.50,1,20,0",
            "spread_negatif": "2024-01-02 10:00:00,2050.00,2051.00,2049.00,2050.50,1,-3,0",
            "spread_non_entier": "2024-01-02 10:00:00,2050.00,2051.00,2049.00,2050.50,1,20.5,0",
            "date_mauvais_format": "02/01/2024 10:00,2050.00,2051.00,2049.00,2050.50,1,20,0",
        }
        for nom, ligne in cas.items():
            with self.subTest(nom):
                with self.assertRaises(ValueError):
                    charger_bougies(self.ecrire([ligne]))

    def test_colonnes_exactes(self):
        with self.assertRaises(ValueError):
            charger_bougies(self.ecrire(["2024-01-02 10:00:00,2050,2051,2049,2050.5,1,0"],
                                        entete="time,open,high,low,close,tick_volume,real_volume\n"))
        with self.assertRaises(ValueError):
            charger_bougies(self.ecrire(["2024-01-02 10:00:00,2050,2051,2049,2050.5,1,20,0,9"],
                                        entete=ENTETE.strip() + ",extra\n"))

    def test_fichier_vide_refuse(self):
        with self.assertRaises(ValueError):
            charger_bougies(self.ecrire([]))

    def test_doublons_dernier_garde_et_signale(self):
        chemin = self.ecrire([
            "2024-01-02 10:00:00,2050.00,2051.00,2049.00,2050.50,1,20,0",
            "2024-01-02 10:15:00,2050.50,2051.00,2050.00,2050.80,1,20,0",
            "2024-01-02 10:15:00,2050.50,2053.00,2050.00,2052.00,7,25,0",
        ])
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df = charger_bougies(chemin)
        self.assertTrue(any("doublon" in str(x.message) for x in w))
        self.assertEqual(len(df), 2)
        self.assertTrue(df.index.is_unique)
        self.assertAlmostEqual(df.loc["2024-01-02 10:15:00", "high"], 2053.00)
        self.assertEqual(df.loc["2024-01-02 10:15:00", "tick_volume"], 7)

    def test_tri(self):
        chemin = self.ecrire([
            "2024-01-02 10:15:00,2050.50,2051.00,2050.00,2050.80,1,20,0",
            "2024-01-02 10:00:00,2050.00,2051.00,2049.00,2050.50,1,20,0",
        ])
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            df = charger_bougies(chemin)
        self.assertTrue(df.index.is_monotonic_increasing)
        self.assertEqual(df.index[0], pd.Timestamp("2024-01-02 10:00:00"))


def _m1(debut: str, n: int) -> pd.DataFrame:
    idx = pd.date_range(debut, periods=n, freq="1min", name="time")
    o = 2000 + np.arange(n, dtype=float)
    return pd.DataFrame({
        "open": o, "high": o + 2.0, "low": o - 1.0, "close": o + 0.5,
        "tick_volume": np.arange(1, n + 1, dtype=np.int64),
        "spread": (np.arange(n) % 7 + 10).astype(np.int64),
        "real_volume": np.zeros(n, dtype=np.int64),
    }, index=idx)


class TestReechantillonner(unittest.TestCase):
    def test_m1_vers_m15_agregats(self):
        df = _m1("2024-01-02 10:00", 30)
        m15 = reechantillonner(df, "15min")
        self.assertEqual(list(m15.index), [pd.Timestamp("2024-01-02 10:00"), pd.Timestamp("2024-01-02 10:15")])
        premiere = df.iloc[:15]
        r = m15.iloc[0]
        self.assertEqual(r["open"], premiere["open"].iloc[0])
        self.assertEqual(r["high"], premiere["high"].max())
        self.assertEqual(r["low"], premiere["low"].min())
        self.assertEqual(r["close"], premiere["close"].iloc[-1])
        self.assertEqual(r["tick_volume"], premiere["tick_volume"].sum())
        self.assertEqual(r["spread"], premiere["spread"].max())
        self.assertEqual(m15["tick_volume"].dtype, np.int64)
        self.assertEqual(m15["spread"].dtype, np.int64)

    def test_fermeture_et_label_a_gauche(self):
        # La bougie M1 de 10:15 appartient à la M15 de 10:15 (période [10:15, 10:30)), pas à 10:00.
        df = _m1("2024-01-02 10:14", 2)
        m15 = reechantillonner(df, "15min")
        self.assertEqual(list(m15.index), [pd.Timestamp("2024-01-02 10:00"), pd.Timestamp("2024-01-02 10:15")])
        self.assertEqual(m15.loc["2024-01-02 10:15", "open"], df.loc["2024-01-02 10:15", "open"])

    def test_periodes_vides_supprimees(self):
        a = _m1("2024-01-02 10:00", 15)
        b = _m1("2024-01-02 12:00", 15)
        h1 = reechantillonner(pd.concat([a, b]), "h")
        self.assertEqual(list(h1.index), [pd.Timestamp("2024-01-02 10:00"), pd.Timestamp("2024-01-02 12:00")])
        self.assertFalse(h1.isna().any().any())

    def test_m15_vers_h1_coherent(self):
        m15 = reechantillonner(_m1("2024-01-02 00:00", 600), "15min")
        h1_direct = reechantillonner(_m1("2024-01-02 00:00", 600), "h")
        h1_via_m15 = reechantillonner(m15, "h")
        pd.testing.assert_frame_equal(h1_direct, h1_via_m15)

    def test_colonne_inconnue_refusee(self):
        df = _m1("2024-01-02 10:00", 5)
        df["autre"] = 1.0
        with self.assertRaises(ValueError):
            reechantillonner(df, "15min")


if __name__ == "__main__":
    unittest.main()
