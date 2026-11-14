"""Tests de scripts/recherche.py : sections conservées, rapport, garde-fous du contrôle final."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import recherche as cli
from sentitrade.recherche.synthetique import generer_univers

SYMS = ["USDJPY", "US500", "XAUUSD", "AUDUSD"]


def petit_univers(args, controle_final):
    return generer_univers(controle_final=controle_final, debut="2014-01-01", graine=args.graine, symboles=SYMS,
                           annees_m15=1.5)


def lancer(argv):
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie), mock.patch.object(cli, "_charger", petit_univers):
        code = cli.main(argv)
    return code, sortie.getvalue()


class TestArguments(unittest.TestCase):

    def test_controle_final_exige_des_finalistes(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--sortie", d, "--controle-final"])
            self.assertIn("--finalistes", str(e.exception))
            with self.assertRaises(SystemExit):
                lancer(["--synthetique", "--sortie", d, "--finalistes", "S1"])

    def test_lire_finalistes(self):
        self.assertEqual(cli.lire_finalistes("s1, S2"), ["S1", "S2"])
        self.assertEqual(cli.lire_finalistes("S1+S2"), ["S1+S2"])
        for mauvais in ("S1,S2,S3", "S5", "S1,S1", ""):
            with self.assertRaises(SystemExit):
                cli.lire_finalistes(mauvais)


class TestParcours(unittest.TestCase):

    def test_developpement_puis_controle_final(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = lancer(["--synthetique", "--sortie", d, "--strategies", "S1,S3", "--sections", "base"])
            self.assertEqual(code, 0)
            racine = Path(d)
            for f in ("rapport.md", "resume.json", "trades_S1.csv", "equity_S1.png", "equity_S3.csv", "equity.png"):
                self.assertTrue((racine / f).exists(), f)
            r = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            self.assertIn(6, r["strategies"]["S1"]["verdict"]["criteres_ko"])
            self.assertIn("incomplet", r["verdict_global"]["explication"])
            sig = r["signature"]
            # seconde commande : sections ajoutées, résultats de la première conservés
            code, _ = lancer(["--synthetique", "--sortie", d, "--strategies", "S1", "--sections", "robustesse,capital"])
            r2 = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            self.assertEqual(r2["signature"], sig)
            self.assertEqual(r2["strategies"]["S1"]["base"]["nb_trades"], r["strategies"]["S1"]["base"]["nb_trades"])
            self.assertIn("S3", r2["strategies"])
            self.assertIn("couts_doubles", r2["strategies"]["S1"]["robustesse"])
            self.assertIn("sim_20_cent", r2["strategies"]["S1"]["capital"])
            rapport = (racine / "rapport.md").read_text(encoding="utf-8")
            self.assertTrue(rapport.split("\n## ")[1].startswith("En bref"))
            self.assertIn("20 $", rapport)
            # hold-out : refusé tant qu'aucun finaliste n'est RETENU
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--sortie", d, "--controle-final", "--finalistes", "S1"])
            self.assertIn("RETENUE", str(e.exception))
            # on simule une hypothèse retenue (test du mécanisme uniquement)
            r2["strategies"]["S1"]["verdict"]["retenue"] = True
            (racine / "resume.json").write_text(json.dumps(r2), encoding="utf-8")
            with mock.patch.object(cli.ev, "verdict_strategie", lambda c, b, rb, rf: {
                    "criteres": [], "retenue": c == "S1", "decision": "x", "criteres_ko": []}):
                code, out = lancer(["--synthetique", "--sortie", d, "--controle-final", "--finalistes", "S1"])
            self.assertEqual(code, 0)
            r3 = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            cf = r3["controle_final"]["finalistes"]["S1"]
            self.assertGreaterEqual(cf["debut"], "2025-11-14")
            self.assertLessEqual(cf["fin"], "2026-11-13")
            self.assertIn(cf["verdict"]["decision"], ("GO paper trading", "NO-GO"))
            self.assertIsNotNone(cf["p5_pct"])
            # une seule fois
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--sortie", d, "--controle-final", "--finalistes", "S1"])
            self.assertIn("DÉJÀ", str(e.exception))

    def test_donnees_differentes_refusees(self):
        with tempfile.TemporaryDirectory() as d:
            lancer(["--synthetique", "--sortie", d, "--strategies", "S3", "--sections", "base"])
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--graine", "2", "--sortie", d, "--controle-final", "--finalistes", "S3"])
            self.assertIn("diffèrent", str(e.exception))


if __name__ == "__main__":
    unittest.main()
