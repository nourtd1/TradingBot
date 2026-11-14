"""Tests de `scripts/recherche.py --cycle 2` : parcours complet, règle « P non évaluée », verrous du
contrôle final, séparation des dossiers des deux cycles et test des nouveaux marchés (données synthétiques)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import recherche as cli
from sentitrade.recherche import cycle2 as c2
from sentitrade.recherche.synthetique import generer_univers

SYMS = ["US500", "GER40", "EURUSD", "XAUUSD", "BTCUSD"]
SYMS_NOUVEAU_BROKER = ["US500", "EURUSD", "AUDUSD", "AUS200", "XTIUSD", "BTCUSD", "XAUUSD"]


def petit_univers(args, controle_final):
    syms = SYMS_NOUVEAU_BROKER if getattr(args, "nouveaux_marches", False) else SYMS
    return generer_univers(controle_final=controle_final, debut="2013-01-01", graine=args.graine, symboles=syms,
                           annees_m15=0)


def lancer(argv):
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie), mock.patch.object(cli, "_charger", petit_univers):
        code = cli.main(argv)
    return code, sortie.getvalue()


def retenu(code, resume):
    return {"criteres": [], "retenue": True, "decision": "RETENUE (simulé pour le test)", "criteres_ko": []}


class TestArgumentsCycle2(unittest.TestCase):

    def test_defaut_cycle_1_inchange(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--sortie", d, "--strategies", "C1"])
            self.assertIn("S1, S2, S3, S4", str(e.exception))
            with self.assertRaises(SystemExit):
                lancer(["--synthetique", "--sortie", d, "--cycle", "2", "--strategies", "S1"])
            with self.assertRaises(SystemExit):
                lancer(["--synthetique", "--sortie", d, "--tournant"])

    def test_lire_finalistes_cycle2(self):
        self.assertEqual(cli.lire_finalistes_cycle2("c1, P"), ["C1", "P"])
        for mauvais in ("C1,C2,P", "S1", "C1,C1", "S1+S2", ""):
            with self.assertRaises(SystemExit):
                cli.lire_finalistes_cycle2(mauvais)

    def test_nouveaux_marches_exige_la_reference(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                lancer(["--donnees", "x", "--sortie", d, "--nouveaux-marches", "--finalistes", "C1"])
            self.assertIn("--reference-univers", str(e.exception))
            with self.assertRaises(SystemExit):
                lancer(["--synthetique", "--sortie", d, "--cycle", "1", "--nouveaux-marches", "--finalistes", "C1"])


class TestParcoursCycle2(unittest.TestCase):

    def test_marche_aleatoire_rien_de_retenu_et_p_non_evaluee(self):
        with tempfile.TemporaryDirectory() as d:
            code, out = lancer(["--cycle", "2", "--synthetique", "--sortie", d])
            self.assertEqual(code, 0)
            racine = Path(d)
            r = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            self.assertEqual(r["cycle"], 2)
            self.assertEqual(r["verdict_global"]["decision"], "NO-GO")
            for c in ("C1", "C2"):
                v = r["strategies"][c]["verdict"]
                self.assertFalse(v["retenue"], c)
                self.assertEqual([x["numero"] for x in v["criteres"]], [1, 2, 3, 4, 5, 6, 7])
                self.assertIn("reference", r["strategies"][c])
                self.assertIn("capital", r["strategies"][c])
            self.assertEqual(r["strategies"]["C1"]["verdict"]["criteres"][2]["seuil"], ">= 3.0")
            self.assertFalse(r["composantes"]["S3"]["verdict"]["retenue"])
            p = r["strategies"]["P"]
            self.assertEqual(p["verdict"]["decision"], "NON ÉVALUÉE")
            self.assertFalse(p["evaluable"])
            self.assertNotIn("base", p)                       # P n'est même pas calculée
            self.assertFalse((racine / "equity_P.csv").exists())
            for f in ("rapport.md", "trades_C1.csv", "trades_C2.csv", "equity_C1.png", "equity_C2.png", "equity.png"):
                self.assertTrue((racine / f).exists(), f)
            rapport = (racine / "rapport.md").read_text(encoding="utf-8")
            self.assertTrue(rapport.split("\n## ")[1].startswith("En bref"))
            self.assertIn("NON ÉVALUÉE", rapport)
            self.assertIn("cycle 2", rapport)
            self.assertIn("P : NON ÉVALUÉE", out)

    def test_dossiers_des_deux_cycles_separes(self):
        with tempfile.TemporaryDirectory() as d:
            lancer(["--synthetique", "--sortie", d, "--strategies", "S3", "--sections", "base"])
            with self.assertRaises(SystemExit) as e:
                lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--strategies", "C1", "--sections", "base"])
            self.assertIn("cycle 2", str(e.exception))
        with tempfile.TemporaryDirectory() as d:
            lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--strategies", "C1", "--sections", "base"])
            with self.assertRaises(SystemExit) as e:
                lancer(["--synthetique", "--sortie", d, "--strategies", "S3", "--sections", "base"])
            self.assertIn("CYCLE 2", str(e.exception))
            with self.assertRaises(SystemExit):
                lancer(["--synthetique", "--sortie", d, "--controle-final", "--finalistes", "S3"])

    def test_verrous_du_controle_final(self):
        with tempfile.TemporaryDirectory() as d:
            racine = Path(d)
            with self.assertRaises(SystemExit) as e:          # pas encore de développement
                lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--controle-final", "--finalistes", "C1"])
            self.assertIn("introuvable", str(e.exception))
            lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--strategies", "C1,C2,P"])
            with self.assertRaises(SystemExit) as e:          # non retenue
                lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--controle-final", "--finalistes", "C1"])
            self.assertIn("RETENUE", str(e.exception))
            with self.assertRaises(SystemExit) as e:          # P non évaluée : refusée
                lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--controle-final", "--finalistes", "P"])
            self.assertIn("NON ÉVALUÉE", str(e.exception))
            with self.assertRaises(SystemExit) as e:          # données changées
                with mock.patch.object(c2, "verdict", retenu):
                    lancer(["--cycle", "2", "--synthetique", "--graine", "2", "--sortie", d, "--controle-final",
                            "--finalistes", "C1"])
            self.assertIn("diffèrent", str(e.exception))
            # hypothèses supposées retenues (test du mécanisme uniquement)
            with mock.patch.object(c2, "verdict", retenu):
                code, out = lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--controle-final",
                                    "--finalistes", "C1,P"])
            self.assertEqual(code, 0)
            r = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            for f in ("C1", "P"):
                cf = r["controle_final"]["finalistes"][f]
                self.assertGreaterEqual(cf["debut"], "2025-11-14")
                self.assertLessEqual(cf["fin"], "2026-11-13")
                self.assertIsNotNone(cf["p5_pct"])
                self.assertTrue(cf["verdict"]["decision"].startswith(("CONFIRMÉE", "NON CONFIRMÉE")))
                self.assertTrue((racine / f"trades_controle_{f}.csv").exists())
            self.assertIn("Contrôle final", (racine / "rapport.md").read_text(encoding="utf-8"))
            with self.assertRaises(SystemExit) as e:          # une seule fois
                with mock.patch.object(c2, "verdict", retenu):
                    lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--controle-final", "--finalistes", "C2"])
            self.assertIn("DÉJÀ", str(e.exception))

    def test_nouveaux_marches_seulement_les_symboles_absents_de_la_reference(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as ref:
            racine = Path(d)
            lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--strategies", "C1,C2,P", "--sections",
                    "base,robustesse"])
            with self.assertRaises(SystemExit) as e:          # non retenue : refusé
                lancer(["--cycle", "2", "--synthetique", "--sortie", d, "--nouveaux-marches", "--finalistes", "C2"])
            self.assertIn("RETENUE", str(e.exception))
            # univers de référence : univers.json avec en plus XAUUSD (déjà vu) et UK100
            (Path(ref) / "univers.json").write_text(json.dumps({"symboles": {
                k: {"classe": "x"} for k in SYMS + ["UK100"]}}), encoding="utf-8")
            with mock.patch.object(c2, "verdict", retenu):
                code, out = lancer(["--synthetique", "--sortie", d, "--nouveaux-marches", "--reference-univers", ref,
                                    "--finalistes", "C1,C2"])
                self.assertEqual(code, 0)
                r = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
                nm = r["nouveaux_marches"]
                self.assertEqual(sorted(nm["nouveaux"]), ["AUDUSD", "AUS200", "XTIUSD"])
                self.assertEqual(nm["finalistes"]["C1"]["symboles"], ["AUS200"])
                self.assertEqual(nm["finalistes"]["C2"]["symboles"], ["AUS200", "XTIUSD"])   # pas de forex
                self.assertLessEqual(nm["finalistes"]["C2"]["fin"], "2025-11-13")            # développement seulement
                for f in ("C1", "C2"):
                    v = nm["finalistes"][f]["verdict"]
                    self.assertEqual(v["ok"], nm["finalistes"][f]["sharpe"] is not None and nm["finalistes"][f]["sharpe"] >= 0)
                self.assertIn("Nouveaux marchés", (racine / "rapport.md").read_text(encoding="utf-8"))
                # P : composantes restreintes aux nouveaux symboles
                lancer(["--synthetique", "--sortie", d, "--nouveaux-marches", "--reference-univers", ref,
                        "--finalistes", "P"])
            r = json.loads((racine / "resume.json").read_text(encoding="utf-8"))
            self.assertEqual(r["nouveaux_marches"]["finalistes"]["P"]["symboles"], ["AUS200", "XTIUSD"])
            # le développement du cycle 2 n'a pas été modifié
            self.assertEqual(r["strategies"]["C1"]["base"]["nb_symboles"], 2)


if __name__ == "__main__":
    unittest.main()
