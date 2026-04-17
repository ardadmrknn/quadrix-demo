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


_MODULES_THAT_GET_STUBBED = {
	"pygame",
	"constants",
	"platform_utils",
	"retro_style",
	"ui_theme",
	"background_effects",
	"block_styles",
	"ui_components",
	"themes",
	"sound",
	"gamepad_manager",
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
	"test_settings_env_default_language_ru.py",
}


def _looks_like_test_stub(mod) -> bool:
	if not isinstance(mod, types.ModuleType):
		return True

	file_path = getattr(mod, "__file__", None)
	if not file_path:
		# ModuleType()/SimpleNamespace ile enjekte edilen stub'lar genelde __file__ taşımaz.
		return True

	if not isinstance(file_path, (str, bytes)):
		return True

	normalized = str(file_path).replace("\\", "/")
	return "/tests/" in normalized


def _purge_leaked_test_stubs(*, skip_pygame: bool = False) -> None:
	for base_name in _MODULES_THAT_GET_STUBBED:
		if skip_pygame and base_name == "pygame":
			continue
		for candidate in (base_name, f"src.{base_name}"):
			module_obj = sys.modules.get(candidate)
			if module_obj is None:
				continue
			if _looks_like_test_stub(module_obj):
				sys.modules.pop(candidate, None)

	# Bazi test modulleri gercek background_effects modulu icindeki shared-layer
	# getter'ini module-level lambda ile degistiriyor. Bu, sonraki testlerde gercek
	# layer fabrikasi yerine test override'inin sizmasina yol aciyor.
	for candidate in ("background_effects", "src.background_effects"):
		module_obj = sys.modules.get(candidate)
		if module_obj is None:
			continue
		getter = getattr(module_obj, "get_shared_falling_blocks_layer", None)
		owner = getattr(getter, "__module__", "")
		if callable(getter) and owner not in ("background_effects", "src.background_effects"):
			sys.modules.pop("background_effects", None)
			sys.modules.pop("src.background_effects", None)
			break

	if skip_pygame:
		return

	# Koleksiyon sınırlarında pygame ailesini tamamen sıfırla.
	# Bazı test dosyaları module-level stub bıraktığı için sonraki dosyada
	# gerçek pygame importu "partially initialized" hatasına düşebiliyor.
	for name in list(sys.modules.keys()):
		if name == "pygame" or name.startswith("pygame."):
			sys.modules.pop(name, None)


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


@pytest.fixture(autouse=True)
def _isolate_test_module_stubs(request: pytest.FixtureRequest):
	_purge_leaked_test_stubs(skip_pygame=True)
	_reset_ui_scale_preset()
	if not _test_requires_runtime_pygame_stub(request):
		_purge_leaked_pygame_stubs()
	yield
	_purge_leaked_test_stubs(skip_pygame=True)
	_purge_leaked_pygame_stubs()
	_reset_ui_scale_preset()
