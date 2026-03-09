# Project Cleanup Audit

Date: 2026-03-09

## Scope

This audit separates root-level items into three groups:
- keep in root
- moved into related folders
- deletion candidates not removed automatically

## Files Kept In Root

These remain in the repository root because code, build scripts, or packaging files refer to them directly:
- main.py
- pyproject.toml
- README.md
- AGENTS.md

## Files Moved During Cleanup

These were root-level files with no active runtime dependency and were grouped under related folders:
- BUILD_README.md -> docs/archive/BUILD_README.md
- PLATFORM_SUPPORT.md -> docs/archive/PLATFORM_SUPPORT.md
- TEST_ESNEK_SINIR.md -> docs/archive/manual-tests/TEST_ESNEK_SINIR.md
- TEST_ESNEK_SINIR_YENI.md -> docs/archive/manual-tests/TEST_ESNEK_SINIR_YENI.md
- Gorev_Modu_Rehberi.docx -> docs/archive/reference/Gorev_Modu_Rehberi.docx
- gunluk_gorevler_word.docx -> docs/archive/reference/gunluk_gorevler_word.docx
- timer.html -> public/timer.html
- build_windows_exe.ps1 -> scripts/build/build_windows_exe.ps1
- build_macos_app.sh -> scripts/build/build_macos_app.sh
- steam_upload_macos.sh -> scripts/build/steam_upload_macos.sh
- run.sh -> scripts/run/run.sh
- run_game.ps1 -> scripts/run/run_game.ps1
- run_test_score.bat -> scripts/run/run_test_score.bat
- start_game.bat -> scripts/run/start_game.bat
- start_game.sh -> scripts/run/start_game.sh
- Tetris.command -> scripts/run/Tetris.command
- README_FULL.md -> docs/guides/README_FULL.md
- README_MACOS.md -> docs/guides/README_MACOS.md
- README_TR.md -> docs/guides/README_TR.md
- pyi_rth_lang_en.py -> packaging/pyinstaller/hooks/pyi_rth_lang_en.py
- pyi_rth_quadrix_data.py -> packaging/pyinstaller/hooks/pyi_rth_quadrix_data.py
- requirements.txt -> packaging/requirements/requirements.txt
- requirements-macos.txt -> packaging/requirements/requirements-macos.txt
- tetris.spec -> packaging/specs/tetris.spec
- tetris_en.spec -> packaging/specs/tetris_en.spec
- tetris_macos.spec -> packaging/specs/tetris_macos.spec
- tetris_macos_allinone.spec -> packaging/specs/tetris_macos_allinone.spec
- tetris_playtest.spec -> packaging/specs/tetris_playtest.spec
- run_tests.sh -> scripts/test/run_tests.sh
- pytest -> scripts/test/pytest
- settings.txt -> config/runtime/settings.txt
- steam_appid.txt -> config/runtime/steam_appid.txt
- menu_layout_runtime.json -> config/runtime/menu_layout_runtime.json
- tetris_user_data.csv -> data/legacy/tetris_user_data.csv
- steam_api64.dll -> local_artifacts/dll/steam_api64.dll
- steam_net_bridge.cp312-win_amd64.pyd -> local_artifacts/bridge/steam_net_bridge.cp312-win_amd64.pyd
- build_log.txt -> reports/logs/build_log.txt
- build_stdout.log -> reports/logs/build_stdout.log
- build_stderr.log -> reports/logs/build_stderr.log
- stderr.log -> reports/logs/stderr.log

## Deletion Candidates

### Safe To Delete Regenerable Artifacts

These are build, cache, or log outputs and can be removed when not needed:
- build/
- dist/
- __pycache__/
- .pytest_cache/
- reports/logs/build_log.txt
- reports/logs/build_stdout.log
- reports/logs/build_stderr.log
- reports/logs/stderr.log

### Likely Redundant Local Build Outputs

Delete only if you do not need the current local build result:
- local_artifacts/dll/steam_api64.dll
- local_artifacts/bridge/steam_net_bridge.cp312-win_amd64.pyd

Reason:
- steam_api64.dll is already documented as a copied artifact; canonical binaries live under dll/
- steam_net_bridge.cp312-win_amd64.pyd is a platform-specific local build product and is ignored by git

### Conditional Cleanup Targets

Review before deleting:
- archive/root_duplicate_tests/
- reports/logs/build_log.txt
- reports/logs/proxy_debug.log
- diary/
- todo/
- models/

Reason:
- these look like archive, diagnostics, worklog, backlog, or local experiment areas rather than core runtime code
- they may still hold useful historical or operational context

## Notes

- settings.txt, steam_appid.txt, and menu_layout_runtime.json were moved to config/runtime/ and code/spec paths were updated accordingly.
- Root should primarily contain entrypoints, top-level metadata, and a small number of human-facing files.
- Legacy docs and manual test notes now live under docs/archive/.
- Launch/build scripts now live under scripts/.
- PyInstaller runtime hooks now live under packaging/pyinstaller/hooks/ and spec files now live under packaging/specs/.
