from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

# Testler bazen top-level import (backend/tools) bazen src import kullanıyor.
# Her iki kökü de garanti ederek import kırılmalarını azalt.
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
	sys.path.insert(0, str(SRC_ROOT))

# localization orijinal fonksiyonlarını yedekle
try:
	import localization
	_orig_loc_t = getattr(localization, "t", None)
	_orig_loc_set_language = getattr(localization, "set_language", None)
	_orig_loc_get_language = getattr(localization, "get_language", None)
except Exception:
	_orig_loc_t = None
	_orig_loc_set_language = None
	_orig_loc_get_language = None

def _sync_sys_modules_aliases():
	"""src.* ve normal modül anahtarlarını sys.modules üzerinde eşitler."""
	for key in list(sys.modules.keys()):
		if key.startswith("src."):
			alias = key[4:]
			if sys.modules[key] is not None:
				if alias not in sys.modules or sys.modules[alias] is not sys.modules[key]:
					sys.modules[alias] = sys.modules[key]
		elif key in _MODULES_THAT_GET_STUBBED:
			alias = f"src.{key}"
			if sys.modules[key] is not None:
				if alias not in sys.modules or sys.modules[alias] is not sys.modules[key]:
					sys.modules[alias] = sys.modules[key]


_MODULES_THAT_GET_STUBBED = {
	"pygame",
	"constants",
	"platform_utils",
	"retro_style",
	"ui_theme",
	"background_effects",
	"background",
	"renderers",
	"renderers.jelly_renderer",
	"block_styles",
	"mode_skins",
	"ui_components",
	"themes",
	"sound",
	"gamepad_manager",
	"promptfont_support",
	"sweep_effects",
	"achievements",
	"user_manager",
	"score_manager",
	"settings_manager",
	"asset_manager",
	"tutorial_progress",
	"atomic_io",
	"data_paths",
	"campaign",
	"campaign.level_data",
	"steam_net_bridge",
	"game",
	"menu",
	"game_modes",
	"game_modes_extra",
	"game_modes_advanced",
	"tutorial",
	"localization",
	"online_pvp_game",
	"steam_integration",
}


_PYGAME_RUNTIME_STUB_TESTS = {
	"test_campaign_debug_unlock_all.py",
	"test_online_pvp_message_validation.py",
	"test_platform_effective_ui_size.py",
	"test_platform_utils_display_toggle.py",
	"test_steam_overlay_single_context.py",
	"test_settings_env_default_language_ru.py",
}


def _looks_like_test_stub(mod) -> bool:
	if not isinstance(mod, types.ModuleType):
		return True

	try:
		file_path = getattr(mod, "__file__", None)
	except Exception:
		# PEP 562 tembel modül __getattr__'ı (örn. pygame.surfarray'ın numpy
		# yükleyicisi) __file__ erişiminde bile istisna fırlatabilir; getattr
		# varsayılanı yalnız AttributeError'u yutar. Erişimi istisna veren
		# modül gerçek pygame parçasıdır: stub sayılmaz, purge döngüsü
		# kesilmeden devam eder (teardown ERROR bu yüzden kuyrudaki
		# _reset_ui_scale_preset'i atlatıyordu).
		return False
	if not file_path:
		# ModuleType()/SimpleNamespace ile enjekte edilen stub'lar genelde __file__ taşımaz.
		return True

	if not isinstance(file_path, (str, bytes)):
		return True

	normalized = str(file_path).replace("\\", "/")
	return "/tests/" in normalized


def _purge_foreign_callable_module(module_names: tuple[str, ...], attr_names: tuple[str, ...]) -> bool:
	allowed_owners = set(module_names)
	for candidate in module_names:
		module_obj = sys.modules.get(candidate)
		if module_obj is None:
			continue
		for attr_name in attr_names:
			try:
				value = getattr(module_obj, attr_name, None)
				owner = getattr(value, "__module__", "")
			except Exception:
				# _looks_like_test_stub guard'ıyla aynı gerekçe: tembel
				# __getattr__'ı istisna fırlatan modülde getattr'ın None
				# varsayılanı yalnız AttributeError'u yutar; bu öznitelik
				# atlanır, purge kesilmeden devam eder.
				continue
			if callable(value) and owner not in allowed_owners:
				for module_name in module_names:
					sys.modules.pop(module_name, None)
				return True
	return False


def _purge_leaked_test_stubs(*, skip_pygame: bool = False) -> None:
	background_effects_purged = False
	jelly_renderer_purged = False
	for base_name in _MODULES_THAT_GET_STUBBED:
		if skip_pygame and base_name == "pygame":
			continue
		for candidate in (base_name, f"src.{base_name}"):
			module_obj = sys.modules.get(candidate)
			if module_obj is None:
				continue
			if _looks_like_test_stub(module_obj):
				sys.modules.pop(candidate, None)
				if base_name == "background_effects":
					background_effects_purged = True
				elif base_name == "renderers.jelly_renderer":
					jelly_renderer_purged = True

	# FAZ A8: gerçek dosyalı modüllerin module-seviyesi pygame binding'i stub'a
	# kilitliyse modülün kendisi de zehirlenir. Mayın senaryosu: collectstart
	# purgesi pygame ailesini düşürür → stub kuran test dosyası (örn.
	# test_platform_utils_display_toggle koleksiyonu) stub'ı sys.modules'a
	# yerleştirir → platform_utils'u silip stub'la yeniden import eder →
	# gerçek __file__'lı olduğu için yukarıdaki koşullu purge onu atlar →
	# oturumun kalanına MOUSEBUTTONDOWN / event.Event gibi nitelikleri
	# olmayan stub pygame servis edilir (letterbox event testleri ham geçiyordu).
	# Binding stub'luysa modül düşürülür; sonraki tüketici güncel pygame'le
	# taze yükler. Stub-runtime gerektiren dosyaların kendi module-level
	# isim bağlamaları düşürmeden etkilenmez (yalnız taze import tazelenir).
	for base_name in _MODULES_THAT_GET_STUBBED:
		if base_name == "pygame":
			continue
		for candidate in (base_name, f"src.{base_name}"):
			module_obj = sys.modules.get(candidate)
			if module_obj is None:
				continue
			try:
				bound_pygame = getattr(module_obj, "pygame", None)
			except Exception:
				# Yukarıdaki guard ile aynı desen: tembel __getattr__ istisna
				# fırlatırsa (getattr None varsayılanı yalnız AttributeError
				# yutar) modül gerçek sayılır — bu aday atlanır, döngü
				# kesilmeden devam eder (purge dayanıklılık vaadi ikinci
				# döngü için de tamamlanmış olur).
				continue
			if (
				isinstance(bound_pygame, types.ModuleType)
				and _looks_like_test_stub(bound_pygame)
			):
				sys.modules.pop(candidate, None)

	# Bazi test modulleri gercek background_effects modulu icindeki shared-layer
	# getter'ini module-level lambda ile degistiriyor. Bu, sonraki testlerde gercek
	# layer fabrikasi yerine test override'inin sizmasina yol aciyor.
	if _purge_foreign_callable_module(
		("background_effects", "src.background_effects"),
		("get_shared_falling_blocks_layer", "sync_shared_falling_blocks_appearance"),
	):
		background_effects_purged = True

	if _purge_foreign_callable_module(
		("renderers.jelly_renderer", "src.renderers.jelly_renderer"),
		("draw_jelly_block", "draw_jelly_border"),
	):
		jelly_renderer_purged = True

	if background_effects_purged:
		for dependent in ("store_screen", "src.store_screen"):
			sys.modules.pop(dependent, None)

	if jelly_renderer_purged:
		for dependent in (
			"background_effects",
			"src.background_effects",
			"store_screen",
			"src.store_screen",
			"menu",
			"src.menu",
			"game",
			"src.game",
			"pvp_game",
			"src.pvp_game",
			"coop_game",
			"src.coop_game",
			"online_pvp_game",
			"src.online_pvp_game",
			"piece_workshop",
			"src.piece_workshop",
			"user_screens",
			"src.user_screens",
		):
			sys.modules.pop(dependent, None)

	if skip_pygame:
		return

	# Koleksiyon sınırlarında pygame ailesini tamamen sıfırla.
	# Bazı test dosyaları module-level stub bıraktığı için sonraki dosyada
	# gerçek pygame importu "partially initialized" hatasına düşebiliyor;
	# import ortasında hata alan pygame yarım modül olarak sys.modules'te
	# kalır (gerçek __file__'lı olduğu için koşullu purge onu atamaz) ve
	# sonraki TÜM dosyaları kırar. Koşulsuz atama bu yarım-modül
	# kirliliğini keser. Yeniden import maliyeti (pygame.__init__ içindeki
	# korunmamış os.add_dll_directory çağrısı) sessionstart'taki güvenli
	# sarmalayıcıyla yutulur.
	for name in list(sys.modules.keys()):
		if name == "pygame" or name.startswith("pygame."):
			sys.modules.pop(name, None)

	# pygame düştü: module-level ``import pygame`` yapmış ağır oyun modülleri
	# eski pygame objesine bağlı kalır. Bazı test dosyaları (test_coop vb.)
	# module-level stub kurup CoopGame/PvPGame import zincirini stub
	# ortamında İLK kez yükletiyor; pvp_game/coop_game gerçek dosyalı
	# olduğundan _looks_like_test_stub bunları atamaz ve kirlenmiş
	# binding'leri (_RS retro_style, _Surf Surface) bir sonraki dosyaya
	# sys.modules üzerinden servis edilir (p0 draw testleri bu yolla düşüyordu).
	# pygame'in atıldığı her koleksiyon sınırında bunlar da düşürülür; sadece
	# import eden sonraki dosya gerçek pygame ile taze yükler.
	for heavy_name in (
		'board', 'pieces', 'coop_board',
		# game.py de module-level ``import pygame`` + EffectSurfaceCache
		# tüketicisidir (bayat-binding sınıfı — v2 conftest'te purge
		# listesindedir), ancak demo'da BİLİNÇLİ olarak düşürülmez:
		# test_game_solid_alpha_* string-form monkeypatch('game.xxx')
		# deseni modülün koşum fazında sys.modules'ta kalmasına güvenir;
		# purge gelirse taze import farklı bir game nesnesi verir ve yama
		# görünmez olur (ölçüldü: 2 test düşüyor, 2026-10-08).
		'pvp_game', 'src.pvp_game',
		'coop_game', 'src.coop_game',
		'online_pvp_game', 'src.online_pvp_game',
		'online_coop_game', 'src.online_coop_game',
		'game_over_surfaces', 'src.game_over_surfaces',
		# OP-036 LRU yardımcısı da pygame.Surface çağırır: pygame ailesiyle
		# birlikte düşmezse koleksiyon sınırında eski pygame örneğine bağlı
		# kalır — sonraki dosyanın taze pygame'iyle binding uyuşmazlığı
		# ghost Surface-sayma testlerinin çok-dosya düşüşüne yol açıyordu.
		'effect_surface_cache', 'src.effect_surface_cache',
	):
		sys.modules.pop(heavy_name, None)


def _purge_leaked_pygame_stubs() -> None:
	root_module = sys.modules.get("pygame")
	purge_root = root_module is not None and _looks_like_test_stub(root_module)

	for name in list(sys.modules.keys()):
		if name != "pygame" and not name.startswith("pygame."):
			continue
		module_obj = sys.modules.get(name)
		if purge_root or _looks_like_test_stub(module_obj):
			sys.modules.pop(name, None)


def _test_requires_runtime_pygame_stub(request: pytest.FixtureRequest) -> bool:
	module_file = getattr(request.module, "__file__", None)
	if not module_file:
		return False
	return Path(str(module_file)).name in _PYGAME_RUNTIME_STUB_TESTS


def _reset_ui_scale_preset() -> None:
	"""UI scale preset process-global oldugu icin testler arasi sizmamasini sagla."""
	try:
		ui_scaling = importlib.import_module("ui_scaling")
		reset_preset = getattr(ui_scaling, "set_ui_scale_preset", None)
		if callable(reset_preset):
			reset_preset("normal")
	except Exception:
		pass


def pytest_sessionstart(session):
	# macOS/Linux'ta os.add_dll_directory yok; bazı testler patch() ile bu
	# attribute'u hedefliyor. Attribute'in varlığını garanti ederek
	# platformlar arası patch hatasını önle.
	if not hasattr(os, "add_dll_directory"):
		def _dummy_add_dll_directory(_path: str):
			class _DummyHandle:
				def close(self):
					return None
			return _DummyHandle()

		os.add_dll_directory = _dummy_add_dll_directory  # type: ignore[attr-defined]

	# FAZ A6: pygame.__init__ (pygame-ce 2.5.6, L56) os.add_dll_directory'i
	# korumasız çağırır. conftest her koleksiyon sınırında pygame ailesini
	# sıfırladığı için pygame defalarca yeniden import edilir; DLL dizin
	# kayıtları birikince Windows WinError 206 fırlatır, pygame YARIM yüklenip
	# sys.modules'te kalır ve sonraki tüm dosyalar "partially initialized"
	# hatasıyla düşer. Çağrıyı güvenli sarmalayalım: hata durumunda None
	# dönsün — pygame DLL'leri aynı satırın PATH ekleme yolundan bulur.
	elif not getattr(os.add_dll_directory, "_quadrix_test_safe", False):
		_real_add_dll_directory = os.add_dll_directory

		def _safe_add_dll_directory(_path):
			try:
				return _real_add_dll_directory(_path)
			except OSError:
				return None

		_safe_add_dll_directory._quadrix_test_safe = True
		os.add_dll_directory = _safe_add_dll_directory

	_purge_leaked_test_stubs()
	_reset_ui_scale_preset()


def pytest_collectstart(collector):
	# Her test modülü import/collect başlamadan hemen önce leaked stub modülleri temizle.
	# Böylece bir test dosyasının bıraktığı sys.modules yan etkisi bir sonraki dosyayı bozmaz.
	candidate = getattr(collector, "path", None)
	if not candidate:
		return

	try:
		candidate_path = Path(str(candidate))
	except Exception:
		return

	if candidate_path.suffix == ".py" and candidate_path.name.startswith("test_"):
		_purge_leaked_test_stubs()


def pytest_pycollect_makemodule(module_path, parent):
	# Test modülü collector'ı üretilmeden hemen önce tekrar temizle.
	# Bu hook, modül importu öncesi çalıştığından sızıntıları daha güvenli keser.
	try:
		candidate_path = Path(str(module_path))
	except Exception:
		return None

	if candidate_path.suffix == ".py" and candidate_path.name.startswith("test_"):
		_purge_leaked_test_stubs()
	return None


def _collect_font_cache_dicts() -> list:
	"""FAZ A6 listesindeki modül-level font cache dict'lerini topla."""
	caches = []
	ui_theme_mod = sys.modules.get('ui_theme') or sys.modules.get('src.ui_theme')
	if ui_theme_mod is not None:
		font_cache = getattr(getattr(ui_theme_mod, 'UIFonts', None), '_cache', None)
		if isinstance(font_cache, dict):
			caches.append(font_cache)
	retro_mod = sys.modules.get('retro_style') or sys.modules.get('src.retro_style')
	if retro_mod is not None:
		cjk_cache = getattr(retro_mod, '_cjk_fallback_font_cache', None)
		if isinstance(cjk_cache, dict):
			caches.append(cjk_cache)
		retro_inst = getattr(retro_mod, 'retro_style', None)
		for inst_cache_attr in ('font_cache', '_script_font_cache'):
			inst_cache = getattr(retro_inst, inst_cache_attr, None)
			if isinstance(inst_cache, dict):
				caches.append(inst_cache)
	pf_mod = sys.modules.get('promptfont_support') or sys.modules.get('src.promptfont_support')
	if pf_mod is not None:
		pf_cache = getattr(pf_mod, '_FONT_CACHE', None)
		if isinstance(pf_cache, dict):
			caches.append(pf_cache)
	return caches


def _evict_dead_cached_fonts() -> None:
	"""Font modülü init'liyken cache'teki ÖLÜ Font girdilerini ayıkla.

	pygame.quit() sonrası yeniden pygame.init() yapıldığında get_init() True
	döner; quit'ten önce yaratılmış Font nesneleri kalıcı olarak ölüdür ve
	cache'ten döndükleri her draw yolunu düşürür. Probe (size("")) test
	teardown'unda tek seferlik çalışır — oyun döngüsünde maliyeti yoktur.
	"""
	for cache in _collect_font_cache_dicts():
		for key, font in list(cache.items()):
			size_fn = getattr(font, 'size', None)
			if not callable(size_fn):
				continue
			try:
				size_fn("")
			except Exception:
				cache.pop(key, None)


@pytest.fixture(autouse=True)
def _isolate_test_module_stubs(request: pytest.FixtureRequest):
	_sync_sys_modules_aliases()
	_purge_leaked_test_stubs(skip_pygame=True)
	_reset_ui_scale_preset()
	if not _test_requires_runtime_pygame_stub(request):
		_purge_leaked_pygame_stubs()

	# sys.modules yedeğini temizlikten SONRA al
	sys_modules_backup = dict(sys.modules)
	yield
	
	# sys.modules'u geri yükle
	current_keys = list(sys.modules.keys())
	for key in current_keys:
		if key not in sys_modules_backup:
			sys.modules.pop(key, None)
	for key, value in sys_modules_backup.items():
		sys.modules[key] = value

	# Akıllı localization stub temizliği ve orijinal fonksiyonların geri yüklenmesi
	try:
		for loc_key in ('localization', 'src.localization'):
			if loc_key in sys.modules:
				loc = sys.modules[loc_key]
				if _orig_loc_t is not None:
					loc.t = _orig_loc_t
				if _orig_loc_set_language is not None:
					loc.set_language = _orig_loc_set_language
				if _orig_loc_get_language is not None:
					loc.get_language = _orig_loc_get_language
		# Eğer localization hala yüklüyse dilini varsayılana sıfırla
		if 'localization' in sys.modules:
			sys.modules['localization'].set_language(sys.modules['localization'].DEFAULT_LANGUAGE)
	except Exception:
		pass

	# FAZ A6: bazı testler finally içinde pygame.quit() çağırır — font modülü
	# kapanınca modül-level font cache'lerindeki (UIFonts._cache,
	# retro_style._cjk_fallback_font_cache, retro_style.retro_style.
	# font_cache/_script_font_cache, promptfont_support) Font nesneleri
	# "font module quit since font created" durumuna düşer. Sonraki test
	# pygame.init() yapsa bile cache'ten dönen ölü Font pygame.error fırlatır
	# (p0 draw testleri bu mayınla düşüyordu). Modülü sys.modules'tan düşürmek
	# yetmez: pvp_game/coop_game gibi tüketicilerin module-level import
	# binding'i eski modül objesine bağlı kalır. Bu yüzden modüller yerinde
	# kalır, yalnızca cache dict'leri temizlenir — sonraki font isteği
	# init'li ortamda yeni Font yaratır.
	#
	# FAZ A8: quit'ten SONRA bir test yeniden pygame.init() yaptığında
	# get_init() True döner — koşullu tam temizlik atlanır ve quit'ten önce
	# yaratılmış ölü Font'lar cache'te kalır (karışık cache: bazı girdiler
	# taze, bazıları ölü; level select level_font mayını bu yolla düşüyordu).
	# Font init'liyken her girdi size("") ile probe edilir: ölü girdiler
	# ayıklanır, canlılar korunur. Probe yalnızca test teardown'unda
	# çalışır — oyun döngüsünde maliyeti yoktur.
	try:
		import pygame as _pygame_probe

		if not _pygame_probe.font.get_init():
			for font_cache in _collect_font_cache_dicts():
				font_cache.clear()
			pf_mod = sys.modules.get('promptfont_support') or sys.modules.get('src.promptfont_support')
			if pf_mod is not None:
				pf_clear = getattr(pf_mod, 'clear_promptfont_cache', None)
				if callable(pf_clear):
					pf_clear()
		else:
			_evict_dead_cached_fonts()
	except Exception:
		pass

	# FAZ A6: pvp/coop/online game-over draw'ları ve LRU yardımcıları
	# (game_over_surfaces) stub pygame ile import edilmişse binding'leri
	# süreç boyunca kirlenir; her test sonunda düşürülür, sonraki ihtiyaçta
	# gerçek pygame ile taze yüklenir. DİKKAT: game/menu/
	# settings_screen_tabbed/game_modes_extra v2 conftest'inde düşürülse de
	# demo tabanında HİÇ düşürülmemiştir — demo testleri (ör.
	# test_game_solid_alpha...) monkeypatch('game.xxx') deseniyle modülün
	# testler arasında sys.modules'ta kalmasına güvenir; modül düşünce
	# monkeypatch yeni bir game objesine patch atar, module-level Game
	# binding'i eski objenin global'inden okur ve patch görünmez olur.
	# Liste bu yüzden yalnız FAZ A6 gerekçeli modüllere sınırlıdır
	# (v2-demo doğal farkı).
	for dep in (
		'pvp_game', 'src.pvp_game',
		'coop_game', 'src.coop_game',
		'online_pvp_game', 'src.online_pvp_game',
		'online_coop_game', 'src.online_coop_game',
		'game_over_surfaces', 'src.game_over_surfaces',
		# OP-036 yardımcısı — game_over_surfaces ile aynı kategori
		# (pygame.Surface çağırır; eski/stub pygame'e bağlanmışsa düşürülmeli).
		'effect_surface_cache', 'src.effect_surface_cache',
	):
		sys.modules.pop(dep, None)

	# Windows'ta PATH şişmesini önle (pygame'in tekrar eden importlarda PATH'i şişirmesini engelle)
	try:
		path_env = os.environ.get("PATH", "")
		if path_env:
			parts = path_env.split(";")
			seen = set()
			unique_parts = []
			for p in parts:
				if p and p not in seen:
					seen.add(p)
					unique_parts.append(p)
			os.environ["PATH"] = ";".join(unique_parts)
	except Exception:
		pass

	_sync_sys_modules_aliases()
	_purge_leaked_test_stubs(skip_pygame=True)
	_purge_leaked_pygame_stubs()
	_reset_ui_scale_preset()
