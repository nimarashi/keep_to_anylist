#!/usr/bin/env python3
"""
generate_master_token.py
========================

Engangs-script: genererer et Google Keep master-token til brug som
KEEP_MASTER_TOKEN secret i GitHub Actions.

Skal køres LOKALT, ikke i Actions. Tokenet logger ind på din konto, så hold
det hemmeligt — vis det aldrig, commit det aldrig, paste det ikke i chat.

Forudsætning: 2-step verification + et App Password.
    https://myaccount.google.com/apppasswords

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

    print("Google Keep master-token-generering")
    print("====================================")
    print()
    print("Du skal bruge et App Password (16 tegn uden mellemrum), IKKE dit")
    print("normale Google-password. Generér ét her hvis du ikke har det:")
    print("  https://myaccount.google.com/apppasswords")
    print()

    email = input("Google email: ").strip()
    if not email or "@" not in email:
        print("FEJL: ugyldig email.", file=sys.stderr)
        return 1

    app_password = getpass.getpass("App Password (skjult): ").strip().replace(" ", "")
    if len(app_password) != 16:
        print(
            f"ADVARSEL: App Passwords er normalt 16 tegn, du gav {len(app_password)}. "
            "Fortsætter alligevel.",
            file=sys.stderr,
        )

    android_id = "0000000000000000"  # vilkårlig konstant; gpsoauth kræver bare en streng
    try:
        result = gpsoauth.perform_master_login(email, app_password, android_id)
    except Exception as e:
        print(f"FEJL: gpsoauth-kald fejlede: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    token = result.get("Token") if isinstance(result, dict) else None
    if not token:
        print("FEJL: ingen Token i svar fra Google.", file=sys.stderr)
        print(f"  Hele svaret: {result}", file=sys.stderr)
        print("  Mest sandsynligt: forkert email eller App Password.", file=sys.stderr)
        return 1

    print()
    print("✓ Master-token genereret.")
    print()
    print("Næste skridt — gem det som GitHub Actions secret:")
    print(f"  Secret-navn: KEEP_MASTER_TOKEN")
    print(f"  Værdi:       {token}")
    print()
    print("ELLER via gh CLI:")
    print(f"  gh secret set KEEP_MASTER_TOKEN --body '{token}'")
    print()
    print("Hold tokenet hemmeligt. Det er ækvivalent til en login-session for din konto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
