# Quadrix surum bilgisi
# Repo tarafinda takip edilen temel surum version_base.py icindedir.
# Platforma ozel lokal build numaralari varsa buradan override edilir.

from __future__ import annotations

import importlib
import sys

from version_base import BUILD_NUMBER as BASE_BUILD_NUMBER
from version_base import VERSION as BASE_VERSION


_PLATFORM_OVERRIDE_MODULES = {
	'win32': 'version_local_windows',
	'darwin': 'version_local_macos',
}


def _load_platform_override() -> tuple[str, int, str]:
	module_name = _PLATFORM_OVERRIDE_MODULES.get(sys.platform)
	if not module_name:
		return BASE_VERSION, BASE_BUILD_NUMBER, 'version_base'

	try:
		module = importlib.import_module(module_name)
	except ImportError:
		return BASE_VERSION, BASE_BUILD_NUMBER, 'version_base'

	version = str(getattr(module, 'VERSION', BASE_VERSION))
	try:
		build_number = int(getattr(module, 'BUILD_NUMBER', BASE_BUILD_NUMBER))
	except (TypeError, ValueError):
		build_number = BASE_BUILD_NUMBER
	return version, build_number, module_name


VERSION, BUILD_NUMBER, VERSION_SOURCE = _load_platform_override()