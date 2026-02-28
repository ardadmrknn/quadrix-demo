"""Ses yöneticisi"""
import math
import os
import random
import shutil
import subprocess
import sys
import re
import difflib
from array import array
from pathlib import Path
import pygame

import constants


class SoundManager:
    """Oyun seslerini yönetir"""
    
    def __init__(self):
        """Ses sistemini başlat"""
        try:
            self.enabled = self._ensure_mixer_ready()
            self.sfx_enabled = True
            self.music_volume = 0.3
            self.sfx_volume = 0.5
            self.music_enabled = True
            self.muted = False
            self._resume_track_name = None
            self._resume_loop = True
            self.assets_root = self._detect_assets_root()
            self.track_volumes = self._default_track_volumes()
            
            self.sounds = {}
            if self.enabled:
                self.create_sounds()
            
            self.current_music_channel = None
            self.music_tracks = {}
            self.track_aliases = {}
            self.current_track_name = None
            self.music_paused = False
            if self.enabled:
                self.create_music()
            
        except Exception as e:
            if constants.DEBUG_MODE:
                print(f"❌ [SoundManager] Hata: {e}")
            self.enabled = False

    def _log_macos_audio_info(self):
        """macOS'ta ses sistemi hakkında detaylı bilgi logla - sadece DEBUG modda"""
        if not constants.DEBUG_MODE:
            return
        try:
            print("=" * 50)
            print("🔊 [macOS] SES SİSTEMİ BİLGİLERİ")
            print("=" * 50)
            audio_driver = os.environ.get('SDL_AUDIODRIVER', 'not set')
            print(f"   SDL_AUDIODRIVER: {audio_driver}")
            init_info = pygame.mixer.get_init()
            if init_info:
                freq, format_bits, channels = init_info
                print(f"   Mixer: {freq}Hz, {abs(format_bits)}-bit, {'stereo' if channels==2 else 'mono'}")
            print("=" * 50)
        except Exception:
            pass

    def _ensure_mixer_ready(self) -> bool:
        """Ensure pygame.mixer is initialized."""
        # Önce mevcut durumu kontrol et
        try:
            init_info = pygame.mixer.get_init()
            if init_info is not None:
                return True
        except Exception:
            pass

        # macOS için SDL_AUDIODRIVER kontrolü
        if sys.platform == 'darwin':
            current_driver = os.environ.get('SDL_AUDIODRIVER', 'not set')
            if current_driver == 'dummy':
                os.environ['SDL_AUDIODRIVER'] = 'coreaudio'

        last_error = None
        if sys.platform == 'darwin':
            candidates = [
                (44100, -16, 2, 4096),
                (44100, -16, 2, 2048),
                (48000, -16, 2, 4096),
                (48000, -16, 2, 2048),
                (44100, -16, 2, 1024),
                (44100, -16, 1, 2048),
                (22050, -16, 2, 2048),
                (22050, -16, 1, 1024),
            ]
        else:
            candidates = [
                (44100, -16, 2, 512),
                (44100, -16, 2, 1024),
                (44100, -16, 2, 2048),
                (48000, -16, 2, 512),
                (48000, -16, 2, 1024),
            ]

        for frequency, size, channels, buffer in candidates:
            try:
                try:
                    pygame.mixer.quit()
                except:
                    pass
                pygame.mixer.init(frequency=frequency, size=size, channels=channels, buffer=buffer)
                if pygame.mixer.get_init():
                    return True
            except Exception as exc:
                last_error = exc
                continue

        # Son çare: varsayılan init
        try:
            pygame.mixer.quit()
        except:
            pass
        try:
            pygame.mixer.init()
            if pygame.mixer.get_init():
                return True
        except Exception as exc:
            last_error = exc

        return False

    def _macos_cached_music_dir(self) -> Path:
        try:
            if sys.platform == 'darwin':
                return (Path.home() / 'Library' / 'Caches' / 'tetris' / 'music').resolve()
        except Exception:
            pass
        return (Path.home() / '.cache' / 'tetris' / 'music').resolve()

    def _convert_mp3_to_ogg(self, mp3_path: str) -> str | None:
        """Try to convert MP3 to OGG using ffmpeg (if available).

        Not: Bu bir "en iyi çaba" fallback. ffmpeg yoksa None döner.
        """
        try:
            src = Path(mp3_path).resolve()
            if not src.exists():
                return None
            if shutil.which('ffmpeg') is None:
                return None

            cache_dir = self._macos_cached_music_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)

            try:
                stamp = int(src.stat().st_mtime)
            except Exception:
                stamp = 0
            out = cache_dir / f"{src.stem}_{stamp}.ogg"
            if out.exists():
                return str(out)

            cmd = [
                'ffmpeg',
                '-y',
                '-loglevel',
                'error',
                '-i',
                str(src),
                '-c:a',
                'libvorbis',
                '-q:a',
                '4',
                str(out),
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                return None
            if out.exists():
                return str(out)
            return None
        except Exception:
            return None

    def set_muted(self, muted: bool) -> bool:
        """Tüm sesleri (müzik + SFX) geçici olarak sustur/geri al.

        Bu, music_enabled/sfx_enabled gibi kalıcı tercihleri değiştirmez.
        Müzik duraklatılır (pause) ve ses açıldığında kaldığı yerden devam eder.
        """
        muted = bool(muted)

        if not self.enabled:
            self.muted = muted
            return self.muted

        if muted == getattr(self, 'muted', False):
            return self.muted

        self.muted = muted

        if self.muted:
            # Şu an çalan track bilgisini koru
            self._resume_track_name = self.current_track_name
            self._resume_loop = True

            # Müziği durdurmak yerine duraklat - kaldığı yerden devam edebilsin
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass

            # Channel tabanlı müzik varsa onu da duraklat
            if self.current_music_channel is not None:
                try:
                    self.current_music_channel.pause()
                except Exception:
                    pass

            # SFX ses objelerini durdur (müzik kanalını bozmamak için mixer.stop() kullanmıyoruz)
            for snd in self.sounds.values():
                try:
                    snd.stop()
                except Exception:
                    pass

            self.music_paused = True
        else:
            # Müziği kaldığı yerden devam ettir
            try:
                pygame.mixer.music.unpause()
            except Exception:
                pass

            # Channel tabanlı müzik varsa onu da devam ettir
            if self.current_music_channel is not None:
                try:
                    self.current_music_channel.unpause()
                except Exception:
                    pass

            self.music_paused = False

            # Eğer müzik bir şekilde durmuşsa (pause yerine stop olmuşsa) yeniden başlat
            try:
                music_busy = pygame.mixer.music.get_busy()
            except Exception:
                music_busy = False

            channel_busy = False
            if self.current_music_channel is not None:
                try:
                    channel_busy = bool(self.current_music_channel.get_busy())
                except Exception:
                    pass

            if not music_busy and not channel_busy and self.music_enabled:
                track = self._resume_track_name or self.current_track_name
                if track:
                    try:
                        self.play_music(track, loop=self._resume_loop)
                    except Exception:
                        pass

        return self.muted
    
    def create_sounds(self):
        """Basit ses efektleri oluştur"""
        try:
            self.create_beep('move', 440, 50)
            self.create_beep('rotate', 523, 50)
            self.create_beep('drop', 330, 100)
            self.create_beep('line', 660, 150)
            self.create_beep('tetris', 880, 300)
            
            # Game over effect try loading from file first
            # Game over effect try loading from file first
            # WAV dosyası daha uyumlu olduğu için onu önceliyoruz
            game_over_wav = self.assets_root / 'assets' / 'effect' / 'game_over_effect.wav'
            game_over_mp3 = self.assets_root / 'assets' / 'effect' / 'game_over_effect.mp3'
            
            game_over_path = None
            if game_over_wav.exists():
                game_over_path = game_over_wav
            elif game_over_mp3.exists():
                game_over_path = game_over_mp3

            loaded_game_over = False
            if game_over_path:
                print(f"🔍 Game over sound aranıyor: {game_over_path}")
                try:
                    self.sounds['gameover'] = pygame.mixer.Sound(str(game_over_path))
                    self.sounds['gameover'].set_volume(self.sfx_volume)
                    loaded_game_over = True
                    print("✅ Game over sound dosyadan yüklendi!")
                except Exception as e:
                    print(f"❌ Game over sound yüklenemedi: {e}")
            else:
                print("❌ Game over sound dosyası bulunamadı!")
            
            if not loaded_game_over:
                self.create_beep('gameover', 220, 500)
                print("⚠️ Game over için varsayılan beep sesi oluşturuldu.")

            # Kart açılma efekti (opsiyonel dosya)
            card_reveal_wav = self.assets_root / 'assets' / 'effect' / 'card_reveal.wav'
            card_reveal_mp3 = self.assets_root / 'assets' / 'effect' / 'card_reveal.mp3'
            card_reveal_path = None
            if card_reveal_wav.exists():
                card_reveal_path = card_reveal_wav
            elif card_reveal_mp3.exists():
                card_reveal_path = card_reveal_mp3
            if card_reveal_path:
                try:
                    self.sounds['card_reveal'] = pygame.mixer.Sound(str(card_reveal_path))
                    self.sounds['card_reveal'].set_volume(self.sfx_volume)
                except Exception:
                    self.create_beep('card_reveal', 760, 60)
            else:
                self.create_beep('card_reveal', 760, 60)
                
            self.create_beep('select', 550, 40)
            self.create_beep('confirm', 700, 80)
            self.create_beep('cancel', 280, 80)
            self.create_beep('deny', 200, 120)
            self.create_beep('combo', 750, 100)
            self.create_beep('levelup', 900, 200)
            self.create_beep('clear', 600, 100)
            self.create_beep('lock', 400, 60)
            self.create_beep('hold', 480, 50)
            
            # Tutorial özel sesleri
            self.create_beep('tutorial_success', 800, 150)
            self.create_beep('tutorial_progress', 600, 80)
            self.create_beep('tutorial_complete', 1000, 250)
            
            # Sniper özel sesi
            self.create_beep('sniper_shot', 1200, 120)  # Yüksek frekanslı keskin ses
        except Exception:
            self.enabled = False
    
    def create_beep(self, name, frequency, duration):
        """Basit bir bip sesi oluştur"""
        try:
            sample_rate = 22050
            num_samples = int(duration * sample_rate / 1000)
            if num_samples <= 0:
                return
            fade_samples = min(500, max(1, num_samples // 4))
            pcm = array('h')
            volume = max(0.0, min(1.0, float(self.sfx_volume)))
            amplitude = int(32767 * volume)
            two_pi_f = 2.0 * math.pi * float(frequency)
            inv_rate = 1.0 / float(sample_rate)
            for i in range(num_samples):
                t = i * inv_rate
                sample_f = math.sin(two_pi_f * t)
                if i < fade_samples:
                    env = i / float(fade_samples)
                elif i >= num_samples - fade_samples:
                    env = (num_samples - 1 - i) / float(fade_samples)
                else:
                    env = 1.0
                if env < 0.0:
                    env = 0.0
                s = int(sample_f * amplitude * env)
                pcm.append(s)
                pcm.append(s)
            sound = pygame.mixer.Sound(buffer=pcm.tobytes())
            self.sounds[name] = sound
        except Exception:
            self.enabled = False
    
    def create_music(self):
        """Harici müzikleri yükle."""
        try:
            self._load_all_music_files()
        except Exception:
            pass
    
    def _load_all_music_files(self):
        """music/ klasöründeki tüm desteklenen müzik dosyalarını otomatik yükle"""
        SUPPORTED_FORMATS = {'.mp3', '.wav', '.ogg', '.flac'}
        try:
            music_dir = (self.assets_root / 'music').resolve()
            if not music_dir.exists():
                return
            for file in music_dir.iterdir():
                if file.is_file() and file.suffix.lower() in SUPPORTED_FORMATS:
                    track_key = file.stem.lower().replace(' ', '_').replace('-', '_')
                    if track_key not in self.music_tracks:
                        self.load_external_music(track_key, str(file))
        except Exception:
            pass
    
    def _print_available_tracks(self):
        """Mevcut müzik parçalarını listele"""
        builtin = []
        external = []
        
        for name, track in self.music_tracks.items():
            if isinstance(track, str):
                ext = Path(track).suffix.upper()[1:]  # .mp3 -> MP3
                external.append(f"{name} ({ext})")
            else:
                builtin.append(name)
        
        if builtin:
            print(f"   🎹 Yerleşik: {', '.join(builtin[:5])}{'...' if len(builtin) > 5 else ''}")
        if external:
            print(f"   📁 Harici: {', '.join(external)}")
    
    def load_external_music(self, name, filepath):
        """Dışarıdan müzik dosyası yükle"""
        SUPPORTED_FORMATS = {'.mp3', '.wav', '.ogg', '.flac', '.mid', '.midi'}
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = (self.assets_root / path).resolve()
            ext = path.suffix.lower()
            if ext not in SUPPORTED_FORMATS:
                return False
            if path.exists():
                self._store_track(name, str(path))
                return True
            return False
        except Exception:
            return False

    def ensure_track_available(self, preference):
        """Return a track key for the given preference, loading files if needed.

        Bu projede yerleşik (sentez) müzik yoktur; sadece dosya tabanlı müzikler.

        Kullanım örnekleri:
        - 'mainv3' -> music/ klasöründen otomatik yüklenen track key
        - 'file:my_song.mp3' -> music/my_song.mp3 dosyası
        - 'file:subfolder/song.ogg' -> music/subfolder/song.ogg
        """
        # Desteklenen formatlar
        SUPPORTED_FORMATS = ('.mp3', '.wav', '.ogg', '.flac', '.mid', '.midi')

        pref = (preference or '').strip()
        if not pref:
            return None
        if pref.lower().startswith('file:'):
            rel_path = pref[5:].strip()
            if not rel_path:
                return None
            # Case-sensitive dosya sistemlerinde (bazı macOS kurulumları dahil)
            # yolu lower() yapmak dosya eşleşmesini bozabilir.
            sanitized = rel_path.replace('\\', '/')
            track_key = f"usertrack::{sanitized}"
            if track_key not in self.music_tracks:
                music_root = (self.assets_root / 'music').resolve()
                absolute_path = (music_root / rel_path).resolve()
                
                # Dosya uzantısız verilmişse, otomatik olarak bul
                if not absolute_path.suffix:
                    for ext in SUPPORTED_FORMATS:
                        test_path = absolute_path.with_suffix(ext)
                        if test_path.exists():
                            absolute_path = test_path
                            break
                
                if absolute_path.exists():
                    if self.load_external_music(track_key, str(absolute_path)):
                        return track_key
                    else:
                        return None
                else:
                    if constants.DEBUG_MODE:
                        print(f"⚠️ Özel müzik bulunamadı: {absolute_path}")
                        print(f"   Desteklenen formatlar: {', '.join(SUPPORTED_FORMATS)}")
                    return None
            return track_key

        normalized = self._normalize_track_name(pref)
        if normalized in self.music_tracks:
            return normalized
        return None
    
    def _normalize_track_name(self, name):
        """Display name'i track key'e çevir
        
        Örnek: 'Crazy Frog' -> 'crazy_frog', 'My Song' -> 'my_song'
        """
        if not name:
            return ''
        
        # Önce direkt eşleşme dene
        normalized = name.lower()
        if normalized in self.music_tracks:
            return normalized
        
        # Boşlukları alt çizgiye çevir
        normalized = name.lower().replace(' ', '_').replace('-', '_')
        if normalized in self.music_tracks:
            return normalized
        
        # Title case'den dönüşüm dene (örn: CrazyFrog -> crazyfrog)
        normalized = name.lower().replace(' ', '')
        if normalized in self.music_tracks:
            return normalized

        # Eski/yeni isim uyumluluğu için alias ve fuzzy eşleşme
        resolved = self._resolve_track_alias(name)
        if resolved:
            return resolved
        
        # Hiçbiri eşleşmezse normalize edilmiş hali döndür
        return name.lower()

    def _slug_track_name(self, value):
        if value is None:
            return ''
        raw = str(value).strip().lower()
        if raw.startswith('file:'):
            raw = raw[5:]
        if raw.startswith('usertrack::'):
            raw = raw.split('::', 1)[1]
        try:
            raw = Path(raw).stem
        except Exception:
            pass
        raw = raw.replace('-', '_').replace(' ', '_')
        raw = re.sub(r'[^a-z0-9_]', '', raw)
        raw = re.sub(r'_+', '_', raw).strip('_')
        return raw

    def _strip_version_suffix(self, slug):
        # Örnek: klasikv3 -> klasik, main_v2 -> main, sprint0 -> sprint
        if not slug:
            return ''
        base = re.sub(r'(?:_?v?\d+)$', '', slug)
        base = re.sub(r'_+', '_', base).strip('_')
        return base

    def _register_track_alias(self, alias, key):
        alias_slug = self._slug_track_name(alias)
        if not alias_slug:
            return
        if alias_slug not in self.track_aliases:
            self.track_aliases[alias_slug] = key

    def _resolve_track_alias(self, raw_name):
        if not raw_name:
            return None

        # Track list yüklenmiş ama alias haritası boşsa yeniden kur
        if self.music_tracks and not self.track_aliases:
            for key, track in self.music_tracks.items():
                self._register_track_alias(key, key)
                if isinstance(track, str):
                    self._register_track_alias(Path(track).stem, key)

        slug = self._slug_track_name(raw_name)
        if not slug:
            return None

        direct = self.track_aliases.get(slug)
        if direct in self.music_tracks:
            return direct

        # Versiyon soneki değişmiş olabilir: klasikv1 -> klasik0 vb.
        base = self._strip_version_suffix(slug)
        if base:
            candidates = []
            pattern = re.compile(rf"^{re.escape(base)}(?:[_v]?\d+)?$")
            for alias, key in self.track_aliases.items():
                if alias == base or pattern.match(alias):
                    candidates.append((alias, key))

            # En yakın/eşdeğer alias'ı tercih et (daha kısa ad genelde temel varyanttır)
            if candidates:
                candidates.sort(key=lambda item: (len(item[0]), item[0]))
                for _alias, key in candidates:
                    if key in self.music_tracks:
                        return key

        # Son çare: en yakın alias adını seç
        alias_keys = list(self.track_aliases.keys())
        if alias_keys:
            matches = difflib.get_close_matches(slug, alias_keys, n=1, cutoff=0.72)
            if matches:
                key = self.track_aliases.get(matches[0])
                if key in self.music_tracks:
                    return key

        return None
    
    def play_music(self, track_name=None, loop=True, force=False):
        """Arka plan müzik çal
        
        Args:
            track_name: Çalınacak parça adı
            loop: Döngüde çal
            force: True ise aynı parça çalıyor olsa bile yeniden başlat
        """
        if not self.enabled or not self.music_enabled:
            return
        if getattr(self, 'muted', False):
            if track_name:
                self._resume_track_name = self._normalize_track_name(track_name)
                self._resume_loop = bool(loop)
            return
        if not track_name:
            return
        
        track_name = self._normalize_track_name(track_name)
        
        try:
            if track_name in self.music_tracks:
                try:
                    music_busy = pygame.mixer.music.get_busy()
                except:
                    music_busy = False
                
                # Force değilse ve aynı parça çalıyorsa atla
                if not force and self.current_track_name == track_name and music_busy:
                    return
                
                if self.current_music_channel:
                    self.current_music_channel.stop()
                pygame.mixer.music.stop()
                
                track = self.music_tracks[track_name]

                if isinstance(track, str):
                    try:
                        pygame.mixer.music.load(track)
                    except Exception as exc:
                        # Fallback: alternatif format dene
                        try:
                            p = Path(str(track))
                            if p.suffix.lower() == '.mp3':
                                for alt_ext in ('.ogg', '.wav', '.flac'):
                                    alt = p.with_suffix(alt_ext)
                                    if alt.exists():
                                        pygame.mixer.music.load(str(alt))
                                        self.music_tracks[track_name] = str(alt)
                                        raise SystemExit
                        except SystemExit:
                            pass
                        except Exception:
                            pass
                        # MP3 > OGG conversion on macOS
                        if sys.platform == 'darwin' and str(track).lower().endswith('.mp3'):
                            ogg = self._convert_mp3_to_ogg(track)
                            if ogg:
                                try:
                                    pygame.mixer.music.load(ogg)
                                    self.music_tracks[track_name] = ogg
                                except Exception:
                                    raise exc
                            else:
                                raise exc
                        else:
                            raise exc
                    
                    volume = self._compute_volume(track_name)
                    pygame.mixer.music.set_volume(volume)
                    pygame.mixer.music.play(-1 if loop else 0)
                    self.current_music_channel = None
                    self.current_track_name = track_name
                    self.music_paused = False
                else:
                    loops = -1 if loop else 0
                    track.set_volume(self._compute_volume(track_name))
                    self.current_music_channel = track.play(loops=loops)
                    self.current_track_name = track_name
                    self.music_paused = False
        except Exception:
            pass
    
    def pause_music(self):
        """Müziği duraklat"""
        if self.enabled and pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.music_paused = True
            if constants.DEBUG_MODE:
                print(f"⏸️ Müzik duraklatıldı: {self.current_track_name}")
    
    def unpause_music(self):
        """Müziği devam ettir"""
        if self.enabled and self.music_paused:
            pygame.mixer.music.unpause()
            self.music_paused = False
            if constants.DEBUG_MODE:
                print(f"▶️ Müzik devam ediyor: {self.current_track_name}")
    
    def stop_music(self):
        """Müziği durdur"""
        if self.current_music_channel:
            self.current_music_channel.stop()
            self.current_music_channel = None
        pygame.mixer.music.stop()
        self.current_track_name = None
        self.music_paused = False
        self.music_playlist_active = False

    def set_music_playlist(self, tracks, loop=True, start_index=0, autoplay=True, force=False, shuffle=False):
        """Playlist tanımla ve istenirse çalmaya başla. shuffle=True ise sıra karıştırılır."""
        if not self.enabled:
            return
        if not isinstance(tracks, list):
            tracks = []
        cleaned = [t for t in tracks if isinstance(t, str) and t]
        if shuffle and len(cleaned) > 1:
            cleaned = list(cleaned)
            random.shuffle(cleaned)
            start_index = 0
        self.music_playlist = cleaned
        self.music_playlist_loop = bool(loop)
        self.music_playlist_index = max(0, min(int(start_index or 0), max(0, len(cleaned) - 1)))
        self.music_playlist_active = bool(cleaned)

        if autoplay and self.music_playlist_active:
            self._play_current_playlist_track(force=force)

    def clear_music_playlist(self):
        self.music_playlist = []
        self.music_playlist_index = 0
        self.music_playlist_active = False

    def _playlist_is_busy(self) -> bool:
        try:
            if self.current_music_channel:
                return bool(self.current_music_channel.get_busy())
        except Exception:
            pass
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def _play_current_playlist_track(self, force=False):
        if not self.music_playlist_active:
            return
        if not self.music_playlist:
            return
        if self.music_playlist_index < 0 or self.music_playlist_index >= len(self.music_playlist):
            self.music_playlist_index = 0
        track_name = self.music_playlist[self.music_playlist_index]
        self.play_music(track_name, loop=False, force=force)

    def play_next_in_playlist(self, force=False):
        if not self.music_playlist_active:
            return
        if not self.music_playlist:
            return

        self.music_playlist_index += 1
        if self.music_playlist_index >= len(self.music_playlist):
            self.music_playlist_index = 0

        self._play_current_playlist_track(force=force)

    def update_music_playlist(self):
        """Playlist aktifse, şarkı bitince sıradakine geç."""
        if not self.music_playlist_active:
            return
        if not self.enabled or not self.music_enabled:
            return
        if getattr(self, 'muted', False):
            return
        if self.music_paused:
            return
        if self._playlist_is_busy():
            return
        self.play_next_in_playlist()
    
    def toggle_music(self):
        """Müziği aç/kapat"""
        self.music_enabled = not self.music_enabled
        if not self.music_enabled:
            self.stop_music()
        return self.music_enabled
    
    def set_music_volume(self, volume):
        """Müzik seviyesini ayarla"""
        self.music_volume = max(0.0, min(1.0, volume))
        for name, track in self.music_tracks.items():
            if hasattr(track, 'set_volume'):
                track.set_volume(self._compute_volume(name))
        if self.current_track_name and isinstance(self.music_tracks.get(self.current_track_name), str):
            pygame.mixer.music.set_volume(self._compute_volume(self.current_track_name))

    def duck_music(self, factor: float = 0.25):
        """Müziği duck et (pause menüsü için). factor: 0-1 arası; 0.25 = %25 seviye."""
        self._music_duck_factor = max(0.0, min(1.0, factor))
        self._apply_duck_volume()

    def unduck_music(self):
        """Müzik duck'ı kaldır, normal seviyeye dön."""
        self._music_duck_factor = 1.0
        self._apply_duck_volume()

    def _apply_duck_volume(self):
        """Mevcut duck factor'ü tüm müzik kanallarına uygula."""
        for name, track in self.music_tracks.items():
            if hasattr(track, 'set_volume'):
                track.set_volume(self._compute_volume(name))
        if self.current_track_name and isinstance(self.music_tracks.get(self.current_track_name), str):
            try:
                pygame.mixer.music.set_volume(self._compute_volume(self.current_track_name))
            except Exception:
                pass
    
    def play(self, sound_name):
        """Ses efekti çal"""
        if self.enabled and (not getattr(self, 'muted', False)) and self.sfx_enabled and sound_name in self.sounds:
            try:
                self.sounds[sound_name].play()
            except Exception:
                pass
    # alias for older usage
    play_sound = play
    
    def toggle(self):
        """Sesi aç/kapat"""
        self.enabled = not self.enabled
        return self.enabled
    
    def set_volume(self, volume):
        """Ses seviyesini ayarla (0.0 - 1.0)"""
        self.sfx_volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.sfx_volume)
    
    def play_game_over_sequence(self):
        """Oyun bittiğinde müziği durdur ve gameover sesini çal"""
        if not self.enabled: return
        
        # Müziği durdur
        self.stop_music()
        
        # Game Over sesini çal (yüksek sesle)
        if 'gameover' in self.sounds:
            try:
                # Force volume to max for visibility
                self.sounds['gameover'].set_volume(1.0)
                self.sounds['gameover'].play()
                print("🔊 Game Over sesi tetiklendi!")
            except Exception as e:
                print(f"❌ Game Over sesi çalma hatası: {e}")
        else:
            print("⚠️ Game Over sesi yüklü değil, beep kullanılıyor.")
            self.create_beep('gameover', 220, 500)
            self.sounds['gameover'].play()

    def get_available_tracks(self):
        """Mevcut tüm müzik parçalarının listesini döndür
        
        Returns:
            dict: {'builtin': [...], 'external': [...]}
        """
        builtin = []
        external = []
        
        for name, track in self.music_tracks.items():
            if isinstance(track, str):
                ext = Path(track).suffix.lower()[1:]  # .mp3 -> mp3
                external.append({'name': name, 'format': ext, 'path': track})
            else:
                builtin.append(name)
        
        return {'builtin': builtin, 'external': external}
    
    @staticmethod
    def get_supported_formats():
        """Desteklenen müzik formatlarını döndür
        
        Returns:
            list: Desteklenen dosya uzantıları
        """
        return ['.mp3', '.wav', '.ogg', '.flac', '.mid', '.midi']

    def _detect_assets_root(self):
        """Projeye göre müzik/asset kökünü bul"""
        if getattr(sys, 'frozen', False):
            return Path(sys._MEIPASS)
        return Path(__file__).resolve().parents[1]

    def _store_track(self, name, track):
        """Track kaydet ve uygun ses seviyesini uygula"""
        self.music_tracks[name] = track
        self._register_track_alias(name, name)
        if isinstance(track, str):
            try:
                self._register_track_alias(Path(track).stem, name)
            except Exception:
                pass
        if hasattr(track, 'set_volume'):
            track.set_volume(self._compute_volume(name))

    def _compute_volume(self, track_name):
        base = self.music_volume
        multiplier = self.track_volumes.get(track_name, 1.0)
        duck = getattr(self, '_music_duck_factor', 1.0)
        return max(0.0, min(1.0, base * multiplier * duck))

    def _default_track_volumes(self):
        """Her parça için göreceli ses seviyesi"""

        # Dosyadan çalınan parçalarda genelde tek bir genel ses seviyesi yeterli.
        # Yine de belirli track key'ler için çarpan tanımlamak isterseniz buraya ekleyebilirsiniz.
        return {}
