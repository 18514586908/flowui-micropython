# ============================================================
# FlowUI v2.0 - MicroPython OLED 用户界面框架
# ============================================================
# 设计灵感来自:
#   https://github.com/AstraThreshold/oled-ui-astra (C++/STM32)
#
# 适用于:
#   - 主控: ESP32（需支持 TouchPad 电容触摸）
#   - 屏幕: SSD1306 OLED 128×64, I2C 接口
#
# 版本历史:
#   v0.1 - 初始版本，基础菜单导航
#   v1.0 - 重构，引入 Config+HAL 架构、App 系统、调试模式
#   v1.1 - 圆角正方形磁贴、滑动过渡、超长文本滚动
#   v2.0 - 中文显示、双缓冲过渡、选择器高度优化、中文调试日志
#
# 文件组织（按出现顺序）:
#   1. Config      - UI 配置中心（所有可调参数）
#   2. HAL         - 硬件抽象层（OLED + 按键）
#   3. Animation   - 指数缓动动画工具
#   4. DrawUtils   - 圆角矩形绘图工具
#   5. Selector    - 选择器/高亮条（索引管理 + 动画）
#   6. Camera      - 摄像机/视口（列表滚动居中）
#   7. Menu        - 菜单节点（树形结构）
#   8. Launcher    - 主控制器（统筹导航、渲染、动画）
#   9. App         - 应用面板基类（用户继承）
# ============================================================

# ── 标准库导入 ──────────────────────────────────────────────
import math      # 数学运算：用于动画插值的浮点计算、圆角矩形中的坐标运算
import time      # 时间相关：time.ticks_ms() 计时、time.sleep_ms() 帧间隔
import gc        # 垃圾回收：gc.mem_free() 获取空闲内存（调试用）
from machine import Pin, SoftI2C, TouchPad  # ESP32 硬件控制：GPIO、软件 I2C、电容触摸
import ssd1306   # SSD1306 OLED 驱动库，提供 I2C 通信和 FrameBuffer
import framebuf  # FrameBuffer 帧缓冲区，提供 fill/pixel/line/text/blit 等绘图原语


# ============================================================
# Config - UI 配置类
# ============================================================
# 集中管理所有 UI 相关的可调参数。
# 每个参数都有合理的默认值，开发者可以直接使用默认值快速上手。
# 如需自定义，在创建 HAL 之前修改 Config 实例：
#
#   cfg = Config()
#   cfg.scroll_speed = 40      # 放慢滚动速度
#   cfg.light_mode = True       # 开启浅色模式
#   hal = HAL(cfg, ...)         # 将 cfg 传入 HAL
#
# 注意：HAL 在初始化时读取 Config 的值，
#       后续修改 Config 不会影响已创建的 HAL。
# ============================================================
class Config:
    """
    UI 配置类，所有界面参数集中在这里调整。

    参数按功能分为 7 组：
    1. 屏幕参数     - 屏幕尺寸
    2. 弹出提示参数  - PopInfo 动画和样式
    3. 过渡动画参数  - 滑动过渡方式
    4. 选择器参数   - 列表高亮条样式
    5. 列表菜单参数  - 行高、滚动速度
    6. 磁贴菜单参数  - Tile 卡片尺寸
    7. 显示模式     - 浅色/深色模式
    """

    # __slots__ 限制实例只能有这些属性，节省 RAM（MicroPython 中每个实例
    # 的 __dict__ 约 100+ bytes，__slots__ 将属性直接存储在元组中，大幅减少开销）
    __slots__ = (
        "screen_width", "screen_height",          # 屏幕尺寸
        "pop_margin", "pop_radius", "pop_speed", "pop_duration",  # 弹出提示
        "fade_speed", "transition_buffer",         # 过渡动画
        "selector_radius", "selector_margin", "selector_height",  # 选择器
        "item_height", "scroll_speed",              # 列表菜单
        "tile_width", "tile_height", "tile_margin", "tile_top_margin",  # 磁贴
        "bar_height", "tile_anim_speed",            # 磁贴进度条和动画
        "light_mode",                              # 显示模式
    )

    def __init__(self):
        """
        初始化所有参数为默认值。
        这些值针对 128×64 SSD1306 和 ESP32 进行了调优，
        大多数情况下无需修改。
        """
        # ── 屏幕参数 ──────────────────────────────────────
        self.screen_width = 128   # OLED 宽度（像素），SSD1306 固定 128
        self.screen_height = 64   # OLED 高度（像素），SSD1306 固定 64

        # ── 弹出提示（PopInfo）参数 ──────────────────────
        self.pop_margin = 4       # 弹出框文字与边框之间的内边距（像素）
        self.pop_radius = 4       # 弹出框圆角半径（像素），越大越圆
        self.pop_speed = 60       # 弹出框滑入/滑出动画速度（1-100，越大越快）
        self.pop_duration = 600   # 弹出框显示时长（毫秒），超时自动关闭

        # ── 过渡动画参数 ──────────────────────────────────
        self.fade_speed = 80       # 淡入淡出速度（1-100，越大越快）
        self.transition_buffer = True
        # ↑ 列表菜单滑动过渡方式：
        #   True  = 双缓冲预渲染（流畅，占 ~4KB 额外 RAM，推荐）
        #   False = 逐帧渲染（兼容，每帧重绘两个菜单，RAM 紧张时使用）

        # ── 选择器（高亮条）参数 ──────────────────────────
        self.selector_radius = 4    # 列表高亮条的圆角半径（像素）
        self.selector_margin = 2    # 列表高亮条距屏幕左右边缘的边距（像素）
        self.selector_height = 18   # 列表高亮条的高度（像素）
        # ↑ v2.0 从 14 改为 18，以完整容纳 16×16 中文字符

        # ── 列表菜单参数 ──────────────────────────────────
        self.item_height = 16      # 列表每项占用的高度（像素），含文字和上下间距
        self.scroll_speed = 80     # 选择器/摄像机滚动动画速度（1-100，越大越快）

        # ── 磁贴菜单（Tile）参数 ─────────────────────────
        self.tile_width = 36       # 磁贴卡片宽度（像素），v1.1 改为 36 正方形
        self.tile_height = 36      # 磁贴卡片高度（像素），v1.1 改为 36 正方形
        self.tile_margin = 12      # 磁贴卡片之间的水平间距（像素）
        self.tile_top_margin = 12  # 磁贴距屏幕顶部的偏移（像素），为进度条留空间
        self.bar_height = 3        # 磁贴顶部进度条的厚度（像素）
        self.tile_anim_speed = 60  # 磁贴选中时放大动画的速度（1-100）

        # ── 显示模式 ──────────────────────────────────────
        self.light_mode = False
        # ↑ False = 黑底白字（深色/默认模式）
        #   True  = 白底黑字（浅色模式），HAL 会自动反转所有颜色


# ============================================================
# HAL - Hardware Abstraction Layer（硬件抽象层）
# 封装 OLED 显示和按键输入，隐藏底层硬件细节
# ============================================================
# HAL - Hardware Abstraction Layer（硬件抽象层）
# ============================================================
# 封装 OLED 显示和按键输入，隐藏底层硬件细节。
#
# 核心职责：
# 1. 提供统一的绘图 API（像素、线条、矩形、文字）
# 2. 自动处理浅色模式颜色反转
# 3. 自动检测中文字符并调用 cn_font 渲染
# 4. 按键状态机（单击/长按检测）
# 5. 提供离屏 FrameBuffer 切换（用于过渡双缓冲预渲染）
#
# 使用方法：
#   hal = HAL(cfg, scl_pin=22, sda_pin=21)
#   hal.fill(0)        # 清屏
#   hal.text("你好", 0, 0, 1)  # 自动显示中文
#   hal.show()         # 刷新到 OLED
# ============================================================
class HAL:
    """
    硬件抽象层（Hardware Abstraction Layer）。

    统一封装了 SSD1306 OLED 的绘图操作和 GPIO 按键的扫描检测。
    所有绘图方法接受逻辑颜色（0=黑, 1=白），
    light_mode 开启时自动取反，外部代码无需关心颜色模式。

    触摸引脚的初始化由用户在 main.py 中自行完成，
    本层只负责物理按键的扫描。
    """

    def __init__(self, config=None, scl_pin=22, sda_pin=21, i2c_addr=0x3C,
                 btn_up=18, btn_down=19):
        """
        初始化硬件：I2C → OLED → GPIO 按键 → 状态机变量

        Args:
            config:     Config 实例。如果为 None，使用默认配置（128×64）
            scl_pin:    I2C 时钟引脚，默认 GPIO22
            sda_pin:    I2C 数据引脚，默认 GPIO21
            i2c_addr:   OLED I2C 设备地址，默认 0x3C（大部分 SSD1306 模块）
            btn_up:     物理上键 GPIO 引脚，默认 GPIO18。设为 None 禁用
            btn_down:   物理下键 GPIO 引脚，默认 GPIO19。设为 None 禁用
        """
        # ── 配置 ──────────────────────────────────────────────
        # 保存配置引用。如果未传入 Config，使用默认配置（128×64）
        self.config = config if config is not None else Config()

        # ── I2C 总线初始化 ───────────────────────────────────
        # 使用 SoftI2C（软件模拟 I2C），可以任意指定 GPIO 引脚
        i2c = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin))

        # ── OLED 初始化 ──────────────────────────────────────
        # 创建 SSD1306 对象，会自动初始化显示器
        self.oled = ssd1306.SSD1306_I2C(
            self.config.screen_width,
            self.config.screen_height,
            i2c,
            addr=i2c_addr
        )

        # 屏幕尺寸常量，供外部代码直接引用
        self.width = self.config.screen_width    # 128 像素
        self.height = self.config.screen_height  # 64 像素

        # 获取 OLED 底层的 FrameBuffer 和原始 bytearray
        # self.buffer: 完整的 bytearray（1024 bytes），
        #              含 I2C 控制字节 0x40 开头，通过 oled.show() 发送
        # self.fb:     FrameBuffer 对象，所有绘图方法委托给它
        self.buffer = self.oled.buffer
        self.fb = self.oled.framebuf

        # ── 物理按键初始化 ──────────────────────────────────
        # 上拉输入模式：不按 = 高电平 (1)，按下 = 低电平 (0)
        # 这是 ESP32 GPIO 的标准按键接线方式
        self.btn_up = Pin(btn_up, Pin.IN, Pin.PULL_UP)      # 向上键
        self.btn_down = Pin(btn_down, Pin.IN, Pin.PULL_UP)  # 向下键

        # ── 按键状态机变量 ──────────────────────────────────
        # 状态机通过 last_update 控制 50ms 防抖间隔，
        # 通过 _key_states 跟踪按键是否被按下，
        # 通过 _key_held 记录按下时刻以区分单击和长按。
        self._keys = [0, 0]           # 事件缓存：[0]UP 键, [1]DOWN 键
        self._key_states = [True, True]   # True=空闲, False=已按下（正在按住）
        self._key_held = [0, 0]       # 按键按下的时刻（time.ticks_ms()）
        self.last_update = 0          # 上次 key_scan 调用的时刻

        # ── 按键事件标志 ────────────────────────────────────
        # 这些标志由 key_scan() 在每帧更新，
        # 外部代码（如 main.py 的触摸循环）读取这些标志来判断用户操作
        self.btn_up_clicked = False   # 上键短按（按下 < 500ms 后松开）
        self.btn_down_clicked = False # 下键短按
        self.btn_up_pressed = False   # 上键长按（按住 >= 500ms 且未松开）
        self.btn_down_pressed = False # 下键长按

        # ── 中文模块缓存 ────────────────────────────────────
        # cn_font 模块在首次遇到中文字符时按需导入，
        # 之后缓存在 _cn_font 中避免重复 import
        self._cn_font = None

        print("[HAL] 硬件初始化完成：屏幕 {}x{}".format(self.width, self.height))

    # ══════════════════════════════════════════════════════════
    # 绘图 API（全部委托给 FrameBuffer）
    # ══════════════════════════════════════════════════════════
    # 所有公共绘图方法都接受 color=0（黑）/1（白），
    # 内部通过 _c() 自动处理浅色模式反转。
    # ══════════════════════════════════════════════════════════

    def _c(self, color):
        """
        颜色转换：在浅色模式下对颜色取反。

        浅色模式（light_mode=True）时：
          用户调用 fill(0)（逻辑黑）→ 实际 fill(1)（物理白）
          用户调用 text("Hi", 0, 0, 1)（逻辑白）→ 实际 text(..., 0)（物理黑）

        这样用户的代码在两种模式下完全一致，只需切换 light_mode。
        """
        if self.config.light_mode:
            return 0 if color else 1  # 颜色取反：0↔1
        return color                  # 深色模式：颜色不变

    def fill(self, color):
        """
        用指定颜色填充整个屏幕。

        Args:
            color: 逻辑颜色。0 = 黑色（填充），1 = 白色（清空）
        """
        self.fb.fill(self._c(color))

    def pixel(self, x, y, color):
        """
        在指定坐标绘制一个像素点。

        Args:
            x: 水平坐标（0=最左）
            y: 垂直坐标（0=最上）
            color: 逻辑颜色 0/1
        """
        self.fb.pixel(x, y, self._c(color))

    def hline(self, x, y, w, color):
        """
        从 (x,y) 向右绘制一条 w 像素宽的水平线。

        Args:
            x: 起始 X 坐标
            y: 起始 Y 坐标
            w: 线段长度（像素）
            color: 逻辑颜色
        """
        self.fb.hline(x, y, w, self._c(color))

    def vline(self, x, y, h, color):
        """
        从 (x,y) 向下绘制一条 h 像素高的垂直线。

        Args:
            x: 起始 X 坐标
            y: 起始 Y 坐标
            h: 线段高度（像素）
            color: 逻辑颜色
        """
        self.fb.vline(x, y, h, self._c(color))

    def rect(self, x, y, w, h, color):
        """
        绘制空心矩形框。

        Args:
            x,y: 左上角坐标
            w: 矩形宽度
            h: 矩形高度
            color: 逻辑颜色
        """
        self.fb.rect(x, y, w, h, self._c(color))

    def fill_rect(self, x, y, w, h, color):
        """
        绘制实心矩形（填充内部）。

        Args:
            x,y: 左上角坐标
            w: 矩形宽度
            h: 矩形高度
            color: 逻辑颜色
        """
        self.fb.fill_rect(x, y, w, h, self._c(color))

    def _text_ascii(self, s, x, y, color):
        """
        内部方法：直接绘制 ASCII 字符串。

        与公共 text() 不同，此方法直接调用 framebuf.text，
        不对 color 做二次 _c() 转换。
        这避免了 cn_font.draw_text 中英文绘制时的双重反转。

        Args:
            s: ASCII 字符串
            x,y: 文字左上角坐标
            color: 已经过 _c() 转换的物理颜色（0 或 1）
        """
        self.fb.text(s, x, y, color)

    def text(self, s, x, y, color=1):
        """
        在指定位置绘制字符串，自动检测并支持中英混合显示。

        工作原理：
        1. 遍历字符串检测是否包含 ASCII 码 > 127 的字符（中文）
        2. 如果不含中文：使用 framebuf 自带的 8×8 字体快速绘制
        3. 如果含中文：首次导入 cn_font 模块，然后调用 cn_font.draw_text
           cn_font 会逐个字符判断：中文用 16×16 点阵绘制，英文用 8×8 字体

        中文英文自动对齐基线：英文 y 偏移 +8，使英文底部与中文底部对齐。

        Args:
            s: 要绘制的字符串（纯英文或中英混合）
            x,y: 文字左上角坐标
            color: 逻辑颜色。默认 1（白色）
        """
        c = self._c(color)  # 转为物理颜色
        # 遍历检测是否有中文字符
        has_cn = False
        for ch in s:
            if ord(ch) > 127:      # 中文字符的 Unicode 值都大于 127
                has_cn = True
                break
        if has_cn:
            # ── 有中文：使用 cn_font 模块渲染 ──────────────
            if self._cn_font is None:
                import cn_font            # 按需导入，只导入一次
                self._cn_font = cn_font   # 缓存模块引用
            self._cn_font.draw_text(self, s, x, y, c)
        else:
            # ── 纯英文：使用 framebuf 内置字体 ─────────────
            self._text_ascii(s, x, y, c)

    def show(self):
        """
        将 FrameBuffer 中的像素数据通过 I2C 刷新到 OLED 屏幕。
        必须在所有绘制操作完成后调用一次。
        """
        self.oled.show()

    def set_framebuffer(self, fb):
        """
        临时切换绘图目标到指定的离屏 FrameBuffer。
        用于过渡动画的双缓冲预渲染。

        用法：
            hal.set_framebuffer(offscreen_fb)
            hal.fill(0)            # 在离屏 fb 上绘制
            menu.render(hal, ...)  # 渲染到离屏 fb
            hal.restore_framebuffer()  # 恢复主屏幕

        Args:
            fb: 目标 FrameBuffer 对象
        """
        self._original_fb = self.fb  # 保存当前主 fb
        self.fb = fb                 # 切换 fb

    def restore_framebuffer(self):
        """恢复绘图目标到 OLED 主屏幕的 FrameBuffer。"""
        if hasattr(self, "_original_fb"):
            self.fb = self._original_fb

    # ----- 按键扫描（状态机实现）-----
    def key_scan(self):
        """
        按键状态机扫描，50ms 间隔防抖
        检测三种事件：
        - CLICK（短按 < 500ms）→ btn_up/down_clicked = True
        - PRESS（长按 >= 500ms）→ btn_up/down_pressed = True
        - RELEASE → 清除状态
        """
        now = time.ticks_ms()  # 当前时间（ms）
        # 防抖：每 50ms 才扫描一次
        if now - self.last_update < 50:
            return
        self.last_update = now

        # 读取两个按键的当前电平（0=按下，1=松开）
        b_up = self.btn_up.value()
        b_down = self.btn_down.value()

        # 清空上次事件标志
        self.btn_up_clicked = False
        self.btn_down_clicked = False
        self.btn_up_pressed = False
        self.btn_down_pressed = False

        # 对 UP/DOWN 两个按键分别处理
        for i in range(2):
            val = b_up if i == 0 else b_down  # 当前引脚电平
            state = self._key_states[i]  # 之前是否空闲
            pressed = val == 0  # 低电平 = 按下

            if pressed and state:
                # 状态A：刚按下（之前空闲）
                self._keys[i] = 1  # 标记为 CLICK 待确认
                self._key_held[i] = now  # 记录按下时间
                self._key_states[i] = False  # 状态改为非空闲

            elif pressed and not state:
                # 状态B：持续按住
                if now - self._key_held[i] > 500:
                    self._keys[i] = 2  # 超过 500ms → PRESS

            elif not pressed and not state:
                # 状态C：松开了
                self._keys[i] = 3  # 标记为 RELEASE
                self._key_states[i] = True  # 状态恢复空闲

        # ---- 解析 UP 按键事件 ----
        if self._keys[0] == 1:
            self.btn_up_clicked = True  # 短按
        elif self._keys[0] == 2:
            self.btn_up_pressed = True  # 长按
        elif self._keys[0] == 3:
            # RELEASE 时：按住时间 < 500ms 也算 CLICK
            if self._key_held[0] > 0 and time.ticks_ms() - self._key_held[0] < 500:
                self.btn_up_clicked = True
            self._key_held[0] = 0  # 重置计时

        # ---- 解析 DOWN 按键事件 ----
        if self._keys[1] == 1:
            self.btn_down_clicked = True
        elif self._keys[1] == 2:
            self.btn_down_pressed = True
        elif self._keys[1] == 3:
            if self._key_held[1] > 0 and time.ticks_ms() - self._key_held[1] < 500:
                self.btn_down_clicked = True
            self._key_held[1] = 0

        # 清空事件缓存
        self._keys = [0, 0]


# ============================================================
# Animation - 动画插值工具类
# ============================================================
# FlowUI 中所有动画效果（选择器移动、菜单滚动、弹出框滑动、
# Tile 放大、过渡滑动）都基于指数缓动算法。
#
# 与线性移动相比，指数缓动的特点是"起始快、接近目标时变慢"，
# 产生类似物理阻尼的自然效果。即使帧率较低（10-30 FPS），
# 视觉上仍然感觉平滑。
# ============================================================

class Animation:
    """
    动画插值工具。
    
    使用指数缓动（Exponential Easing Out）实现平滑运动。
    所有方法都是静态的，可以直接调用。

    公式：
        pos += (target - pos) / factor
        factor = (100 - speed) / 10 + 1

    参数 speed 范围 1-100，映射到 factor 范围 10.9～1.1：
        speed=100 → factor≈1.1  → 每帧移动 90% 的剩余距离（几乎瞬间到达）
        speed=50  → factor≈6    → 每帧移动约 17% 的剩余距离
        speed=1   → factor≈10.9 → 每帧移动约 9% 的剩余距离（非常缓慢）
    
    典型应用：
        # 选择器 Y 位置缓动（int 版本，像素对齐）
        self.y = Animation.move_int(self.y, self.target_y, scroll_speed)
        
        # 弹出框 Y 位置缓动（float 版本，亚像素精度）
        self.popup_y = Animation.move(self.popup_y, self.popup_target_y, pop_speed)
    """

    @staticmethod
    def move(pos, target, speed):
        """
        一维指数缓动（浮点数版本）。

        返回 float 类型，适合亚像素精度的平滑移动。
        当 pos 与 target 的距离 < 1 时，直接返回 target 以避免无限接近。

        Args:
            pos:    当前位置（float）
            target: 目标位置（float）
            speed:  速度（1-100）。1=最慢，100=最快（瞬间到达）

        Returns:
            插值后的新位置（float）
        """
        if pos != target:
            # 如果距离小于 1，直接到达目标（防止无限逼近）
            if abs(pos - target) <= 1:
                return target
            # 计算 factor: speed(1-100) 映射到 factor(10.9~1.1)
            # speed=100: factor≈1.1 → 几乎瞬间
            # speed=1:   factor≈10.9 → 非常慢
            return pos + (target - pos) / ((100 - speed) / 10 + 1)
        return pos

    @staticmethod
    def move_int(pos, target, speed):
        """
        一维指数缓动（整数版本）。

        将 move() 的结果四舍五入取整，适合像素级别的平滑移动。
        用于选择器 Y 坐标、摄像机偏移、弹出框位置等需要整数像素对齐的场景。

        Args:
            pos:    当前位置（int）
            target: 目标位置（int）
            speed:  速度（1-100）

        Returns:
            插值后的新位置（int）
        """
        return int(round(Animation.move(pos, target, speed)))


# ============================================================
# DrawUtils - 高级绘图工具类
# ============================================================
# SSD1306 的 FrameBuffer 只支持矩形（fill_rect/rect），
# 不支持圆角矩形。本工具通过逐像素描点的方式实现圆角矩形。
#
# 圆角掩码（_round_masks）按半径缓存，
# 同一半径的圆角只需计算一次，后续直接复用。
# ============================================================

class DrawUtils:
    """
    高级绘图工具（静态方法集合）。

    在 SSD1306 上绘制圆角矩形（空心/实心）。
    圆角算法使用 1/4 圆的像素掩码，通过 (i+0.5)^2 + (j+0.5)^2 <= r^2
    判断像素是否位于圆内，比整数比较更精确（像素中心采样）。

    应用场景：
        - 列表菜单的高亮选择器（selector）
        - 磁贴菜单的卡片
        - 弹出提示 PopInfo
        - tile 磁贴的圆角正方形
    """

    # 类变量：缓存按半径计算好的圆角掩码
    # key = 半径 r (int)
    # value = 掩码矩阵 (list of list of bool)
    # 每个掩码是 r×r 的矩阵，True 表示该像素属于 1/4 圆区域
    _round_masks = {}

    @staticmethod
    def _get_mask(r):
        """
        获取或生成半径 r 的 1/4 圆掩码。

        使用像素中心采样：对于 r×r 区域中的像素 (i,j)，
        判断其中心 (i+0.5, j+0.5) 到原点 (0,0) 的距离平方是否 <= r^2。
        这比 (i+1)^2+(j+1)^2 <= r^2 在视觉上更平滑。

        Args:
            r: 圆角半径（像素）

        Returns:
            r×r 的 bool 矩阵，True = 属于圆角区域
        """
        # 先从缓存查找，避免重复计算
        mask = DrawUtils._round_masks.get(r)
        if mask is None:
            # 缓存未命中，计算新掩码
            mask = []
            r2 = r * r                     # 半径的平方
            for i in range(r):             # X 方向偏移
                row = []
                for j in range(r):         # Y 方向偏移
                    # 以像素中心 (i+0.5, j+0.5) 为采样点
                    row.append((i + 0.5) ** 2 + (j + 0.5) ** 2 <= r2)
                mask.append(row)
            DrawUtils._round_masks[r] = mask  # 存入缓存
        return mask

    @staticmethod
    def round_rect(hal, x, y, w, h, r, color):
        """
        绘制空心圆角矩形（仅边框）。

        原理：4 条直线边（跳过圆角区域）+ 4 个 1/4 圆弧。

        Args:
            hal:    HAL 硬件抽象实例（用于像素绘制）
            x, y:   矩形左上角坐标
            w, h:   矩形宽度和高度
            r:      圆角半径（像素）。如果半径超过短边的一半，自动缩小
            color:  逻辑颜色（0=黑, 1=白）
        """
        # 限制圆角半径不超过短边的一半，防止圆角重叠
        if r > min(w, h) // 2:
            r = min(w, h) // 2

        # ── 四条直线边（跳过圆角部分）──
        hal.hline(x + r, y, w - 2 * r, color)          # 上边
        hal.hline(x + r, y + h - 1, w - 2 * r, color)  # 下边
        hal.vline(x, y + r, h - 2 * r, color)           # 左边
        hal.vline(x + w - 1, y + r, h - 2 * r, color)  # 右边

        # ── 四个 1/4 圆弧 ──
        # 使用预计算掩码逐像素绘制
        mask = DrawUtils._get_mask(r)
        for i in range(r):      # X 方向偏移（0 ~ r-1）
            for j in range(r):  # Y 方向偏移（0 ~ r-1）
                if mask[i][j]:
                    # 左上角: 镜像到 (x+r-1-i, y+r-1-j)
                    hal.pixel(x + r - 1 - i, y + r - 1 - j, color)
                    # 右上角: 镜像到 (x+w-r+i, y+r-1-j)
                    hal.pixel(x + w - r + i, y + r - 1 - j, color)
                    # 左下角: 镜像到 (x+r-1-i, y+h-r+j)
                    hal.pixel(x + r - 1 - i, y + h - r + j, color)
                    # 右下角: 镜像到 (x+w-r+i, y+h-r+j)
                    hal.pixel(x + w - r + i, y + h - r + j, color)

    @staticmethod
    def fill_round_rect(hal, x, y, w, h, r, color):
        """
        绘制实心圆角矩形（填充内部）。

        原理：1 个大的中间矩形 + 4 个侧边条 + 4 个填充圆弧。
        这种方法比用 fill_rect 整体绘制再抠掉 4 个角更高效。

        Args:
            hal:    HAL 实例
            x, y:   左上角坐标
            w, h:   宽度和高度
            r:      圆角半径
            color:  逻辑颜色
        """
        # 限制圆角半径
        if r > min(w, h) // 2:
            r = min(w, h) // 2

        # ── 中间矩形主体（从 x+r 到 x+w-r，全高）──
        hal.fill_rect(x + r, y, w - 2 * r, h, color)
        # ── 左侧侧边条（从 y+r 到 y+h-r，宽度 r）──
        hal.fill_rect(x, y + r, r, h - 2 * r, color)
        # ── 右侧侧边条 ──
        hal.fill_rect(x + w - r, y + r, r, h - 2 * r, color)

        # ── 填充四个圆角部分 ──
        mask = DrawUtils._get_mask(r)
        for i in range(r):
            for j in range(r):
                if mask[i][j]:
                    # 左上
                    hal.pixel(x + r - 1 - i, y + r - 1 - j, color)
                    # 右上
                    hal.pixel(x + w - r + i, y + r - 1 - j, color)
                    # 左下
                    hal.pixel(x + r - 1 - i, y + h - r + j, color)
                    # 右下
                    hal.pixel(x + w - r + i, y + h - r + j, color)


# ============================================================
# App - 应用面板基类
# 所有功能面板（LED、Sensor、Motor 等）继承此类
# 通过 Menu.add_item(name, app=my_app) 绑定到磁贴/列表
# ============================================================
class App:
    """
    应用面板基类 - 继承此类的子类可以：
    - 被挂载到磁贴或列表项上（通过 Menu.add_item 的 app 参数）
    - 从磁贴打开时自动进入全屏面板模式
    - 长按 UP/GPIO33 返回菜单

    生命周期方法（按调用顺序）：
      1. on_open(launcher)    - 进入面板时调用（初始化用）
      2. update(launcher)     - 每帧调用（处理状态逻辑）
      3. render(hal)          - 每帧调用（绘制屏幕内容）
      4. handle_touch(pin, raw) - 触摸引脚触发时调用
      5. on_close(launcher)   - 退出面板时调用（清理用）

    最简单的用法示例：
        class LEDApp(App):
            def render(self, hal):
                hal.fill(0)
                hal.text("LED ON", 40, 28, 1)
    """

    def on_open(self, launcher):
        """进入应用时调用（初始化资源、重置状态）"""
        pass

    def on_close(self, launcher):
        """退出应用时调用（清理资源）"""
        pass

    def update(self, launcher):
        """每帧更新逻辑（状态机、定时器、动画等）"""
        pass

    def render(self, hal):
        """每帧绘制屏幕（自行 fill(0) 清屏后绘制）"""
        hal.fill(0)
        hal.text(self.__class__.__name__, 20, 28, 1)

    def handle_touch(self, hal):
        """
        触摸/按键事件处理（App 模式时由 Launcher.update 每帧调用）
        :param hal: HAL 实例，App 可通过 hal.btn_up_clicked 等读取输入
        子类按需重写
        """
        pass

    def handle_touch_pin(self, pin_index, raw_value):
        """
        触摸引脚事件处理（由 main.py 的触摸轮询循环直接调用）
        :param pin_index: 触摸引脚索引（0-3）
        :param raw_value: 原始触摸读数
        适合直接使用触摸引脚的场景，子类按需重写
        """
        pass


# ============================================================
# Camera - 视口摄像机
# 实现菜单平滑滚动（选择器在菜单项间移动时，整个菜单会平滑跟谁）
# ============================================================
# ============================================================
# Camera - 摄像机/视口滚动
# ============================================================
# 当菜单项超出屏幕范围时，Camera 负责平滑滚动视口，
# 使当前选中项保持可见且在屏幕中央。
#
# 列表模式（List）：垂直滚动（y 轴）
#   选中项居中公式：target_y = index * item_h - (screen_h - item_h) // 2
#   边界限制：0 <= target_y <= max_y（避免滚动超出内容）
#
# 磁贴模式（Tile）：水平滚动（x 轴）
#   选中项居中公式：target_x = index * (tile_width + tile_margin)
#   滚动量等于选中项前面所有项的宽度之和
# ============================================================

class Camera:
    """
    摄像机/视口滚动控制器。
    
    负责计算并平滑滚动视口偏移量，使当前选中的菜单项自动居中。
    分为 List（垂直）和 Tile（水平）两种模式。

    属性：
        x, y:        当前视口偏移（平滑动画中）
        target_x, target_y: 目标视口偏移（由 follow() 计算）
    """
    __slots__ = ("x", "y", "target_x", "target_y", "config")

    def __init__(self, config):
        """
        初始化摄像机，视口在 (0,0)。
        
        Args:
            config: Config 实例（读取 item_height、scroll_speed 等）
        """
        self.config = config
        self.x = 0          # 当前水平偏移（磁贴模式用）
        self.y = 0          # 当前垂直偏移（列表模式用）
        self.target_x = 0   # 目标水平偏移
        self.target_y = 0   # 目标垂直偏移

    def follow(self, selector, menu):
        """
        根据当前选中索引和菜单类型，计算目标视口偏移。

        列表模式：让选中项垂直居中
            公式：target_y = index * item_h - (screen_h - item_h) / 2
            限制首项和末项不露出空白（0 <= target_y <= max_y）

        磁贴模式：让选中磁贴水平居中
            公式：target_x = index * (tw + tm)
            限制不露出空白（0 <= target_x）

        Args:
            selector: Selector 实例（读取 selector.index）
            menu:     Menu 实例（读取 menu_type、item_count）
        """
        if menu and menu.menu_type == "tile":
            # ── 磁贴模式：水平滚动 ──────────────────────────
            tw = self.config.tile_width
            tm = self.config.tile_margin
            total = menu.item_count()
            total_w = total * tw + max(0, total - 1) * tm
            if total_w <= self.config.screen_width:
                # 总宽度小于屏幕，无需滚动
                self.target_x = 0
            else:
                # 滚动到选中项居中
                target = selector.index * (tw + tm)
                if target < 0:
                    target = 0
                self.target_x = target
        else:
            # ── 列表模式：垂直滚动 ──────────────────────────
            item_h = self.config.item_height
            screen_h = self.config.screen_height
            # 让选中项在屏幕垂直居中
            target = selector.index * item_h - (screen_h - item_h) // 2
            # 限制不超出内容边界
            max_y = menu.item_count() * item_h - screen_h
            if max_y < 0:
                max_y = 0
            if target < 0:
                target = 0
            elif target > max_y:
                target = max_y
            self.target_y = target

    def update(self, menu=None):
        """
        每帧调用：使用指数缓动将视口当前位置移向目标位置。

        Args:
            menu: 当前菜单（用于判断 tile/list 模式）
        """
        if menu and menu.menu_type == "tile":
            self.x = Animation.move_int(
                self.x, self.target_x, self.config.scroll_speed
            )
        else:
            self.y = Animation.move_int(
                self.y, self.target_y, self.config.scroll_speed
            )

    def get_pos(self):
        """
        获取当前视口偏移量。

        Returns:
            (cam_x, cam_y) 元组，分别传递给 Menu.render() 和 Selector.render()
        """
        return (self.x, self.y)

    def reset(self):
        """重置视口到 (0,0)（进入新菜单时调用）。"""
        self.x = 0
        self.y = 0
        self.target_x = 0
        self.target_y = 0


# ============================================================
# Selector - 选择器/高亮条
# ============================================================
# 列表模式下：在选中项位置绘制一个全行宽的圆角矩形白色高亮，
#   文字显示在白色背景上（黑色字），实现"选中"的视觉效果。
#   支持平滑滚动动画（指数缓动）。
#
# 磁贴模式下：不绘制额外高亮框，选中效果由 Menu.render_tile()
#   中的放大大卡动画承担。Selector 只负责绘制顶部进度条和
#   左右导航箭头。
#
# Tile 放大动画：
#   每次切换项时 tile_v_scale 从 0 开始，
#   每帧用 tile_anim_speed 速度插值到 tile_v_scale_target=4。
#   Menu.render_tile() 读取这个值决定选中项比其他项高多少。
# ============================================================

class Selector:
    """
    菜单选择器/高亮条。

    负责两件事：
    1. 管理当前选中项的索引（index）和选择器 Y 位置（y）
    2. 在列表模式下绘制白色圆角矩形高亮背景
    3. 在磁贴模式下绘制进度条和导航箭头
    4. 维护 Tile 放大动画状态（tile_v_scale）

    选中项索引切换时（go_next/go_prev），target_y 立即更新，
    但 y 通过指数缓动动画平滑移动，产生视觉上的滑动效果。

    属性：
        index:          当前选中项的索引（0-based）
        y / target_y:   当前/目标 Y 位置（像素）
        tile_v_scale:   磁贴选中放大的当前值（0~4，动画中）
        menu:           当前关联的 Menu 实例
    """

    __slots__ = ("index", "y", "target_y", "config", "menu",
                 "tile_v_scale", "tile_v_scale_target")

    def __init__(self, config):
        """
        初始化选择器：选中第一项，位置在屏幕顶部。

        Args:
            config: Config 实例
        """
        self.index = 0               # 当前选中项的索引（0=第一项）
        self.y = 0                   # 选择器当前 Y 位置（平滑动画中）
        self.target_y = 0            # 选择器目标 Y 位置
        self.config = config         # 配置引用（读取 item_height 等）
        self.menu = None             # 当前关联的菜单
        self.tile_v_scale = 0        # Tile 放大当前值（0=不放大）
        self.tile_v_scale_target = 4 # Tile 放大目标值（像素）

    def inject(self, menu):
        """
        将选择器关联到一个菜单
        :param menu: Menu 实例
        每次进入新菜单时调用，重置位置到第一项
        """
        self.menu = menu
        self.index = 0  # 默认选中第一项
        self.target_y = 0
        self.y = 0
        self.tile_v_scale = 0
        self.tile_v_scale_target = 4
        print("[Selector] 关联菜单：{}".format(menu.name))

    def go_next(self):
        """选中下一项（边界检查，不循环）"""
        if self.menu and self.index < self.menu.item_count() - 1:
            self.index += 1
            self.target_y = self.index * self.config.item_height
            self.tile_v_scale = 0

    def go_prev(self):
        """选中上一项（边界检查，不循环）"""
        if self.index > 0:
            self.index -= 1
            self.target_y = self.index * self.config.item_height
            self.tile_v_scale = 0

    def update(self):
        """每帧更新：Y 位置平滑移向目标位置"""
        self.y = Animation.move_int(self.y, self.target_y, self.config.scroll_speed)
        self.tile_v_scale = Animation.move_int(
            self.tile_v_scale, self.tile_v_scale_target, self.config.tile_anim_speed
        )

    def render(self, hal, cam_x, cam_y):
        if not self.menu:
            return
        if self.menu.menu_type == "tile":
            self._render_tile(hal, cam_x)
        else:
            self._render_list(hal, cam_y, cam_x)

    def _render_list(self, hal, cam_y, x_offset=0):
        sy = self.y - cam_y
        sh = self.config.selector_height
        # 仅在选择器可见时渲染
        if sy + sh <= 0 or sy >= hal.height:
            return
        item = self.menu.get_item(self.index)
        if not item:
            return
        has_child = self.menu.has_child(self.index)

        # 根据右侧是否显示 '>' 计算可用字符数
        right_space = 12 if has_child else 0
        max_chars = (hal.width - 10 - right_space) // 8
        label = item
        if len(item) > max_chars:
            scroll_chars = len(item) - max_chars
            t = time.ticks_ms() // 300  # 每 300ms 移动一个字符
            offset = t % (scroll_chars + 4)  # 末尾多停 4 拍
            if offset > scroll_chars:
                offset = scroll_chars
            label = item[offset:offset + max_chars]

        # 选择器高度范围内先清空背景，防止文字残影
        hal.fill_rect(x_offset, sy, hal.width, sh, 0)
        DrawUtils.fill_round_rect(
            hal,
            2 + x_offset,
            sy,
            hal.width - 4,
            sh,
            self.config.selector_radius,
            1,
        )
        # 文字在白框中垂直居中（根据中英文自适应高度）
        cn_h = 0
        for ch in label:
            if ord(ch) > 127:
                cn_h = 16
                break
        text_offset_y = (sh - (16 if cn_h else 8)) // 2
        hal.text(label, 6 + x_offset, sy + text_offset_y, 0)
        if has_child:
            hal.text(">", x_offset + hal.width - 12, sy + text_offset_y + 2, 0)

    def _render_tile(self, hal, cam_x):
        total = self.menu.item_count()
        if total == 0:
            return
        bar_w = (self.index + 1) * hal.width // total
        hal.fill_rect(0, 0, hal.width, self.config.bar_height, 0)
        hal.fill_rect(0, 0, bar_w, self.config.bar_height, 1)
        if self.index > 0:
            hal.text("<", 0, hal.height - 10, 1)
        if self.index < total - 1:
            hal.text(">", hal.width - 8, hal.height - 10, 1)

        # 选中高亮完全由 Menu.render_tile 中的放大效果承担，这里不再画额外边框
        pass


# ============================================================
# Menu - 菜单节点（树形结构）
# 支持多级菜单嵌套，每个菜单可以包含多个项目（Item）
# 每个项目可以关联一个子菜单
# ============================================================
class Menu:
    """
    菜单类（树形结构节点）
    一个菜单包含若干项目（_items），每个项目可关联一个子菜单
    示例：
        root = Menu("Main")
        sub = Menu("Settings")
        root.add_item("WiFi", sub)   # 选择 "WiFi" 会进入 sub 菜单
        root.add_item("Exit")         # 选择 "Exit" 没有子菜单
    """

    __slots__ = (
        "name", "menu_type", "_items", "_children", "_apps",
        "parent", "select_index"
    )

    def __init__(self, name="root", menu_type="list"):
        self.name = name
        self.menu_type = menu_type
        self._items = []  # 菜单项目列表（字符串）
        self._children = {}  # 项目 → 子菜单映射
        self._apps = {}  # 项目 → App 面板映射
        self.parent = None  # 父菜单引用（用于返回上级）
        self.select_index = 0  # 从父菜单进入时记住焦点位置

    def add_item(self, name, child_menu=None, app=None):
        """
        添加一个菜单项
        :param name: 项目名称（显示的文本）
        :param child_menu: 关联的子菜单（可选，None 表示叶子节点）
        :param app: 关联的应用面板（可选，菜单项带有面板时，打开直接进入面板）
        :return: self（支持链式调用）
        """
        self._items.append(name)  # 添加到项目列表
        self._children[name] = child_menu  # 记录子菜单（可能为 None）
        self._apps[name] = app  # 记录 App 面板（可能为 None）
        if child_menu:
            child_menu.parent = self  # 子菜单记住父菜单（返回用）
        return self

    def item_count(self):
        """返回此菜单包含的项目数量"""
        return len(self._items)

    def get_item(self, index):
        """获取指定索引的项目名称"""
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def get_child(self, index):
        """获取指定索引项目关联的子菜单"""
        if 0 <= index < len(self._items):
            return self._children.get(self._items[index])
        return None

    def has_child(self, index):
        """检查指定索引的项目是否有子菜单"""
        child = self.get_child(index)
        return child is not None and child.item_count() > 0

    def get_app(self, index):
        """获取指定索引项目绑定的 App（没有返回 None）"""
        if 0 <= index < len(self._items):
            return self._apps.get(self._items[index])
        return None

    def has_app(self, index):
        """检查指定索引的项目是否绑定了 App"""
        return self.get_app(index) is not None

    def render(self, hal, cam_x, cam_y, selected_index=0, tile_v_scale=0, skip_selected=True):
        if self.menu_type == "tile":
            self.render_tile(hal, cam_x, cam_y, selected_index, tile_v_scale)
        else:
            self.render_list(hal, cam_x, cam_y, selected_index, skip_selected)

    def render_list(self, hal, cam_x, cam_y, selected_index=0, skip_selected=True):
        item_h = hal.config.item_height
        screen_h = hal.config.screen_height
        for i, name in enumerate(self._items):
            y = i * item_h - cam_y
            if -item_h < y < screen_h:
                # 正常渲染时当前选中项由 Selector 负责绘制，这里跳过
                if skip_selected and i == selected_index:
                    continue
                has_child = self._children.get(name) is not None
                hal.text(name, 10 + cam_x, y + 4, 1)
                if has_child:
                    hal.text(">", cam_x + hal.width - 12, y + 4, 1)

    def render_tile(self, hal, cam_x, cam_y, selected_index=0, tile_v_scale=0):
        tw = hal.config.tile_width
        th = hal.config.tile_height
        tm = hal.config.tile_margin
        ty = hal.config.tile_top_margin
        total = len(self._items)
        group_w = total * tw + max(0, total - 1) * tm
        if group_w <= hal.width:
            start_x = max(0, (hal.width - group_w) // 2)
        else:
            start_x = (hal.width - tw) // 2
        r = 5  # 圆角半径

        # 先绘制普通（未选中）磁贴
        for i, name in enumerate(self._items):
            if i == selected_index:
                continue
            x = start_x + i * (tw + tm) - cam_x
            if -tw < x < hal.width and x + tw > 0:
                DrawUtils.fill_round_rect(hal, x, ty, tw, th, r, 1)
                short = name[:4]
                hal.text(short, x + (tw - len(short) * 8) // 2, ty + th // 2 - 4, 0)

        # 再绘制选中磁贴（高度随 tile_v_scale 动画放大）
        if 0 <= selected_index < total:
            i = selected_index
            x = start_x + i * (tw + tm) - cam_x
            h = th + tile_v_scale * 2
            y = ty - tile_v_scale
            if -tw < x < hal.width and x + tw > 0:
                DrawUtils.fill_round_rect(hal, x, y, tw, h, r, 1)
                short = self._items[i][:4]
                hal.text(short, x + (tw - len(short) * 8) // 2, y + h // 2 - 4, 0)


# ============================================================
# Launcher - 主控制器（核心）
# 统筹管理菜单导航、选择器、摄像机、输入处理、渲染循环
# ============================================================
class Launcher:
    """
    启动器/主控制器 - FlowUI 的核心
    工作流程：
    1. init(root_menu) → 设置根菜单
    2. 循环调用 update() → 每帧：清屏 → 渲染菜单 → 渲染选择器 → 更新摄像机 → 处理输入
    3. open() / close() → 菜单导航（进入/返回子菜单）
    4. pop_info() → 弹出提示信息（带滑入/滑出动画）
    """

    __slots__ = (
        "hal", "config", "current_menu", "camera", "selector", "widgets",
        "popup_text", "popup_y", "popup_target_y", "popup_w", "popup_h",
        "popup_x", "popup_timer", "popup_duration", "popup_state",
        "app_mode", "active_app", "debug_mode", "_fps", "_frame_count",
        "_fps_timer", "transition",
        "_trans_from_fb", "_trans_to_fb", "_trans_big_fb",
    )

    def __init__(self, hal, config):
        """
        :param hal: HAL 硬件抽象实例
        :param config: Config 配置实例
        """
        self.hal = hal
        self.config = config
        self.current_menu = None
        self.camera = Camera(config)
        self.selector = Selector(config)
        self.widgets = []

        # 非阻塞弹出提示状态
        self.popup_text = None  # 当前弹出文字（None=无弹出）
        self.popup_y = -20  # 弹出框 Y 位置
        self.popup_target_y = -20  # 目标 Y 位置
        self.popup_w = 0  # 弹出框宽度
        self.popup_h = 16  # 弹出框高度
        self.popup_x = 0  # 弹出框 X 位置
        self.popup_timer = 0  # 显示计时器（ms）
        self.popup_duration = 0  # 显示时长
        self.popup_state = 0  # 0=隐藏 1=滑入中 2=显示中 3=滑出中

        # ----- App 面板模式 -----
        self.app_mode = False  # True=当前正在运行一个 App 面板
        self.active_app = None  # 当前活动的 App 实例

        # ----- 调试模式 -----
        self.debug_mode = False  # True=在屏幕底部显示调试信息
        self._fps = 0  # 最近 1 秒的帧数
        self._frame_count = 0  # 当前秒内的帧计数器
        self._fps_timer = time.ticks_ms()  # FPS 计时起点

        # ----- 列表菜单滑动过渡 -----
        self.transition = None

        # 预渲染过渡用的离屏 FrameBuffer
        # 256x64：左侧放 from_menu，右侧放 to_menu
        self._trans_from_buf = bytearray(self.config.screen_width * self.config.screen_height // 8)
        self._trans_to_buf = bytearray(self.config.screen_width * self.config.screen_height // 8)
        self._trans_big_buf = bytearray(self.config.screen_width * 2 * self.config.screen_height // 8)
        self._trans_from_fb = framebuf.FrameBuffer(
            self._trans_from_buf, self.config.screen_width, self.config.screen_height, framebuf.MONO_HLSB
        )
        self._trans_to_fb = framebuf.FrameBuffer(
            self._trans_to_buf, self.config.screen_width, self.config.screen_height, framebuf.MONO_HLSB
        )
        self._trans_big_fb = framebuf.FrameBuffer(
            self._trans_big_buf, self.config.screen_width * 2, self.config.screen_height, framebuf.MONO_HLSB
        )

        print("[Launcher] 启动器初始化完成")

    def init(self, root_menu):
        """
        初始化启动器
        :param root_menu: 根菜单（最顶层菜单）
        设置当前菜单，重置选择器和摄像头
        """
        self.current_menu = root_menu
        self.selector.inject(root_menu)
        self.camera.reset()
        print("[Launcher] 已加载根菜单：{}".format(root_menu.name))

    def open(self):
        """
        进入当前选中项的子菜单或 App 面板
        :return: True=成功, False=失败
        优先检测是否绑定了 App（面板模式），其次才是子菜单
        """
        if not self.current_menu:
            return False

        idx = self.selector.index

        # 优先 1：选中项绑定了 App → 进入 App 面板模式
        if self.current_menu.has_app(idx):
            app = self.current_menu.get_app(idx)
            return self.enter_app(app)

        # 优先 2：选中项有子菜单 → 进入子菜单
        child = self.current_menu.get_child(idx)
        if not child or child.item_count() == 0:
            self.pop_info("empty!", 600)
            return False

        # 记住当前选中位置（返回时恢复）
        child.select_index = idx

        # tile 菜单直接切换；列表菜单使用滑动过渡
        if self.current_menu.menu_type == "tile" or child.menu_type == "tile":
            self.current_menu = child
            self.selector.inject(child)
            self.camera.reset()
            print("[Launcher] 进入子菜单：{}".format(child.name))
        else:
            self.transition = {
                "type": "slide",
                "direction": -1,  # 当前菜单向左滑出，子菜单从右侧滑入
                "progress": 0,
                "from_menu": self.current_menu,
                "to_menu": child,
                "from_index": idx,
                "to_index": 0,
            }
            print("[Launcher] 开始滑动进入子菜单：{}".format(child.name))
        return True

    def close(self):
        """
        返回上一级 / 退出 App 面板
        :return: True=成功, False=已在根菜单或无上级
        如果在 App 面板模式中，则退出 App 回到菜单
        """
        # 优先：在 App 面板模式 → 退出 App
        if self.app_mode:
            return self.exit_app()

        if not self.current_menu or not self.current_menu.parent:
            return False  # 已在根菜单，静默失败

        # 先记住当前菜单在父菜单中的位置，再切回父级
        idx = self.current_menu.select_index
        parent = self.current_menu.parent

        # tile 菜单直接切换；列表菜单使用滑动过渡
        if self.current_menu.menu_type == "tile" or parent.menu_type == "tile":
            self.current_menu = parent
            self.selector.inject(self.current_menu)
            if idx < self.current_menu.item_count():
                self.selector.index = idx
                self.selector.target_y = idx * self.config.item_height
                self.selector.y = idx * self.config.item_height
            self.camera.reset()
            self._center_camera_on_index(self.current_menu, self.selector.index)
            print("[Launcher] 返回父菜单：{}".format(parent.name))
        else:
            self.transition = {
                "type": "slide",
                "direction": 1,  # 当前菜单向右滑出，父菜单从左侧滑入
                "progress": 0,
                "from_menu": self.current_menu,
                "to_menu": parent,
                "from_index": self.selector.index,
                "to_index": idx,
            }
            print("[Launcher] 开始滑动返回父菜单：{}".format(parent.name))
        return True

    def _center_camera_on_index(self, menu, index):
        """将列表菜单摄像机对准指定索引项"""
        item_h = self.config.item_height
        screen_h = self.config.screen_height
        target_y = index * item_h - (screen_h - item_h) // 2
        max_y = menu.item_count() * item_h - screen_h
        if max_y < 0:
            max_y = 0
        if target_y < 0:
            target_y = 0
        elif target_y > max_y:
            target_y = max_y
        self.camera.y = target_y
        self.camera.target_y = target_y

    # ----- App 面板模式入口/出口 -----

    def enter_app(self, app):
        """
        进入 App 面板模式
        :param app: App 实例
        :return: True=成功
        接管屏幕渲染，将触摸/按键事件路由到 App
        """
        if app is None:
            return False
        self.app_mode = True
        self.active_app = app
        print("[Launcher] 进入 App 面板：{}".format(app.__class__.__name__))
        app.on_open(self)
        return True

    def exit_app(self):
        """
        退出 App 面板模式，返回菜单
        :return: True=成功, False=当前不在 App 模式
        """
        if not self.app_mode:
            return False
        if self.active_app:
            print("[Launcher] 退出 App 面板：{}".format(self.active_app.__class__.__name__))
            self.active_app.on_close(self)
        self.app_mode = False
        self.active_app = None
        return True

    def pop_info(self, text, duration=600):
        """
        启动一个弹出提示（非阻塞）
        实际渲染在 update() 中完成
        :param text: 提示文字
        :param duration: 显示时长（ms）
        """
        print("[Launcher] 弹出提示：{} ({}ms)".format(text, duration))
        self.popup_text = text
        self.popup_h = 16
        self.popup_w = len(text) * 8 + self.config.pop_margin * 2
        self.popup_x = (self.hal.width - self.popup_w) // 2
        self.popup_target_y = (self.hal.height - self.popup_h) // 3
        self.popup_y = -self.popup_h
        self.popup_duration = duration
        self.popup_timer = time.ticks_ms()
        self.popup_state = 1  # 滑入中

    def _render_popup(self):
        """在每一帧中渲染弹出框（由 update() 调用）"""
        if self.popup_state == 0:
            return  # 无弹出

        now = time.ticks_ms()
        speed = self.config.pop_speed

        if self.popup_state == 1:
            # 滑入阶段
            self.popup_y = Animation.move_int(self.popup_y, self.popup_target_y, speed)
            if abs(self.popup_y - self.popup_target_y) <= 1:
                self.popup_y = self.popup_target_y
                self.popup_state = 2
                self.popup_timer = now

        elif self.popup_state == 2:
            # 显示阶段
            if now - self.popup_timer >= self.popup_duration:
                self.popup_state = 3  # 超时 → 滑出

        elif self.popup_state == 3:
            # 滑出阶段
            target = -self.popup_h
            self.popup_y = Animation.move_int(self.popup_y, target, speed)
            if self.popup_y <= target:
                self.popup_state = 0  # 完全隐藏
                self.popup_text = None
                return

        # 渲染弹出框
        DrawUtils.fill_round_rect(
            self.hal,
            self.popup_x,
            self.popup_y,
            self.popup_w,
            self.popup_h,
            self.config.pop_radius,
            1,
        )
        DrawUtils.round_rect(
            self.hal,
            self.popup_x + 1,
            self.popup_y + 1,
            self.popup_w - 2,
            self.popup_h - 2,
            self.config.pop_radius - 1,
            0,
        )
        self.hal.text(
            self.popup_text,
            self.popup_x + self.config.pop_margin,
            self.popup_y + (self.popup_h - 8) // 2 + 1,
            0,
        )

    def dismiss_popup(self):
        """外部调用：立即关闭弹出框（无动画，瞬间消失）"""
        self.popup_state = 0
        self.popup_text = None

    def _update_fps(self):
        """更新 FPS 计数器（每帧调用）"""
        self._frame_count += 1
        now = time.ticks_ms()
        if now - self._fps_timer >= 1000:
            self._fps = self._frame_count
            self._frame_count = 0
            self._fps_timer = now

    def _render_transition(self):
        """渲染列表菜单的滑动过渡（双缓冲预渲染，可通过 Config.transition_buffer 切换逐帧渲染）"""
        t = self.transition
        p = t["progress"]
        direction = t["direction"]
        screen_w = self.config.screen_width
        item_h = self.config.item_height
        screen_h = self.config.screen_height
        use_buffer = self.config.transition_buffer

        # ---- 双缓冲预渲染路径（使用 bytearray 切片实现真正滑动）----
        if use_buffer:
            # 预渲染阶段：只执行一次
            if not t.get("prepared"):
                saved_menu = self.selector.menu
                saved_index = self.selector.index
                saved_y = self.selector.y
                saved_target_y = self.selector.target_y
                saved_tile_v = self.selector.tile_v_scale
                saved_tile_v_target = self.selector.tile_v_scale_target

                def cam_y_for(menu, index):
                    target_y = index * item_h - (screen_h - item_h) // 2
                    max_y = menu.item_count() * item_h - screen_h
                    if max_y < 0:
                        max_y = 0
                    if target_y < 0:
                        target_y = 0
                    elif target_y > max_y:
                        target_y = max_y
                    return target_y

                # 渲染 from_menu 到 _trans_from_fb
                from_menu = t["from_menu"]
                from_index = t["from_index"]
                from_y = cam_y_for(from_menu, from_index)
                self.selector.menu = from_menu
                self.selector.index = from_index
                self.selector.y = from_index * item_h
                self.selector.target_y = self.selector.y
                self.hal.set_framebuffer(self._trans_from_fb)
                self._trans_from_fb.fill(0)
                from_menu.render(self.hal, 0, from_y, from_index, self.selector.tile_v_scale, skip_selected=False)
                self.selector.render(self.hal, 0, from_y)
                self.hal.restore_framebuffer()

                # 渲染 to_menu 到 _trans_to_fb
                to_menu = t["to_menu"]
                to_index = t["to_index"]
                to_y = cam_y_for(to_menu, to_index)
                self.selector.menu = to_menu
                self.selector.index = to_index
                self.selector.y = to_index * item_h
                self.selector.target_y = self.selector.y
                self.hal.set_framebuffer(self._trans_to_fb)
                self._trans_to_fb.fill(0)
                to_menu.render(self.hal, 0, to_y, to_index, self.selector.tile_v_scale, skip_selected=False)
                self.selector.render(self.hal, 0, to_y)
                self.hal.restore_framebuffer()

                # 用 bytearray 拷贝合并到 big_buf（256x64）
                # MONO_HLSB: 每 8 行一组（page），每组 256 字节
                pages = screen_h // 8
                row_bytes_big = screen_w * 2  # 256
                row_bytes_small = screen_w    # 128
                for pg in range(pages):
                    src_off = pg * row_bytes_small
                    dst_off = pg * row_bytes_big
                    # from_buf 拷贝到 big_buf 左侧
                    self._trans_big_buf[dst_off:dst_off + row_bytes_small] = \
                        self._trans_from_buf[src_off:src_off + row_bytes_small]
                    # to_buf 拷贝到 big_buf 右侧
                    self._trans_big_buf[dst_off + row_bytes_small:dst_off + row_bytes_big] = \
                        self._trans_to_buf[src_off:src_off + row_bytes_small]

                self.selector.menu = saved_menu
                self.selector.index = saved_index
                self.selector.y = saved_y
                self.selector.target_y = saved_target_y
                self.selector.tile_v_scale = saved_tile_v
                self.selector.tile_v_scale_target = saved_tile_v_target

                t["prepared"] = True

            # 每帧：两个离屏 buffer 分别 blit，负坐标由 blit 内部裁剪实现滑出
            self.hal.fb.fill(0)
            if direction == -1:
                # 进入子菜单：from 左移出，to 从右侧左移入
                self.hal.fb.blit(self._trans_from_fb, -p, 0)
                self.hal.fb.blit(self._trans_to_fb, screen_w - p, 0)
            else:
                # 返回父菜单：from 右移出，to 从左侧右移入
                self.hal.fb.blit(self._trans_from_fb, p, 0)
                self.hal.fb.blit(self._trans_to_fb, p - screen_w, 0)
        else:
            # ---- 逐帧渲染路径（备选） ----
            saved_menu = self.selector.menu
            saved_index = self.selector.index
            saved_y = self.selector.y
            saved_target_y = self.selector.target_y
            saved_tile_v = self.selector.tile_v_scale
            saved_tile_v_target = self.selector.tile_v_scale_target

            def cam_y_for(menu, index):
                target_y = index * item_h - (screen_h - item_h) // 2
                max_y = menu.item_count() * item_h - screen_h
                if max_y < 0:
                    max_y = 0
                if target_y < 0:
                    target_y = 0
                elif target_y > max_y:
                    target_y = max_y
                return target_y

            from_x = direction * p
            to_x = -direction * (screen_w - p)

            from_menu = t["from_menu"]
            from_index = t["from_index"]
            from_y = cam_y_for(from_menu, from_index)
            self.selector.menu = from_menu
            self.selector.index = from_index
            self.selector.y = from_index * item_h
            self.selector.target_y = self.selector.y
            from_menu.render(self.hal, from_x, from_y, from_index, self.selector.tile_v_scale, skip_selected=False)
            self.selector.render(self.hal, from_x, from_y)

            to_menu = t["to_menu"]
            to_index = t["to_index"]
            to_y = cam_y_for(to_menu, to_index)
            self.selector.menu = to_menu
            self.selector.index = to_index
            self.selector.y = to_index * item_h
            self.selector.target_y = self.selector.y
            to_menu.render(self.hal, to_x, to_y, to_index, self.selector.tile_v_scale, skip_selected=False)
            self.selector.render(self.hal, to_x, to_y)

            self.selector.menu = saved_menu
            self.selector.index = saved_index
            self.selector.y = saved_y
            self.selector.target_y = saved_target_y
            self.selector.tile_v_scale = saved_tile_v
            self.selector.tile_v_scale_target = saved_tile_v_target

    def _render_debug(self):
        """在屏幕底部渲染调试信息（2 行：FPS + 菜单路径 + 空闲内存）"""
        if not self.debug_mode:
            return
        h = self.hal.height
        bar_y = h - 16
        # 半透明底条（填充白色矩形）
        self.hal.fill_rect(0, bar_y, self.hal.width, 16, 1)
        self.hal.rect(0, bar_y, self.hal.width, 16, 0)
        # 第 1 行：FPS + 内存
        gc_count = gc.mem_free()
        line1 = "FPS:{} MEM:{}".format(self._fps, gc_count)
        self.hal.text(line1, 1, bar_y + 1, 0)
        # 第 2 行：菜单路径
        path = "N/A"
        if self.current_menu:
            path = self.current_menu.name
            p = self.current_menu.parent
            # 最多显示 3 级路径
            parts = [path]
            for _ in range(2):
                if p:
                    parts.insert(0, p.name)
                    p = p.parent
                else:
                    break
            path = "/".join(parts)
        self.hal.text(path, 1, bar_y + 8, 0)

    def update(self):
        """
        主循环更新函数（每帧调用）
        执行顺序：
        1. 清屏
        2. 检测 App 模式 → 走 App 渲染；否则渲染菜单
        3. 渲染调试覆盖层
        4. 刷新到屏幕 & 更新 FPS
        5. 按键处理 / App 输入分发
        """
        # 处理列表菜单滑动过渡
        if self.transition:
            self.transition["progress"] = Animation.move_int(
                self.transition["progress"], self.config.screen_width, self.config.scroll_speed
            )
            if self.transition["progress"] >= self.config.screen_width - 1:
                # 动画结束，切换到目标菜单
                to_menu = self.transition["to_menu"]
                to_index = self.transition["to_index"]
                self.current_menu = to_menu
                self.selector.inject(to_menu)
                self.selector.index = to_index
                self.selector.y = to_index * self.config.item_height
                self.selector.target_y = self.selector.y
                self.camera.reset()
                self._center_camera_on_index(to_menu, to_index)
                self.transition = None

        self.hal.fill(0)

        if self.app_mode and self.active_app:
            # ===== App 面板模式 =====
            self.active_app.update(self)
            self.active_app.render(self.hal)
        elif self.transition and self.transition["type"] == "slide":
            # ===== 列表菜单滑动过渡 =====
            self._render_transition()
        else:
            # ===== 菜单模式 =====
            cam_x, cam_y = self.camera.get_pos()
            if self.current_menu:
                self.current_menu.render(
                    self.hal, cam_x, cam_y, self.selector.index, self.selector.tile_v_scale
                )
                self.selector.update()  # 先更新选择器位置动画
                self.selector.render(self.hal, cam_x, cam_y)
                self.camera.follow(self.selector, self.current_menu)
                self.camera.update(self.current_menu)

        # 弹出框（所有模式下都显示）
        self._render_popup()

        # 调试覆盖层（所有模式下都显示）
        self._render_debug()

        self.hal.show()
        self._update_fps()

        # ---- 按键处理 / App 输入分发 ----
        # 过渡动画期间不响应按键
        if self.transition:
            self.hal.key_scan()
            return

        self.hal.key_scan()

        if self.app_mode and self.active_app:
            # App 模式：按键事件路由到 App.handle_touch(hal)
            self.active_app.handle_touch(self.hal)

            # 安全退出：长按返回键强制退出 App
            if self.hal.btn_up_pressed:
                self.exit_app()
        else:
            # 菜单模式：标准按键导航
            if self.hal.btn_up_clicked:
                self.selector.go_prev()
            elif self.hal.btn_down_clicked:
                self.selector.go_next()
            elif self.hal.btn_down_pressed:
                self.open()
            elif self.hal.btn_up_pressed:
                self.close()

        time.sleep_ms(30)
