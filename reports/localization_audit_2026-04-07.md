# Localization Audit - 2026-04-07

## Scope
- Project-wide localization audit for all supported languages.
- Root-cause analysis for untranslated UI text and English leakage.
- Runtime-safe fix path using override merge + usage-side hardcoded text cleanup.

## TODO Plan (Completed)
1. Audit localization architecture and fallback flow.
2. Extract per-language untranslated key report.
3. Scan and fix hardcoded UI literals in runtime screens.
4. Apply translation and fallback fixes.
5. Validate syntax and runtime sample output.

## Findings
- Total localization keys: 1528
- Missing keys by language: 0 for all languages.
- Core issue: many keys existed but target-language value was exactly English.
- Hardcoded non-localized literals existed in some UI flows.

## Before/After (same-as-English keys)
- tr: 89 -> 26
- de: 565 -> 73
- fr: 552 -> 47
- es: 537 -> 25
- it: 548 -> 45
- pt: 537 -> 32
- ru: 414 -> 8
- ja: 303 -> 13
- zh: 193 -> 8
- ko: 191 -> 12

## What Was Implemented
- Added runtime override merge support in localization core.
- Generated multilingual override dataset for English-identical entries.
- Added/connected missing localization keys used by color picker and block workshop UI.
- Replaced selected hardcoded UI strings with localization-key lookups.
- Added reusable maintenance script for regeneration of overrides.

## Validation
- Static errors: no errors in modified Python files.
- Runtime smoke check: multi-language lookups return translated output from overrides.
