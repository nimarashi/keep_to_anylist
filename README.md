# keep_to_anylist

Synker ukrydsede items fra en Google Keep-note til en AnyList-liste — designet til at fange voice-input fra en Google Nest med Gemini for Home og overføre det til AnyList automatisk.

Læs [BRIEF.md](../BRIEF.md) for arkitektur og rationale.

## Sådan virker det

1. Du siger til din Nest: *"Hey Google, tilføj mælk til indkøbslisten."*
2. Gemini for Home gemmer "mælk" som ukrydset item i Google Keep-noten `indkøbsliste`.
3. En GitHub Actions-workflow kører hvert 5. minut, læser ukrydsede items, tilføjer dem til AnyList-listen `Indkøb`, og sletter dem fra Keep.
4. AnyList kategoriserer selv automatisk.

Latency: typisk 1-5 min, worst case ~15 min ved GitHub Actions peak load.

## Setup

### 1. Fork eller klon dette repo til en **public** GitHub-konto

Repo'et skal være public for at få ubegrænsede gratis Actions-minutter. Koden indeholder ingen hemmeligheder — alle credentials ligger i GitHub Actions Secrets.

### 2. Generér et Google Keep master-token

Det her er en engangs-operation. Du skal gøre det lokalt, fordi det kræver interaktiv browser-login.

**Bemærk:** App Password-flowet virker ikke længere stabilt — Google har strammet sikkerhed. Vi bruger i stedet "alternative flow" hvor du logger ind via browser og henter en cookie ud.

#### Browser-skridt (gør dette FØRST)

1. Åbn et **privat/incognito-vindue** i din browser.
2. Gå til https://accounts.google.com/EmbeddedSetup
3. Log ind med din Google-konto. Klik "I agree".
4. Ignorer eventuel "Loading..."-skærm — du skal IKKE vente på at den bliver færdig.
5. Åbn DevTools (F12).
6. Find cookien `oauth_token` for `accounts.google.com`:
   - **Chrome/Edge:** Application-fanen → Cookies → accounts.google.com → leder efter `oauth_token`
   - **Firefox:** Storage-fanen → Cookies → accounts.google.com
   - **Safari:** Aktivér Develop-menu (Settings → Advanced → "Show features for web developers") → Develop → Show Web Inspector → Storage → Cookies
7. Copy cookie-værdien (starter typisk med `oauth2_4/`).

cookie'n er kortlivet, så hav scriptet klar i en terminal samtidig.

#### Kør generate-scriptet

```bash
cd keep_to_anylist
python3.12 -m venv .venv
source .venv/bin/activate
pip install gpsoauth
python generate_master_token.py
```

Scriptet prompter for din email og oauth_token-cookie-værdien. Det printer en `gh secret set ...`-kommando med master-tokenet — copy-paste den i terminalen for at sætte secret'en.

Master-tokens udløber ikke automatisk — kun hvis du skifter Google-password eller eksplicit revoker det. Så denne proces er virkelig en engangs-ting i praksis.

### 3. Opret GitHub Actions Secrets

I dit GitHub-repo: Settings → Secrets and variables → Actions → New repository secret. Tilføj:

| Navn | Værdi |
|------|-------|
| `KEEP_EMAIL` | din Google-email (samme som du brugte ovenfor) |
| `KEEP_MASTER_TOKEN` | masterToken-strengen fra step 2 |
| `ANYLIST_EMAIL` | din AnyList-email |
| `ANYLIST_PASSWORD` | dit AnyList-password |

### 4. Test workflow'et manuelt

Push koden, gå til Actions-fanen, find "Sync Keep → AnyList"-workflow, klik "Run workflow". Tjek output.

Hvis den kørte succesfuldt: cron-trigger overtager nu og kører hvert 5. minut.

## Lokal testing

```bash
cp .env.example .env
# udfyld .env
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python sync.py
```

## Forventet adfærd

- Tom Keep-note → exit 0, ingen ændringer.
- Ingen Keep-note med matchende titel → exit 2, log advarsel.
- AnyList-liste findes ikke → exit 1, log fejl.
- Én item fejler → resten synkes, fejlende item bliver i Keep til næste run.

## Fejlsøgning

**`gpsoauth.perform_master_login` returnerer fejl ved token-generering**
- Du brugte sandsynligvis dit normale password i stedet for et App Password. Prøv igen.
- Hvis du ikke har 2-step verification, slå det til først.

**Workflow fejler med "kunne ikke logge ind på Google Keep"**
- Master-tokenet kan være udløbet eller invalideret (sker hvis du har skiftet password eller revoked app password). Generér et nyt og opdatér secret.

**Workflow fejler med "AnyList-listen 'Indkøb' findes ikke"**
- Tjek at listen findes i AnyList med præcis det navn (case-insensitive). Eller override via env: tilføj `ANYLIST_LIST_NAME` som secret/var med det rigtige navn.

**Items duplikeres i AnyList**
- Sker hvis `keep.sync()` fejler efter `add_item_with_details` succes. Tjek workflow-logs. Slet manuelt i AnyList og kryds af i Keep.

**Workflow kører ikke på tid**
- GitHub Actions cron har ikke garanteret præcision — kan forsinkes op til ~15 min ved peak load. Det er expected.

## Sikkerhed

- Workflow-logs er offentligt synlige (public repo). `sync.py` printer kun item-navne og generiske fejlbeskeder, aldrig tokens eller passwords.
- Hvis du ser en mistænkelig kørsel: revoke alle secrets, generér nye, og roter Google App Password.
