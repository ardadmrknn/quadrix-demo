import ast
import os
import pathlib
import re


ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
LOCALIZATION_PATH = ROOT_DIR / 'src' / 'localization.py'


def _load_localization_source_tables():
    source = LOCALIZATION_PATH.read_text(encoding='utf-8')
    module = ast.parse(source)

    supported_languages = None
    translations = None
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'SUPPORTED_LANGUAGES':
                    supported_languages = ast.literal_eval(node.value)
                elif isinstance(target, ast.Name) and target.id == 'TRANSLATIONS':
                    translations = ast.literal_eval(node.value)

    assert supported_languages is not None
    assert translations is not None
    return supported_languages, translations


def test_localization_source_has_all_languages_for_every_key():
    supported_languages, translations = _load_localization_source_tables()

    missing = {}
    for key, values in translations.items():
        absent = [lang for lang in supported_languages if lang not in values]
        if absent:
            missing[key] = absent

    assert not missing, f'Kaynak localization tablosunda eksik diller var: {missing}'


def test_literal_translation_keys_used_in_code_exist_in_source_table():
    _, translations = _load_localization_source_tables()
    pattern = re.compile(r"\b(?:t|get_text)\(\s*['\"]([^'\"]+)['\"]")

    used_keys = {}
    code_files = list((ROOT_DIR / 'src').rglob('*.py')) + [ROOT_DIR / 'main.py']
    for path in code_files:
        text = path.read_text(encoding='utf-8')
        relative_path = path.relative_to(ROOT_DIR).as_posix()
        for match in pattern.finditer(text):
            used_keys.setdefault(match.group(1), set()).add(relative_path)

    missing_keys = {key: sorted(paths) for key, paths in used_keys.items() if key not in translations}
    assert not missing_keys, f'Kodda kullanılıp localization kaynağında olmayan anahtarlar var: {missing_keys}'