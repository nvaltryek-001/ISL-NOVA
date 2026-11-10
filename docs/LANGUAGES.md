# Languages: English · हिन्दी · ಕನ್ನಡ

ISL NOVA shows sign meanings and its interface in **English, Hindi and Kannada**. ISL is its own language; these are the *spoken-language meanings* of each isolated sign, not translations of ISL grammar.

## Coverage (all 200 signs)

| Language | Meanings with text | Status | Source |
|---|---:|---|---|
| English | 200 / 200 | `source_gloss` (from INCLUDE folder names) | INCLUDE |
| Hindi | 200 / 200 | `draft` | machine draft (ISL NOVA v2) |
| Kannada | 200 / 200 | `draft` | machine draft (ISL NOVA v2) |
| **Verified by a linguist** | **0 / 600** | — | needs native speakers + ISL linguist |

Live numbers: `GET /api/v1/translations/coverage`, shown in **Sign Explorer → Translation coverage**.

Each meaning stores `text`, `transliteration` (Latin script), `status` (`pending · source_gloss · draft · verified · rejected`), `source`, `reviewer` and `reviewed_at`.

## Where drafts come from

`dataset/vocabulary/drafts/hi_kn_machine_drafts.csv` holds machine-drafted Hindi and Kannada word meanings with transliterations. `python dataset/scripts/draft_translations.py` merges them into `dataset/vocabulary/translations.csv`. It only fills rows that are still empty and `pending`, so human work is never overwritten. On start-up the server applies the same rule to existing databases.

Drafts are always shown with a **Draft** badge, are excluded from quizzes and quick phrases (which use verified meanings only), and must never be described as verified.

## Review protocol

1. A linguist or admin downloads **Review sheet (CSV)** from Sign Explorer (`GET /api/v1/translations/review-sheet.csv`, UTF-8 with BOM so Excel shows the scripts).
2. Native speakers fill `new_text`, `new_transliteration` and `new_status` (`draft`, `verified` or `rejected`) and a note.
3. **Import reviewed sheet** (`POST /api/v1/translations/import`) applies the changes.
   - Only the `linguist` role can set `verified`.
   - A verified meaning can only be changed by a linguist.
   - Every import is audit-logged; per-row errors are returned.
4. Single meanings can also be edited on a sign's page (`PUT /api/v1/signs/{id}/translations/{lang}`).

Some glosses are ambiguous in English ("Tomorrow"/"Yesterday" are both *kal* in Hindi; "Short" vs "Small"; "Tall" vs "Long"). Drafts disambiguate in brackets; reviewers should confirm the intended sense against the ISL reference video.

## Interface localisation

- `frontend/src/i18n/strings.ts`: 320 interface strings with Hindi and Kannada (machine-drafted, under review). English text is the key; missing keys fall back to English.
- Translated automatically: page titles and kickers, card titles, buttons, field labels, tabs, notices, empty states, all status badges, navigation, header.
- **Coverage:** 100 % of the 238 strings passed as titles, labels and buttons (enforced by `tests/i18n.test.ts`, floor 90 %). Long explanatory paragraphs inside pages remain English for now.
- Language switcher in the header; the choice persists per browser and sets `<html lang>`.
- Fonts: the app uses the system's Devanagari and Kannada fonts (Noto Sans Devanagari / Kannada where installed, Nirmala UI on Windows). No web fonts are loaded, which keeps the strict CSP.
- Speech: `en-IN`, `hi-IN`, `kn-IN` via the browser's speech synthesis. If a voice is missing, the app says so.

## Tests

- Backend: `backend/tests/test_translations.py` covers coverage counts, review-sheet export, import permissions, the linguist-only `verified` status and protection of verified rows. `test_core_and_signs.py` checks that 200 hi/kn drafts exist and none are verified.
- Frontend: `tests/i18n.test.ts` checks that every key has both scripts, the fallback, and string coverage.
- E2E: switching the interface to Hindi and Kannada, persistence across reload, and the coverage panel.
