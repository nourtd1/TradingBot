#!/usr/bin/env python3
"""Export de l'historique MetaTrader 5 pour le backtest de SentiTrade.

À lancer sur le PC Windows, terminal MetaTrader 5 OUVERT et CONNECTÉ
(double-clic sur EXPORTER_DONNEES.bat). Produit dans data/mt5/ le format
exact de docs/SPEC_TECHNIQUE.md, section 2 :

    <SYMBOLE>_M1.csv, <SYMBOLE>_M15.csv, <SYMBOLE>_H1.csv
        colonnes time,open,high,low,close,tick_volume,spread,real_volume ;
        time = heure SERVEUR du broker, "YYYY-MM-DD HH:MM:SS" (aucun fuseau
        appliqué), triées, sans doublon, sans la bougie en cours de formation.
    symbol_info.json
        attributs MT5 du symbole (noms MT5) + "export" + "compte"
        (jamais de login, de nom ni de mot de passe).
    spread_stats.json
        percentiles 50/90/99 du spread (points) par heure serveur et global,
        sur les ticks des 10 derniers jours ouvrés. Structure :
        {"symbole", "unite": "points", "point", "jours": [...], "nb_ticks",
         "global": {"p50", "p90", "p99", "moyenne", "max", "nb_ticks"},
         "par_heure": {"0": {...}, ..., "23": {...}}}  (valeurs null sans tick)

et un rapport lisible dans logs/export_mt5_<date>.txt.

Usage :
    python scripts/exporter_donnees_mt5.py                    # or détecté automatiquement, 5 ans
    python scripts/exporter_donnees_mt5.py --symbole XAUUSD.p --annees 3

Code de sortie : 0 si tout est exporté sans point à regarder, 1 sinon.

À propos des heures : MT5 encode l'heure du serveur comme si c'était un
epoch UTC. On demande donc les plages avec des datetime UTC et on convertit
`time` avec pd.to_datetime(unit="s") en horodatage naïf : c'est directement
l'heure serveur. On n'applique JAMAIS de fuseau.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

try:  # lancé comme script : scripts/ est dans sys.path
    from check_env import (Rapport, choisir_symbole_or, erreur_mt5, est_compte_reel,
                           texte_margin_mode, texte_trade_mode)
except ImportError:  # importé comme module depuis la racine (tests)
    from scripts.check_env import (Rapport, choisir_symbole_or, erreur_mt5, est_compte_reel,
                                   texte_margin_mode, texte_trade_mode)

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_DONNEES = RACINE / "data" / "mt5"
DOSSIER_LOGS = RACINE / "logs"

COLONNES = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
# (suffixe du fichier, constante MT5, valeur documentée de secours, durée d'une bougie en secondes)
TIMEFRAMES = [("M1", "TIMEFRAME_M1", 1, 60),
              ("M15", "TIMEFRAME_M15", 15, 900),
              ("H1", "TIMEFRAME_H1", 16385, 3600)]

JOUR_S = 86400
PAUSE_S = 3.0                     # pause entre deux essais pendant que le terminal télécharge
ATTENTE_MAX_S = 60.0              # attente maximale pour une même demande
CHEVAUCHEMENT = dt.timedelta(days=1)   # recouvrement entre tranches mensuelles
TOLERANCE_DEBUT_JOURS = 7         # au-delà, l'historique obtenu est considéré comme tronqué
TROU_MAX_JOURS = 3                # trou anormal : plus de 3 jours sans bougie, hors week-end
TRANCHES_VIDES_MAX = 2            # tranches vides consécutives = début de l'historique atteint
JOURS_TICKS = 10                  # jours ouvrés pour les statistiques de spread
JOURS_TICKS_SCAN_MAX = 21         # jours calendaires examinés au maximum pour les trouver
TICK_VIEUX_S = 600                # dernier tick plus vieux : marché probablement fermé
ESSAIS_TICK_VIVANT = 15           # secondes d'attente d'un nouveau tick (cotations en direct ?)
LIMITE_PROCHE = 0.9               # barres obtenues >= 90 % de "Max bars" : limite du terminal

# Attributs MT5 recopiés dans symbol_info.json (noms MT5). Les premiers sont exigés par la spec.
ATTRIBUTS_OBLIGATOIRES = ["name", "digits", "point", "trade_contract_size", "volume_min", "volume_step",
                          "volume_max", "trade_stops_level", "trade_tick_size", "trade_tick_value",
                          "currency_profit", "spread"]
ATTRIBUTS_COMPLEMENTAIRES = ["description", "path", "currency_base", "currency_margin",
                             "trade_tick_value_profit", "trade_tick_value_loss", "trade_freeze_level",
                             "volume_limit", "spread_float", "trade_mode", "trade_calc_mode",
                             "trade_exemode", "filling_mode", "order_mode", "swap_mode", "swap_long",
                             "swap_short", "swap_rollover3days", "margin_initial", "margin_maintenance",
                             "margin_hedged", "visible", "select"]

MESSAGE_MAX_BARS = [
    "     Pour récupérer tout l'historique :",
    "       1. dans MetaTrader 5 : Outils > Options > Graphiques (Tools > Options > Charts)",
    "       2. « Nombre max de barres dans le graphique » (Max bars in chart) : choisir Unlimited",
    "       3. OK, puis FERMER et rouvrir MetaTrader 5",
    "       4. relancer EXPORTER_DONNEES.bat",
]


class ErreurExport(Exception):
    """Erreur bloquante avec un message clair pour l'utilisateur."""


def _dormir(secondes: float) -> None:  # remplaçable dans les tests
    time.sleep(secondes)


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def _taille(resultat) -> int:
    try:
        return 0 if resultat is None else len(resultat)
    except TypeError:
        return 0


def _appel_avec_attente(appel, est_suspect, insister: bool = False):
    """Appelle MT5 ; si la réponse est suspecte (historique en cours de
    téléchargement), réessaie après une pause tant que le nombre de lignes
    augmente, sans dépasser ATTENTE_MAX_S. Avec insister=True, une réponse
    vide est réessayée jusqu'au bout du délai."""
    res = appel()
    n = _taille(res)
    if not est_suspect(res) and not (insister and n == 0):
        return res
    essais = int(ATTENTE_MAX_S / PAUSE_S) if PAUSE_S > 0 else 20
    for _ in range(max(1, essais)):
        _dormir(PAUSE_S)
        nouveau = appel()
        m = _taille(nouveau)
        if m > n:  # le terminal télécharge encore : on refait un essai pour voir s'il a fini
            res, n = nouveau, m
            continue
        if insister and n == 0:
            continue
        break
    return res


def _epoch(d: dt.datetime) -> int:
    return int(d.timestamp())


def _texte_epoch(secondes) -> str:
    """Epoch "heure serveur" -> texte, sans aucun fuseau."""
    return (dt.datetime(1970, 1, 1) + dt.timedelta(seconds=int(secondes))).strftime("%Y-%m-%d %H:%M:%S")


def _mois_suivant(d: dt.datetime) -> dt.datetime:
    return d.replace(year=d.year + 1, month=1, day=1) if d.month == 12 else d.replace(month=d.month + 1, day=1)


def tranches_mensuelles(debut: dt.datetime, fin: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
    """Découpe [debut, fin] en mois calendaires qui se chevauchent d'un jour,
    de la plus récente à la plus ancienne."""
    bornes = [debut]
    courant = _mois_suivant(debut.replace(hour=0, minute=0, second=0, microsecond=0))
    while courant < fin:
        bornes.append(courant)
        courant = _mois_suivant(courant)
    bornes.append(fin)
    tranches = []
    for i in range(len(bornes) - 1):
        a = bornes[i] if i == 0 else max(debut, bornes[i] - CHEVAUCHEMENT)
        tranches.append((a, bornes[i + 1]))
    return tranches[::-1]


def nom_fichier_symbole(nom: str) -> str:
    """Nom de symbole utilisable dans un nom de fichier Windows."""
    return "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in nom).strip() or "SYMBOLE"


def _natif(v):
    """Valeur numpy/MT5 -> type JSON natif."""
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)


def _ecrire_atomique(chemin: Path, ecrire) -> None:
    """Écrit dans un fichier temporaire puis le renomme : jamais de fichier à moitié écrit."""
    tmp = chemin.with_name(chemin.name + ".tmp")
    try:
        ecrire(tmp)
        os.replace(tmp, chemin)
    finally:
        if tmp.exists():
            tmp.unlink()


def _ecrire_json(chemin: Path, donnees: dict) -> None:
    texte = json.dumps(donnees, ensure_ascii=False, indent=2) + "\n"
    _ecrire_atomique(chemin, lambda p: p.write_text(texte, encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Barres
# --------------------------------------------------------------------------- #
def telecharger_barres(mt5, symbole: str, code_tf: int, debut: dt.datetime, fin: dt.datetime,
                       r: Rapport, nom_tf: str):
    """Télécharge [debut, fin] par tranches mensuelles (de la plus récente à la
    plus ancienne). Renvoie la liste des tableaux numpy reçus."""
    import numpy as np

    morceaux = []
    vides = 0
    erreurs = []
    for i, (a, b) in enumerate(tranches_mensuelles(debut, fin)):
        limite_suspecte = _epoch(a) + 4 * JOUR_S

        def suspect(res, _lim=limite_suspecte):
            return _taille(res) == 0 or int(res["time"][0]) > _lim

        res = _appel_avec_attente(lambda a=a, b=b: mt5.copy_rates_range(symbole, code_tf, a, b),
                                  suspect, insister=(i == 0))
        if res is None:
            erreurs.append(erreur_mt5(mt5))
        n = _taille(res)
        if n == 0:
            vides += 1
            if morceaux and vides >= TRANCHES_VIDES_MAX:
                break  # plus rien avant : début de l'historique disponible
            if not morceaux and i >= 1:
                break  # rien sur les deux mois les plus récents : inutile d'insister
            continue
        vides = 0
        morceaux.append(np.asarray(res))
    if erreurs and not morceaux:
        r.ecrire(f"     {nom_tf} : MT5 n'a renvoyé aucune barre ({erreurs[-1]})")
    return morceaux


def preparer_barres(morceaux, digits: int, duree_s: int, heure_serveur_now: int | None):
    """Assemble les tranches : dédoublonnage par time, tri, retrait de la bougie
    en cours et des lignes invalides. Renvoie (DataFrame, infos)."""
    import numpy as np
    import pandas as pd

    infos = {"en_cours_retirees": 0, "invalides_retirees": 0}
    if not morceaux:
        return pd.DataFrame(columns=COLONNES), infos
    brut = pd.DataFrame(np.concatenate(morceaux))
    manquantes = [c for c in COLONNES if c not in brut.columns]
    if manquantes:
        raise ErreurExport(f"colonnes absentes de la réponse MT5 : {manquantes}")
    df = brut[COLONNES].copy()
    df = df.drop_duplicates(subset="time", keep="last").sort_values("time", kind="stable")
    if heure_serveur_now is not None:
        en_cours = (df["time"].astype("int64") + duree_s) > heure_serveur_now
        infos["en_cours_retirees"] = int(en_cours.sum())
        df = df[~en_cours]
    prix = df[["open", "high", "low", "close"]]
    invalides = (prix.isna().any(axis=1) | (prix <= 0).any(axis=1)
                 | (df["high"] < prix.max(axis=1)) | (df["low"] > prix.min(axis=1)))
    infos["invalides_retirees"] = int(invalides.sum())
    df = df[~invalides].copy()
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype("float64").round(int(digits))
    for c in ("tick_volume", "spread", "real_volume"):
        df[c] = df[c].astype("int64")
    df["time"] = pd.to_datetime(df["time"].astype("int64"), unit="s")  # naïf = heure serveur
    return df.reset_index(drop=True), infos


def ecrire_csv(df, chemin: Path) -> None:
    _ecrire_atomique(chemin, lambda p: df.to_csv(p, index=False, columns=COLONNES,
                                                 date_format="%Y-%m-%d %H:%M:%S", lineterminator="\n"))


def _week_end_dans(a: int, b: int) -> int:
    """Secondes de samedi/dimanche (calendrier serveur) comprises dans [a, b]."""
    total = 0
    for jour in range(a // JOUR_S, b // JOUR_S + 1):
        if (jour + 3) % 7 >= 5:  # 1970-01-01 était un jeudi ; lundi = 0
            debut, fin = jour * JOUR_S, (jour + 1) * JOUR_S
            total += max(0, min(b, fin) - max(a, debut))
    return total


def trous_anormaux(temps_epoch, duree_s: int) -> list[tuple[str, str, float]]:
    """Trous de plus de TROU_MAX_JOURS jours sans bougie, week-ends exclus.
    Renvoie [(fin de la dernière bougie avant, début de la suivante, jours hors week-end)]."""
    import numpy as np

    t = np.asarray(temps_epoch, dtype="int64")
    if t.size < 2:
        return []
    ecarts = np.diff(t) - duree_s
    trous = []
    for i in np.nonzero(ecarts > TROU_MAX_JOURS * JOUR_S)[0]:
        a, b = int(t[i]) + duree_s, int(t[i + 1])
        hors_we = (b - a - _week_end_dans(a, b)) / JOUR_S
        if hors_we > TROU_MAX_JOURS:
            trous.append((_texte_epoch(a), _texte_epoch(b), round(hors_we, 1)))
    return trous


# --------------------------------------------------------------------------- #
# Spread
# --------------------------------------------------------------------------- #
def _percentiles(valeurs) -> dict:
    import numpy as np

    if len(valeurs) == 0:
        return {"p50": None, "p90": None, "p99": None, "moyenne": None, "max": None, "nb_ticks": 0}
    p50, p90, p99 = np.percentile(valeurs, [50, 90, 99])
    return {"p50": round(float(p50), 1), "p90": round(float(p90), 1), "p99": round(float(p99), 1),
            "moyenne": round(float(np.mean(valeurs)), 2), "max": int(np.max(valeurs)),
            "nb_ticks": int(len(valeurs))}


def statistiques_spread(mt5, symbole: str, point: float, dernier_jour: dt.date) -> dict | None:
    """Percentiles du spread (points) par heure serveur sur les ticks des
    JOURS_TICKS derniers jours ouvrés. Les ticks bruts ne sont pas conservés."""
    import numpy as np

    flags = getattr(mt5, "COPY_TICKS_INFO", 1)
    spreads, heures, jours = [], [], []
    for k in range(JOURS_TICKS_SCAN_MAX):
        jour = dernier_jour - dt.timedelta(days=k)
        if jour.weekday() >= 5:
            continue
        a = dt.datetime(jour.year, jour.month, jour.day, tzinfo=dt.timezone.utc)
        b = a + dt.timedelta(days=1)
        ticks = _appel_avec_attente(lambda a=a, b=b: mt5.copy_ticks_range(symbole, a, b, flags),
                                    lambda res: _taille(res) == 0)
        if _taille(ticks) == 0:
            continue
        bid = np.asarray(ticks["bid"], dtype="float64")
        ask = np.asarray(ticks["ask"], dtype="float64")
        valides = (bid > 0) & (ask >= bid)
        spreads.append(np.rint((ask[valides] - bid[valides]) / point).astype("int64"))
        heures.append((np.asarray(ticks["time"], dtype="int64")[valides] // 3600) % 24)
        jours.append(jour)
        if len(jours) >= JOURS_TICKS:
            break
    if not jours:
        return None
    sp, hr = np.concatenate(spreads), np.concatenate(heures)
    return {
        "symbole": symbole,
        "unite": "points",
        "point": point,
        "methode": "spread = (ask - bid) / point sur les ticks COPY_TICKS_INFO ; heure = heure serveur du tick",
        "jours": [j.isoformat() for j in sorted(jours)],
        "nb_jours": len(jours),
        "nb_ticks": int(sp.size),
        "global": _percentiles(sp),
        "par_heure": {str(h): _percentiles(sp[hr == h]) for h in range(24)},
    }


# --------------------------------------------------------------------------- #
# Symbole et compte
# --------------------------------------------------------------------------- #
def infos_symbole(info) -> dict:
    manquants = [a for a in ATTRIBUTS_OBLIGATOIRES if not hasattr(info, a)]
    if manquants:
        raise ErreurExport(f"symbol_info() ne fournit pas : {', '.join(manquants)}")
    d = {a: _natif(getattr(info, a)) for a in ATTRIBUTS_OBLIGATOIRES}
    d.update({a: _natif(getattr(info, a)) for a in ATTRIBUTS_COMPLEMENTAIRES if hasattr(info, a)})
    return d


def infos_compte(compte) -> dict:
    """Uniquement des informations non identifiantes : ni login, ni nom, ni mot de passe."""
    return {
        "currency": _natif(getattr(compte, "currency", None)),
        "leverage": _natif(getattr(compte, "leverage", None)),
        "margin_mode": texte_margin_mode(getattr(compte, "margin_mode", None))[0],
        "trade_mode": texte_trade_mode(getattr(compte, "trade_mode", None))[0],
        "company": _natif(getattr(compte, "company", None)),
        "server": _natif(getattr(compte, "server", None)),
    }


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #
def _connecter(mt5, r: Rapport):
    """Vérifie terminal et compte. Renvoie (terminal_info, account_info)."""
    r.titre("Terminal MetaTrader 5")
    terminal = mt5.terminal_info()
    if terminal is None:
        raise ErreurExport(f"terminal_info() sans réponse ({erreur_mt5(mt5)})")
    if not getattr(terminal, "connected", False):
        raise ErreurExport("MetaTrader 5 est ouvert mais pas connecté au serveur du broker.\n"
                           "     -> connecte-toi au compte démo (Fichier > Connexion au compte de trading), "
                           "puis relance l'export.")
    r.ecrire(f"[OK] terminal connecté (build {getattr(terminal, 'build', '?')}, "
             f"max barres par graphique : {getattr(terminal, 'maxbars', '?')})")
    compte = mt5.account_info()
    if compte is None:
        raise ErreurExport(f"aucun compte connecté ({erreur_mt5(mt5)}).\n"
                           "     -> connecte-toi au compte démo dans MetaTrader 5, puis relance l'export.")
    c = infos_compte(compte)
    _, mode = texte_trade_mode(getattr(compte, "trade_mode", None))
    r.ecrire(f"     compte {mode}, devise {c['currency']}, levier 1:{c['leverage']}, mode {c['margin_mode']}")
    r.ecrire(f"     broker {c['company']}, serveur {c['server']}")
    if est_compte_reel(mt5, compte):
        r.ecrire("[!!] Compte RÉEL détecté. L'export ne passe aucun ordre, mais la phase actuelle")
        r.ecrire("     se fait UNIQUEMENT sur compte démo : connecte-toi au compte démo du même broker.")
        r.bilan(False, "Compte RÉEL détecté -> utiliser le compte démo pour cette phase")
    if str(c["currency"]).upper() != "USD":
        r.ecrire(f"[!!] devise du compte {c['currency']} : le projet suppose un compte en USD")
        r.bilan(False, f"Devise du compte {c['currency']} -> le projet suppose un compte en USD")
    return terminal, compte


def _choisir_symbole(mt5, demande: str | None, r: Rapport) -> str:
    r.titre("Symbole")
    if demande:
        symbole = demande
        r.ecrire(f"     symbole demandé : {symbole}")
    else:
        symbole, _, explication = choisir_symbole_or(mt5)
        if symbole is None:
            raise ErreurExport(explication)
        r.ecrire(f"[OK] {explication}")
    if not mt5.symbol_select(symbole, True):
        # MT5 réel (build 6317) : symbol_select peut renvoyer False ("Out of memory")
        # alors que le symbole est déjà dans l'Observation du marché. Dans ce cas, on continue.
        info_sel = mt5.symbol_info(symbole)
        if info_sel is not None and bool(getattr(info_sel, "visible", False)):
            r.ecrire(f"[--] symbol_select({symbole}) a échoué ({erreur_mt5(mt5)}), "
                     f"mais le symbole est déjà visible : on continue")
            return symbole
        _, candidats, _ = choisir_symbole_or(mt5)
        aide = f" Symboles de l'or disponibles : {', '.join(candidats)}." if candidats else ""
        raise ErreurExport(f"impossible de sélectionner le symbole {symbole} ({erreur_mt5(mt5)}).{aide}")
    return symbole


def _lire_tick(mt5, symbole: str):
    tick = mt5.symbol_info_tick(symbole)
    return tick if tick is not None and int(getattr(tick, "time", 0) or 0) > 0 else None


def _decalage_serveur(mt5, symbole: str, maintenant: dt.datetime, r: Rapport) -> dict:
    """Décalage heure serveur - UTC = arrondi((tick.time - maintenant UTC) / 3600).

    L'âge du tick ne se mesure pas directement (l'heure serveur est justement
    l'inconnue) : on vérifie que les cotations bougent (nouveau tick en moins de
    ESSAIS_TICK_VIVANT secondes) et que le tick tombe à moins de TICK_VIEUX_S
    d'une heure ronde. Sinon le marché est probablement fermé : décalage NON fiable.
    """
    tick = None
    for _ in range(3):
        tick = _lire_tick(mt5, symbole)
        if tick is not None:
            break
        _dormir(PAUSE_S)
    if tick is None:
        r.ecrire(f"[--] aucun tick reçu pour {symbole} ({erreur_mt5(mt5)}) : décalage serveur inconnu")
        return {"decalage": None, "fiable": False, "dernier_tick": None, "dernier_tick_epoch": None}
    vivant = False
    for _ in range(ESSAIS_TICK_VIVANT):
        _dormir(1.0)
        nouveau = _lire_tick(mt5, symbole)
        if nouveau is not None and int(getattr(nouveau, "time_msc", 0)) != int(getattr(tick, "time_msc", 0)):
            tick, vivant = nouveau, True
            break
    t_tick = int(tick.time)
    ecart = t_tick - maintenant.timestamp()
    decalage = int(round(ecart / 3600))
    residu = abs(ecart - decalage * 3600)
    fiable = vivant and residu <= TICK_VIEUX_S and -12 <= decalage <= 14
    r.ecrire(f"     dernier tick : {_texte_epoch(t_tick)} (heure serveur)")
    if fiable:
        r.ecrire(f"[OK] cotations en direct ; décalage heure serveur - UTC : {decalage:+d} h")
    else:
        r.ecrire(f"[--] AVERTISSEMENT : pas de nouveau tick depuis plus de {ESSAIS_TICK_VIVANT} s, ou dernier tick "
                 f"trop ancien (plus de {TICK_VIEUX_S // 60} min) : marché probablement fermé.")
        r.ecrire(f"     Décalage serveur - UTC estimé à {decalage:+d} h, NON FIABLE. "
                 "Relance l'export pendant l'ouverture du marché (lundi à vendredi) pour le mesurer.")
    return {"decalage": decalage, "fiable": fiable, "dernier_tick": _texte_epoch(t_tick),
            "dernier_tick_epoch": t_tick}


def _exporter_timeframes(mt5, symbole, info, terminal, maintenant, annees, decalage, dossier, r) -> dict:
    debut = maintenant - dt.timedelta(days=365.25 * annees)
    fin = maintenant + dt.timedelta(days=1)  # l'heure serveur est souvent en avance sur UTC
    heure_serveur_now = (_epoch(maintenant) + decalage["decalage"] * 3600) if decalage["fiable"] else None
    maxbars = getattr(terminal, "maxbars", None)
    digits = int(getattr(info, "digits", 2))
    prefixe = nom_fichier_symbole(symbole)
    resume = {}
    for nom_tf, constante, defaut, duree_s in TIMEFRAMES:
        r.titre(f"Bougies {nom_tf}")
        try:
            code_tf = int(getattr(mt5, constante, defaut))
            morceaux = telecharger_barres(mt5, symbole, code_tf, debut, fin, r, nom_tf)
            df, infos = preparer_barres(morceaux, digits, duree_s, heure_serveur_now)
            if df.empty:
                r.ecrire(f"[!!] {nom_tf} : aucune bougie reçue ({erreur_mt5(mt5)})")
                r.bilan(False, f"{nom_tf} : aucune bougie -> vérifie que MT5 est connecté, puis relance")
                continue
            chemin = dossier / f"{prefixe}_{nom_tf}.csv"
            ecrire_csv(df, chemin)
        except ErreurExport:
            raise
        except Exception as e:
            r.ecrire(f"[!!] {nom_tf} : erreur {type(e).__name__} : {e}")
            r.ecrire(traceback.format_exc().rstrip())
            r.bilan(False, f"{nom_tf} : export impossible ({type(e).__name__})")
            continue

        n = len(df)
        premiere, derniere = df["time"].iloc[0], df["time"].iloc[-1]
        r.ecrire(f"[OK] {n} bougies, du {premiere:%Y-%m-%d %H:%M} au {derniere:%Y-%m-%d %H:%M} -> {chemin.name}")
        if infos["en_cours_retirees"]:
            r.ecrire(f"     bougie en cours de formation retirée : {infos['en_cours_retirees']}")
        if infos["invalides_retirees"]:
            r.ecrire(f"[!!] {infos['invalides_retirees']} bougie(s) incohérente(s) (OHLC) retirée(s)")
            r.bilan(False, f"{nom_tf} : {infos['invalides_retirees']} bougie(s) incohérente(s) retirée(s)")

        trous = trous_anormaux(df["time"].to_numpy().astype("datetime64[s]").astype("int64"), duree_s)
        if trous:
            r.ecrire(f"[--] {len(trous)} trou(s) de plus de {TROU_MAX_JOURS} jours hors week-end :")
            for a, b, j in trous[:10]:
                r.ecrire(f"       du {a} au {b} ({j} jours hors week-end)")
            if len(trous) > 10:
                r.ecrire(f"       ... et {len(trous) - 10} autre(s)")
        else:
            r.ecrire(f"     aucun trou de plus de {TROU_MAX_JOURS} jours hors week-end")

        manque_jours = (premiere.to_pydatetime() - debut.replace(tzinfo=None)).days
        tronque = manque_jours > TOLERANCE_DEBUT_JOURS
        cause_limite = False
        if tronque:
            try:
                cause_limite = maxbars is not None and n >= LIMITE_PROCHE * int(maxbars)
            except (TypeError, ValueError):
                cause_limite = False
            r.ecrire(f"{'[!!]' if cause_limite else '[--]'} historique {nom_tf} TRONQUÉ : demandé depuis le "
                     f"{debut:%Y-%m-%d}, obtenu seulement depuis le {premiere:%Y-%m-%d} "
                     f"({manque_jours} jours manquants).")
            if cause_limite:
                r.ecrire(f"     Cause : la limite « Max bars in chart » du terminal ({maxbars} barres) est atteinte.")
                r.bilan(False, f"{nom_tf} : historique tronqué par la limite de barres de MT5 -> "
                               "Outils > Options > Graphiques > Unlimited, redémarrer MT5, relancer")
            else:
                r.ecrire("     Le broker ne semble pas fournir plus d'historique "
                         f"(limite du terminal : {maxbars} barres). Si la limite n'est pas Unlimited :")
            for ligne in MESSAGE_MAX_BARS:
                r.ecrire(ligne)
        resume[nom_tf] = {"fichier": chemin.name, "barres": n,
                          "premiere": f"{premiere:%Y-%m-%d %H:%M:%S}", "derniere": f"{derniere:%Y-%m-%d %H:%M:%S}",
                          "tronque": bool(tronque), "trous_anormaux": len(trous)}
        if not (tronque and cause_limite):
            r.bilan(True, f"{nom_tf} : {n} bougies exportées")
    return resume


def _exporter(mt5, args, maintenant: dt.datetime, dossier: Path, r: Rapport) -> None:
    terminal, compte = _connecter(mt5, r)
    symbole = _choisir_symbole(mt5, args.symbole, r)

    info = mt5.symbol_info(symbole)
    if info is None:
        raise ErreurExport(f"symbol_info({symbole}) sans réponse ({erreur_mt5(mt5)})")
    d_symbole = infos_symbole(info)
    r.ecrire(f"     décimales {d_symbole['digits']}, point {d_symbole['point']}, "
             f"contrat {d_symbole['trade_contract_size']}, volume min {d_symbole['volume_min']}, "
             f"pas {d_symbole['volume_step']}, spread actuel {d_symbole['spread']} points")
    decalage = _decalage_serveur(mt5, symbole, maintenant, r)

    dossier.mkdir(parents=True, exist_ok=True)
    resume = _exporter_timeframes(mt5, symbole, info, terminal, maintenant, args.annees, decalage, dossier, r)

    r.titre("Statistiques de spread")
    try:
        if decalage["dernier_tick_epoch"] is not None:
            dernier_jour = dt.date(1970, 1, 1) + dt.timedelta(days=decalage["dernier_tick_epoch"] // JOUR_S)
        else:
            dernier_jour = maintenant.date()
        stats = statistiques_spread(mt5, symbole, float(d_symbole["point"]), dernier_jour)
        if stats is None:
            r.ecrire(f"[!!] aucun tick reçu sur les {JOURS_TICKS_SCAN_MAX} derniers jours ({erreur_mt5(mt5)})")
            r.bilan(False, "spread_stats.json non écrit : aucun tick reçu")
        else:
            _ecrire_json(dossier / "spread_stats.json", stats)
            g = stats["global"]
            r.ecrire(f"[OK] {stats['nb_ticks']} ticks sur {stats['nb_jours']} jours ouvrés "
                     f"({stats['jours'][0]} au {stats['jours'][-1]})")
            r.ecrire(f"     spread global (points) : médiane {g['p50']}, p90 {g['p90']}, p99 {g['p99']}")
            for h in range(24):
                s = stats["par_heure"][str(h)]
                if s["nb_ticks"]:
                    r.ecrire(f"       {h:02d}h : médiane {s['p50']:>6}  p90 {s['p90']:>6}  p99 {s['p99']:>6}"
                             f"  ({s['nb_ticks']} ticks)")
            if stats["nb_jours"] < JOURS_TICKS:
                r.ecrire(f"[--] seulement {stats['nb_jours']} jours ouvrés avec des ticks (objectif {JOURS_TICKS})")
            r.bilan(True, "spread_stats.json")
    except ErreurExport:
        raise
    except Exception as e:
        r.ecrire(f"[!!] statistiques de spread impossibles : {type(e).__name__} : {e}")
        r.ecrire(traceback.format_exc().rstrip())
        r.bilan(False, f"spread_stats.json non écrit ({type(e).__name__})")

    r.titre("Caractéristiques du symbole")
    build = getattr(terminal, "build", None)
    if build is None:
        try:
            build = mt5.version()[1]
        except Exception:
            build = None
    d_symbole["export"] = {
        "date_utc": f"{maintenant:%Y-%m-%d %H:%M:%S}",
        "decalage_serveur_utc_heures": decalage["decalage"],
        "decalage_fiable": decalage["fiable"],
        "dernier_tick_heure_serveur": decalage["dernier_tick"],
        "build_terminal": _natif(build),
        "max_barres_terminal": _natif(getattr(terminal, "maxbars", None)),
        "annees_demandees": args.annees,
        "timeframes": resume,
    }
    d_symbole["compte"] = infos_compte(compte)
    _ecrire_json(dossier / "symbol_info.json", d_symbole)
    r.ecrire("[OK] symbol_info.json")
    r.bilan(True, "symbol_info.json")


def enregistrer(r: Rapport, maintenant: dt.datetime, dossier_logs: Path) -> Path:
    dossier_logs.mkdir(parents=True, exist_ok=True)
    chemin = dossier_logs / f"export_mt5_{maintenant:%Y%m%d-%H%M%S}.txt"
    chemin.write_text("\n".join(r.lignes) + "\n", encoding="utf-8")
    return chemin


def main(argv: list[str] | None = None, maintenant: dt.datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export de l'historique MetaTrader 5 (SentiTrade)")
    parser.add_argument("--symbole", help="nom exact du symbole chez le broker (sinon détection automatique)")
    parser.add_argument("--annees", type=float, default=5.0, help="années d'historique demandées (défaut 5)")
    parser.add_argument("--dossier", type=Path, default=DOSSIER_DONNEES, help=argparse.SUPPRESS)
    parser.add_argument("--logs", type=Path, default=DOSSIER_LOGS, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")  # console Windows : jamais de plantage d'affichage
    except Exception:
        pass

    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    r = Rapport()
    r.ecrire("SentiTrade - export de l'historique MetaTrader 5")
    r.ecrire(f"Date : {maintenant:%Y-%m-%d %H:%M:%S} UTC | Python {platform.python_version()}")
    r.ecrire(f"Demande : {args.annees:g} an(s) d'historique, symbole "
             f"{args.symbole or 'détecté automatiquement'}, dossier {args.dossier}")

    mt5 = None
    initialise = False
    try:
        if not 0 < args.annees <= 30:
            raise ErreurExport("--annees doit être compris entre 0 et 30")
        for lib in ("numpy", "pandas"):
            try:
                importlib.import_module(lib)
            except Exception as e:
                raise ErreurExport(f"la librairie {lib} est absente ou cassée ({type(e).__name__}) : "
                                   "relance INSTALLER.bat") from None
        try:
            mt5 = importlib.import_module("MetaTrader5")
        except Exception as e:
            raise ErreurExport(f"le module MetaTrader5 est absent ({type(e).__name__}). Il n'existe que sous "
                               "Windows : lance d'abord INSTALLER.bat sur le PC.") from None
        try:
            initialise = bool(mt5.initialize())
        except Exception as e:
            initialise = False
            r.ecrire(f"     initialize() a planté : {type(e).__name__} : {e}")
        if not initialise:
            raise ErreurExport("impossible de joindre le terminal MetaTrader 5.\n"
                               "     -> ouvre MetaTrader 5 et connecte-toi au compte démo, puis relance l'export.\n"
                               f"     erreur MT5 : {erreur_mt5(mt5)}")
        _exporter(mt5, args, maintenant, args.dossier, r)
    except ErreurExport as e:
        r.ecrire(f"[!!] {e}")
        r.bilan(False, str(e).splitlines()[0])
    except Exception as e:
        r.ecrire(f"[!!] Erreur inattendue : {type(e).__name__} : {e}")
        r.ecrire(traceback.format_exc().rstrip())
        r.bilan(False, f"Erreur inattendue ({type(e).__name__}) -> dis-le à Claude")
    finally:
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass

    r.titre("RÉSUMÉ")
    for ok, texte in r.bilans:
        r.ecrire(f"{'[OK]' if ok else '[!!]'} {texte}")
    problemes = sum(1 for ok, _ in r.bilans if not ok)
    r.ecrire()
    if problemes == 0 and r.bilans:
        r.ecrire(f"=> EXPORT TERMINÉ : fichiers dans {args.dossier}")
        code = 0
    else:
        r.ecrire(f"=> {max(problemes, 1)} point(s) à regarder. Claude peut lire ce rapport et t'expliquer quoi faire.")
        code = 1
    try:
        print(f"\nRapport enregistré : {enregistrer(r, maintenant, args.logs)}")
    except OSError as e:
        print(f"\n[!!] Impossible d'enregistrer le rapport : {e}")
    return code


if __name__ == "__main__":
    sys.exit(main())
