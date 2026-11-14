"""Tests de sentitrade/risk_manager.py (SPEC_TECHNIQUE §4 et §8 « Risque »).

Chaque test énonce la règle qu'il protège : si l'un d'eux échoue, aucun passage en réel.
"""
from __future__ import annotations

import dataclasses
import math
import random
import unittest
from datetime import date
from decimal import Decimal

from sentitrade.config import RisqueConfig, SymboleSpec
from sentitrade.risk_manager import (
    GardeRisque,
    ResultatTaille,
    calculer_taille_lot,
    decouper_volume,
)

CFG = RisqueConfig()          # 1 %, -3 %/jour, -15 % DD, levier 10, lot divisible exigé
SPEC = SymboleSpec()          # contrat 100 oz, min 0.01, pas 0.01, max 100
CONTRAT = 100.0
PRIX = 4000.0
NOTIONNEL = PRIX * CONTRAT    # 400 000 $ par lot


def taille(balance, perte, notionnel=NOTIONNEL, cfg=CFG, spec=SPEC):
    return calculer_taille_lot(balance, cfg, perte, notionnel, spec)


def est_multiple(lots: float, pas: float) -> bool:
    return Decimal(repr(lots)) % Decimal(repr(pas)) == 0


class TestTailleCalculeeALaMain(unittest.TestCase):

    def test_cas_nominal_sl_5_dollars(self):
        # 3000 × 1 % = 30 $ ; perte/lot = 5 $ × 100 oz = 500 $ ; 30/500 = 0.06 lot.
        # Levier : 0.06 × 400 000 / 3000 = 8 (≤ 10, non limitant).
        r = taille(3000.0, 5.0 * CONTRAT)
        self.assertIsInstance(r, ResultatTaille)
        self.assertTrue(r.accepte)
        self.assertEqual(r.lots, 0.06)
        self.assertEqual(r.raison, "ok")
        self.assertAlmostEqual(r.risque_montant, 30.0, places=12)
        self.assertAlmostEqual(r.risque_pct, 1.0, places=12)
        self.assertAlmostEqual(r.levier_effectif, 8.0, places=12)

    def test_plafond_levier_sl_2_dollars(self):
        # Risque : 30 / 200 = 0.15 lot ; levier : 10 × 3000 / 400 000 = 0.075 -> 0.07 lot.
        r = taille(3000.0, 2.0 * CONTRAT)
        self.assertTrue(r.accepte)
        self.assertEqual(r.lots, 0.07)
        self.assertEqual(r.raison, "plafond_levier")
        self.assertAlmostEqual(r.levier_effectif, 0.07 * 400_000 / 3000, places=12)  # 9.33
        self.assertLessEqual(r.levier_effectif, CFG.levier_effectif_max)
        self.assertAlmostEqual(r.risque_montant, 30.0, places=12)
        self.assertAlmostEqual(r.risque_pct, 0.07 * 200 / 3000 * 100, places=12)
        self.assertLess(r.risque_pct, CFG.risque_par_trade_pct)

    def test_plafond_volume_max(self):
        spec = dataclasses.replace(SPEC, volume_max=0.05)
        r = taille(3000.0, 500.0, spec=spec)
        self.assertTrue(r.accepte)
        self.assertEqual(r.lots, 0.05)
        self.assertEqual(r.raison, "plafond_volume_max")

    def test_commission_incluse_dans_perte_par_lot(self):
        # SL 5 $ + 7 $ de commission par lot : 30 / 507 = 0.0591 -> 0.05 (et non 0.06).
        sans = taille(3000.0, 500.0)
        avec = taille(3000.0, 500.0 + 7.0)
        self.assertEqual(sans.lots, 0.06)
        self.assertEqual(avec.lots, 0.05)
        self.assertLessEqual(avec.lots * 507.0, avec.risque_montant)
        # Sans compter la commission, 0.06 lot coûterait 0.06 × 507 = 30.42 $ > 30 $.
        self.assertGreater(0.06 * 507.0, 30.0)

    def test_resultat_gele(self):
        r = taille(3000.0, 500.0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            r.lots = 1.0  # type: ignore[misc]


class TestArrondiVersLeBas(unittest.TestCase):
    """Pièges flottants : 0.07/0.01 = 7.000000000000001, 0.29/0.01 = 28.999999999999996, etc."""

    PETIT_NOTIONNEL = 1000.0   # le levier ne limite pas dans ces cas

    def verifier(self, r, attendu, perte):
        self.assertTrue(r.accepte, r)
        self.assertEqual(r.lots, attendu)
        self.assertLessEqual(r.lots * perte, r.risque_montant * (1 + 1e-9))

    def test_0_07_exact(self):
        self.assertGreater(0.07 / 0.01, 7)  # le piège existe bien
        self.verifier(taille(3500.0, 500.0, self.PETIT_NOTIONNEL), 0.07, 500.0)

    def test_0_29_exact(self):
        self.assertLess(0.29 / 0.01, 29)  # en flottant naïf on perdrait un pas
        self.verifier(taille(14500.0, 500.0, self.PETIT_NOTIONNEL), 0.29, 500.0)

    def test_0_06_exact(self):
        self.verifier(taille(3000.0, 500.0, self.PETIT_NOTIONNEL), 0.06, 500.0)

    def test_presque_6_pas_donne_5(self):
        # 2999.99999 × 1 % / 500 = 0.0599999998 : 5.99999998 pas -> 5 pas, jamais 6.
        for balance in (2999.99999, 2999.9999999, 2999.99999999999):
            r = taille(balance, 500.0, self.PETIT_NOTIONNEL)
            self.verifier(r, 0.05, 500.0)

    def test_pas_de_0_1(self):
        spec = dataclasses.replace(SPEC, volume_min=0.1, volume_pas=0.1)
        self.assertLess(0.3 / 0.1, 3)
        # 15000 × 1 % / 500 = 0.3 -> 0.3 (exact)
        self.verifier(taille(15000.0, 500.0, self.PETIT_NOTIONNEL, spec=spec), 0.3, 500.0)
        # 14999 -> 0.29998 -> 0.2
        self.verifier(taille(14999.0, 500.0, self.PETIT_NOTIONNEL, spec=spec), 0.2, 500.0)

    def test_pas_de_1(self):
        spec = dataclasses.replace(SPEC, volume_min=1.0, volume_pas=1.0)
        self.verifier(taille(150000.0, 500.0, self.PETIT_NOTIONNEL, spec=spec), 3.0, 500.0)
        self.verifier(taille(149999.0, 500.0, self.PETIT_NOTIONNEL, spec=spec), 2.0, 500.0)

    def test_lots_arrondis_au_nombre_de_decimales_du_pas(self):
        for balance in (3000.0, 3500.0, 14500.0, 7473.71, 11704.56):
            r = taille(balance, 439.63, self.PETIT_NOTIONNEL)
            self.assertTrue(r.accepte)
            self.assertEqual(r.lots, round(r.lots, 2))
            self.assertTrue(est_multiple(r.lots, 0.01))


class TestRefus(unittest.TestCase):

    def test_lot_non_divisible_balance_500(self):
        # 500 × 1 % / 500 = 0.01 lot : >= minimum mais < 2 × 0.01 -> insécable à TP1.
        r = taille(500.0, 500.0)
        self.assertFalse(r.accepte)
        self.assertEqual(r.raison, "lot_non_divisible")
        self.assertEqual(r.lots, 0.0)

    def test_lot_non_divisible_desactive(self):
        cfg = dataclasses.replace(CFG, exiger_lot_divisible=False)
        r = taille(500.0, 500.0, cfg=cfg)
        self.assertTrue(r.accepte)
        self.assertEqual(r.lots, 0.01)
        self.assertEqual(r.raison, "ok")

    def test_lot_sous_minimum_jamais_arrondi_au_minimum(self):
        # 400 × 1 % / 500 = 0.008 lot < 0.01 : refus, même sans exigence de divisibilité.
        cfg = dataclasses.replace(CFG, exiger_lot_divisible=False)
        r = taille(400.0, 500.0, cfg=cfg)
        self.assertFalse(r.accepte)
        self.assertEqual(r.raison, "lot_inferieur_minimum")
        self.assertEqual(r.lots, 0.0)
        self.assertAlmostEqual(r.risque_montant, 4.0, places=12)

    def test_minimum_broker_superieur_au_pas(self):
        # volume_min = 0.1 : 0.06 lot possible au pas, mais sous le minimum -> refus.
        spec = dataclasses.replace(SPEC, volume_min=0.1)
        r = taille(3000.0, 500.0, spec=spec)
        self.assertFalse(r.accepte)
        self.assertEqual(r.raison, "lot_inferieur_minimum")

    def test_levier_qui_fait_tomber_sous_le_minimum(self):
        # Levier : 10 × 30 / 400 000 = 0.00075 lot -> refus.
        cfg = dataclasses.replace(CFG, exiger_lot_divisible=False)
        r = taille(30.0, 1.0, cfg=cfg)
        self.assertFalse(r.accepte)
        self.assertEqual(r.raison, "lot_inferieur_minimum")


class TestEntreesInvalides(unittest.TestCase):

    MAUVAISES = (0, 0.0, -1.0, -500.0, float("nan"), float("inf"), float("-inf"),
                 None, "3000", True, [1.0])

    def test_arguments_numeriques(self):
        for champ in ("balance", "perte_par_lot", "notionnel_par_lot"):
            for mauvais in self.MAUVAISES:
                args = {"balance": 3000.0, "perte_par_lot": 500.0, "notionnel_par_lot": NOTIONNEL}
                args[champ] = mauvais
                with self.subTest(champ=champ, valeur=mauvais):
                    r = calculer_taille_lot(args["balance"], CFG, args["perte_par_lot"],
                                            args["notionnel_par_lot"], SPEC)
                    self.assertFalse(r.accepte)
                    self.assertEqual(r.lots, 0.0)
                    self.assertEqual(r.raison, f"entree_invalide:{champ}")

    def test_config_et_spec(self):
        cas = [
            (dataclasses.replace(CFG, risque_par_trade_pct=0.0), SPEC, "risque_par_trade_pct"),
            (dataclasses.replace(CFG, risque_par_trade_pct=float("nan")), SPEC, "risque_par_trade_pct"),
            (dataclasses.replace(CFG, risque_par_trade_pct=5.0), SPEC, "risque_par_trade_pct"),
            (dataclasses.replace(CFG, levier_effectif_max=-1.0), SPEC, "levier_effectif_max"),
            (dataclasses.replace(CFG, levier_effectif_max=float("inf")), SPEC, "levier_effectif_max"),
            (dataclasses.replace(CFG, levier_effectif_max=100.0), SPEC, "levier_effectif_max"),
            (CFG, dataclasses.replace(SPEC, volume_min=0.0), "volume_min"),
            (CFG, dataclasses.replace(SPEC, volume_pas=float("nan")), "volume_pas"),
            (CFG, dataclasses.replace(SPEC, volume_pas=-0.01), "volume_pas"),
            (CFG, dataclasses.replace(SPEC, volume_max=0.0), "volume_max"),
            (CFG, dataclasses.replace(SPEC, volume_max=0.001), "volume_max"),  # < volume_min
            (None, SPEC, "risque_par_trade_pct"),
            (CFG, None, "volume_min"),
        ]
        for cfg, spec, champ in cas:
            with self.subTest(champ=champ):
                r = calculer_taille_lot(3000.0, cfg, 500.0, NOTIONNEL, spec)
                self.assertFalse(r.accepte)
                self.assertEqual(r.lots, 0.0)
                self.assertEqual(r.raison, f"entree_invalide:{champ}")

    def test_decouper_entrees_invalides_sans_exception(self):
        self.assertEqual(decouper_volume(0.06, 0.0, SPEC), (0.0, 0.06))
        self.assertEqual(decouper_volume(0.06, 1.0, SPEC), (0.0, 0.06))
        self.assertEqual(decouper_volume(0.06, float("nan"), SPEC), (0.0, 0.06))
        self.assertEqual(decouper_volume(-0.06, 0.5, SPEC), (0.0, -0.06))
        self.assertEqual(decouper_volume(float("nan"), 0.5, SPEC), (0.0, 0.0))
        self.assertEqual(decouper_volume(None, 0.5, SPEC), (0.0, 0.0))
        self.assertEqual(decouper_volume(0.06, 0.5, None), (0.0, 0.06))


class TestPropriete(unittest.TestCase):
    """10 000 combinaisons aléatoires (graine fixe) : les garanties tiennent toujours."""

    def test_garanties(self):
        rng = random.Random(20261113)
        specs = [
            SymboleSpec(),
            SymboleSpec(volume_min=0.1, volume_pas=0.1, volume_max=50.0),
            SymboleSpec(volume_min=1.0, volume_pas=1.0, volume_max=1000.0),
            SymboleSpec(volume_min=0.01, volume_pas=0.01, volume_max=0.5),
            SymboleSpec(volume_min=0.1, volume_pas=0.01, volume_max=20.0),
        ]
        acceptes = refus = limites_levier = 0
        for i in range(10_000):
            balance = round(10 ** rng.uniform(2, 6), rng.choice((0, 2, 5)))
            pct = rng.choice((1.0, 0.5, 2.0, round(rng.uniform(0.01, 2.0), 3)))
            levier = rng.choice((10.0, 1.0, 30.0, round(rng.uniform(0.5, 30.0), 2)))
            cfg = RisqueConfig(risque_par_trade_pct=pct, levier_effectif_max=levier,
                               exiger_lot_divisible=rng.random() < 0.5)
            spec = rng.choice(specs)
            distance_sl = round(rng.uniform(0.05, 20.0), rng.choice((1, 2, 3)))
            commission = rng.choice((0.0, 7.0, round(rng.uniform(0, 15), 2)))
            perte = distance_sl * CONTRAT + commission
            notionnel = round(rng.uniform(1500.0, 5000.0), 2) * CONTRAT
            r = calculer_taille_lot(balance, cfg, perte, notionnel, spec)
            ctx = dict(i=i, balance=balance, pct=pct, levier=levier, perte=perte,
                       notionnel=notionnel, spec=spec, r=r)
            budget = balance * pct / 100
            self.assertAlmostEqual(r.risque_montant, budget, delta=budget * 1e-12, msg=ctx)
            if not r.accepte:
                refus += 1
                self.assertEqual(r.lots, 0.0, ctx)
                self.assertIn(r.raison, ("lot_inferieur_minimum", "lot_non_divisible"), ctx)
                # Le refus est justifié : le minimum (ou 2 × minimum) aurait dépassé une limite.
                mini = spec.volume_min * (2 if r.raison == "lot_non_divisible" else 1)
                self.assertTrue(mini * perte > budget * (1 - 1e-9)
                                or mini * notionnel > levier * balance * (1 - 1e-9)
                                or mini > spec.volume_max, ctx)
                continue
            acceptes += 1
            limites_levier += r.raison == "plafond_levier"
            self.assertLessEqual(r.lots * perte, r.risque_montant * (1 + 1e-9), ctx)
            self.assertLessEqual(r.levier_effectif, levier * (1 + 1e-9), ctx)
            self.assertLessEqual(r.lots * notionnel / balance, levier * (1 + 1e-9), ctx)
            self.assertLessEqual(r.risque_pct, pct * (1 + 1e-9), ctx)
            self.assertTrue(est_multiple(r.lots, spec.volume_pas), ctx)
            self.assertGreaterEqual(r.lots, spec.volume_min, ctx)
            self.assertLessEqual(r.lots, spec.volume_max, ctx)
            if cfg.exiger_lot_divisible:
                self.assertGreaterEqual(r.lots, 2 * spec.volume_min - 1e-12, ctx)
            # Pas trop prudent non plus : un pas de plus aurait violé une limite.
            plus = r.lots + spec.volume_pas
            self.assertTrue(plus * perte > budget * (1 - 1e-9)
                            or plus * notionnel > levier * balance * (1 - 1e-9)
                            or plus > spec.volume_max * (1 + 1e-12), ctx)
        # Le tirage couvre bien les deux issues et le plafond de levier.
        self.assertGreater(acceptes, 1000)
        self.assertGreater(refus, 500)
        self.assertGreater(limites_levier, 100)


class TestDecouperVolume(unittest.TestCase):

    def test_exemples_de_la_spec(self):
        self.assertEqual(decouper_volume(0.06, 0.5, SPEC), (0.03, 0.03))
        self.assertEqual(decouper_volume(0.05, 0.5, SPEC), (0.02, 0.03))
        self.assertEqual(decouper_volume(0.01, 0.5, SPEC), (0.0, 0.01))

    def test_pieges_flottants(self):
        self.assertEqual(decouper_volume(0.07, 0.5, SPEC), (0.03, 0.04))
        self.assertEqual(decouper_volume(0.29, 0.5, SPEC), (0.14, 0.15))
        self.assertEqual(decouper_volume(0.58, 0.5, SPEC), (0.29, 0.29))
        self.assertEqual(decouper_volume(0.02, 0.5, SPEC), (0.01, 0.01))

    def test_deux_parts_au_moins_minimum(self):
        spec = dataclasses.replace(SPEC, volume_min=0.1, volume_pas=0.01)
        self.assertEqual(decouper_volume(0.15, 0.5, spec), (0.0, 0.15))   # 0.07 < 0.1
        self.assertEqual(decouper_volume(0.25, 0.5, spec), (0.12, 0.13))
        self.assertEqual(decouper_volume(0.25, 0.7, spec), (0.0, 0.25))  # reste 0.08 < 0.1

    def test_propriete_somme_et_pas(self):
        rng = random.Random(7)
        for _ in range(2000):
            lots = rng.randint(1, 5000) / 100
            frac = rng.choice((0.5, 0.25, 0.33, 0.75, 0.9))
            a, b = decouper_volume(lots, frac, SPEC)
            self.assertEqual(Decimal(repr(a)) + Decimal(repr(b)), Decimal(repr(lots)))
            if a == 0.0:
                self.assertEqual(b, lots)
            else:
                self.assertTrue(est_multiple(a, 0.01) and est_multiple(b, 0.01))
                self.assertGreaterEqual(min(a, b), SPEC.volume_min)
                self.assertLessEqual(Decimal(repr(a)), Decimal(repr(lots)) * Decimal(repr(frac)))


class TestGardeRisque(unittest.TestCase):

    def setUp(self):
        self.g = GardeRisque(CFG, 3000.0)
        self.j1, self.j2, self.j3 = date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7)

    def test_etat_initial(self):
        self.assertEqual(self.g.peut_ouvrir("t0", 3000.0), (True, "ok"))
        self.assertFalse(self.g.arret_definitif)
        self.assertEqual(self.g.pic_equity, 3000.0)
        self.assertEqual(self.g.balance_debut_jour, 3000.0)
        self.assertEqual(self.g.historique, ())

    def test_perte_jour_sans_nouvelle_journee_reference_balance_initiale(self):
        self.assertEqual(self.g.peut_ouvrir("t1", 2911.0), (True, "ok"))
        self.assertEqual(self.g.peut_ouvrir("t2", 2910.0), (False, "perte_jour_max"))  # -3 % pile

    def test_perte_jour_bloque_jusqu_a_la_journee_suivante(self):
        self.g.nouvelle_journee(self.j1, 3000.0)
        self.g.mettre_a_jour("10:00", 2950.0)
        self.assertEqual(self.g.peut_ouvrir("10:15", 2950.0), (True, "ok"))
        self.g.mettre_a_jour("11:00", 2905.0)                     # -3.17 %
        self.assertEqual(self.g.peut_ouvrir("11:15", 2905.0), (False, "perte_jour_max"))
        # L'equity remonte : le blocage tient jusqu'à la prochaine journée.
        self.g.mettre_a_jour("12:00", 3010.0)
        self.assertEqual(self.g.peut_ouvrir("12:15", 3010.0), (False, "perte_jour_max"))
        # Même date rappelée (redémarrage) : pas de remise à zéro.
        self.g.nouvelle_journee(self.j1, 3010.0)
        self.assertEqual(self.g.peut_ouvrir("12:30", 3010.0), (False, "perte_jour_max"))
        self.g.nouvelle_journee(self.j2, 2905.0)
        self.assertEqual(self.g.peut_ouvrir("j2 09:00", 2905.0), (True, "ok"))
        self.assertFalse(self.g.arret_definitif)
        types = [d.type for d in self.g.historique]
        self.assertEqual(types, ["perte_jour"])
        self.assertAlmostEqual(self.g.historique[0].valeur, 95 / 3000 * 100, places=9)
        self.assertEqual(self.g.historique[0].instant, "11:00")

    def test_perte_jour_relative_a_la_balance_du_jour(self):
        self.g.nouvelle_journee(self.j1, 2800.0)   # -6.7 % depuis le pic, mais nouvelle journée
        self.assertEqual(self.g.peut_ouvrir("t", 2800.0), (True, "ok"))
        self.assertEqual(self.g.peut_ouvrir("t", 2716.0), (False, "perte_jour_max"))  # 84/2800 = 3 %

    def test_drawdown_arret_definitif(self):
        self.g.nouvelle_journee(self.j1, 3000.0)
        self.g.nouvelle_journee(self.j2, 2600.0)
        self.g.mettre_a_jour("j2", 2551.0)          # 14.97 % : pas d'arrêt
        self.assertFalse(self.g.arret_definitif)
        self.g.nouvelle_journee(self.j3, 2560.0)
        self.g.mettre_a_jour("j3 10:00", 2550.0)   # 15 % pile depuis le pic 3000
        self.assertTrue(self.g.arret_definitif)
        self.assertIn("drawdown_max", self.g.raison_arret)
        self.assertEqual(self.g.peut_ouvrir("j3 10:15", 2550.0), (False, "arret_definitif"))
        # Survit à une nouvelle journée et à une remontée de l'equity.
        self.g.nouvelle_journee(date(2026, 1, 8), 2900.0)
        self.assertTrue(self.g.arret_definitif)
        self.assertEqual(self.g.peut_ouvrir("j4", 2900.0), (False, "arret_definitif"))
        dd = [d for d in self.g.historique if d.type == "drawdown_max"]
        self.assertEqual(len(dd), 1)
        self.assertAlmostEqual(dd[0].valeur, 15.0, places=9)
        # Seule une réinitialisation explicite le lève ; le pic repart de la dernière equity.
        self.g.reinitialiser_arret()
        self.assertFalse(self.g.arret_definitif)
        self.assertEqual(self.g.raison_arret, "")
        self.assertEqual(self.g.pic_equity, 2900.0)
        self.assertEqual(self.g.peut_ouvrir("j4 bis", 2900.0), (True, "ok"))
        self.assertEqual(self.g.historique[-1].type, "reinitialisation")

    def test_pic_mobile_gains_puis_pertes(self):
        self.g.nouvelle_journee(self.j1, 3000.0)
        self.g.mettre_a_jour("j1", 4000.0)                     # pic 4000 (+33 %)
        self.g.nouvelle_journee(self.j2, 4000.0)
        self.g.mettre_a_jour("j2 a", 3900.0)
        self.g.nouvelle_journee(self.j3, 3900.0)
        self.g.mettre_a_jour("j3 a", 3800.0)
        self.g.nouvelle_journee(date(2026, 1, 8), 3500.0)
        self.g.mettre_a_jour("j4 a", 3450.0)                   # 13.75 % depuis 4000
        self.assertFalse(self.g.arret_definitif)
        self.assertEqual(self.g.pic_equity, 4000.0)
        self.g.mettre_a_jour("j4 b", 3400.0)                   # 15 % depuis 4000, +13 % vs départ
        self.assertTrue(self.g.arret_definitif)
        self.assertEqual(self.g.peut_ouvrir("j4 c", 3400.0), (False, "arret_definitif"))

    def test_peut_ouvrir_observe_l_equity(self):
        # Sans mettre_a_jour préalable, peut_ouvrir voit lui-même le drawdown.
        self.g.nouvelle_journee(self.j1, 2600.0)
        self.assertEqual(self.g.peut_ouvrir("t", 2500.0), (False, "arret_definitif"))
        self.assertTrue(self.g.arret_definitif)

    def test_reinitialiser_avec_pic_explicite(self):
        self.g.mettre_a_jour("t", 2000.0)
        self.assertTrue(self.g.arret_definitif)
        self.g.reinitialiser_arret(nouveau_pic=2100.0)
        self.assertEqual(self.g.pic_equity, 2100.0)
        self.assertFalse(self.g.arret_definitif)

    def test_equity_invalide(self):
        for mauvais in (float("nan"), 0.0, -10.0, float("inf"), None):
            with self.subTest(equity=mauvais):
                ok, raison = self.g.peut_ouvrir("t", mauvais)
                self.assertFalse(ok)
                self.assertEqual(raison, "entree_invalide:equity")
                self.g.mettre_a_jour("t", mauvais)  # ne lève pas, ne change rien
        self.assertEqual(self.g.pic_equity, 3000.0)
        self.assertFalse(self.g.arret_definitif)
        self.assertIn("equity_invalide", {d.type for d in self.g.historique})
        self.assertEqual(self.g.peut_ouvrir("t", 3000.0), (True, "ok"))

    def test_balance_du_jour_invalide_bloque_la_journee(self):
        self.g.nouvelle_journee(self.j1, float("nan"))
        self.assertEqual(self.g.peut_ouvrir("t", 3000.0), (False, "perte_jour_max"))
        self.g.nouvelle_journee(self.j2, 3000.0)
        self.assertEqual(self.g.peut_ouvrir("t", 3000.0), (True, "ok"))

    def test_construction_invalide(self):
        for bal in (0.0, -1.0, float("nan"), float("inf"), None):
            with self.subTest(balance=bal):
                with self.assertRaises(ValueError):
                    GardeRisque(CFG, bal)
        with self.assertRaises(ValueError):
            GardeRisque(dataclasses.replace(CFG, drawdown_max_pct=float("nan")), 3000.0)
        with self.assertRaises(ValueError):
            GardeRisque(dataclasses.replace(CFG, perte_jour_max_pct=0.0), 3000.0)

    def test_historique_non_modifiable(self):
        self.g.mettre_a_jour("t", 2900.0)
        h = self.g.historique
        self.assertIsInstance(h, tuple)
        self.assertEqual(len(h), 1)
        self.assertTrue(math.isfinite(h[0].valeur))


if __name__ == "__main__":
    unittest.main()
