# 🎮 QUADRIX FULL EDITION V2.6

**Multi-Platform Quadrix Game - Python, TypeScript & C++**

Bu proje klasik Quadrix oyununun 3 farklı dilde implementasyonunu içerir:
- 🐍 **Python** (Pygame ile) - Ana versiyonu
- 📜 **TypeScript** - Web versiyonu  
- ⚡ **C++** - Native performans versiyonu

## 🚀 HIZLI BAŞLANGIÇ



### Windows## Project Structure

**OYUNU_BASLAT.bat** dosyasına çift tıklayın

```

### macOS / Linuxtetris-game

Terminal'de şu komutları çalıştırın:├── src

```bash│   ├── main.ts        # Entry point of the game

cd Desktop/burak│   ├── game.ts        # Game logic management

chmod +x oyunu_baslat.sh│   ├── board.ts       # Game board representation

./oyunu_baslat.sh│   ├── pieces.ts      # Quadrix pieces and their rotations

```│   ├── input.ts       # User input handling

│   ├── render.ts      # Rendering the game on the screen

### Manuel Başlatma (Tüm Platformlar)│   └── types

```bash│       └── index.ts   # Types and interfaces

python src/main.py├── public

# veya│   ├── index.html     # Main HTML file

python3 src/main.py│   └── styles.css     # Styles for the game

```├── package.json       # npm configuration

├── tsconfig.json      # TypeScript configuration

---

## 📋 GEREKSİNİMLER

### 🐍 Python Versiyonu:
- Python 3.7+
- Pygame kütüphanesi

### 📜 TypeScript Versiyonu:
- Node.js ve npm
- Modern web tarayıcısı

### ⚡ C++ Versiyonu:
- CMake 3.15+
- C++17 uyumlu compiler (MinGW/Visual Studio)
- SDL2, SDL2_mixer, SDL2_ttf kütüphaneleri

### Kütüphaneleri Yükleme

**Python:**
```bash
# Windows
pip install -r requirements.txt

# macOS / Linux
pip3 install -r requirements.txt
```

**TypeScript:**
```bash
cd tetris-game
npm install
npm start
```

**C++:**
```batch
cd cpp
build.bat
run.bat
```

Detaylı C++ kurulum için: `cpp/README.md`

---

## ✨ ÖZELLİKLER

### 🎮 Oyun Modları
✅ **Tek Oyunculu** - Klasik Quadrix
✅ **PvP (2 Oyuncu)** - İsim girişi + VS gösterimi

### 🎵 11 Farklı Müzik
Crazy Frog dahil 11 8-bit müzik!

### 🏆 25+ Başarı Sistemi
### 🎨 5 Görsel Tema

### 🖼️ Özel Arka Plan Desteği

## How to Play

---

- Use the arrow keys to move the pieces left, right, and down.

## 🎮 KONTROLLER- Press the up arrow key to rotate the pieces.

- The goal is to fill complete lines to clear them and score points.

**Tek Oyuncu:** ←→↓ Space C P ESC

**PvP:** WASD (P1) + Ok Tuşları (P2)## Contributing



Detaylar için **NASIL_OYNANIR.txt** dosyasına bakın.Feel free to submit issues or pull requests if you have suggestions or improvements for the game.



---## License



## 📁 DOSYA YAPISIThis project is open-source and available under the MIT License.

```
burak/
├── OYUNU_BASLAT.bat    🪟 Windows
├── oyunu_baslat.sh     🍎 macOS/Linux
├── src/                💻 Kaynak kodlar
├── music/              🎵 Müzikler
├── backgrounds/        🖼️ Arka planlar
└── requirements.txt    📦 Gereksinimler
```

---

## 👥 EMEĞİ GEÇENLER

**Arda Demirkan & Burak Yaşayan**

© 2025 - Quadrix Full Edition V2.6

---

## 🌐 PLATFORM DESTEĞİ

✅ Windows 10/11
✅ macOS 10.15+
✅ Linux
