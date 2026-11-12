"""Generate work/translation/en/textures.json: every texture with Japanese text that is translated,
with its Japanese, the English and the drawing style used by tools/tex_make.py.

Skill plate names reuse the executable's translated skill table (strings.json, group elf), so the
plates and the menus agree. MS-skill plates have no text equivalent; names follow the glossary
(VSBR, I-field, Bug, hide bomb, heat rod, psycommu) and the msskill_info.inf descriptions.

python tools/tex_jobs.py
"""
import glob
import json
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import xts_tool  # noqa: E402
from tex_make import STAT_TERMS  # noqa: E402

FPK = os.path.join(ROOT, 'work', 'source', 'fpk')
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'textures.json')

TITLE = 'saga_title0.fpk_/title_03.xts'
TITLE_SUBS = [
    ('sub_01', '＜クロニクルモード＞キャラクター別のストーリーモードです', ['< Chronicle Mode >', 'Story mode for each character.']),
    ('sub_02', '＜プログレスモード＞オリジナルキャラクターの育成モードです', ['< Progress Mode >', 'Raise your own original character.']),
    ('sub_03', '＜エクストラモード＞上級者向け特殊シチュエーションバトル', ['< Extra Mode >', 'Special battles for experts.']),
    ('sub_04', '＜バーサスモード＞1対1の、2プレイヤーズ対戦です', ['< VS Mode >', 'One-on-one, two-player battles.']),
    ('sub_05', '＜カードコレクション＞各モードで集めたカードを閲覧できます', ['< Card Collection >', 'View cards collected in each mode.']),
    ('sub_06', '＜オプション＞操作や設定の変更が行えます', ['< Option >', 'Change controls and settings.']),
    ('sub_07', '＜チュートリアル＞ゲームの操作を体験学習できます', ['< Tutorial >', 'Learn the controls hands-on.']),
]

AS = {'CYOKUGEKI': '直撃', 'CYOU_HATSU': '挑発', 'DAI_KONNRAN': '大混乱', 'FUI_UCHI': '不意打ち',
      'FULL_RELOAD': 'フルリロード', 'IATSU': '威圧', 'ICHIGEKI': '一撃', 'IKAKU': '威嚇',
      'ISHIKI_KAKUDAI': '意識拡大', 'KAKURAN': 'かく乱', 'KAKUSHIWAZA': '隠し技', 'MIKIRI': '見切り',
      'PRESSURE': 'プレッシャー', 'RUSH': 'ラッシュ', 'SEISHIN_BOUGYO': '精神防御', 'SNIPE': 'スナイプ',
      'YUUIN': '誘引', 'ZENRYOKU_KAIHOU': '全力開放'}
PS = {'AURA': 'オーラ', 'EIBIN': '鋭敏', 'ELITE': 'エリート', 'FUKUTU': '不屈', 'HANDAN_RYOKU': '判断力',
      'HIGH_CHARGE': 'ハイチャージ', 'HIGH_SHIELD': 'ハイシールド', 'HISSATSU': '必殺', 'JUKUREN': '熟練',
      'JUNK_SHOP': 'ジャンク屋', 'KAKUSEI': '覚醒', 'KIAI': '気合', 'KIMAGURE': '気まぐれ',
      'KINKYUU_BOUGYO': '緊急防御', 'KOUKI': '高貴', 'KOUSOKU_SENTOU': '高速戦闘', 'KOUUN': '幸運',
      'KUUCHUUSEN_PLUS': '空中戦＋', 'KYOUKA_NINGEN': '強化人間', 'MIWAKU': '魅惑', 'NANJYAKU': '軟弱者',
      'NIGEASHI': '逃げ足', 'OOGATAKI_NORI': '大型機乗り', 'POWER_CUSTOM': 'パワーカスタム',
      'QUICK_RELOAD': 'クイックリロード', 'SAKUTEKI': '索敵', 'SEIJI_RYOKU': '政治力', 'SEISHIN_SYUCYU': '精神集中',
      'SHUNPATSURYOKU': '瞬発力', 'SOKODIKARA': '底力', 'SPEED_SHOT': 'スピードショット', 'TIJYOSEN_PLUS': '地上戦＋',
      'TOUJYOU_AEUG': '搭乗＋［エゥーゴ］', 'TOUJYOU_AXIS': '搭乗＋［アクシズ］', 'TOUJYOU_CROSSBONE': '搭乗＋［クロスボーン］',
      'TOUJYOU_EFSF': '搭乗＋［連邦］', 'TOUJYOU_NEO_ZEON': '搭乗＋［ネオジオン］', 'TOUJYOU_NEW_EFSF': '搭乗＋［新連邦］',
      'TOUJYOU_TITANS': '搭乗＋［ティターンズ］', 'TOUJYOU_ZEON': '搭乗＋［ジオン］', 'TOUSHI': '闘志', 'TOUSOTSU': '統率',
      'UCYUUSEN_PLUS': '宇宙戦＋'}
# MS skill plates: English = the game's own MS-select panel names (unitweapon.fpk wp_*.xts,
# last row); spelling slips corrected (Chain Main, Crow Missile, I F. Attack).
MS = {'BUG': ('バグ召喚', 'Call Bug'), 'BWS': ('ＢＷＳ分離', 'BWS Separation'), 'CHAINMAIN': ('チェーンマイン', 'Chain Mine'),
      'CHARGEKICK': ('チャージキック', 'Charge Kick'), 'COMBINATION': ('コンビネーション', 'Combination'),
      'DUMMY': ('ダミーバルーン', 'Dummy Balloon'), 'E_WIRE': ('電磁ワイヤー', 'Electromag. Wire'),
      'FULL_RELOAD': ('ハイパーサーベル', 'Hyper Saber'), 'GUTS': ('捨て身の攻撃', 'Guts'),
      'HEATROD': ('ヒートロッド', 'Heat Rod'), 'HENKEI': ('変形', 'Transformation'), 'HIDE_BOMB': ('ハイド・ボンブ', 'Hide Bomb'),
      'HIGHSPEED': ('高速移動モード', 'High Speed Mode'), 'IFIELD': ('Ｉフィールド攻撃', 'I.F. Attack'),
      'INVINCIBLE': ('質量を持った残像', 'Invincible'), 'KAKUSHI_UDE': ('隠し腕防御', 'Hidden Arm'),
      'KOUKIDOU': ('高機動', 'Maneuverability'), 'LIMIT_DISARM': ('リミッター解除', 'Limit Disarm'),
      'LONGRIFLE': ('ロング・ライフルＲ', 'Long Rifle'), 'MISSILE': ('胴部ミサイル', 'Missile'),
      'MSDUMMY': ('ＭＳダミーバルーン', 'Dummy Balloon'), 'NAGINATA': ('ナギナタガード', 'Naginata Guard'),
      'POWERARMOR': ('防御姿勢', 'Power Armor'), 'PSYCHOMU': ('サイコミュ強化', 'Psychomu'),
      'RAPIDSHOT': ('ラピッドショット', 'Rapid Shot'), 'SB_COATING': ('強化Ｂコーティング', 'Beam Coating'),
      'SIELD_RELOAD': ('シールドリロード', 'Shield Reload'), 'SNIPESHOT': ('スナイプショット', 'Snipe Shot'),
      'S_ANCHOR': ('シザー・アンカー', 'Scissor Anchor'), 'S_BEAMGUN': ('拡散ビーム砲Ｓ', 'S. Beam Gun'),
      'S_CHARGE': ('ショルダーチャージ', 'Shoulder Charge'), 'THRUST': ('ランサー', 'Thrust'),
      'TORIMOCHI': ('トリモチランチャー', 'Torimochi Launcher'), 'TSUME_MISSILE': ('対空ミサイル', 'Claw Missile'),
      'VSBR': ('ヴェスバーＳ', 'V.S.B.R Snipe Shot'), 'WIREARM': ('有線アーム', 'Wire Arm')}


def skill_en():
    rows = json.load(open(os.path.join(ROOT, 'work', 'translation', 'en', 'strings.json'), encoding='utf-8'))
    return {r['jp']: r['en'] for r in rows if r['group'] == 'elf' and r.get('en')}


def only_image(xts):
    d = open(os.path.join(FPK, xts), 'rb').read()
    _, imgs = xts_tool.parse(d)
    return [x['name'] for x in imgs]


def main():
    en = skill_en()
    jobs = []
    for img, jp, lines in TITLE_SUBS:
        jobs.append({'xts': TITLE, 'image': img, 'style': 'title_sub', 'jp': jp, 'en': lines})
    jobs.append({'xts': 'briefingb.fpk_/BRI_33_BASE.xts', 'image': 'mission_text', 'style': 'label3',
                 'jp': '作戦内容 / 勝利条件 / 敗北条件', 'en': ['Mission', 'Victory', 'Defeat']})
    for fam, table in (('AS', AS), ('PS', PS)):
        for k, jp in table.items():
            if jp not in en:
                raise SystemExit('no executable translation for %s' % jp)
            x = '%s_%s.xts' % (fam, k)
            jobs.append({'xts': 'skill_panel.fpk_/' + x, 'image': only_image('skill_panel.fpk_/' + x)[0],
                         'style': 'plate', 'family': fam, 'jp': jp, 'en': en[jp]})
    for k, (jp, e) in MS.items():
        x = 'msskill_panel.fpk_/MS_%s.xts' % k
        jobs.append({'xts': x, 'image': only_image(x)[0], 'style': 'plate', 'family': 'MS', 'jp': jp, 'en': e})
    # result-edit stat labels: Japanese only -> English term (tex_make.STAT_TERMS). The menu / pause
    # variants (English word + small Japanese gloss over its last letters) are not done yet: the gloss
    # overlaps the English lettering and needs hand repair (see docs/textures.md).
    for k, jp in (('armor', '防御'), ('cp', 'コンディションポイント'), ('infighting', '格闘'),
                  ('mainweapon', '射撃'), ('mobility', '機動'), ('nt', 'ニュータイプ')):
        jobs.append({'xts': 'resultedit.fpk_/PARAMETER.xts', 'image': k, 'style': 'stat_result', 'jp': jp,
                     'en': STAT_TERMS[k]})
    # Japanese layered over English lettering: redrawn, keeping the game's own English wording
    RANK = {'01': ('class_souchou', '曹長', ['Master', 'Sergeant']), '02': ('class_shoui', '少尉', ['2nd', 'Lieutenant']),
            '03': ('class_chuui', '中尉', ['1st', 'Lieutenant']), '04': ('class_taii', '大尉', ['Captain']),
            '05': ('class_shousa', '少佐', ['Major']), '06': ('class_chuusa', '中佐', ['Lieutenant', 'Colonel']),
            '07': ('class_taisa', '大佐', ['Colonel'])}
    for k, (img, jp, lines) in RANK.items():
        jobs.append({'xts': 'abilities.pack.fpk_/status_icon.fpk_/Class%s.xts' % k, 'image': img,
                     'style': 'rank_plate', 'jp': jp, 'en': lines})
    PERS = {'parson_gentle': ('温厚', 'GENTLE'), 'parson_hot': ('熱血', 'HOT-BLOOD'), 'parson_cool': ('冷静', 'COOL')}
    for img, (jp, e) in PERS.items():
        jobs.append({'xts': 'abilities.pack.fpk_/status_icon.fpk_/%s.xts' % img, 'image': img,
                     'style': 'personality', 'jp': jp, 'en': e})
        jobs.append({'xts': 'characteredit1.fpk_/CE_61_PARSONAL.xts', 'image': img,
                     'style': 'personality', 'jp': jp, 'en': e})
    jobs.append({'xts': 'resultedit.fpk_/STATUS.xts', 'image': 'parson_hot', 'style': 'personality',
                 'jp': '熱血', 'en': 'HOT-BLOOD'})
    for x in ('resultedit.fpk_/STATUS.xts', 'resultedit.fpk_/xCLASSUP.xts'):
        jobs.append({'xts': x, 'image': 'class_shoui', 'style': 'rank_plate', 'jp': '少尉', 'en': ['2nd', 'Lieutenant']})
    WORD = {'armor': ('防御', ['ARMOR', None]), 'cp': ('コンディションポイント', ['CP', 'Condition Pts']),
            'infighting': ('格闘', ['INFIGHTING', None]), 'mainweapon': ('射撃', ['MAIN WEAPON', None]),
            'mobility': ('機動', ['MOBILITY', None]), 'nt': ('ニュータイプ', ['NT', 'Newtype'])}
    for x in ('abilities.fpk_/ABI_30_ABILITY.xts', 'abilities2.fpk_/A2_50_ABILITY.xts', 'mainmenu.fpk_/MM_21_ABILITY.xts',
              'pilot_parameter.fpk_/pilot_parameter.xts', 'pause.fpk_/SKILL.xts'):
        for img, (jp, e) in WORD.items():
            jobs.append({'xts': x, 'image': img, 'style': 'stat_word', 'jp': jp, 'en': e})
    # result-edit (ABILITIES SETTING) guide and skill-requirement box
    jobs.append({'xts': 'resultedit.fpk_/TITLE.xts', 'image': 'edit_button', 'style': 'ops', 'jp': 'BEFORE',
                 'en': 'RESET', 'ops': [{'rect': [38, 43, 80, 59], 'text': 'RESET', 'align': 'left',
                                         'outline': [20, 20, 40], 'dy': 1, 'heavy': True}]})
    jobs.append({'xts': 'resultedit.fpk_/xJOUKEN.xts', 'image': 'edit_06', 'style': 'ops', 'jp': '必要',
                 'en': 'Need', 'ops': [{'rect': [4, 4, 59, 25], 'text': 'Need'}]})
    jobs.append({'xts': 'resultedit.fpk_/xJOUKEN.xts', 'image': 'edit_05', 'style': 'ops',
                 'jp': '射撃 / 格闘 / 防御 / 機動 / スキル取得条件', 'en': 'Shoot / Melee / Def. / Mobil. / Skill Req.',
                 'ops': [{'rect': [3, 4, 50, 25], 'text': 'Shoot'}, {'rect': [61, 3, 104, 24], 'text': 'Melee'},
                         {'rect': [5, 35, 48, 56], 'text': 'Def.'}, {'rect': [62, 35, 105, 56], 'text': 'Mobil.'},
                         {'rect': [0, 93, 85, 109], 'text': 'Skill Req.', 'align': 'left', 'bold': False}]})
    # faction name plates: rule + katakana reading under the official English name removed
    for p in sorted(glob.glob(os.path.join(FPK, 'abilities.pack.fpk_', 'status_icon.fpk_', '*.xts'))):
        b = os.path.basename(p)
        if not b.startswith(('army_', 'select_')):
            continue
        x = 'abilities.pack.fpk_/status_icon.fpk_/' + b
        for img in only_image(x):
            if not img.startswith('mark_'):
                jobs.append({'xts': x, 'image': img, 'style': 'faction', 'jp': '(katakana reading)', 'en': ''})
    for j in jobs:
        assert j['image'] in only_image(j['xts']), j
    json.dump(jobs, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(jobs), 'jobs ->', OUT)


if __name__ == '__main__':
    main()
