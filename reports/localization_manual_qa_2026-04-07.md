# Localization Manual QA Checklist - 2026-04-07

## What This Is
- Screen-focused manual QA list for remaining same-as-English keys.
- Includes keys that should still be reviewed by humans even after automated override generation.

## Manual Close - Round 1 (Applied)
- tutorial_welcome_title
- settings_tab_audio
- guide_tips_intro
- campaign_world_tab_format (ja/zh/ko)

## Updated Remaining Counts (same-as-English)
- tr: 26 (actionable: 4, keep: 22)
- de: 70 (actionable: 38, keep: 32)
- fr: 45 (actionable: 29, keep: 16)
- es: 22 (actionable: 8, keep: 14)
- it: 42 (actionable: 16, keep: 26)
- pt: 30 (actionable: 9, keep: 21)
- ru: 7 (actionable: 0, keep: 7)
- ja: 12 (actionable: 0, keep: 12)
- zh: 7 (actionable: 1, keep: 6)
- ko: 11 (actionable: 1, keep: 10)

## Keep-As-Is Candidates (Usually OK)
- Brand/Proper nouns: QUADRIX, Zen, Ultra, Sprint, PvP, VS.
- Input labels: ESC, ENTER, key_*.
- Pure format wrappers: campaign_progress, guide_controls_line, hud_key_uses, block_workshop_block_name.

## High Priority Actionable Backlog
- sos_instagram (6 langs): Instagram text context review.
- tutorial_success_4 (4 langs): Bravo! consistency.
- zen_panel_bonus (4 langs): Bonus label consistency.
- mode_tetris_extra (4 langs): QUADRIX EXTRA mode label localization choice.
- survival_panel_antivirus (4 langs): ANTIVIRUS label localization choice.
- pvp_top_out (3 langs): TOP-OUT combat term review.
- pvp_minutes (3 langs): min abbreviation consistency.
- setting_volume (3 langs): Volume label consistency.
- cascade_level_message (2 langs): CASCADE x{level}! line.
- menu_dashboard_pvp_online_sub (2 langs): Steam 1v1 subtitle.
- campaign_world_short_3 (2 langs): Lava world short-name.
- color_cyan/color_orange (2 langs): color naming consistency.
- ctrl_pause/gp_pause/guide_action_pause/pause/pvp_pause_hint (2 langs): Pause consistency across screens.
- user_bio/user_field_avatar (2 langs): profile labels.
- version (2 langs): version label policy.
- exit_no/no (2 langs): No (ESC) style consistency.

## Screen Buckets for QA Pass
1. Main Menu + Dashboard
- mode_tetris_extra
- menu_dashboard_pvp_online_sub
- mode labels (Sprint/Ultra/Zen) only if product wants localized naming.

2. Settings Screen
- setting_volume
- settings_section_system (de policy check)

3. Guide / Tutorial
- tutorial_success_4
- guide_action_pause / pause
- pvp_minutes

4. Campaign / Worlds
- campaign_world_short_3
- cascade_level_message

5. PvP / Online PvP
- pvp_top_out
- pvp_pause_hint

6. User/Profile
- user_bio
- user_field_avatar

## Data Sources
- reports/localization_remaining_same_as_en_post_manual.json
- reports/localization_remaining_usage_2026-04-07.json
