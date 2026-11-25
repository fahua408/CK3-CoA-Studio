"""Built-in visual step-by-step beginner tutorial dialog with real in-game screenshots."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig, get_resource_path


class TutorialDialog(QDialog):
    """Foolproof 3-step visual guide for players on how to convert and paste CoA into CK3."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("新手必看：3 步把图片变成游戏纹章 — 十字军之王3纹章生成工坊")
        self.resize(980, 780)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Top Title Banner
        header = QFrame(self)
        header.setObjectName("PairBanner")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(2)

        title = QLabel("🎮 保姆级 3 步傻瓜式教程：如何把任意图片（如卡皮巴拉）放进 CK3 变成纹章？")
        title.setStyleSheet("font-size: 15.5px; font-weight: 800; color: #E6C775;")
        subtitle = QLabel("不用记任何命令行！按下面 3 步操作，第一次玩的萌新也能 10 秒搞定。")
        subtitle.setStyleSheet("font-size: 12px; color: #B6BFC9;")
        hl.addWidget(title)
        hl.addWidget(subtitle)
        root.addWidget(header)

        # Scrollable tutorial body
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(2, 2, 6, 2)
        cl.setSpacing(10)

        # Step 1 & Step 2 side by side or compact stacked
        cl.addWidget(
            self._make_step_card(
                "第一步：点顶部「📷 正方形截图」或导入图片（自动锁死 1:1 正方形防变形）",
                "• 点击软件顶部金色 <b>「📷 正方形截图」</b>（或 <code>Ctrl+Shift+A</code>）框选图片（如卡皮巴拉）→ "
                "点 <b>「💾 保存 1:1 图片」</b>，软件会自动生成对应的 <code>.txt</code> 纹章代码。<br>"
                "• <b>为什么要正方形？</b>因为 CK3 游戏纹章底图是 <code>1:1</code> 正方形，长方形直接转会被拉扁，本工具已自动帮你锁定 1:1。",
            )
        )

        cl.addWidget(
            self._make_step_card(
                "第二步：点绿色按钮「📋 一键复制完整纹章代码」（切勿用记事本手动打开复制！）",
                "• <span style='color:#FCD34D;'><b>⚠️ 防卡死</b></span>：纹章代码有 <b>5 万～7 万行</b>，<b>千万不要</b>用系统记事本打开全选复制（会卡死）！直接点本软件的绿色复制按钮，0.1 秒完成。<br>"
                "• <span style='color:#6EE7B7;'><b>⚠️ 家族纹章 vs 领地旗帜（最易踩坑）</b></span>：改 <b>家族/宗族纹章</b>（默认）<b>不勾选</b> <code>领地旗帜 (-t)</code>；"
                "改 <b>伯爵领/公国/王国/帝国的领地旗帜</b> 必须在右侧 <b>勾选 <code>[✓] 领地旗帜 (-t)</code></b> 点生成后再复制，否则游戏里点粘贴没反应！",
            )
        )

        # Step 3 with side-by-side real in-game screenshots
        step3_card = QFrame(content)
        step3_card.setObjectName("PanelCard")
        s3l = QVBoxLayout(step3_card)
        s3l.setContentsMargins(12, 10, 12, 10)
        s3l.setSpacing(8)

        s3_title = QLabel("第三步：进入 CK3 游戏纹章界面，点击右下角「从剪贴板粘贴」（看下图红箭头）")
        s3_title.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #E6C775;")
        s3l.addWidget(s3_title)

        s3_desc = QLabel(
            "打开《十字军之王 3》进入 <b>统治者设计器 → 设计你自己的纹章</b>（或游戏内点纹章旁边的自定义按钮），"
            "点击<b>右下角红箭头指的「从剪贴板粘贴」</b>。<b>耐心等 1～3 秒加载</b>（游戏在渲染几万个色块，短暂顿一下属正常现象），"
            "卡皮巴拉就会完美出现在纹章、旗帜与角色盾牌上了！"
        )
        s3_desc.setWordWrap(True)
        s3_desc.setTextFormat(Qt.TextFormat.RichText)
        s3_desc.setStyleSheet("color: #E6E3DC; font-size: 12px;")
        s3l.addWidget(s3_desc)

        imgs_row = QHBoxLayout()
        imgs_row.setSpacing(10)
        imgs_row.addWidget(
            self._make_image_box(
                "assets/ck3_paste_step1.jpg",
                "① 点击游戏右下角红箭头所指的【从剪贴板粘贴】",
            ),
            1,
        )
        imgs_row.addWidget(
            self._make_image_box(
                "assets/ck3_paste_step2.jpg",
                "② 等待 1~3 秒后，卡皮巴拉完美变成游戏纹章与盾牌！",
            ),
            1,
        )
        s3l.addLayout(imgs_row)
        cl.addWidget(step3_card)

        legal = QLabel(
            "⚖️ 免责与致谢：本软件为免费开源图形化前端，底层转换由第三方工具 coaConverter (by Perondas) 提供；"
            "《十字军之王 III》(Crusader Kings III) 游戏画面与商标归 Paradox Interactive AB 所有，本项目为玩家非官方辅助工具。"
        )
        legal.setWordWrap(True)
        legal.setStyleSheet("color: #8E96A4; font-size: 11px; padding: 2px 4px;")
        cl.addWidget(legal)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # Footer bar
        footer = QHBoxLayout()
        self._startup_chk = QCheckBox("下次启动软件时自动弹出本新手教程（随时可点顶部「📖 新手教程」查看）")
        self._startup_chk.setChecked(self._config.show_tutorial_on_startup)
        self._startup_chk.toggled.connect(self._on_toggle_startup)
        footer.addWidget(self._startup_chk)
        footer.addStretch()

        ok_btn = QPushButton("✓ 我学会了，开始制作纹章！")
        ok_btn.setObjectName("PrimaryGoldBtn")
        ok_btn.clicked.connect(self.accept)
        footer.addWidget(ok_btn)
        root.addLayout(footer)

    def _make_step_card(self, title_text: str, body_html: str) -> QFrame:
        card = QFrame()
        card.setObjectName("PanelCard")
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        t = QLabel(title_text)
        t.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #E6C775;")
        b = QLabel(body_html)
        b.setWordWrap(True)
        b.setTextFormat(Qt.TextFormat.RichText)
        b.setStyleSheet("color: #E6E3DC; font-size: 12px;")
        l.addWidget(t)
        l.addWidget(b)
        return card

    def _make_image_box(self, rel_asset: str, caption: str) -> QFrame:
        box = QFrame()
        box.setStyleSheet(
            "QFrame { background: #101318; border: 1px solid #282E3A; border-radius: 8px; }"
        )
        vl = QVBoxLayout(box)
        vl.setContentsMargins(6, 6, 6, 6)
        vl.setSpacing(5)

        img_lbl = QLabel()
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = get_resource_path(rel_asset)
        if path.is_file():
            pm = QPixmap(str(path))
            if not pm.isNull():
                img_lbl.setPixmap(
                    pm.scaled(
                        440,
                        248,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        vl.addWidget(img_lbl)

        cap_lbl = QLabel(caption)
        cap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cap_lbl.setStyleSheet("color: #6EE7B7; font-weight: 600; font-size: 11.5px; border: none;")
        vl.addWidget(cap_lbl)
        return box

    def _on_toggle_startup(self, checked: bool) -> None:
        self._config.show_tutorial_on_startup = checked
        self._config.save()
