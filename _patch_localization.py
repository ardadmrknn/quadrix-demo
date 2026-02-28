"""
Patch localization.py: Add missing language entries to every TRANSLATIONS key.
For EU langs (de/fr/es/it/pt) and ru: use English fallback with proper translations where available.
For CJK (ja/zh/ko): use English fallback.
Also merges _RU_TRANSLATIONS into main TRANSLATIONS dict.
"""
import re
import sys
import os

sys.path.insert(0, 'src')
os.environ['TETRIS_LOCALIZATION_HOT_RELOAD'] = '0'

SUPPORTED = ['tr', 'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'ja', 'zh', 'ko']

# ── Step 1: Read source and parse raw TRANSLATIONS ─────────────────────
with open('src/localization.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract raw TRANSLATIONS dict
trans_start = content.index("TRANSLATIONS = {")
trans_end_marker = "\ndef _ensure_language_fallback"
trans_end = content.index(trans_end_marker)
trans_code = content[trans_start:trans_end].rstrip()

ns = {}
exec(trans_code, ns)
raw = ns['TRANSLATIONS']

# Extract _RU_TRANSLATIONS
ru_start = content.index("_RU_TRANSLATIONS = {")
ru_block = content[ru_start:]
ru_end_pos = ru_block.index("\n}")
ru_code = ru_block[:ru_end_pos + 2]
ns2 = {}
exec(ru_code, ns2)
ru_trans = ns2['_RU_TRANSLATIONS']

print(f"Raw keys: {len(raw)}")
print(f"RU override keys: {len(ru_trans)}")

# ── Step 2: Merge RU translations into raw dict ─────────────────────
for k, v in ru_trans.items():
    if k in raw:
        raw[k]['ru'] = v

# ── Step 3: Build translation maps for EU languages ─────────────────
# Common word translations for all EU languages
EU_COMMON = {
    'de': {
        'Back': 'Zurück', 'Default': 'Standard', 'Transparency': 'Transparenz',
        'Delete': 'Löschen', 'Duplicate': 'Duplizieren', 'Modes': 'Modi',
        'New': 'Neu', 'Rename': 'Umbenennen', 'Select': 'Auswählen',
        'Exit': 'Beenden', 'Guide': 'Anleitung', 'Settings': 'Einstellungen',
        'Quit': 'Beenden', 'Cancel': 'Abbrechen', 'On': 'An', 'Off': 'Aus',
        'Yes': 'Ja', 'No': 'Nein', 'Save': 'Speichern', 'Load': 'Laden',
        'Reset': 'Zurücksetzen', 'Close': 'Schließen', 'Open': 'Öffnen',
        'Start': 'Starten', 'Stop': 'Stoppen', 'Pause': 'Pause',
        'Resume': 'Fortsetzen', 'Restart': 'Neustart', 'Continue': 'Weiter',
        'Next': 'Weiter', 'Previous': 'Zurück', 'Skip': 'Überspringen',
        'Confirm': 'Bestätigen', 'Apply': 'Anwenden', 'OK': 'OK',
    },
    'fr': {
        'Back': 'Retour', 'Default': 'Par défaut', 'Transparency': 'Transparence',
        'Delete': 'Supprimer', 'Duplicate': 'Dupliquer', 'Modes': 'Modes',
        'New': 'Nouveau', 'Rename': 'Renommer', 'Select': 'Sélectionner',
        'Exit': 'Quitter', 'Guide': 'Guide', 'Settings': 'Paramètres',
        'Quit': 'Quitter', 'Cancel': 'Annuler', 'On': 'Activé', 'Off': 'Désactivé',
        'Yes': 'Oui', 'No': 'Non', 'Save': 'Sauvegarder', 'Load': 'Charger',
        'Reset': 'Réinitialiser', 'Close': 'Fermer', 'Open': 'Ouvrir',
        'Start': 'Démarrer', 'Stop': 'Arrêter', 'Pause': 'Pause',
        'Resume': 'Reprendre', 'Restart': 'Redémarrer', 'Continue': 'Continuer',
        'Next': 'Suivant', 'Previous': 'Précédent', 'Skip': 'Passer',
        'Confirm': 'Confirmer', 'Apply': 'Appliquer', 'OK': 'OK',
    },
    'es': {
        'Back': 'Atrás', 'Default': 'Predeterminado', 'Transparency': 'Transparencia',
        'Delete': 'Eliminar', 'Duplicate': 'Duplicar', 'Modes': 'Modos',
        'New': 'Nuevo', 'Rename': 'Renombrar', 'Select': 'Seleccionar',
        'Exit': 'Salir', 'Guide': 'Guía', 'Settings': 'Configuración',
        'Quit': 'Salir', 'Cancel': 'Cancelar', 'On': 'Activado', 'Off': 'Desactivado',
        'Yes': 'Sí', 'No': 'No', 'Save': 'Guardar', 'Load': 'Cargar',
        'Reset': 'Restablecer', 'Close': 'Cerrar', 'Open': 'Abrir',
        'Start': 'Iniciar', 'Stop': 'Detener', 'Pause': 'Pausa',
        'Resume': 'Reanudar', 'Restart': 'Reiniciar', 'Continue': 'Continuar',
        'Next': 'Siguiente', 'Previous': 'Anterior', 'Skip': 'Omitir',
        'Confirm': 'Confirmar', 'Apply': 'Aplicar', 'OK': 'OK',
    },
    'it': {
        'Back': 'Indietro', 'Default': 'Predefinito', 'Transparency': 'Trasparenza',
        'Delete': 'Elimina', 'Duplicate': 'Duplica', 'Modes': 'Modalità',
        'New': 'Nuovo', 'Rename': 'Rinomina', 'Select': 'Seleziona',
        'Exit': 'Esci', 'Guide': 'Guida', 'Settings': 'Impostazioni',
        'Quit': 'Esci', 'Cancel': 'Annulla', 'On': 'Attivo', 'Off': 'Disattivo',
        'Yes': 'Sì', 'No': 'No', 'Save': 'Salva', 'Load': 'Carica',
        'Reset': 'Reimposta', 'Close': 'Chiudi', 'Open': 'Apri',
        'Start': 'Avvia', 'Stop': 'Ferma', 'Pause': 'Pausa',
        'Resume': 'Riprendi', 'Restart': 'Ricomincia', 'Continue': 'Continua',
        'Next': 'Avanti', 'Previous': 'Precedente', 'Skip': 'Salta',
        'Confirm': 'Conferma', 'Apply': 'Applica', 'OK': 'OK',
    },
    'pt': {
        'Back': 'Voltar', 'Default': 'Padrão', 'Transparency': 'Transparência',
        'Delete': 'Excluir', 'Duplicate': 'Duplicar', 'Modes': 'Modos',
        'New': 'Novo', 'Rename': 'Renomear', 'Select': 'Selecionar',
        'Exit': 'Sair', 'Guide': 'Guia', 'Settings': 'Configurações',
        'Quit': 'Sair', 'Cancel': 'Cancelar', 'On': 'Ligado', 'Off': 'Desligado',
        'Yes': 'Sim', 'No': 'Não', 'Save': 'Salvar', 'Load': 'Carregar',
        'Reset': 'Redefinir', 'Close': 'Fechar', 'Open': 'Abrir',
        'Start': 'Iniciar', 'Stop': 'Parar', 'Pause': 'Pausa',
        'Resume': 'Retomar', 'Restart': 'Reiniciar', 'Continue': 'Continuar',
        'Next': 'Próximo', 'Previous': 'Anterior', 'Skip': 'Pular',
        'Confirm': 'Confirmar', 'Apply': 'Aplicar', 'OK': 'OK',
    },
}

def get_eu_translation(en_val, lang):
    """Try to translate using common word map, else return English."""
    stripped = en_val.strip()
    common = EU_COMMON.get(lang, {})
    if stripped in common:
        return common[stripped]
    return en_val

# ── Step 4: Fill ALL missing language entries ─────────────────────
filled = 0
for key in raw:
    for lang in SUPPORTED:
        if lang not in raw[key]:
            en_val = raw[key].get('en', raw[key].get('tr', key))
            if lang in ('de', 'fr', 'es', 'it', 'pt'):
                raw[key][lang] = get_eu_translation(en_val, lang)
            else:
                raw[key][lang] = en_val
            filled += 1

print(f"Filled {filled} missing entries")

# ── Step 5: Write back to localization.py ─────────────────────
# Build the new TRANSLATIONS block
lines = []
lines.append("TRANSLATIONS = {")

# Group keys by section comments from original file
# Extract section comments
original_trans_block = content[trans_start:trans_end]
# Parse comments and key order
current_section = None
key_order = []
section_map = {}  # key -> section comment before it
prev_comments = []

for line in original_trans_block.split('\n'):
    stripped = line.strip()
    if stripped.startswith('#'):
        prev_comments.append(line)
    elif re.match(r"    '\w+':\s*\{", stripped) or re.match(r"    '\w+':\s*\{", line):
        m = re.match(r"    '(\w+)':", line)
        if m:
            k = m.group(1)
            if k in raw:
                key_order.append(k)
                if prev_comments:
                    section_map[k] = prev_comments[:]
                prev_comments = []

# Keys in raw but not in key_order (like user_profile_updated we just added)
extra_keys = [k for k in raw if k not in key_order]
key_order.extend(sorted(extra_keys))

for key in key_order:
    if key not in raw:
        continue
    # Add section comments if any
    if key in section_map:
        for c in section_map[key]:
            lines.append(c)
    
    entry = raw[key]
    lines.append(f"    '{key}': {{")
    
    # Write in consistent language order
    for lang in SUPPORTED:
        if lang in entry:
            val = entry[lang]
            # Escape single quotes and newlines in value
            val_escaped = val.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
            lines.append(f"        '{lang}': '{val_escaped}',")
    
    lines.append("    },")

lines.append("}")
new_trans_block = '\n'.join(lines)

# ── Step 6: Replace TRANSLATIONS block and remove _RU_TRANSLATIONS ─────────
# Replace TRANSLATIONS block
new_content = content[:trans_start] + new_trans_block + content[trans_end:]

# Remove _RU_TRANSLATIONS block and its merge loop
ru_section_start = new_content.index("\n# =====================================================================\n# RUSÇA (RU)")
ru_merge_end_marker = "TRANSLATIONS[_ru_key]['ru'] = _ru_val\n"
ru_merge_end = new_content.index(ru_merge_end_marker) + len(ru_merge_end_marker)
new_content = new_content[:ru_section_start] + "\n" + new_content[ru_merge_end:]

with open('src/localization.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Done! localization.py updated.")

# Verify
with open('src/localization.py', 'r', encoding='utf-8') as f:
    verify = f.read()
print(f"New file size: {len(verify)} chars, {verify.count(chr(10))} lines")
