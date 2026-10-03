"""Survival zafer alt başlığındaki dakika hesabını kılan regresyon testi.

Yabancı (bu oturum dışı yazılmış, commit-dışı) Steam-başarım akışı, survival
zafer alt başlığındaki sabit minutes=3 yerine gerçek survival_time
(ms // 60000) gösterimini getirdi (src/game.py, oyun-sonu overlay'i).
GAME_DURATION = 600000 ms = 10 dakika olduğundan sabit '3' yanlış
kullanıcı-görünür metindi. Bu test o düzeltmeyi AST düzeyinde pinler;
davranışsel draw testi ağır stub gerektirdiğinden deponun mevcut
AST-extraction deseni kullanıldı (tests/test_steam_achievements_sync.py
örneği).
"""

import ast
import pathlib

ROOT_DIR = pathlib.Path(__file__).parent.parent
GAME_SOURCE = ROOT_DIR / "src" / "game.py"


def _find_survival_minutes_kw(tree):
    """survival_victory_subtitle t() çağrısının minutes kwarg'ını bul."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "t"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "survival_victory_subtitle"
        ):
            for kw in node.keywords:
                if kw.arg == "minutes":
                    return kw.value
    return None


def _references_survival_time(node):
    """İfade survival_time'a mı atıf yapıyor?

    İki meşru biçim: doğrudan Name (survival_time) veya
    getattr(self, 'survival_time', 0) çağrısı — game.py'deki mevcut
    kazanç dalı ikincisini kullanır.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "survival_time":
            return True
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "getattr"
            and any(
                isinstance(a, ast.Constant) and a.value == "survival_time"
                for a in sub.args
            )
        ):
            return True
    return False


def _divides_survival_time_by_60000(node):
    """İfade, survival_time'ı 60000'e (ms -> dakika) bölüyor mu?

    Hem gerçek bölme (/) hem kat bölme (//) kabul edilir; mevcut kaynak
    int(... // 60000) kullanır.
    """
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.BinOp)
            and isinstance(sub.op, (ast.Div, ast.FloorDiv))
            and isinstance(sub.right, ast.Constant)
            and sub.right.value == 60000
            and _references_survival_time(sub.left)
        ):
            return True
    return False


def test_survival_victory_subtitle_minutes_derives_from_survival_time():
    source = GAME_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)

    minutes = _find_survival_minutes_kw(tree)
    assert minutes is not None, (
        "survival_victory_subtitle çağrısında minutes kwarg bulunamadı"
    )
    assert isinstance(minutes, ast.Name), (
        "minutes parametresi sabit olmamalı — eski 'minutes=3' regresyonu "
        "geri dönmüş olabilir; gerçek survival_time türevi bekleniyor"
    )
    assert any(
        isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == minutes.id for t in n.targets)
        and _divides_survival_time_by_60000(n.value)
        for n in ast.walk(tree)
    ), (
        f"'{minutes.id}' değeri survival_time // 60000 hesabından türemiyor "
        "(ms -> dakika dönüşümü kaybolmuş olabilir)"
    )
