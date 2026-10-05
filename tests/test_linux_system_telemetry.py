# -*- coding: utf-8 -*-
"""linux_system_telemetry: Linux sistem telemetri modülü birim testleri.

Kapsam:
- Non-Linux platformda no-op (Windows/macOS davranışı değişmez).
- Linux zorlamasında yerel log dosyası oluşur; bölümler (OS/CPU/MEMORY/
  DISPLAY/RUNTIME/ENV) toplanır.
- Log YEREL dizine yazılır (cloud alt dizinine ASLA).
- Gizli bilgi güvenliği: LEADERBOARD_*/Steam benzeri credential değerleri
  logda ASLA görünmez; QUADRIX_* önekli anahtarlar (hassas olmayanlar) loglanır.
- Boyut sınırı: 512 KB üzeri eski log .old'a döner.
- Hata dayanıklılığı: tek koleksiyon bölümü çökse bile blok yazılır.
- Bir süreçte bir kez yazılır (force ile yeniden).
"""

import os
import sys

import pytest


_here = os.path.dirname(__file__)
_src_dir = os.path.abspath(os.path.join(_here, '..', 'src'))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import linux_system_telemetry as lst  # noqa: E402


@pytest.fixture
def linux_env(monkeypatch, tmp_path):
    """Modülü Linux kabul et + yerel veri dizinini tmp_path'e yönlendir."""
    monkeypatch.setattr(lst, 'IS_LINUX', True)
    monkeypatch.setattr(lst, '_resolve_data_dir', lambda: str(tmp_path))
    monkeypatch.setattr(lst, '_SESSION_WRITTEN', False)
    monkeypatch.setattr(lst, '_LAST_LOG_PATH', None)
    return tmp_path


def test_non_linux_is_noop(monkeypatch, tmp_path):
    """Windows/macOS'ta hiçbir dosya yazılmaz (dönüş None)."""
    monkeypatch.setattr(lst, 'IS_LINUX', False)
    monkeypatch.setattr(lst, '_resolve_data_dir', lambda: str(tmp_path))
    monkeypatch.setattr(lst, '_SESSION_WRITTEN', False)
    assert lst.collect_and_log_startup() is None
    assert not (tmp_path / lst.LOG_FILENAME).exists()


def test_linux_writes_local_log_file(linux_env):
    """Linux zorlamasında log YEREL dizinde oluşur ve bölümler toplanır."""
    path = lst.collect_and_log_startup()
    assert path is not None
    log_file = linux_env / lst.LOG_FILENAME
    assert log_file.exists()
    content = log_file.read_text(encoding='utf-8')
    assert 'QUADRIX LINUX SYSTEM TELEMETRY' in content
    # Windows test makinesinde /proc okunamaz → bölümler boş kalabilir; OS ve
    # RUNTIME bölümleri platformdan bağımsız her zaman dolmalı.
    assert 'os =' in content
    assert 'python = ' in content
    assert 'frozen = ' in content


def test_written_once_per_process(linux_env, monkeypatch):
    """Bir süreçte bir kez yazılır; force=True yeniden yazar."""
    first = lst.collect_and_log_startup()
    second = lst.collect_and_log_startup()
    assert first == second
    counter = {'n': 0}

    def counting_dir():
        counter['n'] += 1
        return str(linux_env)

    monkeypatch.setattr(lst, '_resolve_data_dir', counting_dir)
    assert lst.collect_and_log_startup() is first
    assert counter['n'] == 0  # cache'ten döndü, yeniden çözmedi
    lst.collect_and_log_startup(force=True)
    assert counter['n'] == 1


def test_log_path_is_local_dir_not_cloud(monkeypatch):
    """Gerçek çözümleyici local/ alt dizinini döndürür (cloud/ ASLA — Auto-Cloud
    yalnız cloud/ alt dizinini eşzamanlar, telemetri buluta çıkmaz)."""
    # Stub kalıntılarını temizle → gerçek data_paths ile çözümle.
    for key in ('data_paths', 'src.data_paths'):
        sys.modules.pop(key, None)
    monkeypatch.setattr(lst, 'IS_LINUX', True)
    monkeypatch.setattr(lst, '_SESSION_WRITTEN', False)
    data_dir = lst._resolve_data_dir()
    if data_dir is None:
        pytest.skip('data_paths çözümlenemedi')
    normalized = os.path.normpath(data_dir).replace('\\', '/')
    assert normalized.endswith('/local')
    assert '/cloud' not in normalized


def test_secrets_never_logged(linux_env, monkeypatch):
    """Credential env değerleri toplanmaz; sızsa bile redaction maskeler."""
    secret_token = 'SuperSecretTokenValue123456789'
    steam_secret = 'SteamSecretValue87654321'
    monkeypatch.setenv('LEADERBOARD_CLIENT_TOKEN', secret_token)
    monkeypatch.setenv('LEADERBOARD_BACKEND_URL', 'https://example.invalid/api')
    monkeypatch.setenv('STEAMCLIENT_TOKEN', steam_secret)
    monkeypatch.setenv('QUADRIX_LINUX_FULLSCREEN_MODE', 'auto')
    monkeypatch.setenv('QUADRIX_TEST_FLAG', '1')

    lst.collect_and_log_startup(force=True)
    content = (linux_env / lst.LOG_FILENAME).read_text(encoding='utf-8')

    assert secret_token not in content
    assert steam_secret not in content
    assert 'LEADERBOARD_CLIENT_TOKEN' not in content
    assert 'env_LEADERBOARD' not in content
    # Hassas olmayan QUADRIX_* ve whitelist anahtarları loglanır.
    assert 'env_QUADRIX_LINUX_FULLSCREEN_MODE = auto' in content
    assert 'env_QUADRIX_TEST_FLAG = 1' in content


def test_sensitive_quatrix_prefix_filtered(linux_env, monkeypatch):
    """Hassas işaretli QUADRIX_* anahtarı toplanmaz (savunma derinliği)."""
    monkeypatch.setenv('QUADRIX_SECRET_TOKEN', 'value1234567890')
    lst.collect_and_log_startup(force=True)
    content = (linux_env / lst.LOG_FILENAME).read_text(encoding='utf-8')
    assert 'QUADRIX_SECRET_TOKEN' not in content


def test_rotation_on_oversize(linux_env):
    """Mevcut log sınırı aşarsa .old'a döner; yeni blok taze dosyaya yazılır."""
    log_file = linux_env / lst.LOG_FILENAME
    log_file.write_bytes(b'x' * (lst._MAX_LOG_BYTES + 1024))
    lst.collect_and_log_startup(force=True)
    assert (linux_env / (lst.LOG_FILENAME + lst._ROTATED_SUFFIX)).exists()
    fresh = log_file.read_text(encoding='utf-8')
    assert 'QUADRIX LINUX SYSTEM TELEMETRY' in fresh
    assert 'xxxx' not in fresh  # eski içerik yeni dosyada değil


def test_collector_failure_does_not_block_writing(linux_env, monkeypatch):
    """Tek bölüm çökerse bile blok yazılır (best-effort sözleşmesi)."""
    def _boom():
        raise RuntimeError('collector failure')

    monkeypatch.setattr(lst, '_collect_cpu', _boom)
    path = lst.collect_and_log_startup(force=True)
    assert path is not None
    content = (linux_env / lst.LOG_FILENAME).read_text(encoding='utf-8')
    assert '--- CPU ---' not in content  # çöken bölüm atlandı
    assert '--- OS ---' in content       # sağlıklı bölüm yazıldı


def test_data_dir_failure_returns_none(monkeypatch):
    """Veri dizini çözülemezse sessiz None döner (oyun düşmez)."""
    monkeypatch.setattr(lst, 'IS_LINUX', True)
    monkeypatch.setattr(lst, '_SESSION_WRITTEN', False)
    monkeypatch.setattr(lst, '_resolve_data_dir', lambda: None)
    assert lst.collect_and_log_startup() is None


def test_redaction_masks_leaked_values(monkeypatch):
    """_redact_sensitive_values: sızan hassas değer <REDACTED> olur."""
    secret = 'LeakedSecretValue987654321'
    monkeypatch.setenv('LEADERBOARD_CLIENT_TOKEN', secret)
    text = f'preamble {secret} postamble'
    result = lst._redact_sensitive_values(text)
    assert secret not in result
    assert '<REDACTED>' in result


def test_is_sensitive_key_markers():
    """Hassas anahtar işaretleri: token/secret/password/credential/apikey."""
    assert lst._is_sensitive_key('LEADERBOARD_CLIENT_TOKEN')
    assert lst._is_sensitive_key('QUADRIX_SECRET')
    assert lst._is_sensitive_key('STEAM_PASSWORD')
    assert lst._is_sensitive_key('QUADRIX_APIKEY')
    assert not lst._is_sensitive_key('QUADRIX_LINUX_FULLSCREEN_MODE')
    assert not lst._is_sensitive_key('XDG_SESSION_TYPE')


def test_host_distro_read_from_run_host(linux_env, monkeypatch):
    """Soldier konteynerinde host dağıtımı /run/host/etc/os-release'tan okunur.

    /etc/os-release konteyner kimliğini (steamrt) taşır; host gerçeği
    host_distro_* alanlarıyla ek olarak loglanır — iki bilgi birden kalır.
    """
    def fake_read(path):
        if path == '/run/host/etc/os-release':
            return {'PRETTY_NAME': 'Void Linux', 'NAME': 'Void Linux',
                    'VERSION_ID': 'rolling', 'ID': 'void'}
        if path == '/etc/os-release':
            return {'PRETTY_NAME': 'Steam Runtime 2 (soldier)', 'ID': 'steamrt'}
        return {}

    monkeypatch.setattr(lst, '_read_kv_file', fake_read)
    lst.collect_and_log_startup(force=True)
    content = (linux_env / lst.LOG_FILENAME).read_text(encoding='utf-8')
    assert 'host_distro_pretty_name = Void Linux' in content
    assert 'host_distro_id = void' in content
    # Konteyner kimliği de korunur (ayrı bilgi).
    assert 'distro_pretty_name = Steam Runtime 2 (soldier)' in content


def test_no_host_distro_when_native(linux_env, monkeypatch):
    """Konteyner dışında /run/host yok → host_distro satırları yazılmaz.

    Doğal çalıştırmada distro_* zaten host'un kendisidir; tekrar yazılmaz.
    """
    def fake_read(path):
        if path == '/etc/os-release':
            return {'PRETTY_NAME': 'Arch Linux', 'ID': 'arch'}
        return {}

    monkeypatch.setattr(lst, '_read_kv_file', fake_read)
    lst.collect_and_log_startup(force=True)
    content = (linux_env / lst.LOG_FILENAME).read_text(encoding='utf-8')
    assert 'host_distro' not in content
    assert 'distro_pretty_name = Arch Linux' in content


def test_env_whitelist_has_no_credential_keys():
    """Beyaz liste bilinçli olarak credential anahtarı içermez (sabit sözleşme)."""
    for key in lst._ENV_WHITELIST:
        assert not lst._is_sensitive_key(key), f'whitelist hassas anahtar: {key}'
        assert not key.startswith(('LEADERBOARD_', 'STEAM')), key
