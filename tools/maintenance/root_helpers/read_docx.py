import re
from pathlib import Path

from docx import Document


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DOC = REPO_ROOT / 'docs' / 'archive' / 'reference' / 'Gorev_Modu_Rehberi.docx'

def read_docx():
    try:
        doc = Document(SOURCE_DOC)
    except Exception as e:
        print(f"Error reading docx: {e}")
        return

    current_level = None
    level_data = {}

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text: continue
        
        # Match "Seviye X: Name"
        m = re.match(r'^Seviye\s+(\d+):\s+(.*)', text)
        if m:
            current_level = int(m.group(1))
            if current_level > 30:
                break
            level_data[current_level] = {'name': m.group(2).replace(' [BOSS BÖLÜMÜ]', ''), 'text': []}
            continue
            
        if current_level:
            level_data[current_level]['text'].append(text)

    with open('docx_output.txt', 'w', encoding='utf-8') as f:
        for lvl, data in level_data.items():
            f.write(f"--- Level {lvl} ---\n")
            f.write(f"Name: {data['name']}\n")
            for line in data['text']:
                f.write(line + "\n")

if __name__ == '__main__':
    read_docx()
