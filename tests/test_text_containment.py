"""FAZ A5: ortak text fitting / containment kütüphanesi sözleşme testleri.

Gorsel_Olcek_Sorunlari_Cozum_Plani.md FAZ A5 (plan satır 265-280):
- measure / width-aware wrap / max-lines / line-height / minimum readable
  font / ellipsis ortak yardımcıları (ui_text_layout + text_cache.measure_text)
- taşma sırası: wrap -> kontrollü ellipsis
- font sınırsız büyümez; minimum font eşiği altına SESSİZCE düşülmez
  (``min_size_hit`` bayrağı taşmayı bildirir)
- tr/en/ru uzun + aksanlı string fixture'ları (TRANSLATIONS'tan, modül
  çalıştırılarak yüklenir — süpürme bulgusu: 67 yinelenen anahtar 'son giren
  kazanır' semantiğiyle çakıştığından ilk-grep okuma yanlış değer verir;
  fixture'lar yalnız test GÖVDESİNDE, live_env'in taze modülünden çözülür)
- PNG asset sözleşmesi: varsayılan ellipsis ASCII '...' (emoji yok, CLAUDE.md)

Kabul kriteri (plan): 'text surface parent box'ı aşmıyor veya
ellipsis/wrap kanıtlanıyor' — bu dosya ölçüm düzeyinde kanıtlar;
tüketici ekranı A0 capture'ı manuel adımdır (gerçek ekran, uydurma değil).

Kalıp: FAZ A4 hermetik live_env (v2 tests/test_settings_preset_transition.py)
— modül-seviyesi gerçek pygame importu (koleksiyon anı, WinError 206
koruması), bare+src ÇİFT anahtar purge, pygame kaydı, kimlik assert'leri.
Yeni purge anahtarı: ui_text_layout (retro_style'ı lazy çözdüğü için
retro_style purge'ünde birlikte düşmelidir).
"""
import os
import sys

import pygame
import pytest


def _ensure_src_on_path() -> None:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    src_path = os.path.join(repo_root, 'src')
    # abspath zorunlu: 'tests\\..\\src' yazımı modül __file__ değerine sızar ve
    # conftest'in _looks_like_test_stub denetimi GERÇEK modülü stub sanıp
    # söker. Girdiyi ayrıca koşulsuz ÖNE al (öndeki kirli yazımı ezer).
    if src_path in sys.path:
        sys.path.remove(src_path)
    sys.path.insert(0, src_path)


@pytest.fixture(scope="module", autouse=True)
def live_env():
    """Gerçek modülleri hermetik yükle; pygame'i dummy sürücüyle hazırla.

    Koleksiyon anındaki sys.modules kirliliği önceki dosyaların stub
    pygame'ine bağlı kopyalar yakalayabiliyor (FAZ A4 dersleri). İlgili
    anahtarların bare VE 'src.' varyantları temizlenip taze import edilir.
    """
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    _ensure_src_on_path()

    _module_keys = [
        'ui_text_layout', 'text_cache', 'retro_style', 'localization',
        'constants', 'background', 'ui_scaling', 'ui_theme',
    ]
    _module_lookup_keys = [
        key
        for mod in _module_keys
        for key in (mod, f'src.{mod}')
    ]
    _pygame_leaked = sys.modules.get('pygame')
    if _pygame_leaked is not pygame:
        sys.modules['pygame'] = pygame

    _original_modules = {key: sys.modules.get(key) for key in _module_lookup_keys}
    for key in _module_lookup_keys:
        sys.modules.pop(key, None)

    if not hasattr(pygame, 'K_h'):
        pytest.skip('pygame stub environment')

    pygame.init()
    if not pygame.display.get_init():
        pygame.display.init()
    if not pygame.font.get_init():
        pygame.font.init()

    import ui_text_layout as utl
    import text_cache as tc
    import retro_style as rs_mod
    import localization as loc
    import ui_scaling

    # Hermetiklik sözleşmesi: ui_text_layout module-seviyesinde text_cache'i
    # bağlar; retro_style'ı yalnız ÇAĞRI ANINDA çözer — kayıtların bu
    # fixture'ın taze import ettiği kopyalara işaret etmesi gerekir.
    assert sys.modules['ui_text_layout'] is utl
    assert sys.modules['text_cache'] is tc
    assert sys.modules['retro_style'] is rs_mod

    class _Env:
        def __init__(self):
            self.pygame = pygame
            self.utl = utl
            self.tc = tc
            self.rs = rs_mod.retro_style
            self.loc = loc
            self.ui_scaling = ui_scaling

    yield _Env()

    # Sonraki test dosyalarına temiz durum bırak.
    for _key, _original in _original_modules.items():
        if _original is not None:
            sys.modules[_key] = _original
        else:
            sys.modules.pop(_key, None)
    if _pygame_leaked is not None and _pygame_leaked is not pygame:
        sys.modules['pygame'] = _pygame_leaked
    elif _pygame_leaked is None:
        sys.modules.pop('pygame', None)


def _fixture_text(live_env, key, lang, **fmt):
    """TRANSLATIONS fixture'ı — live_env'in taze modülünden (son giren kazanır)."""
    raw = live_env.loc.TRANSLATIONS[key][lang]
    return raw.format(**fmt) if fmt else raw


class _MetricFont:
    """Deterministik sahte font: genişlik = len(text) * char_width.

    retro_style.wrap_text de font.size(...) kullanır — iki taraf aynı sayıyı
    görür, parite testleri deterministik kalır (süpürme: _MetricFont kalıbı,
    tests/test_demo_upgrade_prompt_layout.py ailesi).
    """

    def __init__(self, char_width=8, height=16):
        self.char_width = max(1, int(char_width))
        self.height = max(1, int(height))

    def size(self, text):
        return (max(0, len(text)) * self.char_width, self.height)

    def get_height(self):
        return self.height


class _ScaledMetricFont:
    """Boyuta oranlı sahte font: küçülen font dar metin üretir (fit döngüsü için)."""

    def __init__(self, size, height_factor=1.0):
        self._size = max(1, int(size))
        self.height = max(1, int(size * height_factor))

    def size(self, text):
        return (max(0, len(text)) * max(1, self._size // 2), self.height)

    def get_height(self):
        return self.height


class _CountingFont(_MetricFont):
    """Ölçüm cache kanıtı: size() çağrı sayacını tutar."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.size_calls = 0

    def size(self, text):
        self.size_calls += 1
        return super().size(text)


_LONG_TEXT = (
    'Quadrix panellerinde uzun lokalizasyon metinleri sabit bütçeleri '
    'aşabildiği için sarma ve kontrollü kısaltma aynı sözleşme altında '
    'birleşmelidir'
)
# Önek-korunumu testi için: tüm kelimeler <= 10 karakter (sarma kelime
# sınırlarından geçer, birleştirme orijinali birebir geri kurar).
_SHORT_WORDS_TEXT = 'bu metindeki tum kelimeler kisa ve sarmada bolunmeden kalabilir'


# ---------------------------------------------------------------------------
# 1) Ölçüm: font.size eşdeğerliği + LRU cache sözleşmesi
# ---------------------------------------------------------------------------

def test_measure_text_matches_font_size(live_env):
    font = _MetricFont(char_width=7, height=15)
    for text in ('Merhaba', 'merhaba dünya', '', 'CJK 漢字 metni'):
        assert live_env.tc.measure_text(font, text) == font.size(text)
        assert live_env.tc.measure_text_width(font, text) == font.size(text)[0]


def test_measure_text_is_cached(live_env):
    font = _CountingFont(char_width=6)
    assert live_env.tc.measure_text(font, 'birinci metin') == (78, 16)
    assert live_env.tc.measure_text(font, 'birinci metin') == (78, 16)
    assert font.size_calls == 1  # ikinci okuma LRU'dan

    live_env.tc.measure_text(font, 'ikinci metin')
    assert font.size_calls == 2

    live_env.tc.clear_text_cache()
    live_env.tc.measure_text(font, 'birinci metin')
    assert font.size_calls == 3  # temizlik sonrası yeniden ölçer


# ---------------------------------------------------------------------------
# 2) wrap_text: retro_style paritesi (testle kilitli tek uygulama yolu)
# ---------------------------------------------------------------------------

_PARITY_TEXTS = [
    'Kısa bir satır',
    'Bu cümle birkaç kelime içerir ve sarma davranışını sınar',
    'Elle bölünmüş\n\nikinci paragraf',
    'Boşluksuz CJK metni中日友好合作関係の継続',
    'superkalifragilistikexpialidocious uzun tek kelime',
    '',
    '   baş ve sondaki boşluklar   ',
]


@pytest.mark.parametrize('char_width', [4, 8])
@pytest.mark.parametrize('max_width', [60, 120, 240, 480])
@pytest.mark.parametrize('text', _PARITY_TEXTS)
def test_wrap_text_parity_with_retro_style(live_env, text, max_width, char_width):
    font = _MetricFont(char_width=char_width)
    mine = live_env.utl.wrap_text(text, font, max_width)
    theirs = live_env.rs.wrap_text(text, font, max_width)
    assert mine == theirs


def test_wrap_text_returns_fresh_list_not_shared_cache_object(live_env):
    font = _MetricFont(char_width=6)
    a = live_env.utl.wrap_text('paylasilan cache satirlari', font, 60)
    a.append('mutasyon')
    b = live_env.utl.wrap_text('paylasilan cache satirlari', font, 60)
    assert 'mutasyon' not in b  # cache hit yine de taze list döndürür


def test_wrap_text_cache_skips_measurement_on_hit(live_env):
    font = _CountingFont(char_width=6)
    live_env.utl.wrap_text('ikinci kez sarilacak metin kontrolu', font, 60)
    calls_after_first = font.size_calls
    assert calls_after_first > 0
    live_env.utl.wrap_text('ikinci kez sarilacak metin kontrolu', font, 60)
    assert font.size_calls == calls_after_first  # hit: sıfır ek ölçüm


def test_wrap_preserves_manual_newlines(live_env):
    font = _MetricFont(char_width=8)
    lines = live_env.utl.wrap_text('satir1\n\nsatir3', font, 200)
    assert lines == ['satir1', '', 'satir3']


# ---------------------------------------------------------------------------
# 3) wrap_text_limited: max_lines + kontrollü ellipsis (taşma sırası)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('max_lines', [1, 2, 3])
def test_wrap_limited_respects_max_lines_and_width(live_env, max_lines):
    font = _MetricFont(char_width=6)
    wrapped = live_env.utl.wrap_text_limited(
        _SHORT_WORDS_TEXT, font, 60, max_lines=max_lines,
    )
    assert len(wrapped.lines) == max_lines
    assert wrapped.truncated is True
    for line in wrapped.lines:
        assert font.size(line)[0] <= 60
    assert wrapped.lines[-1].endswith('...')
    # Kelime sırası korunur: kesilen içerik kaybolmaz, orijinalin öneki kalır
    # (kelime sınırlarından sarılan metni birleştirmek orijinali geri kurar).
    joined = ' '.join(wrapped.lines)
    stripped = joined[:-3] if joined.endswith('...') else joined
    assert _SHORT_WORDS_TEXT.startswith(stripped.rstrip())


def test_wrap_limited_no_limit_equals_plain_wrap(live_env):
    font = _MetricFont(char_width=6)
    wrapped = live_env.utl.wrap_text_limited(_LONG_TEXT, font, 90)
    assert list(wrapped.lines) == live_env.utl.wrap_text(_LONG_TEXT, font, 90)
    assert wrapped.truncated is False


def test_wrap_limited_short_text_not_truncated(live_env):
    font = _MetricFont(char_width=6)
    wrapped = live_env.utl.wrap_text_limited('kisa metin', font, 240, max_lines=3)
    assert list(wrapped.lines) == ['kisa metin']
    assert wrapped.truncated is False


def test_wrap_limited_unbreakable_token_guarded(live_env):
    font = _MetricFont(char_width=8)
    # Boşluksuz CJK: _break_long_token böler; eldeki tek-karakter aşımı
    # (dejenere dar bütçe) son çare ellipsis güvencesine düşer.
    wrapped = live_env.utl.wrap_text_limited('中日友好合作関係継続' * 4, font, 40)
    assert len(wrapped.lines) >= 1
    for line in wrapped.lines:
        if line:
            assert font.size(line)[0] <= 40 or line.endswith('...')


# ---------------------------------------------------------------------------
# 4) ellipsize_text: kontrollü kısaltma
# ---------------------------------------------------------------------------

def test_ellipsize_fits_width_and_marks(live_env):
    font = _MetricFont(char_width=6)
    result = live_env.utl.ellipsize_text('Merhaba dünya', font, 30)
    assert result.endswith('...')
    assert font.size(result)[0] <= 30
    assert 'Merhaba dünya'.startswith(result[:-3])


def test_ellipsize_short_text_unchanged(live_env):
    font = _MetricFont(char_width=4)
    assert live_env.utl.ellipsize_text('kisa', font, 200) == 'kisa'


def test_ellipsize_degenerate_budget(live_env):
    font = _MetricFont(char_width=6)
    # max_width <= 0: dejenere bütçe, metin dokunulmaz.
    assert live_env.utl.ellipsize_text('metin', font, 0) == 'metin'
    # Ellipsis'in kendisi bile sığmıyorsa yalnız ellipsis döner.
    assert live_env.utl.ellipsize_text('uzun bir metin burada', font, 10) == '...'


def test_ellipsize_ascii_ellipsis_default(live_env):
    # PNG asset sözleşmesi: emoji yok; varsayılan ASCII '...'.
    assert all(ord(ch) < 128 for ch in live_env.utl.DEFAULT_ELLIPSIS)
    assert live_env.utl.DEFAULT_ELLIPSIS == '...'


# ---------------------------------------------------------------------------
# 5) fit_font_to_width: get_fitting_font paritesi + enjeksiyonlu fabrika
# ---------------------------------------------------------------------------

def test_fit_font_to_width_parity_with_retro_style(live_env):
    """Aynı font fabrikası altında iki algoritma aynı boyutta durur.

    retro_style.get_fitting_font kendi get_font zincirini kullanır; pariteyi
    ölçmek için get_font geçici olarak aynı sahte fabrikaya bağlanır
    (davranış karakterizasyonu — sonraki fazlarda retro_style'ın bu modüle
    vekillik etmesi bu kilit sayesinde güvenli olur).
    """
    utl, rs = live_env.utl, live_env.rs
    text = 'Ayarlar panelinde tek satirlik baslik metni'
    factory = lambda size, bold=True: _ScaledMetricFont(size)
    original_get_font = rs.get_font
    try:
        rs.get_font = lambda size, bold=True: _ScaledMetricFont(size)
        reference_font = rs.get_fitting_font(text, 20, 120)
    finally:
        rs.get_font = original_get_font

    fitted = utl.fit_font_to_width(text, factory, base_size=20, max_width=120)
    assert fitted.final_size == reference_font._size
    assert fitted.font.size(text)[0] == fitted.text_width
    # Sözleşme: ya sığar ya tabana inildiği BİLDİRİLİR; büyümez.
    assert fitted.text_width <= 120 or fitted.min_size_hit is True
    assert fitted.final_size <= 20
    assert fitted.final_size >= utl.MIN_FONT_SIZE


def test_fit_font_to_width_min_size_not_silent(live_env):
    font_factory = lambda size, bold=True: _ScaledMetricFont(size)
    # min_size=6 < mutlak taban 8: eff_min = max(8, 6) = 8 (retro paritesi).
    fitted = live_env.utl.fit_font_to_width(
        'cok uzun bir metin ki kuculse bile sigmayacak olan',
        font_factory, base_size=20, max_width=40, min_size=6,
    )
    assert fitted.final_size == 8  # mutlak taban
    assert fitted.min_size_hit is True  # taşma BİLDİRİLİR, gizlenmez


def test_fit_font_to_width_zero_width_returns_base(live_env):
    factory = lambda size, bold=True: _ScaledMetricFont(size)
    fitted = live_env.utl.fit_font_to_width('metin', factory, base_size=18, max_width=0)
    assert fitted.final_size == 18
    assert fitted.min_size_hit is False


# ---------------------------------------------------------------------------
# 6) fit_text_to_box: kutu containment (text budget sözleşmesi)
# ---------------------------------------------------------------------------

_BOX_GRID = [(240, 80), (400, 120), (120, 60), (600, 200)]

_BOX_TEXT_CASES = [
    ('long', 'Quadrix panellerinde uzun lokalizasyon metinleri'),
    ('short', 'Kısa başlık'),
    ('game_over_ru', ('coop_game_over_reason_p2_frozen', 'ru')),
    ('confirm_de', ('quit_confirm_message', 'de')),
]


@pytest.mark.parametrize('box', _BOX_GRID)
@pytest.mark.parametrize('case_id,case', _BOX_TEXT_CASES)
def test_fit_text_to_box_containment(live_env, case_id, case, box):
    if isinstance(case, tuple):
        key, lang = case
        text = _fixture_text(live_env, key, lang)
    else:
        text = case
    box_w, box_h = box
    layout = live_env.utl.fit_text_to_box(
        text,
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=box_w, box_height=box_h,
        base_size=18, min_size=8,
    )
    # Her satır genişliğe sığar (guard ellipsis dahil).
    for line in layout.lines:
        if line:
            assert layout.font.size(line)[0] <= box_w
    assert layout.max_line_width <= box_w
    # Yükseklik: ya sığar ya da tabana inildiği BİLDİRİLİR.
    if layout.total_height > box_h:
        assert layout.min_size_hit is True
    else:
        assert layout.min_size_hit is False
    # Font sınırsız büyümez, mutlak tabanın altına inmez.
    assert layout.final_size <= 18
    assert layout.final_size >= live_env.utl.MIN_FONT_SIZE
    # Toplam yükseklik formülü (retro_style.fit_wrapped_font paritesi).
    n = len(layout.lines)
    assert layout.total_height == n * layout.line_height + max(0, n - 1) * layout.line_spacing


def test_fit_text_to_box_min_size_overflow_reported(live_env):
    layout = live_env.utl.fit_text_to_box(
        _LONG_TEXT,
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=40, box_height=20,
        base_size=18, min_size=8,
    )
    assert layout.final_size == 8
    assert layout.total_height > 20
    assert layout.min_size_hit is True  # sessiz taşma yok


def test_fit_text_to_box_max_lines_budget(live_env):
    layout = live_env.utl.fit_text_to_box(
        _LONG_TEXT,
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=300, box_height=200,
        base_size=18, min_size=8, max_lines=2,
    )
    assert len(layout.lines) == 2
    assert layout.truncated is True
    assert layout.lines[-1].endswith('...')


def test_fit_text_to_box_never_grows_above_base(live_env):
    layout = live_env.utl.fit_text_to_box(
        'kisa',
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=600, box_height=400,
        base_size=14, min_size=8,
    )
    assert layout.final_size == 14
    assert layout.lines == ('kisa',)


# ---------------------------------------------------------------------------
# 7) clamp_rect_in_parent: panel containment primitifi (menu.py modeli)
# ---------------------------------------------------------------------------

def test_clamp_rect_in_parent_pulls_right_and_bottom(live_env):
    pygame = live_env.pygame
    parent = pygame.Rect(100, 100, 200, 150)
    child = pygame.Rect(250, 200, 100, 80)  # sağ 350 > 300, alt 280 > 250
    out = live_env.utl.clamp_rect_in_parent(child, parent, padding=10)
    # Taşıma semantiği (menu.py:3955-3958 paritesi): boyut korunur, rect geri çekilir.
    assert out.right == 290 and out.width == 100
    assert out.bottom == 240 and out.height == 80
    assert child.right == 350  # orijinal MUTATE EDİLMEZ (kopya döner)


def test_clamp_rect_in_parent_inside_unchanged(live_env):
    pygame = live_env.pygame
    parent = pygame.Rect(0, 0, 500, 400)
    inside = pygame.Rect(120, 120, 50, 50)
    out = live_env.utl.clamp_rect_in_parent(inside, parent)
    assert out == inside
    assert out is not inside  # her zaman kopya


# ---------------------------------------------------------------------------
# 8) Kuşak + invalidasyon: ui_scaling preset zinciri sözleşmesi
# ---------------------------------------------------------------------------

def test_clear_layout_caches_bumps_generation(live_env):
    utl = live_env.utl
    font = _MetricFont(char_width=6)
    utl.wrap_text('kusak testi sarma', font, 60)
    utl.ellipsize_text('kusak testi kisaltma', font, 40)
    assert len(utl._WRAP_CACHE._data) >= 1
    assert len(utl._ELLIPSIZE_CACHE._data) >= 1

    gen0 = utl.layout_generation()
    utl.clear_layout_caches()
    assert utl.layout_generation() == gen0 + 1
    assert len(utl._WRAP_CACHE._data) == 0
    assert len(utl._ELLIPSIZE_CACHE._data) == 0
    assert len(utl._LIMITED_WRAP_CACHE._data) == 0


def test_ui_scaling_preset_invalidates_layout_caches(live_env):
    utl = live_env.utl
    tc = live_env.tc
    font = _MetricFont(char_width=6)
    utl.wrap_text('preset gecisi oncesi isinma', font, 60)
    utl.ellipsize_text('preset gecisi oncesi kisaltma', font, 40)
    tc.measure_text(font, 'preset gecisi oncesi olcum')
    assert len(utl._WRAP_CACHE._data) >= 1
    assert len(tc._MEASURE_CACHE._data) >= 1

    gen0 = utl.layout_generation()
    try:
        live_env.ui_scaling.set_ui_scale_preset('large')
        assert len(utl._WRAP_CACHE._data) == 0
        assert len(utl._ELLIPSIZE_CACHE._data) == 0
        assert len(tc._MEASURE_CACHE._data) == 0
        assert utl.layout_generation() == gen0 + 1
    finally:
        live_env.ui_scaling.set_ui_scale_preset('normal')


# ---------------------------------------------------------------------------
# 9) Gerçek font: ölçüm/render tutarlılığı + ru görünür piksel
# ---------------------------------------------------------------------------

def test_real_font_measure_render_consistency(live_env):
    pygame = live_env.pygame
    if pygame.font.match_font('arial') is None:
        pytest.skip('sistem fontu yok — gerçek font tutarlılık kontrolü atlandı')
    font = pygame.font.SysFont('arial', 18)
    for line in ('Merhaba Quadrix', 'Sigmali panel metni', 'Normale Wörter'):
        width, height = live_env.tc.measure_text(font, line)
        surf = font.render(line, True, (255, 255, 255))
        assert surf.get_width() == width
        assert surf.get_height() == height


def test_ru_cyrillic_visible_pixels(live_env):
    """ru fixture'ı default font zincirinde GÖRÜNÜR piksel üretmelidir.

    Süpürme bulgusu (kullanıcıya raporlandı, A5 kapsamı dışında): ui_language
    _profile.py:38-41 Kiril gliflerinin KyrillaSansSerif-Black.ttf'de boş/
    şeffaf piksel ürettiğini belgelerken retro_style._script_font_paths
    ('cyrillic') hâlâ aynı dosyaya yönlendiriyor — iki modül çelişiyor.
    Varsayılan (profil-sıfır) font zinciri sistem fontuna düştüğünden bu test
    o yolu doğrular; çoklu-script yönlendirmesi ayrı iştir.
    """
    pygame = live_env.pygame
    if pygame.font.match_font('arial') is None:
        pytest.skip('sistem fontu yok — Kiril görünür piksel kontrolü atlandı')
    font = pygame.font.SysFont('arial', 20)
    text = _fixture_text(live_env, 'quit_confirm_message', 'ru')[:40]
    surf = font.render(text, True, (255, 255, 255))
    mask = pygame.mask.from_surface(surf)
    assert mask.count() > 0  # sıfır olmayan alfa değil, görünür piksel


# ---------------------------------------------------------------------------
# 10) Lokalizasyon stres fixture'ları (tr/en/ru uzun + aksanlı)
# ---------------------------------------------------------------------------

_L10N_STRESS_CASES = [
    ('guide_tip_5', 'tr'),        # aksan yoğunluğu: İ, ü, ş, ğ, ı
    ('guide_tip_5', 'en'),
    ('guide_cards_intro', 'de'),  # tek satırda en uzun (293)
    ('guide_cards_intro', 'ru'),
    ('coop_game_over_reason_p2_frozen', 'ru'),
    ('quit_confirm_message', 'fr'),
    ('tutorial_card_synergy_feedback_line_bonus', 'tr'),
]


@pytest.mark.parametrize('key,lang', _L10N_STRESS_CASES)
def test_localization_stress_fit_containment(live_env, key, lang):
    text = _fixture_text(live_env, key, lang)
    assert len(text) > 20  # gerçekten stres metni
    layout = live_env.utl.fit_text_to_box(
        text,
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=320, box_height=96,
        base_size=16, min_size=8,
    )
    assert layout.max_line_width <= 320
    if layout.total_height > 96:
        assert layout.min_size_hit is True
    # El işi '\n' korunumu: sarma paragraf yapısını bozmaz.
    if '\n\n' in text:
        assert len(layout.lines) >= 2


def test_campaign_progress_placeholder_formatted(live_env):
    # Placeholder'lar .format() SONRASI ölçülmeli (süpürme bulgusu).
    text = _fixture_text(
        live_env, 'campaign_progress', 'tr',
        current=12, total=40, level_label='BÖLÜM', stars=3, stars_label='YILDIZ',
    )
    assert '{' not in text
    layout = live_env.utl.fit_text_to_box(
        text,
        lambda size, bold=True: _ScaledMetricFont(size),
        box_width=280, box_height=60,
        base_size=16, min_size=8,
    )
    assert layout.max_line_width <= 280
    if layout.total_height > 60:
        assert layout.min_size_hit is True


# NOT: v2'deki test_v2_store_feedback_popup_stress burada BİLİNÇLİ yok —
# 'store_feedback_popup_desc' anahtarı yalnız v2'de var (demo'da store
# kısıtlı; çift depo ayrımı, CLAUDE.md madde 5).
