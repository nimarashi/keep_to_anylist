#!/usr/bin/env python3
"""
generate_master_token.py
========================

Engangs-script: genererer et Google Keep master-token til brug som
KEEP_MASTER_TOKEN secret i GitHub Actions.

Skal køres LOKALT, ikke i Actions. Tokenet logger ind på din konto, så hold
det hemmeligt — vis det aldrig, commit det aldrig, paste det ikke i chat.

Den klassiske App Password-flow virker ikke længere stabilt (Google har
strammet sikkerhed). Vi bruger derfor "alternative flow" hvor du logger
ind via browser og henter en `oauth_token`-cookie ud, som vi exchanger til
et master-token.

Browser-flow:
    1. Åbn et privat/incognito-vindue (vigtigt — undgår at blande med
       din normale session) og gå til:
           https://accounts.google.com/EmbeddedSetup
    2. Log ind med din Google-konto. Klik "I agree" når den spørger.
       Ignorer eventuel "Loading..."-skærm — du skal IKKE vente på den.
    3. Åbn DevTools (F12 eller højreklik → Inspect).
    4. Find oauth_token-cookien:
       - Chrome/Edge: Application-fanen → Cookies → accounts.google.com
                     → leder efter "oauth_token". Copy Value.
       - Firefox:    Storage-fanen → Cookies → accounts.google.com
                     → leder efter "oauth_token". Copy.
       - Safari:     Aktivér Develop-menu først (Settings → Advanced →
                     "Show features for web developers"). Develop →
                     Show Web Inspector → Storage → Cookies.
    5. Værdien starter typisk med "oauth2_4/" eller lignende. Paste her.

Kør:
    pip install gpsoauth
    python generate_master_token.py
"""

from __future__ import annotations

import getpass
import sys


def main() -> int:
    try:
        import gpsoauth
    except ImportError:
        print("FEJL: gpsoauth er ikke installeret.", file=sys.stderr)
        print("  Installér først:  pip install gpsoauth", file=sys.stderr)
        return 1

    print("Google Keep master-token-generering (browser-flow)")
    print("===================================================")
    print()
    print("Følg disse skridt FØRST i din browser:")
    print()
    print("  1. Åbn et privat/incognito-vindue.")
    print("  2. Gå til: https://accounts.google.com/EmbeddedSetup")
    print("  3. Log ind. Klik 'I agree' når du bliver spurgt.")
    print("     Ignorer eventuel 'Loading...'-skærm — du skal IKKE vente.")
    print("  4. Åbn DevTools (F12).")
    print("  5. Find cookie 'oauth_token' for accounts.google.com.")
    print("     Chrome/Edge: Application → Cookies → accounts.google.com")
    print("     Firefox:     Storage → Cookies → accounts.google.com")
    print("     Safari:      (kræver Develop-menu) Storage → Cookies")
    print("  6. Copy Value. Den starter typisk med 'oauth2_4/'.")
    print()

    email = input("Google email: ").strip()
    if not email or "@" not in email:
        print("FEJL: ugyldig email.", file=sys.stderr)
        return 1

    oauth_token = getpass.getpass("oauth_token cookie-værdi (skjult): ").strip()
    if not oauth_token:
        print("FEJL: tom oauth_token.", file=sys.stderr)
        return 1

    android_id = "0123456789abcdef"  # vilkårlig konstant; gpsoauth kræver bare en hex-streng
    try:
        result = gpsoauth.exchange_token(email, oauth_token, android_id)
    except Exception as e:
        print(f"FEJL: gpsoauth-kald fejlede: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    token = result.get("Token") if isinstance(result, dict) else None
    if not token:
        print("FEJL: ingen Token i svar fra Google.", file=sys.stderr)
        print(f"  Hele svaret: {result}", file=sys.stderr)
        print(
            "  Mest sandsynlige årsager:\n"
            "    - oauth_token cookien er udløbet (de er kortlivede — generér en ny\n"
            "      ved at gå til EmbeddedSetup-URL'en igen)\n"
            "    - Forkert email\n"
            "    - Du copy-paste'de en anden cookie end oauth_token",
            file=sys.stderr,
        )
        return 1

    print()
    print("✓ Master-token genereret.")
    print()
    print("Sæt det som GitHub Actions secret:")
    print(f"  gh secret set KEEP_MASTER_TOKEN --body '{token}' \\")
    print(f"    --repo nimarashi/keep_to_anylist")
    print()
    print("Hold tokenet hemmeligt. Det er ækvivalent til en login-session for din konto.")
    print("Master-tokens udløber ikke automatisk — kun hvis du skifter password eller")
    print("eksplicit revoker det.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
