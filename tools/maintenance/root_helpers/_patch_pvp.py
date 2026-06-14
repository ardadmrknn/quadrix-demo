with open('src/pvp_game.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the "# P - Duraklat" section
start = None
for i, line in enumerate(lines):
    if '# P - Duraklat' in line and 'pvp_controls' in lines[i+1]:
        start = i
        break

if start is None:
    print("SECTION NOT FOUND")
else:
    print(f"Found at line {start+1}")
    for j in range(start, start+30):
        print(f"{start+1+j-start}: {repr(lines[j])}")
