"""Tests du cycle 2 (docs/RECHERCHE_PLAN_CYCLE2.md) : C1, C2, combinaison P, critères, nouveaux marchés.

Les dates de C1 sont calculées à la main dans les commentaires (calendrier 2020). Données fabriquées
ou synthétiques uniquement.
"""
from __future__ import annotations

import unittest
from unittest import mock

import numpy as np
import pandas as pd

from sentitrade.recherche import cycle2 as c2
from sentitrade.recherche import evaluation as ev
from sentitrade.recherche import moteur as mo
from sentitrade.recherche import strategies as st
from sentitrade.recherche.donnees import construire_univers
from sentitrade.recherche.synthetique import generer_univers
from tests.test_recherche_moteur import bougies, info, stats, univers
from tests.test_recherche_strategies import _d1

T = pd.Timestamp


def plat(debut, fin, retirer=()):
    """Bougies D1 plates (1000, plus haut 1001, plus bas 999 : ATR20 = 2) du lundi au vendredi."""
    idx = pd.bdate_range(debut, fin)
    idx = idx[~idx.isin(pd.DatetimeIndex([T(x) for x in retirer]))]
    n = len(idx)
    return bougies(idx, [1000] * n, [1001] * n, [999] * n, [1000] * n)


def u_indice(d1):
    return univers({"IDXA": ("indices", info(contrat=1.0, base="USD"), stats(0), {"D1": d1})})


def c1(**kw):
    b = st.strategie_base("C1")
    return st.Strategie("C1", "test", st.ParamC1(**kw), "D1", b.risque_pct, b.description, b.classes)


# =========================================================================== paramètres et univers

class TestParametres(unittest.TestCase):

    def test_parametres_du_plan_cycle2(self):
        b1 = st.strategie_base("C1")
        self.assertEqual((b1.params.entree_avant_j, b1.params.jour_sortie, b1.params.stop_atr), (0, 4, 3.0))
        self.assertEqual(b1.risque_pct, 0.5)
        self.assertEqual(b1.classes, ("indices",))
        self.assertEqual([(v.params.entree_avant_j, v.params.jour_sortie, v.params.stop_atr)
                          for v in st.variantes_voisines("C1")], [(1, 4, 3.0), (0, 3, 3.0), (0, 4, 4.0)])
        b2 = st.strategie_base("C2").params
        self.assertEqual((b2.sma, b2.frequence, b2.vol_cible, b2.vol_barres, b2.stop_atr, b2.seuil_reequilibrage,
                          b2.levier_max), (200, "semaine", 0.10, 60, 4.0, 0.25, 10.0))
        self.assertEqual([(v.params.sma, v.params.frequence) for v in st.variantes_voisines("C2")],
                         [(150, "semaine"), (250, "semaine"), (200, "mois")])
        self.assertIsNone(st.strategie_base("C2").risque_pct)
        self.assertFalse(any(v.params.toujours_long for c in ("C1", "C2") for v in st.variantes_voisines(c)))
        self.assertTrue(st.reference_toujours_long("C1").params.toujours_long)
        self.assertEqual(st.reference_toujours_long("C2").params, st.ParamC2(toujours_long=True))
        self.assertEqual(st.CODES, ("S1", "S2", "S3", "S4"))           # cycle 1 inchangé
        self.assertEqual(ev.SEUILS["tstat_min"], 2.5)
        self.assertEqual(ev.SEUILS_CYCLE2["tstat_min"], 3.0)

    def test_classes_energies_et_matieres_acceptees(self):
        d1 = plat("2020-01-01", "2020-02-28")
        brut = {}
        for nom, classe in (("US500", "indices"), ("XAUUSD", "metaux"), ("XTIUSD", "energies"), ("COCOA", "matieres"),
                            ("BTCUSD", "crypto"), ("EURUSD", "forex")):
            brut[nom] = {"nom_broker": nom, "classe": classe, "info": info(contrat=1.0, base="USD"),
                         "spread_stats": stats(0), "bougies": {"D1": d1}}
        u = construire_univers(brut)
        self.assertEqual(u.exclus, {})
        self.assertEqual(mo.symboles_strategie(u, st.strategie_base("C1")), ["US500"])
        self.assertEqual(mo.symboles_strategie(u, st.strategie_base("C2")), ["BTCUSD", "US500", "XAUUSD", "XTIUSD"])
        # le cycle 1 ne voit pas les nouvelles classes
        self.assertNotIn("XTIUSD", mo.symboles_strategie(u, st.strategie_base("S2")))
        self.assertNotIn("COCOA", mo.symboles_strategie(u, st.strategie_base("S1")))


# =========================================================================== C1 : dates à la main

class TestDatesC1(unittest.TestCase):

    def test_calendrier(self):
        d = np.array(["2020-02-27", "2020-02-28", "2020-05-28", "2020-03-30", "2020-05-30"], dtype="datetime64[D]")
        nb = st.jour_ouvre_suivant(d)
        self.assertEqual([str(x) for x in nb], ["2020-02-28", "2020-03-02", "2020-05-29", "2020-03-31", "2020-06-01"])
        self.assertEqual([str(x) for x in st.dernier_jour_ouvre_du_mois(nb)],
                         ["2020-02-28", "2020-03-31", "2020-05-29", "2020-03-31", "2020-06-30"])

    def test_signal_mois_finissant_samedi_dimanche_et_en_semaine(self):
        # 29/02/2020 samedi -> J = ven 28/02 : ordre à la clôture du jeu 27/02.
        # 31/05/2020 dimanche -> J = ven 29/05 : ordre à la clôture du jeu 28/05.
        # 31/03/2020 mardi -> J = mar 31/03 : ordre à la clôture du lun 30/03.
        # 30/04/2020 jeudi -> J = jeu 30/04 : ordre à la clôture du mer 29/04.
        df = plat("2020-01-01", "2020-06-10")
        s = st.signaux_c1(df, st.ParamC1())
        decisions = list(df.index[s["entree"].to_numpy()].strftime("%Y-%m-%d"))
        # janvier : 31/01 vendredi -> ordre le 30/01 (ATR20 prêt depuis la 21e bougie, le 29/01)
        self.assertEqual(decisions, ["2020-01-30", "2020-02-27", "2020-03-30", "2020-04-29", "2020-05-28"])
        prevu = s.loc[T("2020-05-28"), "jour_prevu"]
        self.assertEqual(pd.Timestamp(int(prevu) * mo.NS_JOUR), T("2020-05-29"))
        # variante J-1 : J-1 = jeu 27/02 -> ordre le mer 26/02 ; J-1 = jeu 28/05 -> ordre le mer 27/05
        s1 = st.signaux_c1(df, st.ParamC1(entree_avant_j=1))
        d1 = list(df.index[s1["entree"].to_numpy()].strftime("%Y-%m-%d"))
        self.assertIn("2020-02-26", d1)
        self.assertIn("2020-05-27", d1)
        self.assertEqual(len(d1), 5)
        # rang dans le mois (bougies reçues) : mars 2020 commence le lundi 2
        self.assertEqual(int(s.loc[T("2020-03-04"), "rang_mois"]), 3)

    def test_entree_j_sortie_4e_jour(self):
        # Données à partir du 15/01 : ATR non prêt fin janvier, un seul trade (février).
        # Entrée ouverture ven 28/02 ; mars : lun 2, mar 3, mer 4 terminées -> sortie ouverture jeu 05/03.
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20")), st.strategie_base("C1"))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual((t["entree_a"], t["sortie_a"], t["raison_sortie"], t["barres"], t["sens"]),
                         (T("2020-02-28"), T("2020-03-05"), "fin_tournant", 4, 1))
        self.assertAlmostEqual(t["stop_initial"], 1000 - 3 * 2.0)
        # 0,5 % de 10 000 = 50 $ ; perte au stop 6 $ par lot (spread et glissement nuls) -> 8.33 lots -> 49.98 $
        self.assertAlmostEqual(t["lots"], 8.33)
        self.assertAlmostEqual(t["risque_pct"], 0.4998, places=9)

    def test_mois_finissant_dimanche(self):
        # 31/05/2020 dimanche : entrée ven 29/05 ; juin : 1, 2, 3 -> sortie ouverture jeu 04/06.
        r = mo.simuler(u_indice(plat("2020-04-20", "2020-06-12")), st.strategie_base("C1"))
        self.assertEqual(list(zip(r.trades["entree_a"], r.trades["sortie_a"])), [(T("2020-05-29"), T("2020-06-04"))])

    def test_variante_entree_j_moins_1(self):
        # Entrée jeu 27/02, sortie inchangée (jeu 05/03) : 5 bougies en position.
        v = st.variantes_voisines("C1")[0]
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20")), v)
        t = r.trades.iloc[0]
        self.assertEqual((t["entree_a"], t["sortie_a"], t["barres"]), (T("2020-02-27"), T("2020-03-05"), 5))

    def test_variante_sortie_3e_jour(self):
        # Sortie à l'ouverture du 3e jour de cotation de mars : mer 04/03 (après lun 2 et mar 3).
        v = st.variantes_voisines("C1")[1]
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20")), v)
        t = r.trades.iloc[0]
        self.assertEqual((t["entree_a"], t["sortie_a"], t["barres"]), (T("2020-02-28"), T("2020-03-04"), 3))

    def test_jour_j_manquant_ordre_annule(self):
        # Ven 28/02 absent : l'ordre du jeu 27/02 vaut pour le 28/02 seulement ; la bougie suivante est le
        # lun 02/03 -> ordre annulé (jamais d'entrée en retard dans le nouveau mois).
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20", retirer=["2020-02-28"])), st.strategie_base("C1"))
        self.assertEqual(len(r.trades), 0)
        self.assertEqual(r.compteurs.get("annulation:jour_entree_absent"), 1)

    def test_veille_de_j_manquante_pas_d_entree(self):
        # Jeu 27/02 absent : à la clôture du mer 26/02, le jour ouvré suivant est le 27/02, pas J : pas d'ordre.
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20", retirer=["2020-02-27"])), st.strategie_base("C1"))
        self.assertEqual(len(r.trades), 0)
        self.assertNotIn("annulation:jour_entree_absent", r.compteurs)
        # variante J-1 : ordre du mer 26/02 pour le jeu 27/02, absent -> annulé à l'ouverture du ven 28/02
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20", retirer=["2020-02-27"])), st.variantes_voisines("C1")[0])
        self.assertEqual(len(r.trades), 0)
        self.assertEqual(r.compteurs.get("annulation:jour_entree_absent"), 1)

    def test_jour_manquant_dans_le_nouveau_mois(self):
        # Mar 03/03 absent : bougies reçues lun 2, mer 4, jeu 5 -> sortie à l'ouverture du ven 06/03.
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20", retirer=["2020-03-03"])), st.strategie_base("C1"))
        t = r.trades.iloc[0]
        self.assertEqual((t["entree_a"], t["sortie_a"], t["barres"]), (T("2020-02-28"), T("2020-03-06"), 4))

    def test_stop_puis_attente_du_mois_suivant(self):
        # Entrée ven 28/02 à 1000, stop 994 ; lun 02/03 plus bas 990 -> stop ; pas de nouvelle entrée en mars.
        d1 = plat("2020-01-15", "2020-03-27")
        d1.loc[T("2020-03-02"), "low"] = 990.0
        r = mo.simuler(u_indice(d1), st.strategie_base("C1"))
        self.assertEqual(list(r.trades["raison_sortie"]), ["stop"])
        self.assertEqual(r.trades.iloc[0]["sortie_a"], T("2020-03-02"))

    def test_reference_toujours_long(self):
        # Achat dès que l'ATR existe (clôture du 12/02, 21e bougie -> ouverture du 13/02), renouvellement à
        # l'ouverture du ven 28/02 (même instant que C1), position toujours ouverte ensuite.
        r = mo.simuler(u_indice(plat("2020-01-15", "2020-03-20")), st.reference_toujours_long("C1"))
        self.assertEqual(list(r.trades["entree_a"]), [T("2020-02-13"), T("2020-02-28")])
        self.assertEqual(list(r.trades["raison_sortie"]), ["renouvellement_mensuel", "fin_periode"])
        self.assertTrue((r.trades["sens"] == 1).all())
        # après un stop : rachat à l'ouverture suivante
        d1 = plat("2020-01-15", "2020-03-20")
        d1.loc[T("2020-03-02"), "low"] = 990.0
        r = mo.simuler(u_indice(d1), st.reference_toujours_long("C1"))
        self.assertEqual(list(r.trades["raison_sortie"]), ["renouvellement_mensuel", "stop", "fin_periode"])
        self.assertEqual(r.trades.iloc[2]["entree_a"], T("2020-03-03"))


# =========================================================================== C2

def fabrique_c2(signes: dict, vols: dict, atr=1.0):
    """Signaux C2 injectés : signe (0/1) et vol de rééquilibrage par indice de bougie (lundis)."""
    def f(df, p, crypto):
        out = pd.DataFrame(index=df.index)
        iso = df.index.isocalendar()
        sem = iso["week"].to_numpy()
        out["reequilibrer"] = np.concatenate([[False], sem[1:] != sem[:-1]])
        out.iloc[0, 0] = True
        sg, vl, cur_s, cur_v = [], [], 1.0, 0.10
        for i in range(len(df)):
            cur_s = signes.get(i, cur_s)
            cur_v = vols.get(i, cur_v)
            sg.append(cur_s)
            vl.append(cur_v)
        out["signe"] = sg
        out["vol"] = vl
        out["atr"] = atr
        out["pret"] = True
        return out
    return f


class TestC2(unittest.TestCase):

    def test_signal_sma200_strict_et_jamais_negatif(self):
        df = _d1(700)
        s = st.signaux_c2(df, st.ParamC2(), crypto=False)
        c = df["close"]
        for i in (250, 400, 699):          # valeurs « veille » : clôture i-1 contre SMA200 des bougies i-200..i-1
            sma = c.iloc[i - 200:i].mean()
            self.assertEqual(s["signe"].iloc[i], 1.0 if c.iloc[i - 1] > sma else 0.0)
        vals = set(s["signe"].dropna().unique())
        self.assertTrue(vals <= {0.0, 1.0})
        self.assertEqual(vals, {0.0, 1.0})
        self.assertTrue(s["signe"].iloc[:200].isna().all())
        self.assertTrue((df.index[s["reequilibrer"].to_numpy()].weekday == 0).all())
        m = st.signaux_c2(df, st.ParamC2(frequence="mois"), crypto=False)
        jours = df.index[m["reequilibrer"].to_numpy()]
        self.assertTrue(len(jours) > 20)
        self.assertTrue(all(df.index[df.index.get_loc(j) - 1].month != j.month for j in jours))
        ref = st.signaux_c2(df, st.ParamC2(toujours_long=True), crypto=False)
        self.assertEqual(set(ref["signe"].dropna().unique()), {1.0})
        pd.testing.assert_series_equal(ref["pret"], s["pret"])     # même période d'évaluation que C2
        vol = df["close"].pct_change().iloc[400 - 60:400].std(ddof=1) * np.sqrt(365)
        self.assertAlmostEqual(st.signaux_c2(df, st.ParamC2(), crypto=True)["vol"].iloc[400], vol)

    def test_sort_sous_la_sma_au_reequilibrage_suivant(self):
        # 300 bougies qui montent, puis une chute : la position est fermée au premier rééquilibrage dont la
        # clôture de la veille est <= SMA200, et n'est jamais retournée en vente.
        idx = pd.bdate_range("2015-01-05", periods=420)
        c = np.concatenate([1000 + np.arange(300) * 1.0, 1299 - np.arange(1, 121) * 6.0])
        o = np.concatenate([[1000], c[:-1]])
        d1 = bougies(idx, o, np.maximum(o, c) + 1, np.minimum(o, c) - 1, c)
        u = u_indice(d1)
        r = mo.simuler(u, st.strategie_base("C2"))
        self.assertTrue((r.trades["sens"] == 1).all())
        sma = pd.Series(c).rolling(200).mean().to_numpy()
        sem = idx.isocalendar()["week"].to_numpy()
        attendu = next(i for i in range(201, len(c)) if sem[i] != sem[i - 1] and c[i - 1] <= sma[i - 1])
        sorties = r.trades[r.trades["raison_sortie"] == "reequilibrage_sortie"]
        self.assertEqual(len(sorties), 1)
        self.assertEqual(sorties.iloc[0]["sortie_a"], idx[attendu])
        self.assertTrue((r.trades["entree_a"] < idx[attendu]).all())    # à plat ensuite (signal 0)

    def test_signal_zero_ferme_et_reste_a_plat(self):
        idx = pd.bdate_range("2024-01-08", periods=15)
        d1 = bougies(idx, [1000] * 15, [1000] * 15, [1000] * 15, [1000] * 15)
        with mock.patch.object(st, "signaux_c2", fabrique_c2({0: 1.0, 5: 0.0}, {})):
            r = mo.simuler(u_indice(d1), st.strategie_base("C2"))
        self.assertEqual(len(r.trades), 1)
        t = r.trades.iloc[0]
        self.assertEqual((t["sens"], t["entree_a"], t["sortie_a"], t["raison_sortie"]),
                         (1, T("2024-01-08"), T("2024-01-15"), "reequilibrage_sortie"))

    def test_reequilibrage_seulement_au_dela_de_25_pourcent(self):
        # Même calcul que S2 : 10 lots, puis 12.5 (écart 25 % exactement : rien), 12.51 (rééquilibré), 10.52 (rien).
        idx = pd.bdate_range("2024-01-08", periods=20)
        d1 = bougies(idx, [1000] * 20, [1000] * 20, [1000] * 20, [1000] * 20)
        with mock.patch.object(st, "signaux_c2", fabrique_c2({0: 1.0}, {0: 0.10, 5: 0.08, 10: 0.0799, 15: 0.095})):
            r = mo.simuler(u_indice(d1), st.strategie_base("C2"))
        self.assertEqual(len(r.trades), 1)
        self.assertAlmostEqual(r.trades.iloc[0]["lots"], 12.51)
        self.assertEqual(r.trades.iloc[0]["ajustements"], 1)
        self.assertEqual(r.nb_reequilibrages, 4)

    def test_stop_puis_a_plat_jusqu_au_signal_suivant(self):
        idx = pd.bdate_range("2024-01-08", periods=10)
        lows = [1000] * 10
        lows[1] = 990
        d1 = bougies(idx, [1000] * 10, [1000] * 10, lows, [1000] * 10)
        with mock.patch.object(st, "signaux_c2", fabrique_c2({0: 1.0}, {})):
            r = mo.simuler(u_indice(d1), st.strategie_base("C2"))
        self.assertEqual(list(r.trades["raison_sortie"]), ["stop", "fin_periode"])
        self.assertEqual(r.trades.iloc[1]["entree_a"], T("2024-01-15"))


# =========================================================================== anti-anticipation

class TestAntiAnticipation(unittest.TestCase):

    def _compare(self, f, df, coupures):
        complet = f(df)
        for k in coupures:
            pd.testing.assert_frame_equal(complet.iloc[:k + 1], f(df.iloc[:k + 1]), check_dtype=False, obj=f"coupure {k}")

    def test_signaux_c1_c2(self):
        df = _d1(700)
        for v in [st.strategie_base("C1")] + st.variantes_voisines("C1"):
            self._compare(lambda d, v=v: st.signaux_c1(d, v.params), df, [30, 290, 699])
        for v in [st.strategie_base("C2"), st.reference_toujours_long("C2")] + st.variantes_voisines("C2"):
            self._compare(lambda d, v=v: st.signaux_c2(d, v.params, False), df, [100, 260, 455, 699])

    def test_moteur_c1_c2_p_par_troncature(self):
        u = generer_univers(debut="2014-01-01", fin="2021-06-30", graine=11, annees_m15=0,
                            symboles=["EURUSD", "US500", "GER40", "NAS100", "XAUUSD", "BTCUSD"])
        coupure = pd.Timestamp("2020-06-15")
        ut = u.tronquer(coupure)
        cols = ["symbole", "sens", "entree_a", "stop_initial"]
        tri = ["entree_a", "symbole"]
        for s in (st.strategie_base("C1"), st.strategie_base("C2"), st.reference_toujours_long("C1"),
                  st.reference_toujours_long("C2")):
            complet = mo.simuler(u, s, journal_complet=False).trades
            tronque = mo.simuler(ut, s, journal_complet=False).trades
            a = complet[complet["entree_a"] <= coupure].sort_values(tri)[cols].reset_index(drop=True)
            b = tronque[tronque["entree_a"] <= coupure].sort_values(tri)[cols].reset_index(drop=True)
            self.assertGreater(len(a), 3, s.nom)
            pd.testing.assert_frame_equal(a, b, obj=s.nom)
            fa = complet[complet["sortie_a"] < coupure - pd.Timedelta(days=1)].sort_values(tri).reset_index(drop=True)
            fb = tronque[tronque["sortie_a"] < coupure - pd.Timedelta(days=1)].sort_values(tri).reset_index(drop=True)
            pd.testing.assert_frame_equal(fa, fb, obj=s.nom + " (fermés)")
        # P : l'equity combinée des jours antérieurs à la coupure ne dépend pas du futur
        pc, pt = mo.simuler_p(u, journal_complet=False), mo.simuler_p(ut, journal_complet=False)
        jusque = coupure.normalize() - pd.Timedelta(days=2)
        ea, eb = pc.equity.loc[:jusque], pt.equity.loc[:jusque]
        self.assertGreater(len(ea), 500)
        pd.testing.assert_frame_equal(ea, eb, check_exact=False, rtol=1e-12)


# =========================================================================== combinaison P

def _res(eq, capital, trades=None, nom="X", symboles=None):
    vide = pd.DataFrame(columns=mo.COLONNES_TRADES)
    return mo.ResultatSimulation(nom, "base", capital, eq, vide if trades is None else trades,
                                 pd.DataFrame(columns=mo.COLONNES_EVENEMENTS), pd.DataFrame(columns=mo.COLONNES_TENTATIVES),
                                 {}, {}, symboles or {}, None, None)


class TestCombinaisonP(unittest.TestCase):

    def test_moyenne_des_rendements_journaliers(self):
        idx = pd.bdate_range("2024-01-08", periods=3)
        # A : +1 %, 0 % ; B : -1 %, +2 % ; C : absente le 1er jour (0 %), puis +3 %, puis absente (0 %)
        a = pd.DataFrame({"equity": [1010.0, 1010.0, 1010.0], "equity_pire": [1000.0, 1005.0, 1010.0],
                          "balance": 1000.0}, index=idx)
        b = pd.DataFrame({"equity": [990.0, 1009.8, 1009.8], "equity_pire": [980.0, 990.0, 1009.8],
                          "balance": 1000.0}, index=idx)
        c = pd.DataFrame({"equity": [1030.0], "equity_pire": [1000.0], "balance": 1000.0}, index=idx[1:2])
        p = mo.combiner_rendements([_res(a, 1000.0), _res(b, 1000.0), _res(c, 1000.0)], "P", 3000.0)
        # jour 1 : (1 - 1 + 0)/3 = 0 -> 3000 ; jour 2 : (0 + 2 + 3)/3 = 5/3 % -> 3050 ; jour 3 : 0 -> 3050
        np.testing.assert_allclose(p.equity["equity"].to_numpy(), [3000.0, 3050.0, 3050.0])
        # pire prix jour 1 : (0 % - 2 % + 0 %)/3 -> 3000 x (1 - 0.02/3) = 2980
        self.assertAlmostEqual(p.equity["equity_pire"].iloc[0], 2980.0)
        # jour 2 : A 1005/1010 - 1, B 990/990 - 1 = 0, C 1000/1000 - 1 = 0 -> 3000 x (1 + (-0.00495...)/3)
        self.assertAlmostEqual(p.equity["equity_pire"].iloc[1], 3000.0 * (1 + (1005 / 1010 - 1) / 3))
        self.assertEqual(p.capital_initial, 3000.0)

    def test_simuler_p_un_tiers_du_capital(self):
        u = generer_univers(debut="2016-01-01", fin="2020-12-31", graine=2, annees_m15=0,
                            symboles=["EURUSD", "US500", "GER40", "XAUUSD"])
        parts = []
        with mock.patch.object(mo, "combiner_rendements", lambda r, n, c: parts.extend(r) or "ok"):
            mo.simuler_p(u, 9000.0, journal_complet=False)
        self.assertEqual([r.strategie for r in parts], ["C1", "C2", "S3"])
        self.assertEqual([r.capital_initial for r in parts], [3000.0] * 3)
        v = st.variantes_voisines("C2")[2]
        self.assertEqual([s.variante for s in mo.strategies_p(v)], ["base", "évaluation mensuelle", "base"])
        self.assertEqual(len(c2.variantes("P")), 9)


# =========================================================================== critères et règle de P

def _base_ok(**kw):
    b = {"annees": 15.0, "nb_trades": 500, "sharpe": 0.9, "tstat": 3.5, "dd_pire_pct": 8.0,
         "pct_annees_positives": 75.0, "part_symboles_positifs": 0.8, "nb_symboles": 5, "nb_symboles_positifs": 4}
    b.update(kw)
    return b


ROB_OK = {"variantes": {"a": {"sharpe": 0.6}, "b": {"sharpe": 0.5}}, "couts_doubles": {"sharpe": 0.4}}


class TestCriteres(unittest.TestCase):

    def test_tstat_3_et_reste_identique(self):
        ref = {"nom": "r", "sharpe": 0.2, "dd_pire_pct": 30.0}
        self.assertTrue(ev.verdict_strategie_cycle2("C1", _base_ok(), ROB_OK, ref)["retenue"])
        v = ev.verdict_strategie_cycle2("C1", _base_ok(tstat=2.99), ROB_OK, ref)
        self.assertEqual(v["criteres_ko"], [3])
        self.assertEqual(v["criteres"][2]["seuil"], ">= 3.0")
        self.assertTrue(ev.verdict_strategie_cycle2("C1", _base_ok(tstat=3.0), ROB_OK, ref)["retenue"])
        self.assertEqual(ev.verdict_strategie_cycle2("C1", _base_ok(part_symboles_positifs=0.4), ROB_OK, ref)["criteres_ko"], [6])
        self.assertEqual(ev.verdict_strategie_cycle2("C1", _base_ok(sharpe=0.2), ROB_OK, ref)["criteres_ko"], [2, 7])
        self.assertEqual(ev.verdict_strategie_cycle2("C1", _base_ok(), None, ref)["criteres_ko"], [6])
        self.assertEqual(ev.verdict_strategie_cycle2("C1", _base_ok(), ROB_OK, None)["criteres_ko"], [7])
        for c in ev.verdict_strategie_cycle2("C1", _base_ok(), ROB_OK, ref)["criteres"]:
            self.assertEqual(set(c), {"numero", "nom", "valeur", "seuil", "ok", "detail"})

    def test_critere_7_c2_sharpe_et_deux_tiers_du_drawdown(self):
        ref = {"nom": "r", "sharpe": 0.8, "dd_pire_pct": 12.0}
        self.assertTrue(ev.verdict_strategie_cycle2("C2", _base_ok(dd_pire_pct=8.0), ROB_OK, ref)["retenue"])
        self.assertEqual(ev.verdict_strategie_cycle2("C2", _base_ok(dd_pire_pct=8.01), ROB_OK, ref)["criteres_ko"], [7])
        self.assertEqual(ev.verdict_strategie_cycle2("C2", _base_ok(sharpe=0.8, dd_pire_pct=5.0), ROB_OK, ref)["criteres_ko"], [7])
        self.assertEqual(ev.verdict_strategie_cycle2("C2", _base_ok(), ROB_OK, {"sharpe": 0.1})["criteres_ko"], [7])

    def _resume(self, c1_ok, c2_ok, s3_ok, s3_present=True):
        ref = {"nom": "r", "sharpe": 0.2, "dd_pire_pct": 30.0}
        r = {"strategies": {
            "C1": {"base": _base_ok(sharpe=0.9 if c1_ok else 0.1), "robustesse": ROB_OK, "reference": ref},
            "C2": {"base": _base_ok(sharpe=0.9 if c2_ok else 0.1), "robustesse": ROB_OK, "reference": ref},
            "P": {}}, "composantes": {}}
        if s3_present:
            r["composantes"]["S3"] = {"base": _base_ok(sharpe=0.9 if s3_ok else 0.1, part_symboles_positifs=0.0),
                                      "robustesse": ROB_OK, "reference": {"nom": "US500", "sharpe": 0.6}}
        return r

    def test_regle_p_non_evaluee(self):
        ok, raison = c2.evaluabilite_p(self._resume(False, False, False))
        self.assertFalse(ok)
        self.assertIn("aucune composante", raison)
        v = c2.verdict("P", self._resume(False, False, False))
        self.assertEqual((v["decision"], v["retenue"], v["criteres"]), ("NON ÉVALUÉE", False, []))
        self.assertIn("incomplets", c2.evaluabilite_p(self._resume(False, False, False, s3_present=False))[1])
        for args in ((True, False, False), (False, True, False), (False, False, True)):
            self.assertTrue(c2.evaluabilite_p(self._resume(*args))[0], args)
        # S3 seule : critère de part des symboles NON appliqué (comme au cycle 1), t-stat 3,0 appliquée
        r = self._resume(False, False, True)
        r["composantes"]["S3"]["base"]["tstat"] = 2.9
        self.assertFalse(c2.evaluabilite_p(r)[0])
        # référence de P : le plus grand Sharpe des références des composantes
        self.assertEqual(c2.reference_p(self._resume(True, False, False))["sharpe"], 0.6)
        r = self._resume(True, False, False)
        r["strategies"]["P"] = {"base": _base_ok(sharpe=0.59), "robustesse": ROB_OK}
        self.assertEqual(c2.verdict("P", r)["criteres_ko"], [7])
        r["strategies"]["P"]["base"]["sharpe"] = 0.61
        self.assertTrue(c2.verdict("P", r)["retenue"])

    def test_nouveaux_marches_regle_bloquante(self):
        self.assertFalse(ev.verdict_nouveaux_marches(-0.01, 3)["ok"])
        self.assertIn("ÉCHEC", ev.verdict_nouveaux_marches(-0.01, 3)["decision"])
        self.assertTrue(ev.verdict_nouveaux_marches(0.0, 3)["ok"])
        self.assertFalse(ev.verdict_nouveaux_marches(None, 3)["ok"])
        self.assertFalse(ev.verdict_nouveaux_marches(1.0, 0)["ok"])

    def test_symboles_nouveaux_par_nom_generique(self):
        u = generer_univers(debut="2020-01-01", fin="2021-01-31", graine=1, annees_m15=0,
                            symboles=["US500", "EURUSD", "AUDUSD", "AUS200", "XTIUSD", "BTCUSD"])
        self.assertEqual(c2.symboles_nouveaux(u, ["us500", "EURUSD", "AUDUSD", "UK100"]), ["AUS200", "BTCUSD", "XTIUSD"])
        r = c2.simuler_nouveaux(u, "C2", ["AUS200", "BTCUSD", "XTIUSD"])
        self.assertEqual(set(r.symboles), {"AUS200", "BTCUSD", "XTIUSD"})
        self.assertEqual(set(c2.simuler_nouveaux(u, "C1", ["AUS200", "BTCUSD", "XTIUSD"]).symboles), {"AUS200"})
        rp = c2.simuler_nouveaux(u, "P", ["AUS200", "BTCUSD", "XTIUSD"])
        self.assertEqual(set(rp.symboles), {"AUS200", "BTCUSD", "XTIUSD"})
        self.assertFalse(set(rp.trades["symbole"]) & {"US500", "EURUSD", "AUDUSD"})


# =========================================================================== le moteur voit un vrai avantage

class TestDetection(unittest.TestCase):

    def test_tournant_du_mois_injecte_c1_detecte(self):
        syms = ["US500", "NAS100", "US30", "GER40", "EURUSD"]
        u = generer_univers(debut="2010-01-01", graine=3, symboles=syms, annees_m15=0, tournant_mois=0.002)
        res, m, ref, bs, _ = c2.section_base(u, "C1")
        v = ev.verdict_strategie_cycle2("C1", m, c2.section_robustesse(u, "C1"), ref)
        self.assertTrue(v["retenue"], v["criteres_ko"])
        self.assertGreater(m["tstat"], 3.0)
        self.assertGreater(m["sharpe"], ref["sharpe"])
        self.assertLess(m["sharpe"], 3.0)
        # même graine, sans effet : rien de détecté
        u0 = generer_univers(debut="2010-01-01", graine=3, symboles=syms, annees_m15=0)
        _, m0, ref0, _, _ = c2.section_base(u0, "C1")
        self.assertLess(m0["tstat"], 3.0)
        self.assertFalse(ev.verdict_strategie_cycle2("C1", m0, None, ref0)["retenue"])

    def test_regimes_de_tendance_c2_meilleur_que_la_reference_en_drawdown(self):
        syms = ["US500", "NAS100", "US30", "GER40", "EURUSD", "XAUUSD", "XAGUSD"]
        tend = {"amplitude": 0.4, "periode_jours": 900, "derive_moyenne": 0.15}
        u = generer_univers(debut="2010-01-01", graine=3, symboles=syms, annees_m15=0, tendance=tend)
        res, m, ref, _, _ = c2.section_base(u, "C2")
        self.assertTrue((res.trades["sens"] == 1).all())
        self.assertLessEqual(m["dd_pire_pct"], ref["dd_pire_pct"] * 2 / 3)
        self.assertGreater(m["sharpe"], ref["sharpe"])
        self.assertEqual(ev.verdict_strategie_cycle2("C2", m, None, ref)["criteres"][6]["ok"], True)
        # marche aléatoire (même graine) : pas de critère 7 ni de t-stat
        u0 = generer_univers(debut="2010-01-01", graine=3, symboles=syms, annees_m15=0)
        _, m0, ref0, _, _ = c2.section_base(u0, "C2")
        self.assertLess(m0["tstat"], 3.0)
        self.assertFalse(ev.verdict_strategie_cycle2("C2", m0, None, ref0)["criteres"][6]["ok"])


if __name__ == "__main__":
    unittest.main()
