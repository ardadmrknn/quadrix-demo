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
            sound_keys = (
                'move', 'rotate', 'drop', 'line', 'clear', 'lock', 'hold',
                'click', 'pause', 'select', 'confirm', 'cancel', 'deny',
                'combo', 'levelup', 'tetris', 'gameover', 'card_reveal',
                'tutorial_success', 'tutorial_progress', 'tutorial_complete',
                'sniper_shot',
            )
            for key in sound_keys:
                self.create_gameplay_sfx(key)

            self._register_sound_alias('game_over', 'gameover')
            self._register_sound_alias('level_up', 'levelup')
        except Exception:
            self.enabled = False

    def create_gameplay_sfx(self, name):
        """Tema uyumlu kisa synth efektleri olustur."""
        profiles = {
            'move': {
                'duration_ms': 34,
                'attack_ms': 2,
                'release_ms': 20,
                'noise_amount': 0.003,
                'transient_amount': 0.012,
                'stereo_width': 0.006,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 520.0, 'end_freq': 430.0, 'amplitude': 0.42},
                    {'wave': 'sine', 'start_freq': 690.0, 'end_freq': 560.0, 'amplitude': 0.12},
                    {'wave': 'sine', 'start_freq': 260.0, 'end_freq': 220.0, 'amplitude': 0.15},
                ],
            },
            'rotate': {
                'duration_ms': 50,
                'attack_ms': 2,
                'release_ms': 28,
                'noise_amount': 0.002,
                'transient_amount': 0.008,
                'stereo_width': 0.012,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 360.0, 'end_freq': 560.0, 'amplitude': 0.34},
                    {'wave': 'sine', 'start_freq': 540.0, 'end_freq': 760.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 720.0, 'end_freq': 920.0, 'amplitude': 0.10},
                ],
            },
            'drop': {
                'duration_ms': 108,
                'attack_ms': 1,
                'release_ms': 76,
                'noise_amount': 0.020,
                'transient_amount': 0.080,
                'stereo_width': 0.006,
                'layers': [
                    {'wave': 'sine', 'start_freq': 240.0, 'end_freq': 118.0, 'amplitude': 0.64},
                    {'wave': 'triangle', 'start_freq': 420.0, 'end_freq': 170.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 96.0, 'end_freq': 72.0, 'amplitude': 0.18},
                ],
            },
            'lock': {
                'duration_ms': 64,
                'attack_ms': 1,
                'release_ms': 42,
                'noise_amount': 0.018,
                'transient_amount': 0.055,
                'stereo_width': 0.004,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 320.0, 'end_freq': 200.0, 'amplitude': 0.58},
                    {'wave': 'sine', 'start_freq': 170.0, 'end_freq': 140.0, 'amplitude': 0.22},
                    {'wave': 'sine', 'start_freq': 610.0, 'end_freq': 420.0, 'amplitude': 0.10},
                ],
            },
            'hold': {
                'duration_ms': 72,
                'attack_ms': 2,
                'release_ms': 46,
                'noise_amount': 0.008,
                'transient_amount': 0.020,
                'stereo_width': 0.018,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 510.0, 'end_freq': 650.0, 'amplitude': 0.40},
                    {'wave': 'sine', 'start_freq': 760.0, 'end_freq': 930.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 255.0, 'end_freq': 280.0, 'amplitude': 0.14},
                ],
            },
            'clear': {
                'duration_ms': 148,
                'attack_ms': 3,
                'release_ms': 84,
                'noise_amount': 0.010,
                'transient_amount': 0.014,
                'stereo_width': 0.022,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 520.0, 'end_freq': 640.0, 'amplitude': 0.34},
                    {'wave': 'sine', 'start_freq': 655.0, 'end_freq': 820.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 780.0, 'end_freq': 980.0, 'amplitude': 0.16},
                    {'wave': 'sine', 'start_freq': 260.0, 'end_freq': 310.0, 'amplitude': 0.14},
                ],
            },
            'line': {
                'duration_ms': 164,
                'attack_ms': 3,
                'release_ms': 92,
                'noise_amount': 0.004,
                'transient_amount': 0.010,
                'stereo_width': 0.020,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 392.0, 'end_freq': 494.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 494.0, 'end_freq': 659.0, 'amplitude': 0.22},
                    {'wave': 'sine', 'start_freq': 587.0, 'end_freq': 784.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 196.0, 'end_freq': 247.0, 'amplitude': 0.12},
                ],
            },
            'tetris': {
                'duration_ms': 260,
                'attack_ms': 3,
                'release_ms': 120,
                'noise_amount': 0.003,
                'transient_amount': 0.010,
                'stereo_width': 0.026,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 392.0, 'end_freq': 523.0, 'amplitude': 0.22},
                    {'wave': 'sine', 'start_freq': 523.0, 'end_freq': 784.0, 'amplitude': 0.20},
                    {'wave': 'sine', 'start_freq': 659.0, 'end_freq': 1047.0, 'amplitude': 0.16},
                    {'wave': 'sine', 'start_freq': 196.0, 'end_freq': 261.0, 'amplitude': 0.10},
                ],
            },
            'click': {
                'duration_ms': 28,
                'attack_ms': 1,
                'release_ms': 18,
                'noise_amount': 0.004,
                'transient_amount': 0.016,
                'stereo_width': 0.004,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 620.0, 'end_freq': 520.0, 'amplitude': 0.30},
                    {'wave': 'sine', 'start_freq': 920.0, 'end_freq': 760.0, 'amplitude': 0.10},
                ],
            },
            'pause': {
                'duration_ms': 86,
                'attack_ms': 2,
                'release_ms': 52,
                'noise_amount': 0.004,
                'transient_amount': 0.012,
                'stereo_width': 0.010,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 420.0, 'end_freq': 320.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 280.0, 'end_freq': 220.0, 'amplitude': 0.18},
                ],
            },
            'select': {
                'duration_ms': 34,
                'attack_ms': 1,
                'release_ms': 22,
                'noise_amount': 0.003,
                'transient_amount': 0.014,
                'stereo_width': 0.008,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 560.0, 'end_freq': 640.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 820.0, 'end_freq': 900.0, 'amplitude': 0.08},
                ],
            },
            'confirm': {
                'duration_ms': 92,
                'attack_ms': 2,
                'release_ms': 54,
                'noise_amount': 0.003,
                'transient_amount': 0.014,
                'stereo_width': 0.014,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 520.0, 'end_freq': 700.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 660.0, 'end_freq': 920.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 260.0, 'end_freq': 320.0, 'amplitude': 0.12},
                ],
            },
            'cancel': {
                'duration_ms': 96,
                'attack_ms': 2,
                'release_ms': 58,
                'noise_amount': 0.004,
                'transient_amount': 0.012,
                'stereo_width': 0.010,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 430.0, 'end_freq': 300.0, 'amplitude': 0.26},
                    {'wave': 'sine', 'start_freq': 320.0, 'end_freq': 220.0, 'amplitude': 0.18},
                ],
            },
            'deny': {
                'duration_ms': 112,
                'attack_ms': 1,
                'release_ms': 66,
                'noise_amount': 0.010,
                'transient_amount': 0.016,
                'stereo_width': 0.006,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 240.0, 'end_freq': 170.0, 'amplitude': 0.30},
                    {'wave': 'sine', 'start_freq': 310.0, 'end_freq': 210.0, 'amplitude': 0.14},
                ],
            },
            'combo': {
                'duration_ms': 118,
                'attack_ms': 2,
                'release_ms': 70,
                'noise_amount': 0.004,
                'transient_amount': 0.012,
                'stereo_width': 0.020,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 480.0, 'end_freq': 640.0, 'amplitude': 0.20},
                    {'wave': 'sine', 'start_freq': 640.0, 'end_freq': 860.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 240.0, 'end_freq': 320.0, 'amplitude': 0.12},
                ],
            },
            'levelup': {
                'duration_ms': 182,
                'attack_ms': 3,
                'release_ms': 96,
                'noise_amount': 0.004,
                'transient_amount': 0.012,
                'stereo_width': 0.024,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 440.0, 'end_freq': 660.0, 'amplitude': 0.22},
                    {'wave': 'sine', 'start_freq': 660.0, 'end_freq': 990.0, 'amplitude': 0.20},
                    {'wave': 'sine', 'start_freq': 220.0, 'end_freq': 330.0, 'amplitude': 0.10},
                ],
            },
            'gameover': {
                'duration_ms': 420,
                'attack_ms': 2,
                'release_ms': 180,
                'noise_amount': 0.006,
                'transient_amount': 0.008,
                'stereo_width': 0.010,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 220.0, 'end_freq': 130.0, 'amplitude': 0.24},
                    {'wave': 'sine', 'start_freq': 330.0, 'end_freq': 165.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 110.0, 'end_freq': 70.0, 'amplitude': 0.12},
                ],
            },
            'card_reveal': {
                'duration_ms': 126,
                'attack_ms': 2,
                'release_ms': 74,
                'noise_amount': 0.006,
                'transient_amount': 0.010,
                'stereo_width': 0.028,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 620.0, 'end_freq': 760.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 880.0, 'end_freq': 1180.0, 'amplitude': 0.16},
                    {'wave': 'sine', 'start_freq': 1180.0, 'end_freq': 1520.0, 'amplitude': 0.08},
                ],
            },
            'tutorial_success': {
                'duration_ms': 124,
                'attack_ms': 2,
                'release_ms': 70,
                'noise_amount': 0.003,
                'transient_amount': 0.012,
                'stereo_width': 0.020,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 520.0, 'end_freq': 700.0, 'amplitude': 0.22},
                    {'wave': 'sine', 'start_freq': 700.0, 'end_freq': 980.0, 'amplitude': 0.16},
                ],
            },
            'tutorial_progress': {
                'duration_ms': 72,
                'attack_ms': 1,
                'release_ms': 40,
                'noise_amount': 0.003,
                'transient_amount': 0.010,
                'stereo_width': 0.014,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 460.0, 'end_freq': 560.0, 'amplitude': 0.20},
                    {'wave': 'sine', 'start_freq': 640.0, 'end_freq': 760.0, 'amplitude': 0.10},
                ],
            },
            'tutorial_complete': {
                'duration_ms': 210,
                'attack_ms': 3,
                'release_ms': 110,
                'noise_amount': 0.004,
                'transient_amount': 0.012,
                'stereo_width': 0.028,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 520.0, 'end_freq': 784.0, 'amplitude': 0.20},
                    {'wave': 'sine', 'start_freq': 784.0, 'end_freq': 1175.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 260.0, 'end_freq': 392.0, 'amplitude': 0.08},
                ],
            },
            'sniper_shot': {
                'duration_ms': 96,
                'attack_ms': 1,
                'release_ms': 48,
                'noise_amount': 0.020,
                'transient_amount': 0.080,
                'stereo_width': 0.004,
                'layers': [
                    {'wave': 'triangle', 'start_freq': 1400.0, 'end_freq': 920.0, 'amplitude': 0.18},
                    {'wave': 'sine', 'start_freq': 240.0, 'end_freq': 120.0, 'amplitude': 0.16},
                ],
            },
        }
        profile = profiles.get(name)
        if profile is None:
            raise KeyError(f"Bilinmeyen gameplay SFX profili: {name}")
        self.create_layered_sfx(name, **profile)

    def _register_sound_alias(self, alias, target):
        sound = self.sounds.get(target)
        if sound is not None:
            self.sounds[alias] = sound

    def create_layered_sfx(
        self,
        name,
        *,
        layers,
        duration_ms,
        attack_ms=2,
        release_ms=24,
        noise_amount=0.0,
        transient_amount=0.0,
        stereo_width=0.0,
    ):
        """Katmanli, kisa synth efektleri olustur."""
        try:
            mixer_info = pygame.mixer.get_init()
            sample_rate = int(mixer_info[0]) if mixer_info else 44100
            num_samples = max(1, int(duration_ms * sample_rate / 1000))
            attack_samples = max(1, int(attack_ms * sample_rate / 1000))
            release_samples = max(1, int(release_ms * sample_rate / 1000))
            transient_samples = max(1, int(min(duration_ms * 0.35, 12) * sample_rate / 1000))
            pcm = array('h')
            phases = [[0.0, 0.0] for _ in layers]
            inv_rate = 1.0 / float(sample_rate)
            amplitude_scale = 0.80

            for i in range(num_samples):
                progress = i / float(max(1, num_samples - 1))
                env = self._sfx_envelope(i, num_samples, attack_samples, release_samples)
                noise_env = max(0.0, 1.0 - (progress * 1.8))
                transient_env = max(0.0, 1.0 - (i / float(transient_samples))) if i < transient_samples else 0.0
                left = 0.0
                right = 0.0

                for layer_idx, layer in enumerate(layers):
                    start_freq = float(layer['start_freq'])
                    end_freq = float(layer.get('end_freq', start_freq))
                    layer_amp = float(layer.get('amplitude', 1.0))
                    wave = layer.get('wave', 'sine')
                    freq = start_freq + (end_freq - start_freq) * progress
                    detune = stereo_width * (layer_idx + 1)
                    freq_l = max(1.0, freq * (1.0 - detune))
                    freq_r = max(1.0, freq * (1.0 + detune))
                    phases[layer_idx][0] += 2.0 * math.pi * freq_l * inv_rate
                    phases[layer_idx][1] += 2.0 * math.pi * freq_r * inv_rate
                    left += self._oscillator_sample(phases[layer_idx][0], wave) * layer_amp
                    right += self._oscillator_sample(phases[layer_idx][1], wave) * layer_amp

                if noise_amount > 0.0:
                    noise = (random.random() * 2.0 - 1.0) * noise_amount * noise_env
                    left += noise
                    right += noise * (1.0 - stereo_width * 0.5)

                if transient_amount > 0.0 and transient_env > 0.0:
                    transient = transient_amount * transient_env
                    left += transient
                    right += transient * 0.92

                left *= env * amplitude_scale
                right *= env * amplitude_scale
                left = max(-1.0, min(1.0, left))
                right = max(-1.0, min(1.0, right))
                pcm.append(int(left * 32767))
                pcm.append(int(right * 32767))

            sound = pygame.mixer.Sound(buffer=pcm.tobytes())
            self.sounds[name] = sound
        except Exception:
            self.enabled = False

    def _sfx_envelope(self, index, total_samples, attack_samples, release_samples):
        if total_samples <= 1:
            return 1.0
        if index < attack_samples:
            return 0.5 - 0.5 * math.cos(math.pi * (index / float(max(1, attack_samples))))
        release_start = max(0, total_samples - release_samples)
        if index >= release_start:
            release_progress = (index - release_start) / float(max(1, release_samples))
            return 0.5 + 0.5 * math.cos(math.pi * min(1.0, release_progress))
        return 1.0

    def _oscillator_sample(self, phase, wave):
        phase = math.fmod(phase, 2.0 * math.pi)
        if wave == 'triangle':
            return (2.0 / math.pi) * math.asin(math.sin(phase))
        return math.sin(phase)
    
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
        - 'main_1' -> music/ klasöründen otomatik yüklenen track key
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

        # Versiyon soneki değişmiş olabilir: klasikv1 -> klasik_1 vb.
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
            self.create_gameplay_sfx('gameover')
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
