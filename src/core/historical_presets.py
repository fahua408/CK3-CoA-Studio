"""Built-in library of 16 authentic European historical Coats of Arms from Wikimedia Commons (Public Domain / CC)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image

from src.core.config import get_resource_path
from src.core.image_ops import load_oriented_rgba


@dataclass
class HistoricalPreset:
    """Metadata and image loader for a famous European historical Coat of Arms."""

    preset_id: str
    name: str
    dynasty_or_realm: str
    description: str
    generator: Callable[[int], Image.Image]


def _make_asset_loader(preset_id: str) -> Callable[[int], Image.Image]:
    def _load(size: int = 512) -> Image.Image:
        path = get_resource_path(f"assets/historical/{preset_id}.png")
        img = load_oriented_rgba(path)
        if size > 0 and img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        return img

    return _load


HISTORICAL_PRESETS: list[HistoricalPreset] = [
    HistoricalPreset(
        preset_id="hist_spain_bourbon",
        name="西班牙波旁王室大联合全徽（1700–1761 历史原图）",
        dynasty_or_realm="西班牙波旁王朝 · 腓力五世",
        description="维基共享历史原图：集卡斯蒂利亚、莱昂、阿拉贡、西西里、奥地利、勃艮第、佛兰德斯、蒂罗尔、格拉纳达与中央法兰西波旁三百合，外环金羊毛骑士团项链、勃艮第十字与双狮。",
        generator=_make_asset_loader("hist_spain_bourbon"),
    ),
    HistoricalPreset(
        preset_id="hist_charles_v_hre",
        name="神圣罗马帝国查理五世大复合皇室纹章（历史原图）",
        dynasty_or_realm="哈布斯堡王朝 · 查理五世 (Charles V)",
        description="维基共享历史原图：双头黑鹰与神罗皇冠托举哈布斯堡-西班牙大复合盾徽，两侧配赫拉克勒斯之柱（PLVS OVLTRE 新大陆格言）与金羊毛勋章。",
        generator=_make_asset_loader("hist_charles_v_hre"),
    ),
    HistoricalPreset(
        preset_id="hist_austria_habsburg",
        name="奥地利哈布斯堡帝国双头鹰全徽（历史原图）",
        dynasty_or_realm="哈布斯堡-洛林皇室",
        description="维基共享历史原图：头戴鲁道夫皇冠的哈布斯堡双头鹰，双翼环绕匈牙利、波希米亚、威尼斯、加利西亚等帝国领地盾徽，胸前为哈布斯堡-奥地利-洛林三分核心盾。",
        generator=_make_asset_loader("hist_austria_habsburg"),
    ),
    HistoricalPreset(
        preset_id="hist_hre_emperor",
        name="神圣罗马帝国霍亨斯陶芬皇室黑鹰（历史原图）",
        dynasty_or_realm="霍亨斯陶芬王朝 · 腓特烈一世/二世",
        description="维基共享历史原图：中世纪盛期神圣罗马帝国金底单头/双头皇室黑鹰，胸前嵌霍亨斯陶芬三黑狮家族盾。",
        generator=_make_asset_loader("hist_hre_emperor"),
    ),
    HistoricalPreset(
        preset_id="hist_byzantium_eagle",
        name="东罗马 / 拜占庭巴列奥略皇室双头鹰（历史原图）",
        dynasty_or_realm="巴列奥略王朝 (Palaiologos)",
        description="维基共享历史原图：帝国绯红底配黄金双头鹰，胸前圆章嵌巴列奥略王朝希腊文连字徽记（ΠΑΛΑΙΟΛΟΓΟΣ）。",
        generator=_make_asset_loader("hist_byzantium_eagle"),
    ),
    HistoricalPreset(
        preset_id="hist_byzantium_4b",
        name="东罗马 / 拜占庭帝国四B金十字军旗（历史原图）",
        dynasty_or_realm="东罗马帝国 · 君士坦丁堡",
        description="维基共享历史原图：绯红底黄金正十字配四个对称火镰/希腊字母 Β（万王之王，统御诸王）。",
        generator=_make_asset_loader("hist_byzantium_4b"),
    ),
    HistoricalPreset(
        preset_id="hist_england_france_union",
        name="英法百年战争四分联统王室纹章（1399–1603 历史原图）",
        dynasty_or_realm="金雀花 / 兰开斯特 / 都铎王室",
        description="维基共享历史原图：左上右下法兰西三朵金百合 + 右上左下英格兰三头金狮，英王宣称法兰西王位时期的经典四分联统盾徽。",
        generator=_make_asset_loader("hist_england_france_union"),
    ),
    HistoricalPreset(
        preset_id="hist_england_plantagenet",
        name="英格兰金雀花王朝三金狮王室纹章（历史原图）",
        dynasty_or_realm="金雀花王朝 · 狮心王理查一世",
        description="维基共享历史原图：1198 年狮心王理查一世确立的英格兰皇家绯红底配三头蓝舌蓝爪迈步凝视金狮。",
        generator=_make_asset_loader("hist_england_plantagenet"),
    ),
    HistoricalPreset(
        preset_id="hist_france_royal",
        name="法兰西王国波旁/瓦卢瓦三金百合纹章（历史原图）",
        dynasty_or_realm="卡佩 / 瓦卢瓦 / 波旁王室",
        description="维基共享历史原图：法兰西王国经典皇家深蓝底配三朵鎏金鸢尾百合花（Fleur-de-lis）。",
        generator=_make_asset_loader("hist_france_royal"),
    ),
    HistoricalPreset(
        preset_id="hist_jerusalem",
        name="耶路撒冷十字军王国黄金五十字纹章（历史原图）",
        dynasty_or_realm="耶路撒冷王国 (Kingdom of Jerusalem)",
        description="维基共享历史原图：欧洲纹章学最著名的银底黄金T字大十字配四角小十字（Jerusalem Cross）。",
        generator=_make_asset_loader("hist_jerusalem"),
    ),
    HistoricalPreset(
        preset_id="hist_teutonic_grandmaster",
        name="条顿骑士团大团长黑金十字与神罗鹰盾（历史原图）",
        dynasty_or_realm="条顿骑士团国 (Deutscher Orden)",
        description="维基共享历史原图：银白底黑铁正十字，内嵌百合金十字与神罗皇帝腓特烈二世御赐的中央金底黑鹰小盾。",
        generator=_make_asset_loader("hist_teutonic_grandmaster"),
    ),
    HistoricalPreset(
        preset_id="hist_savoy_duchy",
        name="萨伏依公国复合大纹章（含耶路撒冷/塞浦路斯/萨克森 历史原图）",
        dynasty_or_realm="萨伏依王朝 (House of Savoy)",
        description="维基共享历史原图：复合西发里亚白马、萨克森王冠条纹、耶路撒冷、卢西尼昂狮与中央萨伏依红底白十字核心盾。",
        generator=_make_asset_loader("hist_savoy_duchy"),
    ),
    HistoricalPreset(
        preset_id="hist_castile",
        name="卡斯蒂利亚王国三塔黄金城堡（历史原图）",
        dynasty_or_realm="伊比利亚 · 卡斯蒂利亚王冠领",
        description="维基共享历史原图：绯红底配精致石砖纹理与蓝门蓝窗的三塔黄金城堡。",
        generator=_make_asset_loader("hist_castile"),
    ),
    HistoricalPreset(
        preset_id="hist_leon",
        name="莱昂王国戴冠紫红直立雄狮（历史原图）",
        dynasty_or_realm="伊比利亚 · 莱昂王国",
        description="维基共享历史原图：银白底配头戴王冠、红舌红爪的紫红色直立咆哮雄狮（顶配皇家宝石王冠）。",
        generator=_make_asset_loader("hist_leon"),
    ),
    HistoricalPreset(
        preset_id="hist_aragon",
        name="阿拉贡王国金红条纹盾徽（Senyera 历史原图）",
        dynasty_or_realm="伊比利亚 · 阿拉贡王冠领",
        description="维基共享历史原图：黄金底配四道垂直绯红条纹。",
        generator=_make_asset_loader("hist_aragon"),
    ),
    HistoricalPreset(
        preset_id="hist_navarre",
        name="纳瓦拉王国黄金锁链与绿宝石盾徽（历史原图）",
        dynasty_or_realm="伊比利亚 · 纳瓦拉王国",
        description="维基共享历史原图：绯红底配立体环形黄金锁链方阵与中央翡翠绿宝石。",
        generator=_make_asset_loader("hist_navarre"),
    ),
]


def get_historical_preset(preset_id: str) -> HistoricalPreset:
    for p in HISTORICAL_PRESETS:
        if p.preset_id == preset_id:
            return p
    return HISTORICAL_PRESETS[0]
