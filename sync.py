#!/usr/bin/env python3
"""
sync.py
=======

Synker ukrydsede items fra en Google Keep-note til en AnyList-liste.

Designet til at køre som GitHub Actions scheduled workflow hvert 5. minut.
Kan også køres lokalt med en `.env`-fil til debugging.

Flow:
    1. Læs ukrydsede items fra Keep-noten (default: "indkøbsliste").
    2. Tilføj hver item til AnyList-listen (default: "Indkøb").
       Kategori sættes ikke — AnyList klassificerer selv.
    3. Slet successfully-overførte items fra Keep-noten.

Miljøvariabler (alle påkrævede undtagen de to titler):
    KEEP_EMAIL              Google-konto-email
    KEEP_MASTER_TOKEN       gkeepapi master-token (genereret én gang lokalt)
    ANYLIST_EMAIL           AnyList-konto-email
    ANYLIST_PASSWORD        AnyList-konto-password
    KEEP_NOTE_TITLE         Default: "indkøbsliste"
    ANYLIST_LIST_NAME       Default: "Indkøb"

Exit-koder:
    0  Succes (også hvis intet at synke)
    1  Auth- eller konfigurationsfejl
    2  Note ikke fundet
"""

from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env er kun til lokal kørsel; i Actions kommer alt via env-vars


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(f"FEJL: miljøvariablen {name} er ikke sat.", file=sys.stderr)
        sys.exit(1)
    return val


_AUTH_ERROR_MARKERS = (
    "auth", "login", "credential", "password", "token",
    "unauthorized", "401", "403", "forbidden", "invalid",
)


def _looks_like_auth_error(exc: Exception) -> bool:
    msg = (str(exc) + " " + type(exc).__name__).lower()
    return any(marker in msg for marker in _AUTH_ERROR_MARKERS)


def _find_note(keep, title: str):
    """Find første note med matching title (case-insensitive). Returnerer None hvis ingen match."""
    target_title = title.strip().lower()
    for note in keep.all():
        note_title = (getattr(note, "title", "") or "").strip().lower()
        if note_title == target_title:
            return note
    return None


def _find_list(client, list_name: str):
    """Find AnyList-listen ud fra dens navn (case-insensitive). None hvis ingen match."""
    target = list_name.strip().lower()
    for lst in client.get_lists():
        if (lst.name or "").strip().lower() == target:
            return lst
    return None


def _capitalize_first(text: str) -> str:
    """Stort første bogstav, resten urørt. 'mælk' -> 'Mælk', 'USB-kabel' -> 'USB-kabel'."""
    if not text:
        return text
    return text[:1].upper() + text[1:]


def _build_category_lookup(target_list) -> dict[str, str]:
    """
    Byg {normaliseret_navn: kategori} mapping fra alle items på listen
    (både krydsede og ukrydsede). Ved konflikt (samme navn → flere
    kategorier historisk) vælges den hyppigste.

    Vi udnytter at AnyList-listen er "lærings-data" — varer brugeren før
    har tilføjet bærer den kategori klienten valgte dengang.
    """
    by_name: dict[str, Counter] = defaultdict(Counter)
    for item in getattr(target_list, "items", []) or []:
        name = (getattr(item, "name", "") or "").strip().lower()
        category = (getattr(item, "category", None) or "").strip()
        if name and category:
            by_name[name][category] += 1
    return {name: counter.most_common(1)[0][0] for name, counter in by_name.items()}


def main() -> int:
    keep_email = _require("KEEP_EMAIL")
    keep_token = _require("KEEP_MASTER_TOKEN")
    al_email = _require("ANYLIST_EMAIL")
    al_password = _require("ANYLIST_PASSWORD")
    note_title = os.environ.get("KEEP_NOTE_TITLE", "indkøbsliste")
    list_name = os.environ.get("ANYLIST_LIST_NAME", "Indkøb")

    # 1. Login til Keep
    try:
        import gkeepapi
    except ImportError:
        print("FEJL: gkeepapi er ikke installeret.", file=sys.stderr)
        return 1

    keep = gkeepapi.Keep()
    try:
        keep.authenticate(keep_email, keep_token)
    except Exception as e:
        if _looks_like_auth_error(e):
            print(
                "FEJL: Google Keep master-token er udløbet eller invalideret.\n"
                "  Sandsynlige årsager:\n"
                "    - Du har skiftet Google-password\n"
                "    - App Password'et er blevet revoked på myaccount.google.com\n"
                "    - Google har strammet sikkerhed for kontoen\n"
                "  Fix: Generér et nyt token lokalt og opdatér KEEP_MASTER_TOKEN secret:\n"
                "    cd keep_to_anylist && python generate_master_token.py\n"
                f"  Underliggende fejl: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        else:
            print(
                f"FEJL: Keep-login fejlede uventet: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        return 1

    # 2. Find noten
    note = _find_note(keep, note_title)
    if note is None:
        print(f"Ingen Keep-note med titel '{note_title}' fundet. Intet at gøre.")
        return 2

    if not hasattr(note, "items"):
        print(
            f"Note '{note_title}' er ikke en checkliste-note "
            "(skal have checkbox-items, ikke fri tekst).",
            file=sys.stderr,
        )
        return 2

    # 3. Saml ukrydsede items (capitalize første bogstav: "mælk" → "Mælk")
    pending: list[tuple[str, object]] = []
    for item in note.items:
        text = (item.text or "").strip()
        if not text or item.checked:
            continue
        pending.append((text[:1].upper() + text[1:], item))
    if not pending:
        print("Ingen ukrydsede items i Keep-noten. Intet at synke.")
        return 0

    # 4. Login til AnyList
    try:
        from pyanylist import AnyListClient
    except ImportError:
        print("FEJL: pyanylist er ikke installeret.", file=sys.stderr)
        return 1

    try:
        client = AnyListClient.login(al_email, al_password)
    except Exception as e:
        if _looks_like_auth_error(e):
            print(
                "FEJL: AnyList-login fejlede — credentials er sandsynligvis forkerte.\n"
                "  Tjek at ANYLIST_EMAIL og ANYLIST_PASSWORD secrets matcher\n"
                "  det du logger ind med i AnyList-appen.\n"
                f"  Underliggende fejl: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        else:
            print(
                f"FEJL: AnyList-login fejlede uventet: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
        return 1

    target_list = _find_list(client, list_name)
    if target_list is None:
        print(f"FEJL: AnyList-listen '{list_name}' findes ikke.", file=sys.stderr)
        return 1
    list_id = target_list.id

    # 4b. Byg kategori-lookup fra brugerens egen historik på listen.
    # AnyList's egen auto-kategorisering er klient-side og trigges ikke via API,
    # så vi imiterer den ved at slå op i tidligere tilføjede items.
    category_lookup = _build_category_lookup(target_list)

    # 5. Sync hver item, slet i Keep efter succes
    added: list[tuple[str, Optional[str]]] = []
    failed: list[tuple[str, str]] = []

    for text, item in pending:
        display_name = _capitalize_first(text)
        category = category_lookup.get(text.lower())
        try:
            if category:
                client.add_item_with_details(list_id, display_name, category=category)
            else:
                client.add_item_with_details(list_id, display_name)
            item.delete()
            added.append((display_name, category))
        except Exception as e:
            # Lad item ligge i Keep, prøv igen næste run
            failed.append((display_name, str(e)))

    # 6. Commit Keep-deletions
    if added:
        try:
            keep.sync()
        except Exception as e:
            print(f"ADVARSEL: kunne ikke commit'e Keep-deletions: {e}", file=sys.stderr)
            # Items er sat lokalt til deleted, men Google's server ved det ikke endnu.
            # Næste run vil se dem som "ukrydsede" igen og duplikere → log som warning.

    # 7. Summary (uden secrets)
    print(
        f"Synket {len(added)} item(s) fra Keep '{note_title}' til AnyList "
        f"'{list_name}' (kategori-lookup havde {len(category_lookup)} entries)."
    )
    for name, category in added:
        suffix = f" → {category}" if category else " (ingen kategori — ny vare)"
        print(f"  + {name}{suffix}")
    if failed:
        print(f"\n{len(failed)} item(s) fejlede:", file=sys.stderr)
        for name, err in failed:
            print(f"  ! {name}: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
