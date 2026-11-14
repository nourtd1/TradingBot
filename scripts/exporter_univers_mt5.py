#!/usr/bin/env python3
"""Export de l'univers de recherche multi-marchés depuis MetaTrader 5.

À lancer sur le PC Windows, terminal MetaTrader 5 OUVERT et CONNECTÉ au compte
démo (double-clic sur EXPORTER_UNIVERS.bat). Univers : docs/RECHERCHE_PLAN.md,
section 1. Les noms génériques (EURUSD, US500...) sont traduits en noms du
broker grâce à config/univers_symboles.json (alias + table « forcer »).

Sorties (contrat partagé avec la recherche, ne pas changer sans la prévenir).
<DOSSIER> vaut data/univers par défaut, ou data/univers_<nom> avec --dossier
(un dossier par broker : on ne mélange jamais deux serveurs dans un même dossier).

    <DOSSIER>/univers.json
        {"genere_le_utc", "serveur", "societe",
         "decalage_serveur_utc_heures", "decalage_fiable", "decalage_mesure_le_utc",
         "build_terminal",
         "symboles": {"<GENERIQUE>": {"nom_broker", "classe", "dossier", "trade_mode_texte",
                      "timeframes": {"D1": {"barres", "premiere", "derniere"}, ...}}},
         "absents": {"<GENERIQUE>": "raison"}}
        serveur / societe : account_info().server et .company (jamais le login ni le nom).
        trade_mode_texte : "complet", "désactivé" (pas tradable sur ce compte), etc.
        decalage_mesure_le_utc : date de la mesure du décalage (un export partiel garde
        un décalage fiable déjà mesuré plutôt qu'une mesure non fiable).
    <DOSSIER>/<GENERIQUE>/D1.csv, H1.csv, M15.csv (M15 : 6 symboles seulement)
        colonnes time,open,high,low,close,tick_volume,spread,real_volume ;
        time = heure SERVEUR naïve "YYYY-MM-DD HH:MM:SS", trié, sans doublon,
        sans la bougie en cours de formation.
    <DOSSIER>/<GENERIQUE>/symbol_info.json   (noms MT5 + swap_mode_texte, trade_mode_texte)
    <DOSSIER>/<GENERIQUE>/spread_stats.json  (structure de exporter_donnees_mt5.py ;
        absent si aucun tick n'a été reçu, ce que le rapport signale)

et un rapport lisible dans logs/export_univers_<date>.txt.

Usage :
    python scripts/exporter_univers_mt5.py                       # tout l'univers
    python scripts/exporter_univers_mt5.py --symboles EURUSD,US500
    python scripts/exporter_univers_mt5.py --annees 20 --annees-m15 5
    python scripts/exporter_univers_mt5.py --dossier data/univers_monbroker
    python scripts/exporter_univers_mt5.py --lister              # liste des symboles du broker
    python scripts/exporter_univers_mt5.py --terminal "C:\\Program Files\\MonBroker MT5\\terminal64.exe"

Code de sortie : 0 si, pour chaque classe (forex, métaux, indices, énergies,
crypto) dont au moins un symbole existe chez le broker, au moins un symbole a
été exporté ; 1 sinon.

Sécurité : aucun ordre n'est passé ; un compte réel arrête l'export (démo
uniquement) ; ni login, ni nom, ni mot de passe ne sont lus pour être écrits
(seuls le serveur et la société sont notés). Les fonctions MT5 (connexion, téléchargement par
tranches, retrait de la bougie en cours, décalage serveur, statistiques de
spread) viennent de scripts/exporter_donnees_mt5.py et scripts/check_env.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import platform
import re
import shutil
import sys
import traceback
from pathlib import Path

try:  # lancé comme script : scripts/ est dans sys.path
    import check_env as ce
    import exporter_donnees_mt5 as ex
except ImportError:  # importé comme module depuis la racine (tests)
    from scripts import check_env as ce
    from scripts import exporter_donnees_mt5 as ex

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_UNIVERS = RACINE / "data" / "univers"
DOSSIER_LOGS = RACINE / "logs"
CHEMIN_CONFIG = RACINE / "config" / "univers_symboles.json"

CLASSES = ("forex", "metaux", "indices", "energies", "crypto")
NOMS_CLASSES = {"forex": "forex", "metaux": "métaux", "indices": "indices", "energies": "énergies",
                "crypto": "crypto"}
# Classes reconnues par mots-clés (path / description) plutôt que par devise de base
CLASSES_MOTS_CLES = ("indices", "energies")
# Nom du dossier de sortie : data/univers ou data/univers_<nom> (un dossier par broker)
MOTIF_DOSSIER = re.compile(r"^univers(_[A-Za-z0-9-]+)?$")
# Décalage heure serveur - UTC plausible (en heures) ; hors de cet intervalle, la mesure est rejetée
DECALAGE_MIN, DECALAGE_MAX = -12, 14
# Plan pré-enregistré (RECHERCHE_PLAN.md §1) : M15 seulement pour ces symboles
SYMBOLES_M15 = ("XAUUSD", "EURUSD", "GBPUSD", "US500", "NAS100", "GER40")
# (nom, constante MT5, valeur documentée de secours, durée d'une bougie en secondes)
TF_D1 = ("D1", "TIMEFRAME_D1", 16408, 86400)
TF_H1 = ("H1", "TIMEFRAME_H1", 16385, 3600)
TF_M15 = ("M15", "TIMEFRAME_M15", 15, 900)
# symboles essayés en premier pour mesurer le décalage serveur (la crypto cote le week-end)
ORDRE_DECALAGE = ("EURUSD", "BTCUSD", "XAUUSD", "ETHUSD", "GBPUSD")
ESSAIS_DECALAGE_MAX = 3

# Résolution des noms
PREFIXES_IGNORES = "#!._"          # ex. "#US30", ".DE40"
SEPARATEURS_SUFFIXE = ".-_#+!"      # ex. "EURUSD.p", "US500-cash", "XAUUSD_i"
SUFFIXE_SEPARE_MAX = 10
SUFFIXE_LETTRES_MAX = 5             # ex. "EURUSDm", "EURUSDpro", "US500Cash"
ALIAS_COURT_MAX = 2                 # alias de 2 caractères ou moins (« CL ») : pas de lettres collées
MOTS_ACTION_PATH = ("STOCK", "SHARE", "EQUIT", "WARRANT", "FUND")
MOTS_ACTION_DESCRIPTION = {"ETF", "ETFS", "ETN", "ETNS", "SHARES", "ADR", "FUND", "FUNDS", "TRUST",
                           "WARRANT", "WARRANTS"}
MOTS_INDICE = ("INDE", "INDIC", "INDIZ", "IDX")   # index, indices, indizes, idx
MOTS_ENERGIE = ("ENERG", "OIL", "CRUDE", "PETROL", "GAS")
# Contrats à échéance : mois dans le nom (CL-DEC26, WTI_MAR2027, BRENT-Z6...)
MOIS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_RE_MOIS_COLLE = re.compile(r"(?:%s)(?:\d{4}|\d{2})(?!\d)|(?<![A-Z0-9])\d{2}(?:%s)" % ("|".join(MOIS), "|".join(MOIS)))
_RE_JETON_DATE = re.compile(r"^(?:(?:%s)\d{0,4}|[FGHJKMNQUVXZ]\d{1,2}|\d{2}|\d{4}|\d{6}|\d{8})$" % "|".join(MOIS))
# ENUM_SYMBOL_CALC_MODE interdits (actions, obligations, collatéral), reconnus à leur libellé
MOTS_CALC_INTERDITS = ("STOCKS", "BONDS", "COLLATERAL")

# Libellés des énumérations (documentation MetaQuotes), complétés par les constantes du module.
SWAP_MODES = {0: "SYMBOL_SWAP_MODE_DISABLED", 1: "SYMBOL_SWAP_MODE_POINTS",
              2: "SYMBOL_SWAP_MODE_CURRENCY_SYMBOL", 3: "SYMBOL_SWAP_MODE_CURRENCY_MARGIN",
              4: "SYMBOL_SWAP_MODE_CURRENCY_DEPOSIT", 5: "SYMBOL_SWAP_MODE_INTEREST_CURRENT",
              6: "SYMBOL_SWAP_MODE_INTEREST_OPEN", 7: "SYMBOL_SWAP_MODE_REOPEN_CURRENT",
              8: "SYMBOL_SWAP_MODE_REOPEN_BID"}
CALC_MODES = {0: "SYMBOL_CALC_MODE_FOREX", 1: "SYMBOL_CALC_MODE_FUTURES", 2: "SYMBOL_CALC_MODE_CFD",
              3: "SYMBOL_CALC_MODE_CFDINDEX", 4: "SYMBOL_CALC_MODE_CFDLEVERAGE",
              5: "SYMBOL_CALC_MODE_FOREX_NO_LEVERAGE", 32: "SYMBOL_CALC_MODE_EXCH_STOCKS",
              33: "SYMBOL_CALC_MODE_EXCH_FUTURES", 34: "SYMBOL_CALC_MODE_EXCH_FUTURES_FORTS",
              35: "SYMBOL_CALC_MODE_EXCH_OPTIONS", 36: "SYMBOL_CALC_MODE_EXCH_OPTIONS_MARGIN",
              37: "SYMBOL_CALC_MODE_EXCH_BONDS", 38: "SYMBOL_CALC_MODE_EXCH_STOCKS_MOEX",
              39: "SYMBOL_CALC_MODE_EXCH_BONDS_MOEX", 64: "SYMBOL_CALC_MODE_SERV_COLLATERAL"}
JOURS_SEMAINE = {0: "dimanche", 1: "lundi", 2: "mardi", 3: "mercredi", 4: "jeudi", 5: "vendredi",
                 6: "samedi"}  # ENUM_DAY_OF_WEEK (swap_rollover3days)
# Historique minimal du plan (RECHERCHE_PLAN.md §7.1), signalé dans le rapport
ANNEES_MIN = {"D1": 8.0, "M15": 4.0}
TOUT_UNIVERS = "tout l'univers"
TRADE_MODES_SYMBOLE = {0: "désactivé", 1: "achat seul", 2: "vente seule", 3: "clôture seule", 4: "complet"}

# Champs de symbol_info recopiés en plus de ceux de exporter_donnees_mt5 (noms MT5)
ATTRIBUTS_SUPPLEMENTAIRES = ["custom", "chart_mode", "expiration_mode", "order_gtc_mode", "start_time",
                             "expiration_time", "margin_hedged_use_leg", "trade_accrued_interest",
                             "trade_face_value", "trade_liquidity_rate", "exchange", "isin", "basis",
                             "category", "bank", "page", "formula", "option_mode", "option_right"]


class ErreurSymbole(Exception):
    """Échec limité à un symbole : il part dans « absents », les autres continuent."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def _liste_textes(valeur, quoi: str) -> list[str]:
    if isinstance(valeur, str):
        valeur = [valeur]
    if not isinstance(valeur, list) or not valeur or not all(isinstance(v, str) and v.strip() for v in valeur):
        raise ex.ErreurExport(f"{quoi} : liste de textes non vide attendue")
    return [v.strip() for v in valeur]


def charger_config(chemin: Path) -> dict:
    """Lit et vérifie config/univers_symboles.json. Renvoie
    {"symboles": {gen: {"classe", "alias", "base", "profit", "mots_cles", "mots_exclus"}},
     "forcer": {gen: nom}}.

    Indices et énergies : reconnus par « mots_cles » (description) ou par un mot de la classe
    dans le path/la description ; pas de « base ». Autres classes : « base » obligatoire,
    « mots_cles » facultatif (s'il est donné, la description ou le path doit en contenir un).
    « mots_exclus » (facultatif, toutes classes) : aucun ne doit apparaître dans le nom, le
    path ou la description (ex. « BRENT » pour le WTI)."""
    try:
        brut = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ex.ErreurExport(f"fichier de configuration absent : {chemin}") from None
    except (OSError, ValueError) as e:
        raise ex.ErreurExport(f"{chemin} illisible ({type(e).__name__} : {e}). "
                              "Vérifie les virgules et guillemets, ou demande à Claude.") from None
    if not isinstance(brut, dict) or not isinstance(brut.get("symboles"), dict) or not brut["symboles"]:
        raise ex.ErreurExport(f"{chemin} : section « symboles » absente ou vide")
    symboles = {}
    for gen, spec in brut["symboles"].items():
        g = str(gen).strip().upper()
        if not isinstance(spec, dict):
            raise ex.ErreurExport(f"{chemin} : {gen} doit être un objet")
        classe = spec.get("classe")
        if classe not in CLASSES:
            raise ex.ErreurExport(f"{chemin} : {gen}, classe « {classe} » inconnue ({', '.join(CLASSES)})")
        d = {"classe": classe, "alias": _liste_textes(spec.get("alias", [g]), f"{gen}.alias"),
             "profit": [v.upper() for v in _liste_textes(spec.get("profit"), f"{gen}.profit")],
             "base": [], "mots_cles": [], "mots_exclus": []}
        if classe in CLASSES_MOTS_CLES:
            d["mots_cles"] = [v.upper() for v in _liste_textes(spec.get("mots_cles", [g]), f"{gen}.mots_cles")]
        else:
            d["base"] = [v.upper() for v in _liste_textes(spec.get("base"), f"{gen}.base")]
            if "mots_cles" in spec:
                d["mots_cles"] = [v.upper() for v in _liste_textes(spec["mots_cles"], f"{gen}.mots_cles")]
        if "mots_exclus" in spec:
            d["mots_exclus"] = [v.upper() for v in _liste_textes(spec["mots_exclus"], f"{gen}.mots_exclus")]
        symboles[g] = d
    forcer = brut.get("forcer") or {}
    if not isinstance(forcer, dict):
        raise ex.ErreurExport(f"{chemin} : « forcer » doit être un objet {{\"GENERIQUE\": \"NOM_BROKER\"}}")
    forcer_ok = {}
    for gen, nom in forcer.items():
        g = str(gen).strip().upper()
        if g not in symboles:
            raise ex.ErreurExport(f"{chemin} : « forcer » cite {gen}, absent de l'univers")
        if not isinstance(nom, str) or not nom.strip():
            raise ex.ErreurExport(f"{chemin} : « forcer » {gen} doit être un nom de symbole")
        forcer_ok[g] = nom.strip()
    return {"symboles": symboles, "forcer": forcer_ok}


# --------------------------------------------------------------------------- #
# Résolution des noms
# --------------------------------------------------------------------------- #
def _norm(texte) -> str:
    return "".join(c for c in str(texte).upper() if c not in "/& ")


def correspond_alias(nom: str, alias: str) -> bool:
    """Vrai si le nom du broker est l'alias, éventuellement avec un préfixe
    (#, !, ., _) ou un suffixe de broker : séparateur puis texte court
    (".p", "-cash", "_i", ".ecn") ou quelques lettres ("m", "pro", "Cash").
    Des chiffres collés à l'alias sont refusés (US30 n'est pas US300)."""
    n = _norm(nom).lstrip(PREFIXES_IGNORES)
    a = _norm(alias)
    if not a or not n.startswith(a):
        return False
    reste = n[len(a):]
    if not reste:
        return True
    if reste[0] in SEPARATEURS_SUFFIXE:
        return len(reste) <= SUFFIXE_SEPARE_MAX
    if len(a) <= ALIAS_COURT_MAX:  # « CL » : CL, CL.cash, mais pas CLOROX ni CLB
        return False
    return reste.isalpha() and len(reste) <= SUFFIXE_LETTRES_MAX


def rang_alias(nom: str, alias: list[str]) -> int | None:
    for i, a in enumerate(alias):
        if correspond_alias(nom, a):
            return i
    return None


def _texte(s, attr: str) -> str:
    return str(getattr(s, attr, "") or "").strip()


def valider_candidat(s, spec: dict, force: bool = False, mt5=None) -> tuple[str | None, list[str]]:
    """Vérifie qu'un symbole du broker est bien l'instrument attendu.
    Renvoie (raison du rejet ou None, avertissements)."""
    avert: list[str] = []
    chemin = _texte(s, "path").upper()
    description = _texte(s, "description").upper()
    if getattr(s, "custom", False):
        return "symbole personnalisé (custom)", avert
    jetons_path = [j for j in re.split(r"[\\/ ._\-]+", chemin) if j]
    if any(m in chemin for m in MOTS_ACTION_PATH) or any(j.startswith("ETF") for j in jetons_path):
        return f"action ou ETF (path « {_texte(s, 'path')} »)", avert
    mots_desc = set(re.findall(r"[A-Z0-9]+", description))
    if mots_desc & MOTS_ACTION_DESCRIPTION:
        return f"action ou ETF (description « {_texte(s, 'description')} »)", avert
    calc = texte_calc_mode(mt5, getattr(s, "trade_calc_mode", None))
    if any(m in calc for m in MOTS_CALC_INTERDITS):
        return f"mode de calcul {calc} (action ou obligation)", avert
    date = echeance_dans_nom(_texte(s, "name"))
    if date:
        return (f"contrat à échéance daté (« {date} » dans le nom) : pas d'historique continu, "
                "il faut le CFD continu (sans date)"), avert
    nom_u = _texte(s, "name").upper()
    exclus = [m for m in spec.get("mots_exclus", []) if m in chemin or m in description or m in nom_u]
    if exclus:
        return f"évoque un autre instrument (« {exclus[0]} » dans le nom, le path ou la description)", avert
    echeance = _a_echeance(mt5, s)
    if echeance:
        avert.append(f"attention : {echeance}, sans date dans le nom : vérifie avec --lister qu'il s'agit "
                     "bien d'un CFD continu")
    base = _texte(s, "currency_base").upper()
    profit = _texte(s, "currency_profit").upper()
    classe = spec["classe"]
    if classe in CLASSES_MOTS_CLES:
        if not profit:
            if not force:
                return "devise de cotation non renseignée", avert
            avert.append("devise de cotation non renseignée par le broker (nom forcé : accepté)")
        elif profit not in spec["profit"]:
            return f"devise de cotation {profit} au lieu de {'/'.join(spec['profit'])}", avert
        mots_classe = MOTS_INDICE if classe == "indices" else MOTS_ENERGIE
        quoi = "un indice" if classe == "indices" else "une énergie"
        precis = any(k in description for k in spec["mots_cles"])
        evoque = precis or any(m in chemin or m in description for m in mots_classe)
        if not evoque:
            if not force:
                return f"ni le path ni la description n'évoquent {quoi}", avert
            avert.append(f"ni le path ni la description n'évoquent {quoi} (nom forcé : accepté)")
        elif classe == "energies" and not precis:
            avert.append(f"attention : la description ne précise pas l'instrument (attendu : "
                         f"{', '.join(spec['mots_cles'][:3])}...) : vérifie avec --lister")
        return None, avert
    if not base or not profit:
        if not force:
            return f"devises non renseignées (base « {base} », cotation « {profit} »)", avert
        avert.append("devises non renseignées par le broker (nom forcé : accepté)")
        return None, avert
    if base not in spec["base"] or profit not in spec["profit"]:
        return (f"devises {base}/{profit} au lieu de {'|'.join(spec['base'])}/{'|'.join(spec['profit'])}",
                avert)
    if spec.get("mots_cles") and not any(k in description for k in spec["mots_cles"]):
        if not force:
            return f"la description ne contient ni {', '.join(spec['mots_cles'])}", avert
        avert.append("la description ne confirme pas l'instrument (nom forcé : accepté)")
    return None, avert


def echeance_dans_nom(nom: str) -> str | None:
    """Renvoie le morceau du nom qui désigne une échéance (« DEC26 », « Z6 », « 2612 »...) ou None.
    Le premier morceau (le nom de l'instrument : US30, HK50...) n'est jamais lu comme une date,
    sauf s'il porte un mois suivi d'une année (CLDEC26)."""
    n = str(nom).upper()
    m = _RE_MOIS_COLLE.search(n)
    if m:
        return m.group(0)
    jetons = [j for j in re.split(r"[^A-Z0-9]+", n) if j]
    for j in jetons[1:]:
        if _RE_JETON_DATE.match(j):
            return j
    return None


def _a_echeance(mt5, s) -> str | None:
    """Décrit l'échéance d'un symbole (date d'expiration ou mode de calcul « futures »), sinon None."""
    try:
        expiration = int(getattr(s, "expiration_time", 0) or 0)
    except (TypeError, ValueError):
        expiration = 0
    if expiration > 0:
        jour = dt.datetime.fromtimestamp(expiration, dt.timezone.utc)
        return f"contrat à échéance (expiration le {jour:%Y-%m-%d})"
    calc = texte_calc_mode(mt5, getattr(s, "trade_calc_mode", None))
    if "FUTURES" in calc:
        return f"contrat à terme (mode de calcul {calc})"
    return None


def _plein(mt5) -> int:
    return int(getattr(mt5, "SYMBOL_TRADE_MODE_FULL", ce.SYMBOL_TRADE_MODE_FULL))


def _tradable(mt5, s) -> bool:
    try:
        return int(getattr(s, "trade_mode", -1)) == _plein(mt5)
    except (TypeError, ValueError):
        return False


def tous_les_symboles(mt5, config: dict) -> list:
    """Tous les symboles du terminal. Repli, si symbols_get() échoue : une
    recherche par alias (symbols_get(group="*ALIAS*"))."""
    try:
        res = mt5.symbols_get()
    except Exception:
        res = None
    if res:
        return [s for s in res if s is not None and _texte(s, "name")]
    trouves: dict = {}
    for spec in config["symboles"].values():
        for a in spec["alias"]:
            motif = "".join(c for c in a if c.isalnum())
            try:
                res = mt5.symbols_get(group=f"*{motif}*")
            except Exception:
                res = None
            for s in res or ():
                trouves.setdefault(_texte(s, "name"), s)
    for nom in config["forcer"].values():
        try:
            res = mt5.symbols_get(group=nom)
        except Exception:
            res = None
        for s in res or ():
            trouves.setdefault(_texte(s, "name"), s)
    return list(trouves.values())


def resoudre(mt5, symboles: list, config: dict, generiques: list[str]) -> tuple[dict, dict, dict]:
    """Choisit le symbole du broker de chaque générique.
    Renvoie (choix {gen: SymbolInfo}, absents {gen: raison}, journal {gen: [lignes]})."""
    par_nom = {_texte(s, "name"): s for s in symboles}
    choix, absents, journal = {}, {}, {}
    for gen in generiques:
        spec = config["symboles"][gen]
        lignes = journal.setdefault(gen, [])
        if gen in config["forcer"]:
            nom = config["forcer"][gen]
            s = par_nom.get(nom)
            if s is None:
                absents[gen] = f"nom forcé « {nom} » introuvable chez le broker"
                continue
            raison, avert = valider_candidat(s, spec, force=True, mt5=mt5)
            if raison:
                absents[gen] = f"nom forcé « {nom} » refusé : {raison}"
                continue
            lignes.append(f"nom imposé par « forcer » : {nom}")
            lignes.extend(avert)
            choix[gen] = s
            continue
        valides, rejets = [], []
        for nom, s in par_nom.items():
            rang = rang_alias(nom, spec["alias"])
            if rang is None:
                continue
            raison, avert = valider_candidat(s, spec, mt5=mt5)
            if raison:
                rejets.append(f"{nom} rejeté : {raison}")
            else:
                # un CFD continu passe avant un contrat à échéance, puis tradable, visible, nom court
                cle = (_a_echeance(mt5, s) is not None, not _tradable(mt5, s),
                       not bool(getattr(s, "visible", False)), len(nom), rang)
                valides.append((cle, nom, s, avert))
        lignes.extend(sorted(rejets))
        if not valides:
            detail = f" ({len(rejets)} candidat(s) rejeté(s), voir le rapport)" if rejets else ""
            absents[gen] = f"introuvable chez le broker{detail} : alias cherchés {', '.join(spec['alias'])}"
            continue
        valides.sort(key=lambda v: (v[0], v[1]))
        if len(valides) >= 2 and valides[0][0] == valides[1][0]:
            ex_aequo = [v[1] for v in valides if v[0] == valides[0][0]]
            absents[gen] = (f"ambigu : {', '.join(ex_aequo)} conviennent autant l'un que l'autre. "
                            f"Choisis-en un dans config/univers_symboles.json, section « forcer »")
            continue
        cle, nom, s, avert = valides[0]
        qualites = [q for q, ok in (("tradable", not cle[1]), ("visible", not cle[2])) if ok]
        if len(valides) == 1:
            lignes.append(f"retenu : {nom}" + (f" ({', '.join(qualites)})" if qualites else ""))
        else:
            autres = ", ".join(v[1] for v in valides[1:])
            lignes.append(f"retenu : {nom} parmi {len(valides)} candidats valides (autres : {autres}) ; "
                          f"règle : CFD continu (sans échéance), puis tradable, puis visible "
                          f"(retenu : {', '.join(['continu'] * (not cle[0]) + qualites) or 'aucune de ces qualités'}), "
                          "puis nom le plus court, puis ordre des alias")
        lignes.extend(avert)
        if cle[1]:
            lignes.append(f"attention : {nom} n'est pas tradable chez ce broker "
                          f"(trade_mode {texte_trade_mode_symbole(getattr(s, 'trade_mode', None))})")
        choix[gen] = s
    # un même symbole du broker ne peut servir deux génériques
    vus: dict = {}
    for gen in list(choix):
        nom = _texte(choix[gen], "name")
        if nom in vus:
            absents[gen] = f"{nom} est déjà utilisé pour {vus[nom]}"
            del choix[gen]
        else:
            vus[nom] = gen
    return choix, absents, journal


# --------------------------------------------------------------------------- #
# Libellés
# --------------------------------------------------------------------------- #
def _libelle_enum(mt5, valeur, table: dict, prefixe: str) -> str:
    try:
        v = int(valeur)
    except (TypeError, ValueError):
        return f"INCONNU_{valeur}"
    noms = dict(table)
    for nom in dir(mt5) if mt5 is not None else ():
        if nom.startswith(prefixe):
            try:
                noms.setdefault(int(getattr(mt5, nom)), nom)
            except (TypeError, ValueError):
                pass
    return noms.get(v, f"INCONNU_{v}")


def texte_swap_mode(mt5, valeur) -> str:
    return _libelle_enum(mt5, valeur, SWAP_MODES, "SYMBOL_SWAP_MODE_")


def texte_calc_mode(mt5, valeur) -> str:
    return _libelle_enum(mt5, valeur, CALC_MODES, "SYMBOL_CALC_MODE_")


def texte_trade_mode_symbole(valeur) -> str:
    try:
        return TRADE_MODES_SYMBOLE.get(int(valeur), f"inconnu ({valeur})")
    except (TypeError, ValueError):
        return f"inconnu ({valeur})"


def infos_symbole_univers(mt5, info) -> dict:
    """symbol_info complet (noms MT5) pour SymboleSpec.depuis_json et le calcul des coûts."""
    d = ex.infos_symbole(info)
    d.update({a: ex._natif(getattr(info, a)) for a in ATTRIBUTS_SUPPLEMENTAIRES if hasattr(info, a)})
    d["swap_mode_texte"] = texte_swap_mode(mt5, d.get("swap_mode"))
    d["trade_calc_mode_texte"] = texte_calc_mode(mt5, d.get("trade_calc_mode"))
    d["trade_mode_texte"] = texte_trade_mode_symbole(d.get("trade_mode"))
    return d


# --------------------------------------------------------------------------- #
# Téléchargement
# --------------------------------------------------------------------------- #
def tranches_annuelles(debut: dt.datetime, fin: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
    """Découpe [debut, fin] en années civiles qui se chevauchent d'un jour,
    de la plus récente à la plus ancienne (D1)."""
    bornes = [debut]
    courant = debut.replace(year=debut.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    while courant < fin:
        bornes.append(courant)
        courant = courant.replace(year=courant.year + 1)
    bornes.append(fin)
    tranches = []
    for i in range(len(bornes) - 1):
        a = bornes[i] if i == 0 else max(debut, bornes[i] - ex.CHEVAUCHEMENT)
        tranches.append((a, bornes[i + 1]))
    return tranches[::-1]


def telecharger_d1(mt5, symbole: str, code_tf: int, debut: dt.datetime, fin: dt.datetime,
                   r: ce.Rapport) -> list:
    """Même logique que exporter_donnees_mt5.telecharger_barres (attente du
    téléchargement, arrêt au début de l'historique), par tranches annuelles."""
    import numpy as np

    morceaux, vides, erreurs = [], 0, []
    for i, (a, b) in enumerate(tranches_annuelles(debut, fin)):
        limite_suspecte = ex._epoch(a) + 4 * ex.JOUR_S

        def suspect(res, _lim=limite_suspecte):
            return ex._taille(res) == 0 or int(res["time"][0]) > _lim

        res = ex._appel_avec_attente(lambda a=a, b=b: mt5.copy_rates_range(symbole, code_tf, a, b),
                                     suspect, insister=(i == 0))
        if res is None:
            erreurs.append(ce.erreur_mt5(mt5))
        if ex._taille(res) == 0:
            vides += 1
            if morceaux and vides >= ex.TRANCHES_VIDES_MAX:
                break
            if not morceaux and i >= 1:
                break
            continue
        vides = 0
        morceaux.append(np.asarray(res))
    if erreurs and not morceaux:
        r.ecrire(f"     D1 : MT5 n'a renvoyé aucune barre ({erreurs[-1]})")
    return morceaux


def selectionner(mt5, nom: str, r: ce.Rapport) -> bool:
    """Ajoute le symbole à l'Observation du marché. Renvoie True si c'est nous
    qui l'avons ajouté (à retirer ensuite pour libérer la mémoire du terminal).
    Tolère symbol_select False quand le symbole est déjà visible (MT5 build 6317,
    « Out of memory »)."""
    try:
        avant = mt5.symbol_info(nom)
    except Exception:
        avant = None
    deja_visible = avant is not None and bool(getattr(avant, "visible", False))
    if mt5.symbol_select(nom, True):
        return not deja_visible
    info = mt5.symbol_info(nom)
    if info is not None and bool(getattr(info, "visible", False)):
        r.ecrire(f"[--] symbol_select({nom}) a échoué ({ce.erreur_mt5(mt5)}), "
                 "mais le symbole est déjà visible : on continue")
        return False
    raise ErreurSymbole(f"impossible d'ajouter {nom} à l'Observation du marché ({ce.erreur_mt5(mt5)}). "
                        "Ajoute-le à la main dans MetaTrader 5 (Affichage > Symboles), puis relance")


def deselectionner(mt5, noms: set) -> None:
    for nom in sorted(noms):
        try:
            mt5.symbol_select(nom, False)
        except Exception:
            pass
    noms.clear()


def mesurer_decalage(mt5, choix: dict, ctx: dict, r: ce.Rapport) -> dict:
    """Décalage heure serveur - UTC, mesuré sur un symbole qui cote en direct."""
    r.titre("Décalage horaire du serveur")
    ordre = [g for g in ORDRE_DECALAGE if g in choix] + [g for g in choix if g not in ORDRE_DECALAGE]
    mesures = []
    for gen in ordre[:ESSAIS_DECALAGE_MAX]:
        nom = _texte(choix[gen], "name")
        try:
            if selectionner(mt5, nom, r):
                ctx["ajoutes"].add(nom)
            r.ecrire(f"     mesure sur {nom} ({gen})")
            mesure = ex._decalage_serveur(mt5, nom, ctx["maintenant"], r)
        except Exception as e:
            r.ecrire(f"[--] mesure impossible sur {nom} : {type(e).__name__} : {e}")
            continue
        mesures.append(mesure)
        if mesure["fiable"]:
            break
    resultat = choisir_decalage(mesures)
    rejetees = [m["decalage"] for m in mesures if m["decalage"] is not None and not decalage_plausible(m["decalage"])]
    if rejetees:
        r.ecrire(f"[--] mesure(s) rejetée(s), hors de [{DECALAGE_MIN:+d}, {DECALAGE_MAX:+d}] h : "
                 f"{', '.join(f'{d:+d} h' for d in rejetees)} (symbole qui ne cote plus ?)")
    if not resultat["fiable"]:
        if resultat["decalage"] is not None:
            r.ecrire(f"     mesure la plus plausible gardée : {resultat['decalage']:+d} h (tick le plus récent), "
                     "NON fiable")
        r.ecrire("[--] décalage non fiable : chaque symbole retire alors toute bougie qui finit après son "
                 "dernier tick (prudent : peut retirer une bougie complète).")
    return resultat


def decalage_plausible(decalage) -> bool:
    try:
        return decalage is not None and DECALAGE_MIN <= int(decalage) <= DECALAGE_MAX
    except (TypeError, ValueError):
        return False


def choisir_decalage(mesures: list[dict]) -> dict:
    """La première mesure fiable ; sinon, parmi les mesures plausibles (dans [DECALAGE_MIN,
    DECALAGE_MAX]), celle du tick le plus récent ; sinon « inconnu ». Une mesure hors de
    l'intervalle (symbole qui ne cote plus depuis des mois) n'est jamais gardée."""
    for m in mesures:
        if m.get("fiable") and decalage_plausible(m.get("decalage")):
            return m
    plausibles = [m for m in mesures if decalage_plausible(m.get("decalage"))]
    if plausibles:
        return dict(max(plausibles, key=lambda m: m.get("dernier_tick_epoch") or 0), fiable=False)
    return {"decalage": None, "fiable": False, "dernier_tick": None, "dernier_tick_epoch": None}


# --------------------------------------------------------------------------- #
# Export d'un symbole
# --------------------------------------------------------------------------- #
def _texte_annees(premiere, derniere) -> str:
    return f"{(derniere - premiere).days / 365.25:.1f} ans"


def _exporter_tf(mt5, gen, nom, info, tf, annees, heure_now, ctx, dossier_tmp, r) -> dict | None:
    nom_tf, constante, defaut, duree_s = tf
    maintenant = ctx["maintenant"]
    debut = maintenant - dt.timedelta(days=365.25 * annees)
    fin = maintenant + dt.timedelta(days=1)  # l'heure serveur est souvent en avance sur UTC
    code_tf = int(getattr(mt5, constante, defaut))
    if nom_tf == "D1":
        morceaux = telecharger_d1(mt5, nom, code_tf, debut, fin, r)
    else:
        morceaux = ex.telecharger_barres(mt5, nom, code_tf, debut, fin, r, nom_tf)
    df, infos = ex.preparer_barres(morceaux, int(getattr(info, "digits", 5)), duree_s, heure_now)
    if heure_now is None and not df.empty:
        df = df.iloc[:-1].reset_index(drop=True)
        r.ecrire(f"     {nom_tf} : heure serveur inconnue, dernière bougie retirée par prudence")
    if df.empty:
        r.ecrire(f"[!!] {nom_tf} : aucune bougie reçue ({ce.erreur_mt5(mt5)})")
        return None
    ex.ecrire_csv(df, dossier_tmp / f"{nom_tf}.csv")
    n = len(df)
    premiere, derniere = df["time"].iloc[0], df["time"].iloc[-1]
    r.ecrire(f"[OK] {nom_tf} : {n} bougies, du {premiere:%Y-%m-%d %H:%M} au {derniere:%Y-%m-%d %H:%M} "
             f"({_texte_annees(premiere, derniere)} ; demandé : {annees:g} ans)")
    if infos["en_cours_retirees"]:
        r.ecrire(f"     bougie en cours de formation retirée : {infos['en_cours_retirees']}")
    duree_ans = (derniere - premiere).days / 365.25
    if nom_tf in ANNEES_MIN and duree_ans < ANNEES_MIN[nom_tf] and annees >= ANNEES_MIN[nom_tf]:
        r.ecrire(f"[--] {nom_tf} : {duree_ans:.1f} ans seulement chez ce broker, moins que les "
                 f"{ANNEES_MIN[nom_tf]:g} ans exigés par le plan de recherche pour ce timeframe")
        ctx["avertissements"].setdefault(gen, []).append(f"{nom_tf} : {duree_ans:.1f} ans d'historique seulement")
    if infos["invalides_retirees"]:
        r.ecrire(f"[!!] {infos['invalides_retirees']} bougie(s) incohérente(s) (OHLC) retirée(s)")
        ctx["avertissements"].setdefault(gen, []).append(
            f"{nom_tf} : {infos['invalides_retirees']} bougie(s) incohérente(s) retirée(s)")
    trous = ex.trous_anormaux(df["time"].to_numpy().astype("datetime64[s]").astype("int64"), duree_s)
    if trous:
        r.ecrire(f"[--] {len(trous)} trou(s) de plus de {ex.TROU_MAX_JOURS} jours hors week-end :")
        for a, b, j in trous[:5]:
            r.ecrire(f"       du {a} au {b} ({j} jours hors week-end)")
        if len(trous) > 5:
            r.ecrire(f"       ... et {len(trous) - 5} autre(s)")
    maxbars = ctx["maxbars"]
    try:
        limite = maxbars is not None and n >= ex.LIMITE_PROCHE * int(maxbars)
    except (TypeError, ValueError):
        limite = False
    if limite:
        r.ecrire(f"[!!] {nom_tf} : {n} bougies, proche de la limite « Max bars in chart » ({maxbars}) : "
                 "historique probablement tronqué.")
        for ligne in ex.MESSAGE_MAX_BARS:
            r.ecrire(ligne.replace("EXPORTER_DONNEES.bat", "EXPORTER_UNIVERS.bat"))
        ctx["avertissements"].setdefault(gen, []).append(f"{nom_tf} : tronqué par la limite de barres de MT5")
    return {"barres": n, "premiere": f"{premiere:%Y-%m-%d %H:%M:%S}", "derniere": f"{derniere:%Y-%m-%d %H:%M:%S}"}


def remplacer_dossier(nouveau: Path, final: Path) -> None:
    """Remplace final par nouveau sans jamais laisser un dossier à moitié supprimé :
    l'ancien est d'abord renommé, puis effacé seulement après la mise en place du nouveau."""
    ancien = final.with_name(f".{final.name}.ancien")
    if ancien.exists():
        shutil.rmtree(ancien)
    if final.exists():
        try:
            os.replace(final, ancien)
        except PermissionError as e:
            raise ErreurSymbole(f"le dossier {final} est verrouillé ({e}) : ferme le fichier ouvert "
                                "(Excel ?) puis relance") from None
    try:
        os.replace(nouveau, final)
    except Exception:
        if ancien.exists() and not final.exists():
            os.replace(ancien, final)  # on remet l'ancien export
        raise
    shutil.rmtree(ancien, ignore_errors=True)


def exporter_symbole(mt5, gen: str, spec: dict, candidat, ctx: dict, r: ce.Rapport) -> dict:
    """Exporte un symbole dans <dossier>/<gen>/. Renvoie son entrée de univers.json.
    Lève ErreurSymbole (ou toute exception) en cas d'échec : le dossier final n'est alors pas touché."""
    nom = _texte(candidat, "name")
    r.titre(f"{gen} ({NOMS_CLASSES[spec['classe']]}) -> {nom}")
    if selectionner(mt5, nom, r):
        ctx["ajoutes"].add(nom)
    info = mt5.symbol_info(nom)
    if info is None:
        raise ErreurSymbole(f"symbol_info({nom}) sans réponse ({ce.erreur_mt5(mt5)})")
    d_symbole = infos_symbole_univers(mt5, info)
    r.ecrire(f"     {d_symbole.get('description', '')} | path {d_symbole.get('path', '')}")
    r.ecrire(f"     devises {d_symbole.get('currency_base')}/{d_symbole.get('currency_profit')} "
             f"(marge {d_symbole.get('currency_margin')}), décimales {d_symbole['digits']}, "
             f"contrat {d_symbole['trade_contract_size']}, lots {d_symbole['volume_min']} à "
             f"{d_symbole['volume_max']} par {d_symbole['volume_step']}, "
             f"{texte_trade_mode_symbole(d_symbole.get('trade_mode'))}")
    r.ecrire(f"     calcul {d_symbole['trade_calc_mode_texte']}, swap {d_symbole['swap_mode_texte']} "
             f"(long {d_symbole.get('swap_long')}, short {d_symbole.get('swap_short')}, "
             f"triple le {JOURS_SEMAINE.get(d_symbole.get('swap_rollover3days'), d_symbole.get('swap_rollover3days'))}), spread actuel {d_symbole['spread']} points")
    if not _tradable(mt5, info):
        r.ecrire(f"[--] trade_mode « {d_symbole['trade_mode_texte']} » : {nom} n'est PAS tradable sur ce compte. "
                 "Ses données servent à la recherche, mais pas à la démo chez ce broker.")
        ctx["avertissements"].setdefault(gen, []).append(
            f"pas tradable sur ce compte (trade_mode « {d_symbole['trade_mode_texte']} »)")

    tick = ex._lire_tick(mt5, nom)
    decalage = ctx["decalage"]
    if decalage["fiable"]:
        heure_now = ex._epoch(ctx["maintenant"]) + int(decalage["decalage"]) * 3600
    elif tick is not None:
        heure_now = int(tick.time)  # dernier tick <= heure serveur actuelle : prudent
    else:
        heure_now = None

    dossier = ctx["dossier"]
    dossier_tmp = dossier / f".{gen}.tmp"
    if dossier_tmp.exists():
        shutil.rmtree(dossier_tmp)
    dossier_tmp.mkdir(parents=True)
    try:
        timeframes = {}
        liste = [(TF_D1, ctx["annees"]), (TF_H1, ctx["annees"])]
        if gen in SYMBOLES_M15:
            liste.append((TF_M15, ctx["annees_m15"]))
        for tf, annees in liste:
            try:
                res = _exporter_tf(mt5, gen, nom, info, tf, annees, heure_now, ctx, dossier_tmp, r)
            except Exception as e:
                if tf is TF_D1:
                    raise
                r.ecrire(f"[!!] {tf[0]} : erreur {type(e).__name__} : {e}")
                r.ecrire(traceback.format_exc().rstrip())
                res = None
            if res is None:
                if tf is TF_D1:
                    raise ErreurSymbole(f"aucune bougie D1 reçue ({ce.erreur_mt5(mt5)})")
                ctx["avertissements"].setdefault(gen, []).append(f"{tf[0]} absent")
                continue
            timeframes[tf[0]] = res

        try:
            if tick is not None:
                dernier_jour = dt.date(1970, 1, 1) + dt.timedelta(days=int(tick.time) // ex.JOUR_S)
            else:
                dernier_jour = ctx["maintenant"].date()
            stats = ex.statistiques_spread(mt5, nom, float(d_symbole["point"]), dernier_jour)
        except Exception as e:
            r.ecrire(f"[!!] statistiques de spread impossibles : {type(e).__name__} : {e}")
            stats = None
        if stats is None:
            r.ecrire(f"[!!] spread_stats.json non écrit : aucun tick sur les {ex.JOURS_TICKS_SCAN_MAX} derniers jours")
            ctx["avertissements"].setdefault(gen, []).append("spread_stats.json absent (aucun tick)")
        else:
            ex._ecrire_json(dossier_tmp / "spread_stats.json", stats)
            g = stats["global"]
            r.ecrire(f"[OK] spread (points) sur {stats['nb_jours']} jours ouvrés : médiane {g['p50']}, "
                     f"p90 {g['p90']}, p99 {g['p99']} ({stats['nb_ticks']} ticks)")
            if stats["nb_jours"] < ex.JOURS_TICKS:
                r.ecrire(f"[--] seulement {stats['nb_jours']} jours avec des ticks (objectif {ex.JOURS_TICKS})")

        ex._ecrire_json(dossier_tmp / "symbol_info.json", d_symbole)
        remplacer_dossier(dossier_tmp, dossier / gen)
    finally:
        if dossier_tmp.exists():
            shutil.rmtree(dossier_tmp, ignore_errors=True)
        deselectionner(mt5, ctx["ajoutes"])
    r.ecrire(f"[OK] fichiers dans {dossier.name}/{gen}/ : {', '.join(f'{t}.csv' for t in timeframes)}, "
             f"symbol_info.json{', spread_stats.json' if stats is not None else ''}")
    return {"nom_broker": nom, "classe": spec["classe"], "dossier": gen,
            "trade_mode_texte": d_symbole["trade_mode_texte"], "timeframes": timeframes}


# --------------------------------------------------------------------------- #
# Liste des symboles du broker
# --------------------------------------------------------------------------- #
def lister(mt5, symboles: list, config: dict, maintenant: dt.datetime, dossier_logs: Path,
           r: ce.Rapport) -> Path:
    """logs/symboles_broker_<date>.txt : tous les symboles du terminal + résolution proposée."""
    choix, absents, journal = resoudre(mt5, symboles, config, list(config["symboles"]))
    lignes = [f"Symboles du terminal MetaTrader 5 - {maintenant:%Y-%m-%d %H:%M:%S} UTC - {len(symboles)} symboles",
              "Pour imposer un nom : config/univers_symboles.json, section \"forcer\", "
              "par exemple \"US500\": \"SPX500.cash\"", "",
              "nom | path | description | base/cotation/marge | trade_mode | visible"]
    for s in sorted(symboles, key=lambda s: (_texte(s, "path").upper(), _texte(s, "name"))):
        lignes.append(" | ".join([
            _texte(s, "name"), _texte(s, "path"), _texte(s, "description"),
            f"{_texte(s, 'currency_base')}/{_texte(s, 'currency_profit')}/{_texte(s, 'currency_margin')}",
            texte_trade_mode_symbole(getattr(s, "trade_mode", None)),
            "oui" if getattr(s, "visible", False) else "non"]))
    lignes += ["", "Résolution automatique proposée :"]
    for gen in config["symboles"]:
        if gen in choix:
            lignes.append(f"  {gen:<7} -> {_texte(choix[gen], 'name')}")
        else:
            lignes.append(f"  {gen:<7} -> ABSENT : {absents.get(gen, '?')}")
        for l in journal.get(gen, []):
            lignes.append(f"            {l}")
    dossier_logs.mkdir(parents=True, exist_ok=True)
    chemin = dossier_logs / f"symboles_broker_{maintenant:%Y%m%d-%H%M%S}.txt"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    r.ecrire(f"[OK] {len(symboles)} symboles listés dans {chemin}")
    return chemin


# --------------------------------------------------------------------------- #
# Programme principal
# --------------------------------------------------------------------------- #
def _lire_univers_existant(chemin: Path) -> dict:
    try:
        d = json.loads(chemin.read_text(encoding="utf-8"))
        if isinstance(d.get("symboles"), dict) and isinstance(d.get("absents"), dict):
            return d
    except (OSError, ValueError, AttributeError):
        pass
    return {"symboles": {}, "absents": {}}


def verifier_meme_serveur(chemin_univers: Path, serveur) -> None:
    """Refuse d'écrire dans un dossier qui contient l'export d'un AUTRE serveur (ou d'un export
    ancien qui ne dit pas de quel serveur il vient) : on ne mélange jamais deux brokers."""
    if not chemin_univers.exists():
        return
    ancien = _lire_univers_existant(chemin_univers)
    ancien_serveur = ancien.get("serveur")
    dossier = chemin_univers.parent
    conseil = (f"     -> exporte dans un dossier propre à ce broker : --dossier data/univers_<nom_du_broker>\n"
               f"        (ou renomme {dossier} si tu veux vraiment le refaire)")
    if not ancien_serveur:
        raise ex.ErreurExport(f"{chemin_univers} ne dit pas de quel serveur il vient (export ancien ou illisible) : "
                              f"pour ne pas mélanger deux brokers, ce dossier n'est pas modifié.\n{conseil}")
    if not serveur or str(ancien_serveur).strip() != str(serveur).strip():
        raise ex.ErreurExport(f"{dossier} contient l'export du serveur « {ancien_serveur} », et MetaTrader 5 est "
                              f"connecté à « {serveur or 'inconnu'} » : ce dossier n'est pas modifié.\n{conseil}")


def decalage_a_ecrire(mesure: dict, ancien: dict, partiel: bool, maintenant: dt.datetime) -> tuple[dict, str | None]:
    """Décalage à écrire dans univers.json : {"decalage", "fiable", "mesure_le"} et, s'il vient de
    l'ancien fichier, la raison (pour le rapport). Un export partiel ne remplace jamais un décalage
    fiable par un non fiable, ni un décalage plausible par « inconnu »."""
    nouveau = {"decalage": mesure["decalage"] if decalage_plausible(mesure["decalage"]) else None,
               "fiable": bool(mesure["fiable"]) and decalage_plausible(mesure["decalage"]),
               "mesure_le": f"{maintenant:%Y-%m-%d %H:%M:%S}"}
    if not nouveau["fiable"] and nouveau["decalage"] is None:
        nouveau["mesure_le"] = None
    if not partiel or nouveau["fiable"]:
        return nouveau, None
    a_dec = ancien.get("decalage_serveur_utc_heures")
    if not decalage_plausible(a_dec):
        return nouveau, None
    a_fiable = ancien.get("decalage_fiable") is True
    garde = {"decalage": int(a_dec), "fiable": a_fiable,
             "mesure_le": ancien.get("decalage_mesure_le_utc") or ancien.get("genere_le_utc")}
    if a_fiable:
        return garde, f"décalage fiable déjà mesuré ({int(a_dec):+d} h, le {garde['mesure_le']}) conservé"
    if nouveau["decalage"] is None:
        return garde, f"décalage précédent ({int(a_dec):+d} h, NON fiable) conservé, faute de nouvelle mesure"
    return nouveau, None


def _exporter_univers(mt5, args, config: dict, generiques: list[str], maintenant: dt.datetime,
                      r: ce.Rapport) -> int:
    terminal, compte = ex._connecter(mt5, r)
    c = ex.infos_compte(compte)  # ni login, ni nom
    if ex.est_compte_reel(mt5, compte):
        raise ex.ErreurExport("compte RÉEL connecté : cette phase se fait UNIQUEMENT sur un compte démo. "
                              "Connecte-toi au compte démo, puis relance.")
    r.titre("Symboles du broker")
    symboles = tous_les_symboles(mt5, config)
    r.ecrire(f"     {len(symboles)} symboles dans le terminal")
    if not symboles:
        raise ex.ErreurExport(f"aucun symbole reçu du terminal ({ce.erreur_mt5(mt5)})")
    if args.lister:
        lister(mt5, symboles, config, maintenant, args.logs, r)
        r.bilan(True, "liste des symboles écrite")
        return 0

    r.titre("Résolution des noms")
    choix, absents, journal = resoudre(mt5, symboles, config, generiques)
    for gen in generiques:
        etat = f"-> {_texte(choix[gen], 'name')}" if gen in choix else f"ABSENT : {absents[gen]}"
        r.ecrire(f"{'[OK]' if gen in choix else '[--]'} {gen:<7} {etat}")
        for l in journal.get(gen, []):
            r.ecrire(f"            {l}")

    chemin_univers = args.dossier / "univers.json"
    verifier_meme_serveur(chemin_univers, c["server"])
    ctx = {"maintenant": maintenant, "annees": args.annees, "annees_m15": args.annees_m15,
           "dossier": args.dossier, "maxbars": getattr(terminal, "maxbars", None),
           "ajoutes": set(), "avertissements": {}}
    for gen in choix:
        for l in journal.get(gen, []):
            if l.startswith("attention") and "pas tradable" not in l:  # (non tradable : signalé à l'export)
                ctx["avertissements"].setdefault(gen, []).append(l)
    args.dossier.mkdir(parents=True, exist_ok=True)
    try:
        ctx["decalage"] = mesurer_decalage(mt5, choix, ctx, r) if choix else {
            "decalage": None, "fiable": False, "dernier_tick": None, "dernier_tick_epoch": None}
    finally:
        deselectionner(mt5, ctx["ajoutes"])

    exportes = {}
    for gen in generiques:
        if gen not in choix:
            continue
        try:
            exportes[gen] = exporter_symbole(mt5, gen, config["symboles"][gen], choix[gen], ctx, r)
        except ex.ErreurExport:
            raise
        except ErreurSymbole as e:
            r.ecrire(f"[!!] {gen} non exporté : {e}")
            absents[gen] = f"échec de l'export de {_texte(choix[gen], 'name')} : {e}"
        except Exception as e:
            r.ecrire(f"[!!] {gen} non exporté : erreur {type(e).__name__} : {e}")
            r.ecrire(traceback.format_exc().rstrip())
            absents[gen] = f"échec de l'export de {_texte(choix[gen], 'name')} : {type(e).__name__} : {e}"
        finally:
            deselectionner(mt5, ctx["ajoutes"])

    # univers.json : avec --symboles, les autres symboles déjà exportés sont conservés
    ancien = _lire_univers_existant(chemin_univers) if args.symboles else {"symboles": {}, "absents": {}}
    garder = [g for g in config["symboles"] if g not in generiques]
    build = getattr(terminal, "build", None)
    decalage, note_decalage = decalage_a_ecrire(ctx["decalage"], ancien, bool(args.symboles), maintenant)
    univers = {
        "genere_le_utc": f"{maintenant:%Y-%m-%d %H:%M:%S}",
        "serveur": c["server"],
        "societe": c["company"],
        "decalage_serveur_utc_heures": decalage["decalage"],
        "decalage_fiable": decalage["fiable"],
        "decalage_mesure_le_utc": decalage["mesure_le"],
        "build_terminal": ex._natif(build),
        "symboles": {}, "absents": {},
    }
    for gen in config["symboles"]:
        if gen in exportes:
            univers["symboles"][gen] = exportes[gen]
        elif gen in absents:
            univers["absents"][gen] = absents[gen]
        elif gen in garder and gen in ancien["symboles"]:
            univers["symboles"][gen] = ancien["symboles"][gen]
        elif gen in garder and gen in ancien["absents"]:
            univers["absents"][gen] = ancien["absents"][gen]
    ex._ecrire_json(chemin_univers, univers)

    r.titre("RÉSUMÉ")
    r.ecrire(f"Serveur : {c['server']} ({c['company']})")
    dec = decalage["decalage"]
    r.ecrire(f"Décalage heure serveur - UTC : {'inconnu' if dec is None else f'{int(dec):+d}'} h "
             f"({'fiable' if decalage['fiable'] else 'NON fiable'})")
    if note_decalage:
        r.ecrire(f"     (export partiel : {note_decalage})")
    if not decalage["fiable"]:
        r.ecrire("     -> relance l'export un jour de semaine, marché ouvert, pour mesurer le décalage.")
    for gen in generiques:
        if gen in exportes:
            e = exportes[gen]
            tfs = " ; ".join(f"{t} {v['barres']} ({v['premiere'][:10]} -> {v['derniere'][:10]})"
                             for t, v in e["timeframes"].items())
            r.ecrire(f"[OK] {gen:<7} {e['nom_broker']:<12} {tfs}")
            for a in ctx["avertissements"].get(gen, []):
                r.ecrire(f"       [!!] {a}")
        else:
            r.ecrire(f"[--] {gen:<7} ABSENT : {absents.get(gen, '?')}")
    disponibles = {config["symboles"][g]["classe"] for g in choix}
    reussies = {config["symboles"][g]["classe"] for g in exportes}
    r.ecrire()
    for classe in CLASSES:
        gens = [g for g in generiques if config["symboles"][g]["classe"] == classe]
        if not gens:
            continue
        n_ok = sum(1 for g in gens if g in exportes)
        if classe not in disponibles:
            r.ecrire(f"     {NOMS_CLASSES[classe]} : aucun symbole chez ce broker")
        else:
            r.ecrire(f"{'[OK]' if classe in reussies else '[!!]'} {NOMS_CLASSES[classe]} : "
                     f"{n_ok}/{len(gens)} symbole(s) exporté(s)")
    r.ecrire(f"     univers.json : {chemin_univers}")
    ok = bool(exportes) and disponibles <= reussies
    if garder and args.symboles:
        r.ecrire("     (export partiel : les autres symboles de univers.json sont conservés)")
    return 0 if ok else 1


def enregistrer(r: ce.Rapport, maintenant: dt.datetime, dossier_logs: Path) -> Path:
    dossier_logs.mkdir(parents=True, exist_ok=True)
    chemin = dossier_logs / f"export_univers_{maintenant:%Y%m%d-%H%M%S}.txt"
    chemin.write_text("\n".join(r.lignes) + "\n", encoding="utf-8")
    return chemin


def main(argv: list[str] | None = None, maintenant: dt.datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export de l'univers multi-marchés depuis MetaTrader 5")
    parser.add_argument("--symboles", help="sous-ensemble de noms génériques, ex. EURUSD,US500")
    parser.add_argument("--annees", type=float, default=20.0, help="années de D1 et H1 (défaut 20)")
    parser.add_argument("--annees-m15", type=float, default=5.0, help="années de M15 (défaut 5)")
    parser.add_argument("--lister", action="store_true",
                        help="écrit seulement la liste des symboles du broker dans logs/")
    parser.add_argument("--dossier", type=Path, default=DOSSIER_UNIVERS,
                        help="dossier de sortie, data/univers (défaut) ou data/univers_<nom> : un dossier par broker")
    parser.add_argument("--terminal", type=Path, default=None,
                        help="chemin de terminal64.exe si plusieurs MetaTrader 5 sont installés")
    parser.add_argument("--logs", type=Path, default=DOSSIER_LOGS, help=argparse.SUPPRESS)
    parser.add_argument("--config", type=Path, default=CHEMIN_CONFIG, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not args.dossier.is_absolute():  # relatif à la racine du projet, d'où que l'on lance le script
        args.dossier = RACINE / args.dossier
    try:
        sys.stdout.reconfigure(errors="replace")  # console Windows : jamais de plantage d'affichage
    except Exception:
        pass

    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    r = ce.Rapport()
    r.ecrire("Recherche multi-marchés - export de l'univers MetaTrader 5")
    r.ecrire(f"Date : {maintenant:%Y-%m-%d %H:%M:%S} UTC | Python {platform.python_version()}")
    if args.lister:
        r.ecrire("Demande : liste des symboles du broker")
    else:
        r.ecrire(f"Demande : D1 et H1 sur {args.annees:g} ans, M15 sur {args.annees_m15:g} ans, "
                 f"symboles {args.symboles or TOUT_UNIVERS}, dossier {args.dossier}")

    mt5 = None
    code = 1
    try:
        for nom, v in (("--annees", args.annees), ("--annees-m15", args.annees_m15)):
            if not 0 < v <= 30:
                raise ex.ErreurExport(f"{nom} doit être compris entre 0 et 30")
        if not args.lister and not MOTIF_DOSSIER.match(args.dossier.name):
            raise ex.ErreurExport(f"--dossier {args.dossier} : le nom du dossier doit être « univers » ou "
                                  "« univers_<nom> » (lettres, chiffres, tiret), par exemple data/univers_monbroker")
        config = charger_config(args.config)
        generiques = list(config["symboles"])
        if args.symboles:
            demandes = [g.strip().upper() for g in args.symboles.split(",") if g.strip()]
            inconnus = [g for g in demandes if g not in config["symboles"]]
            if inconnus or not demandes:
                raise ex.ErreurExport(f"symbole(s) générique(s) inconnu(s) : {', '.join(inconnus) or '(vide)'}. "
                                      f"Choix possibles : {', '.join(generiques)}")
            generiques = [g for g in generiques if g in demandes]
        r.ecrire(f"Configuration : {len(config['symboles'])} symboles génériques, "
                 f"{len(config['forcer'])} nom(s) imposé(s) par « forcer »")
        for lib in ("numpy", "pandas"):
            try:
                importlib.import_module(lib)
            except Exception as e:
                raise ex.ErreurExport(f"la librairie {lib} est absente ou cassée ({type(e).__name__}) : "
                                      "relance INSTALLER.bat") from None
        try:
            mt5 = importlib.import_module("MetaTrader5")
        except Exception as e:
            raise ex.ErreurExport(f"le module MetaTrader5 est absent ({type(e).__name__}). Il n'existe que sous "
                                  "Windows : lance d'abord INSTALLER.bat sur le PC.") from None
        try:
            # --terminal : quand plusieurs MetaTrader 5 sont installés, désigne celui du broker voulu
            initialise = bool(mt5.initialize(path=str(args.terminal)) if args.terminal else mt5.initialize())
        except Exception as e:
            initialise = False
            r.ecrire(f"     initialize() a planté : {type(e).__name__} : {e}")
        if not initialise:
            raise ex.ErreurExport("impossible de joindre le terminal MetaTrader 5.\n"
                                  "     -> ouvre MetaTrader 5 et connecte-toi au compte démo, puis relance.\n"
                                  f"     erreur MT5 : {ce.erreur_mt5(mt5)}")
        code = _exporter_univers(mt5, args, config, generiques, maintenant, r)
    except ex.ErreurExport as e:
        r.ecrire(f"[!!] {e}")
        code = 1
    except Exception as e:
        r.ecrire(f"[!!] Erreur inattendue : {type(e).__name__} : {e}")
        r.ecrire(traceback.format_exc().rstrip())
        code = 1
    finally:
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass

    r.ecrire()
    if code == 0:
        r.ecrire("=> TERMINÉ : " + ("liste écrite dans logs." if args.lister else
                                     "au moins un symbole exporté dans chaque classe disponible."))
    else:
        r.ecrire("=> Points à regarder. Claude peut lire ce rapport et t'expliquer quoi faire.")
    try:
        print(f"\nRapport enregistré : {enregistrer(r, maintenant, args.logs)}")
    except OSError as e:
        print(f"\n[!!] Impossible d'enregistrer le rapport : {e}")
    return code


if __name__ == "__main__":
    sys.exit(main())
