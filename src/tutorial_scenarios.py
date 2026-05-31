"""Tutorial senaryo verisi ve evaluator yardımcıları.

Bu modül, pygame runtime'ına bağımlı olmadan tutorial board dersleri için
senaryo tanımlarını ve board metrik hesaplamalarını sunar.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

try:
    from .localization import t  # type: ignore
except Exception:
    from localization import t


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "gap_fill_double": {
        "goal_key": "tutorial_board_gap_fill_goal",
        "board_rows": [
            "XXX...XXXX",
            "XXXX.XXXXX",
        ],
        "current_piece": {"name": "T", "x": 1, "y": 0, "rotation": 0},
        "next_queue": ["L", "I", "O"],
        "allow_hold": False,
        "highlight_placements": [["T", 2, 3]],
        "goal_text": "Hedef: T parçasını döndürüp doğru yere koyarak iki satır temizle.",
        "tip_key": "tutorial_board_gap_fill_tip",
        "tip_text": "T parçasının şeklini boşluğun şekliyle eşleştir; döndür ve kaydır.",
        "objectives": [
            {
                "id": "clear_lines",
                "text": "2 satırı temizle",
                "metric": "line_delta",
                "comparison": "min",
                "value": 2,
            },
            {
                "id": "avoid_holes",
                "text": "Yeni delik oluşturma",
                "metric": "hole_delta",
                "comparison": "max",
                "value": 0,
            },
            {
                "id": "keep_height_stable",
                "text": "İdeal: yüksekliği artırma",
                "metric": "height_delta",
                "comparison": "max",
                "value": 0,
            },
        ],
        "coach_feedback": {
            "clean": "Geniş boşluğu tek hamlede doğru okudun. Bu bakış kart kararlarında da işine yarar.",
            "need_more_lines": "Ana boşluğu doğrudan kapatacak yerleşimi ara; yan hamlelere kaydığında hedef kaçıyor.",
            "created_holes": "Çözüm üretirken yeni delik açma. Önce yüzeyi sade tut, sonra temizliği al.",
            "stack_too_high": "Aynı problemi daha alçak ve güvenli bir yerleşimle çözmeyi dene.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },
    "keep_stack_low": {
        "goal_key": "tutorial_board_keep_low_goal",
        "board_rows": [
            "XXXXXXX...",
            "XXXXXXX..X",
            "XXXXXXX.XX",
        ],
        "current_piece": {"name": "T", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["L", "S", "O"],
        "allow_hold": False,
        "highlight_placements": [["T", 2, 7]],
        "goal_text": "Hedef: Parçayı döndürüp doğru yere koyarak yüksekliği azalt.",
        "tip_key": "tutorial_board_keep_low_tip",
        "tip_text": "T parçasını sağa taşı ve döndür — kuleyi büyütmeden iki satırı temizleyebilirsin.",
        "objectives": [
            {
                "id": "height_limit",
                "text": "Yüksekliği +1'den fazla artırma",
                "metric": "height_delta",
                "comparison": "max",
                "value": 1,
            },
            {
                "id": "avoid_holes",
                "text": "Yeni delik oluşturma",
                "metric": "hole_delta",
                "comparison": "max",
                "value": 0,
            },
            {
                "id": "ideal_height",
                "text": "İdeal: yüksekliği hiç artırma",
                "metric": "height_delta",
                "comparison": "max",
                "value": 0,
            },
        ],
        "coach_feedback": {
            "clean": "Temiz kalmak için her hamlede satır temizlemen gerekmediğini doğru gösterdin.",
            "need_more_lines": "Bu derste asıl öncelik satır değil, yüzeyi sakin tutmak. Önce güvenli tarafı seç.",
            "created_holes": "Tahtayı düşük tutmaya çalışırken yeni delik açarsan sonraki hamlelerin zorlaşır.",
            "stack_too_high": "Yüksekliği zorlamadan çözülebilecek açık tarafı tekrar ara.",
        },
        "evaluation": {
            "required_line_clears": 0,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },
    "vertical_well_quadrix": {
        "goal_key": "tutorial_board_vertical_well_goal",
        "board_rows": [
            "XXXXXXXXX.",
            "XXXXXXXXX.",
            "XXXXXXXXX.",
            "XXXXXXXXX.",
        ],
        "current_piece": {"name": "I", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["O", "T", "L"],
        "allow_hold": False,
        "highlight_placements": [["I", 1, 7]],
        "goal_text": "Hedef: I parçasını en sağa taşı, dikleştir ve Quadrix yap.",
        "tip_key": "tutorial_board_vertical_well_tip",
        "tip_text": "I parçasını sağa taşı, döndürerek dikleştir ve kuyuya bırak.",
        "objectives": [
            {
                "id": "quadrix",
                "text": "4 satır temizle",
                "metric": "line_delta",
                "comparison": "min",
                "value": 4,
            },
            {
                "id": "avoid_holes",
                "text": "Yeni delik oluşturma",
                "metric": "hole_delta",
                "comparison": "max",
                "value": 0,
            },
            {
                "id": "ideal_height_drop",
                "text": "İdeal: yüksekliği azalt",
                "metric": "height_delta",
                "comparison": "max",
                "value": -1,
            },
        ],
        "coach_feedback": {
            "clean": "Kuyuyu sabırla koruyup doğru anda kapattın. Quadrix hazırlığı mantığını doğru okudun.",
            "need_more_lines": "I parçasını doğrudan kuyuyla buluşturacak hattı koru; yan yüzeyi bozma.",
            "created_holes": "Kuyuyu çözmeye çalışırken yeni delik bırakırsan güçlü plan boşa gider.",
            "stack_too_high": "Bu dersin gücü yüksek kuleye çıkmakta değil, hazır çözümü sabırla tamamlamakta.",
        },
        "evaluation": {
            "required_line_clears": 4,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -1,
        },
    },

    # ── Yeni senaryolar ──────────────────────────────────────────

    "avoid_holes_trap": {
        "goal_key": "tutorial_avoid_holes_goal",
        "board_rows": [
            "XXXX....XX",
            "XXXXX...XX",
            "XXXXX..XXX",
        ],
        "current_piece": {"name": "S", "x": 2, "y": 0, "rotation": 0},
        "next_queue": ["T", "O", "L"],
        "allow_hold": False,
        "highlight_placements": [["S", 0, 5]],
        "goal_text": "Hedef: S parçasını delik açmadan doğru basamağa yerleştir.",
        "tip_key": "tutorial_avoid_holes_tip",
        "tip_text": "S'in basamak şeklini tahtadaki boşlukla eşleştir; bir sütun kaydırmak bile delik açar.",
        "objectives": [
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
            {"id": "keep_height", "text": "Yüksekliği +2'den fazla artırma", "metric": "height_delta", "comparison": "max", "value": 2},
        ],
        "coach_feedback": {
            "clean": "Delik açmadan yerleştirdin — gelecekteki hamlelerin daha rahat olacak.",
            "need_more_lines": "Bu derste satır temizleme öncelik değil; deliksiz yerleştirme hedef.",
            "created_holes": "Parçayı koymadan önce altında boşluk kalıp kalmayacağını kontrol et.",
            "stack_too_high": "Delik açmamak güzel ama yüksekliği de kontrol altında tut.",
        },
        "evaluation": {
            "required_line_clears": 0,
            "max_new_holes": 0,
            "max_height_increase": 2,
            "preferred_max_height_increase": 0,
        },
    },

    "hold_save_practice": {
        "goal_key": "tutorial_hold_save_goal",
        "board_rows": [
            "XXXXX.XXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "O", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "T", "L"],
        "allow_hold": True,
        "expected_hold_usage": True,
        "highlight_placements": [["I", 1, 3]],
        "goal_text": "Hedef: Hold kullanarak daha iyi bir yerleştirme yap.",
        "tip_key": "tutorial_hold_save_tip",
        "tip_text": "O parçası tek sütunluk kuyuya sığmaz — hold'a al, I parçasıyla devam et.",
        "objectives": [
            {"id": "used_hold", "text": "Hold kullan", "metric": "hold_used", "comparison": "min", "value": 1},
            {"id": "clear_lines", "text": "En az 1 satır temizle", "metric": "line_delta", "comparison": "min", "value": 1},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Doğru parçayı hold'a alıp kuyuyu I parçasıyla kapattın — harika!",
            "need_hold": "Bu derste çözüm hold ile başlıyor. O parçasını sakla ve I parçasını kuyu için kullan.",
            "need_more_lines": "Hold kullanarak uygun parçayla kuyuyu kapatmayı dene.",
            "created_holes": "Hold sonrası gelen parçayı yanlış yere koydun — kuyuya odaklan.",
            "stack_too_high": "Kuyuyu doldurmak yerine temizlemeye çalış.",
        },
        "evaluation": {
            "required_line_clears": 1,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },

    "queue_read_setup": {
        "goal_key": "tutorial_queue_read_goal",
        "board_rows": [
            "XXX....XXX",
            "XXXX...XXX",
            "XXXX..XXXX",
        ],
        "current_piece": {"name": "S", "x": 7, "y": 0, "rotation": 0},
        "next_queue": ["I", "T", "L"],
        "allow_hold": False,
        "highlight_placements": [["S", 0, 4]],
        "goal_text": "Hedef: Sıradaki parçayı düşünerek satır temizle.",
        "tip_key": "tutorial_queue_read_tip",
        "tip_text": "S parçasını doğru boşluğa oturt; sonraki parça için yer bırak.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 1 satır temizle", "metric": "line_delta", "comparison": "min", "value": 1},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Sıradaki parçayı hesaba katarak doğru boşluğu buldun.",
            "need_more_lines": "S'in basamak şeklini tahtadaki basamak boşluğuyla eşleştirmeye çalış.",
            "created_holes": "Yanlış sütuna koymak delik açar — S'in alt kısmının nereye oturduğunu kontrol et.",
            "stack_too_high": "Daha alçak bir çözüm bul — sıradaki parçayı düşün.",
        },
        "evaluation": {
            "required_line_clears": 1,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -1,
        },
    },

    "hold_vs_place_decision": {
        "goal_key": "tutorial_hold_vs_place_goal",
        "board_rows": [
            "XXXX..XXXX",
            "XXXXX.XXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "T", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "O", "L"],
        "allow_hold": True,
        "expected_hold_usage": True,
        "highlight_placements": [["I", 1, 3]],
        "goal_text": "Hedef: Doğru hold kararını ver.",
        "tip_key": "tutorial_hold_vs_place_tip",
        "tip_text": "T parçası şu ana uyuyor mu, yoksa I parçasını beklemek daha mı iyi?",
        "objectives": [
            {"id": "used_hold", "text": "Doğru karar olarak hold kullan", "metric": "hold_used", "comparison": "min", "value": 1},
            {"id": "clear_lines", "text": "En az 1 satır temizle", "metric": "line_delta", "comparison": "min", "value": 1},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Doğru kararı verdin — parçayı koymak veya saklamak board'a göre değişir.",
            "need_hold": "Bu senaryoda daha değerli karar hold. I parçasını bekleyip boşluğu onunla çöz.",
            "need_more_lines": "Board'u oku — hangi parça şu an daha çok satır temizler?",
            "created_holes": "Hold kararından önce her iki seçeneğin sonucunu zihninde canlandır.",
            "stack_too_high": "Hold ya da koyma kararını verirken yüksekliği de düşün.",
        },
        "evaluation": {
            "required_line_clears": 1,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },

    "two_step_combo": {
        "goal_key": "tutorial_two_step_goal",
        "board_rows": [
            "XXX...XXXX",
            "XXXX..XXXX",
            "XXXX.XXXXX",
            "XXXX.XXXXX",
        ],
        "current_piece": {"name": "L", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["I", "T", "O"],
        "allow_hold": False,
        "max_piece_locks": 2,
        "highlight_placements": [["L", 3, 3], ["I", 1, 3]],
        "goal_text": "Hedef: İki parçayı sırayla yerleştirip çoklu satır temizle.",
        "tip_key": "tutorial_two_step_tip",
        "tip_text": "İlk parçayı yerleştirirken ikincisinin nereye gideceğini düşün.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 2 satır temizle", "metric": "line_delta", "comparison": "min", "value": 2},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "İki hamlelik plan kurup temizliği aldın — bu planlama gücü.",
            "need_more_lines": "İlk parçayı ikinciye zemin hazırlayacak şekilde yerleştir.",
            "created_holes": "Acele etme — iki hamlede de delik açmamak öncelik.",
            "stack_too_high": "Planlı yerleştirme yüksekliği artırmadan temizlik almalı.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": 2,
            "preferred_max_height_increase": 0,
        },
    },

    "recovery_breathing_room": {
        "goal_key": "tutorial_recovery_breathing_goal",
        "board_rows": [
            "XXXXX.XXXX",
            "XXXX...XXX",
            "XXXXXX.XXX",
            "XXXXXX.XXX",
        ],
        "current_piece": {"name": "L", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "O", "T"],
        "allow_hold": False,
        "max_piece_locks": 2,
        "highlight_placements": [["L", 3, 4], ["I", 1, 4]],
        "goal_text": "Hedef: 2 parçayla en az 3 satır temizleyip nefes alanı aç.",
        "tip_key": "tutorial_recovery_breathing_tip",
        "tip_text": "Önce L ile yüzeyi düzelt, sonra I bloğunu dikey kullan.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 3 satır temizle", "metric": "line_delta", "comparison": "min", "value": 3},
            {"id": "avoid_holes", "text": "En fazla 1 yeni delik", "metric": "hole_delta", "comparison": "max", "value": 1},
            {"id": "reduce_height", "text": "Yüksekliği en az 1 azalt", "metric": "height_delta", "comparison": "max", "value": -1},
        ],
        "coach_feedback": {
            "clean": "Panik yapmadan önce alan açtın — nefes alan hayatta kalır.",
            "need_more_lines": "Önce L ile ortadaki boşluğu düzleştir, sonra I ile sütunu kapat.",
            "created_holes": "Kurtarma modunda yeni delik açmak durumu kötüleştirir.",
            "stack_too_high": "Alan açarken yüzeyi alçalt; dikey I için temiz sütun bırak.",
        },
        "evaluation": {
            "required_line_clears": 3,
            "max_new_holes": 1,
            "max_height_increase": -1,
            "preferred_max_height_increase": -2,
        },
    },

    "recovery_hole_vs_height": {
        "goal_key": "tutorial_recovery_hole_height_goal",
        "board_rows": [
            "..X.......",
            "X.XX..XXXX",
            "XXXX.XXXXX",
            "XXXXX.XXXX",
            "XX.XXXXXXX",
            "XXXXXXX.XX",
            "XXX..XXXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "J", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["T", "I", "O"],
        "allow_hold": False,
        "max_piece_locks": 2,
        "highlight_placements": [["J", 1, 0], ["T", 1, 3]],
        "goal_text": "Hedef: Deliği azalt ve 2 satır temizle.",
        "tip_key": "tutorial_recovery_hole_height_tip",
        "tip_text": "Önce J ile soldaki deliği toparla, sonra T ile temizliği al.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 2 satır temizle", "metric": "line_delta", "comparison": "min", "value": 2},
            {"id": "reduce_holes", "text": "En az 1 deliği azalt", "metric": "hole_delta", "comparison": "max", "value": -1},
            {"id": "height_control", "text": "Yüksekliği artırma", "metric": "height_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Doğru önceliği seçtin — deliği azaltıp satırları aldın.",
            "need_more_lines": "Önce deliği güvene al, sonra T ile iki satırı tamamla.",
            "created_holes": "Yeni delik açarak sorunu büyütme — önce mevcut deliklere odaklan.",
            "stack_too_high": "Delik önceliğini doğru belirle ama yüksekliği de gözden kaçırma.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": -1,
            "max_height_increase": 0,
            "preferred_max_height_increase": -1,
        },
    },

    "recovery_reduce_ceiling": {
        "goal_key": "tutorial_recovery_ceiling_goal",
        "board_rows": [
            "XXXX.XXXXX",
            "XXXX.XXXXX",
            "XX.XXXXXXX",
            "XX.XXXXXXX",
            "XXXXXXX.XX",
            "XXXXXXX.XX",
        ],
        "current_piece": {"name": "J", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["O", "I", "T"],
        "allow_hold": True,
        "expected_hold_usage": True,
        "max_piece_locks": 3,
        "highlight_placements": [["J", 1, 3], ["I", 1, 0]],
        "hold_highlight_index": 1,
        "goal_text": "Hedef: Hold ile I al ve tavanı indirerek satır temizle.",
        "tip_key": "tutorial_recovery_ceiling_tip",
        "tip_text": "Önce J'yi orta boşluğa yerleştir. Sonra O'yu C ile saklayıp I bloğunu dikey indir.",
        "objectives": [
            {"id": "use_hold", "text": "C ile hold kullan", "metric": "hold_used", "comparison": "min", "value": 1},
            {"id": "clear_lines", "text": "En az 2 satır temizle", "metric": "line_delta", "comparison": "min", "value": 2},
            {"id": "reduce_height", "text": "Yüksekliği artırma", "metric": "height_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Önce zemini kurup sonra hold ile I aldın — tavanı doğru indirdin.",
            "need_hold": "Önce J'yi yerleştir, sonra O'yu C ile saklayıp I bloğunu al.",
            "need_more_lines": "J ile zemini hazırladıktan sonra I bloğunu dikey kullanıp satırları temizle.",
            "created_holes": "Tavanı düşürürken yeni delik açma — sorun büyür.",
            "stack_too_high": "J ile orta boşluğu düzleştir; sonra I için temiz bir sütun bırak.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -2,
        },
    },

    "recovery_wrong_side": {
        "goal_key": "tutorial_recovery_wrong_side_goal",
        "board_rows": [
            "XXXX..XXXX",
            "XXXX...XXX",
            "XXXX...XXX",
        ],
        "current_piece": {"name": "J", "x": 7, "y": 0, "rotation": 0},
        "next_queue": ["O", "I", "T"],
        "allow_hold": False,
        "max_piece_locks": 2,
        "highlight_placements": [["J", 1, 3], ["O", 0, 5]],
        "goal_text": "Hedef: Yanlış taraftaki parçayı sola taşı, sonra boşluğu kapat.",
        "tip_key": "tutorial_recovery_wrong_side_tip",
        "tip_text": "Önce J'yi sola taşıyıp yüzeyi düzelt. Ardından O ile kalan boşluğu kapat.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 2 satır temizle", "metric": "line_delta", "comparison": "min", "value": 2},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
            {"id": "reduce_height", "text": "Yüksekliği en az 1 azalt", "metric": "height_delta", "comparison": "max", "value": -1},
        ],
        "coach_feedback": {
            "clean": "Yanlış taraftan başlayıp doğru yüzeyi kurdun — harika!",
            "need_more_lines": "Önce J'yi sola taşıyıp yüzeyi hazırla, sonra O ile temizliği tamamla.",
            "created_holes": "Dengeyi düzeltirken yeni delik açma — sorun büyür.",
            "stack_too_high": "Yanlış tarafa koymak yerine solu rahatlatıp yüksekliği düşür.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": -1,
            "preferred_max_height_increase": -1,
        },
    },

    "exam_board_combined": {
        "goal_key": "tutorial_exam_board_goal",
        "board_rows": [
            "X.....XXXX",
            "XX...XXXXX",
            "XXX..XXXXX",
            "XXXX.XXXXX",
            "XXXX.XXXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "T", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "L", "O"],
        "allow_hold": False,
        "max_piece_locks": 2,
        "highlight_placements": [["T", 2, 2], ["I", 1, 2]],
        "goal_text": "Hedef: Birden fazla hedefi aynı anda tamamla.",
        "tip_key": "tutorial_exam_board_tip",
        "tip_text": "İpuçları az — öğrendiklerini birleştir.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 3 satır temizle", "metric": "line_delta", "comparison": "min", "value": 3},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
            {"id": "height_control", "text": "Yüksekliği artırma", "metric": "height_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Yüzey, delik ve kuyu kararlarını birlikte uyguladın — harika!",
            "need_more_lines": "Birden fazla ilkeyi birleştir — kuyu ve satır hedeflerini birlikte düşün.",
            "created_holes": "Sınavda delik açmak puanını düşürür — ilkeleri hatırla.",
            "stack_too_high": "Yükseklik kontrolü de sınavın parçası — alçak tut.",
        },
        "evaluation": {
            "required_line_clears": 3,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -1,
        },
    },

    "exam_plan_combined": {
        "goal_key": "tutorial_exam_plan_goal",
        "board_rows": [
            "XXX...XXXX",
            "XXXX..XXXX",
            "XXXX.XXXXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "S", "x": 3, "y": 0, "rotation": 0},
        "next_queue": ["I", "T", "L"],
        "allow_hold": True,
        "expected_hold_usage": True,
        "max_piece_locks": 2,
        "highlight_placements": [["I", 1, 1], ["T", 1, 3]],
        "goal_text": "Hedef: Hold ve queue'yu kullanarak temiz sonuç al.",
        "tip_key": "tutorial_exam_plan_tip",
        "tip_text": "Az ipucu — sırayı ve hold'u birlikte düşün.",
        "objectives": [
            {"id": "used_hold", "text": "Hold kullan", "metric": "hold_used", "comparison": "min", "value": 1},
            {"id": "clear_lines", "text": "En az 2 satır temizle", "metric": "line_delta", "comparison": "min", "value": 2},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Queue ve hold'u birlikte kullanarak planlı sonuç aldın.",
            "need_hold": "Bu sınavda hold kararını gerçekten kullanman gerekiyor. Önce sakla, sonra sırayı değerlendir.",
            "need_more_lines": "Sırayı oku, hold'u düşün — planlı iki hamle tek hamleden güçlüdür.",
            "created_holes": "Planlama sınavında delik açmak plansızlık demek.",
            "stack_too_high": "Hold ve queue ile daha temiz bir çözüm mümkün.",
        },
        "evaluation": {
            "required_line_clears": 2,
            "max_new_holes": 0,
            "max_height_increase": 1,
            "preferred_max_height_increase": 0,
        },
    },

    "exam_hybrid_final": {
        "goal_key": "tutorial_exam_hybrid_goal",
        "board_rows": [
            "X.....XXXX",
            "XX...XXXXX",
            "XXX..XXXXX",
            "XXXX.XXXXX",
            "XXXXX.XXXX",
            "XXX.XXXXXX",
            "XXXXXXX.XX",
            "XX.XXXXXXX",
            "XXXXXX.XXX",
            "XXXXX.XXXX",
        ],
        "current_piece": {"name": "T", "x": 4, "y": 0, "rotation": 0},
        "next_queue": ["I", "L", "J", "O"],
        "allow_hold": True,
        "max_piece_locks": 4,
        "highlight_placements": [["T", 2, 2], ["L", 3, 3], ["J", 1, 4], ["O", 0, 1]],
        "goal_text": "Hedef: Tüm becerileri tek bir senaryoda göster.",
        "tip_key": "tutorial_exam_hybrid_tip",
        "tip_text": "Artık ipucu yok — sen biliyorsun.",
        "objectives": [
            {"id": "clear_lines", "text": "En az 3 satır temizle", "metric": "line_delta", "comparison": "min", "value": 3},
            {"id": "avoid_holes", "text": "Yeni delik oluşturma", "metric": "hole_delta", "comparison": "max", "value": 0},
            {"id": "reduce_height", "text": "Yüksekliği artırma", "metric": "height_delta", "comparison": "max", "value": 0},
        ],
        "coach_feedback": {
            "clean": "Tüm ilkeleri birleştirdin — tebrikler, eğitimi tamamladın!",
            "need_more_lines": "Her şeyi birleştir — yüzey, queue, hold, kurtarma.",
            "created_holes": "Final sınavında delik açmak puanını düşürür — ilkeleri hatırla.",
            "stack_too_high": "Final'de yükseklik kontrolü kritik — alçak ve temiz bitir.",
        },
        "evaluation": {
            "required_line_clears": 3,
            "max_new_holes": 0,
            "max_height_increase": 0,
            "preferred_max_height_increase": -2,
        },
    },
}


def get_scenario(scenario_id: str | None) -> Dict[str, Any] | None:
    if not scenario_id:
        return None
    scenario = SCENARIOS.get(str(scenario_id))
    if not scenario:
        return None

    hydrated = deepcopy(scenario)
    hydrated["id"] = str(scenario_id)
    goal_key = hydrated.get("goal_key")
    if goal_key:
        hydrated["goal_text"] = t(str(goal_key), default=str(hydrated.get("goal_text") or ""))
    tip_key = hydrated.get("tip_key")
    if tip_key:
        hydrated["tip_text"] = t(str(tip_key), default=str(hydrated.get("tip_text") or ""))
    return hydrated


def _empty_occupancy(width: int, height: int) -> List[List[bool]]:
    return [[False for _ in range(width)] for _ in range(height)]


def build_occupancy_from_rows(
    board_rows: Iterable[str] | None,
    *,
    width: int = 10,
    height: int = 20,
    fill_chars: str = "X#1@",
) -> List[List[bool]]:
    occupancy = _empty_occupancy(width, height)
    rows = [str(row) for row in (board_rows or []) if row is not None]
    for source_index, row in enumerate(reversed(rows[-height:])):
        y = height - 1 - source_index
        normalized = row[:width].ljust(width, ".")
        for x, cell in enumerate(normalized):
            occupancy[y][x] = cell in fill_chars
    return occupancy


def count_holes(occupancy: List[List[bool]]) -> int:
    if not occupancy:
        return 0
    height = len(occupancy)
    width = len(occupancy[0]) if occupancy[0] else 0
    holes = 0
    for x in range(width):
        seen_block = False
        for y in range(height):
            filled = bool(occupancy[y][x])
            if filled:
                seen_block = True
            elif seen_block:
                holes += 1
    return holes


def get_column_heights(occupancy: List[List[bool]]) -> List[int]:
    if not occupancy:
        return []
    height = len(occupancy)
    width = len(occupancy[0]) if occupancy[0] else 0
    column_heights: List[int] = []
    for x in range(width):
        column_height = 0
        for y in range(height):
            if occupancy[y][x]:
                column_height = height - y
                break
        column_heights.append(column_height)
    return column_heights


def max_height(occupancy: List[List[bool]]) -> int:
    heights = get_column_heights(occupancy)
    return max(heights) if heights else 0


def count_filled_cells(occupancy: List[List[bool]]) -> int:
    return sum(1 for row in occupancy for cell in row if cell)


def capture_board_metrics(board: Any) -> Dict[str, Any]:
    occupancy = [list(map(bool, row)) for row in getattr(board, "occupancy", [])]
    return {
        "holes": count_holes(occupancy),
        "column_heights": get_column_heights(occupancy),
        "max_height": max_height(occupancy),
        "filled_cells": count_filled_cells(occupancy),
        "lines_cleared": int(getattr(board, "lines_cleared", 0) or 0),
    }


def evaluate_scenario(
    initial_metrics: Dict[str, Any] | None,
    current_metrics: Dict[str, Any] | None,
    evaluation: Dict[str, Any] | None,
) -> Dict[str, Any]:
    initial = deepcopy(initial_metrics) if isinstance(initial_metrics, dict) else {}
    current = deepcopy(current_metrics) if isinstance(current_metrics, dict) else {}
    rules = deepcopy(evaluation) if isinstance(evaluation, dict) else {}

    line_delta = int(current.get("lines_cleared", 0) or 0) - int(initial.get("lines_cleared", 0) or 0)
    hole_delta = int(current.get("holes", 0) or 0) - int(initial.get("holes", 0) or 0)
    height_delta = int(current.get("max_height", 0) or 0) - int(initial.get("max_height", 0) or 0)

    required_line_clears = max(0, int(rules.get("required_line_clears", 0) or 0))
    max_new_holes = int(rules.get("max_new_holes", 999) or 0)
    max_height_increase = int(rules.get("max_height_increase", 999) or 0)
    preferred_height_increase = int(rules.get("preferred_max_height_increase", max_height_increase) or 0)

    success = (
        line_delta >= required_line_clears
        and hole_delta <= max_new_holes
        and height_delta <= max_height_increase
    )

    stars = 0
    if success:
        stars = 1
        if hole_delta <= 0:
            stars += 1
        if height_delta <= preferred_height_increase:
            stars += 1
        stars = max(1, min(3, stars))

    feedback_key = "clean"
    if line_delta < required_line_clears:
        feedback_key = "need_more_lines"
    elif hole_delta > max_new_holes:
        feedback_key = "created_holes"
    elif height_delta > max_height_increase:
        feedback_key = "stack_too_high"

    # FAZ E — Pedagojik geri bildirim: "iyi yapılan" ve "geliştirilecek" davranışlar.
    did_well_keys: List[str] = []
    improve_keys: List[str] = []
    if hole_delta <= 0:
        did_well_keys.append("no_new_holes")
    else:
        improve_keys.append("created_holes")
    if height_delta <= 0:
        did_well_keys.append("kept_height")
    elif height_delta > max_height_increase:
        improve_keys.append("stack_too_high")
    if required_line_clears > 0 and line_delta >= required_line_clears:
        did_well_keys.append("cleared_lines")
    elif line_delta < required_line_clears:
        improve_keys.append("need_more_lines")

    return {
        "success": bool(success),
        "stars": int(stars),
        "feedback_key": feedback_key,
        "line_delta": line_delta,
        "hole_delta": hole_delta,
        "height_delta": height_delta,
        "required_line_clears": required_line_clears,
        "did_well_keys": did_well_keys,
        "improve_keys": improve_keys,
    }


def enrich_scenario_outcome(outcome: Dict[str, Any] | None, scenario: Dict[str, Any] | None) -> Dict[str, Any]:
    enriched = deepcopy(outcome) if isinstance(outcome, dict) else {}
    scenario_data = deepcopy(scenario) if isinstance(scenario, dict) else {}
    if not enriched or not scenario_data:
        return enriched

    metric_values = {
        "line_delta": int(enriched.get("line_delta", 0) or 0),
        "hole_delta": int(enriched.get("hole_delta", 0) or 0),
        "height_delta": int(enriched.get("height_delta", 0) or 0),
        "hold_used": int(enriched.get("hold_used", 0) or 0),
    }

    objective_results: List[Dict[str, Any]] = []
    for objective in list(scenario_data.get("objectives") or []):
        if not isinstance(objective, dict):
            continue
        metric_name = str(objective.get("metric") or "")
        if metric_name not in metric_values:
            continue
        comparison = str(objective.get("comparison") or "max")
        target_value = int(objective.get("value", 0) or 0)
        actual_value = metric_values[metric_name]
        passed = actual_value >= target_value if comparison == "min" else actual_value <= target_value
        objective_results.append(
            {
                "id": objective.get("id"),
                "text": str(objective.get("text") or ""),
                "passed": bool(passed),
            }
        )

    if objective_results:
        enriched["objective_results"] = objective_results

    coach_feedback = scenario_data.get("coach_feedback")
    feedback_key = str(enriched.get("feedback_key") or "")
    if isinstance(coach_feedback, dict) and feedback_key:
        coach_text = coach_feedback.get(feedback_key)
        if coach_text:
            enriched["coach_text"] = str(coach_text)

    return enriched
