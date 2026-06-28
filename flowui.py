# ============================================================
# FlowUI - MicroPython OLED 用户界面框架
# 设计灵感来自: https://github.com/AstraThreshold/oled-ui-astra (C++/STM32)
# 适用于 ESP32 + SSD1306 OLED 128x64
# ============================================================

import math  # 数学运算（用于动画插值、圆角计算）
import time  # 时间相关（ms计时、延时）
import gc  # 垃圾回收（调试信息用）
from machine import Pin, SoftI2C, TouchPad  # ESP32 GPIO、I2C、触摸引脚
import ssd1306  # SSD1306 OLED 驱动库
import framebuf  # 帧缓冲区（用于像素级绘图）


# ============================================================
# Config - UI 配置类
# 集中管理所有 UI 相关的可调参数
# ============================================================
class Config:
    """UI 配置类，所有界面参数集中在这里调整"""

    __slots__ = (
        "screen_width", "screen_height",
        "pop_margin", "pop_radius", "pop_speed", "pop_duration",
        "fade_speed",
        "selector_radius", "selector_margin", "selector_height",
        "item_height", "scroll_speed",
        "tile_width", "tile_height", "tile_margin", "tile_top_margin",
        "bar_height", "tile_anim_speed",
        "light_mode",
    )

    def __init__(self):
        # ----- 屏幕参数 -----
        self.screen_width = 128  # OLED 宽度（像素）
        self.screen_height = 64  # OLED 高度（像素）

        # ----- 弹出提示（PopInfo）参数 -----
        self.pop_margin = 4  # 弹出框内边距
        self.pop_radius = 4  # 弹出框圆角半径
        self.pop_speed = 60  # 弹出框动画速度（越大越快）
        self.pop_duration = 600  # 弹出框显示时长（毫秒）

        # ----- 过渡动画参数 -----
        self.fade_speed = 80  # 淡入淡出速度

        # ----- 选择器（高亮条）参数 -----
        self.selector_radius = 4  # 选择器圆角
        self.selector_margin = 2  # 选择器边距
        self.selector_height = 14  # 选择器高度

        # ----- 菜单项参数（List 纵向列表）-----
        self.item_height = 16
        self.scroll_speed = 80

        # ----- Tile 横向磁贴参数 -----
        self.tile_width = 40
        self.tile_height = 32
        self.tile_margin = 8
        self.tile_top_margin = 8
        self.bar_height = 3
        self.tile_anim_speed = 60

        # ----- 显示模式 -----
        self.light_mode = False  # 是否浅色模式（白底黑字）


# ============================================================
# HAL - Hardware Abstraction Layer（硬件抽象层）
# 封装 OLED 显示和按键输入，隐藏底层硬件细节
# ============================================================
class HAL:
    """
    硬件抽象层
    职责：管理 OLED 屏幕绘制、按键扫描
    支持的输入方式：物理按键（GPIO 上拉）、触摸引脚
    """

    def __init__(self, config=None, scl_pin=22, sda_pin=21, i2c_addr=0x3C, btn_up=18, btn_down=19):
        """
        初始化硬件
        :param config: UI 配置实例（默认 None，使用内置默认 128x64）
        :param scl_pin: I2C 时钟引脚（默认 GPIO22）
        :param sda_pin: I2C 数据引脚（默认 GPIO21）
        :param i2c_addr: OLED I2C 地址（默认 0x3C）
        :param btn_up: 向上按键引脚（默认 GPIO18，未使用时设为 None）
        :param btn_down: 向下按键引脚（默认 GPIO19，未使用时设为 None）
        """
        # 使用传入配置或默认配置
        self.config = config if config is not None else Config()

        # 初始化 I2C 总线（软件模拟 I2C）
        i2c = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin))

        # 创建 OLED 对象
        self.oled = ssd1306.SSD1306_I2C(self.config.screen_width, self.config.screen_height, i2c, addr=i2c_addr)

        # 屏幕尺寸常量
        self.width = self.config.screen_width
        self.height = self.config.screen_height

        # 获取底层 buffer（直接像素操作用）
        self.buffer = self.oled.buffer  # 完整 buffer（含 I2C 控制字节 0x40 开头）
        self.fb = self.oled.framebuf  # FrameBuffer 对象（真正的像素数据）

        # 初始化按键引脚（上拉输入，按下 = 低电平）
        self.btn_up = Pin(btn_up, Pin.IN, Pin.PULL_UP)  # 向上键
        self.btn_down = Pin(btn_down, Pin.IN, Pin.PULL_UP)  # 向下键

        # ----- 按键状态机变量 -----
        self._keys = [0, 0]  # 按键事件缓存：[0]UP [1]DOWN
        self._key_states = [True, True]  # 按键是否空闲（True=未按下）
        self._key_held = [0, 0]  # 按键按下的时间戳（ms）
        self.last_update = 0  # 上次按键扫描时间

        # 按键事件标志（外部读取用）
        self.btn_up_clicked = False  # 短按 UP
        self.btn_down_clicked = False  # 短按 DOWN
        self.btn_up_pressed = False  # 长按 UP（>500ms）
        self.btn_down_pressed = False  # 长按 DOWN（>500ms）

    # ----- 绘图 API（委托给 FrameBuffer） -----
    def _c(self, color):
        """颜色转换：浅色模式下对颜色取反"""
        if self.config.light_mode:
            return 0 if color else 1
        return color

    def fill(self, color):
        """填充全屏：逻辑 0=黑，1=白（浅色模式自动取反）"""
        self.fb.fill(self._c(color))

    def pixel(self, x, y, color):
        """在 (x,y) 画一个像素点"""
        self.fb.pixel(x, y, self._c(color))

    def hline(self, x, y, w, color):
        """从 (x,y) 向右画 w 像素的水平线"""
        self.fb.hline(x, y, w, self._c(color))

    def vline(self, x, y, h, color):
        """从 (x,y) 向下画 h 像素的垂直线"""
        self.fb.vline(x, y, h, self._c(color))

    def rect(self, x, y, w, h, color):
        """画空心矩形"""
        self.fb.rect(x, y, w, h, self._c(color))

    def fill_rect(self, x, y, w, h, color):
        """画实心矩形"""
        self.fb.fill_rect(x, y, w, h, self._c(color))

    def text(self, s, x, y, color=1):
        """在 (x,y) 绘制 8x8 ASCII 字符串"""
        self.fb.text(s, x, y, self._c(color))

    def show(self):
        """将缓冲区内容刷新到 OLED 屏幕"""
        self.oled.show()

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
# Animation - 动画工具类
# 提供平滑缓动函数（类似 CSS ease-out）
# ============================================================
class Animation:
    """
    动画插值工具
    使用指数缓动（exponential easing out）实现平滑运动
    公式: pos += (target - pos) / factor
    """

    @staticmethod
    def move(pos, target, speed):
        """
        一维指数缓动（浮点数）
        :param pos: 当前位置
        :param target: 目标位置
        :param speed: 速度（1-100，越大越快）
        :return: 插值后的新位置
        原理：每次向目标移动剩余距离的 1/factor
        起始快、接近目标时变慢，产生平滑效果
        """
        if pos != target:
            if abs(pos - target) <= 1:  # 距离 < 1 就直接到达
                return target
            # (100 - speed) / 10 + 1 把 speed(1-100) 映射到 factor(10.9~1.1)
            # speed=100: factor≈1 → 瞬间到达
            # speed=1:   factor≈10.9 → 非常缓慢
            return pos + (target - pos) / ((100 - speed) / 10 + 1)
        return pos

    @staticmethod
    def move_int(pos, target, speed):
        """
        一维指数缓动（整数版本）
        用于像素级别的平滑移动
        """
        return int(round(Animation.move(pos, target, speed)))


# ============================================================
# DrawUtils - 绘图工具类
# 提供 SSD1306 原生不支持的复杂图形（如圆角矩形）
# ============================================================
class DrawUtils:
    """
    高级绘图工具
    SSD1306 的 FrameBuffer 只支持矩形，不支持圆角
    这里用逐像素描点的方式实现圆角矩形
    """

    # 按半径缓存圆角掩码，避免每帧重复计算
    _round_masks = {}

    @staticmethod
    def _get_mask(r):
        """获取半径 r 的圆角掩码，缓存加速"""
        mask = DrawUtils._round_masks.get(r)
        if mask is None:
            mask = []
            r2 = r * r
            for i in range(r):
                row = []
                for j in range(r):
                    row.append((i + 1) ** 2 + (j + 1) ** 2 <= r2)
                mask.append(row)
            DrawUtils._round_masks[r] = mask
        return mask

    @staticmethod
    def round_rect(hal, x, y, w, h, r, color):
        """
        画空心圆角矩形（边框）
        :param hal: HAL 实例
        :param x,y: 左上角坐标
        :param w,h: 宽高
        :param r: 圆角半径
        :param color: 0=黑 1=白
        原理：4条直线 + 4个 1/4 圆弧
        """
        if r > min(w, h) // 2:  # 限制半径不超过短边的一半
            r = min(w, h) // 2

        # 四条直线边（跳过圆角部分）
        hal.hline(x + r, y, w - 2 * r, color)  # 上边
        hal.hline(x + r, y + h - 1, w - 2 * r, color)  # 下边
        hal.vline(x, y + r, h - 2 * r, color)  # 左边
        hal.vline(x + w - 1, y + r, h - 2 * r, color)  # 右边

        # 绘制四个圆角
        mask = DrawUtils._get_mask(r)
        for i in range(r):  # i: x偏移
            for j in range(r):  # j: y偏移
                if mask[i][j]:
                    # 左上角
                    hal.pixel(x + r - 1 - i, y + r - 1 - j, color)
                    # 右上角
                    hal.pixel(x + w - r + i, y + r - 1 - j, color)
                    # 左下角
                    hal.pixel(x + r - 1 - i, y + h - r + j, color)
                    # 右下角
                    hal.pixel(x + w - r + i, y + h - r + j, color)

    @staticmethod
    def fill_round_rect(hal, x, y, w, h, r, color):
        """
        画实心圆角矩形
        :param hal: HAL 实例
        :param x,y: 左上角坐标
        :param w,h: 宽高
        :param r: 圆角半径
        :param color: 0=黑 1=白
        原理：1个矩形 + 4个侧边条 + 4个填充圆弧
        """
        if r > min(w, h) // 2:
            r = min(w, h) // 2

        # 中间的矩形主体（去掉圆角部分）
        hal.fill_rect(x + r, y, w - 2 * r, h, color)  # 中间的完整列
        hal.fill_rect(x, y + r, r, h - 2 * r, color)  # 左侧中间条
        hal.fill_rect(x + w - r, y + r, r, h - 2 * r, color)  # 右侧中间条

        # 填充四个圆角部分
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
class Camera:
    __slots__ = ("x", "y", "target_x", "target_y", "config")

    def __init__(self, config):
        self.config = config
        self.x = 0
        self.y = 0
        self.target_x = 0
        self.target_y = 0

    def follow(self, selector, menu):
        if menu and menu.menu_type == "tile":
            tw = self.config.tile_width
            tm = self.config.tile_margin
            total = menu.item_count()
            total_w = total * tw + max(0, total - 1) * tm
            if total_w <= self.config.screen_width:
                # 总宽度不超过屏幕，无需滚动，居中偏移由 Menu 自己处理
                self.target_x = 0
            else:
                # 让当前选中磁贴尽量居中
                center_x = self.config.screen_width // 2 - tw // 2
                target = selector.index * (tw + tm) - center_x
                max_x = total_w - self.config.screen_width
                if target < 0:
                    target = 0
                elif target > max_x:
                    target = max_x
                self.target_x = target
        else:
            item_h = self.config.item_height
            screen_h = self.config.screen_height
            # 让当前选中项尽量垂直居中，开头和结尾自然对齐
            target = selector.index * item_h - (screen_h - item_h) // 2
            max_y = menu.item_count() * item_h - screen_h
            if max_y < 0:
                max_y = 0
            if target < 0:
                target = 0
            elif target > max_y:
                target = max_y
            self.target_y = target

    def update(self, menu=None):
        if menu and menu.menu_type == "tile":
            self.x = Animation.move_int(self.x, self.target_x, self.config.scroll_speed)
        else:
            self.y = Animation.move_int(self.y, self.target_y, self.config.scroll_speed)

    def get_pos(self):
        return (self.x, self.y)

    def reset(self):
        self.x = 0
        self.y = 0
        self.target_x = 0
        self.target_y = 0


# ============================================================
# Selector - 选择器（高亮条）
# 当前选中的菜单项会用圆角矩形高亮显示
# ============================================================
class Selector:
    """
    菜单选择器（光标/高亮条）
    在当前选中的菜单项位置绘制一个圆角矩形高亮
    支持平滑移动动画
    """

    __slots__ = ("index", "y", "target_y", "config", "menu")

    def __init__(self, config):
        self.index = 0  # 当前选中项的索引
        self.y = 0  # 当前 Y 位置（实际显示位置）
        self.target_y = 0  # 目标 Y 位置（缓动动画用）
        self.config = config  # UI 配置引用
        self.menu = None  # 所属菜单引用

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

    def go_next(self):
        """选中下一项（边界检查，不循环）"""
        if self.menu and self.index < self.menu.item_count() - 1:
            self.index += 1
            self.target_y = self.index * self.config.item_height

    def go_prev(self):
        """选中上一项（边界检查，不循环）"""
        if self.index > 0:
            self.index -= 1
            self.target_y = self.index * self.config.item_height

    def update(self):
        """每帧更新：Y 位置平滑移向目标位置"""
        self.y = Animation.move_int(self.y, self.target_y, self.config.scroll_speed)

    def render(self, hal, cam_x, cam_y):
        if not self.menu:
            return
        if self.menu.menu_type == "tile":
            self._render_tile(hal, cam_x)
        else:
            self._render_list(hal, cam_y)

    def _render_list(self, hal, cam_y):
        sy = self.y - cam_y
        sh = self.config.selector_height
        # 仅在选择器可见时渲染
        if sy + sh <= 0 or sy >= hal.height:
            return
        # 选择器高度范围内先清空背景，防止文字残影
        hal.fill_rect(0, sy, hal.width, sh, 0)
        DrawUtils.fill_round_rect(
            hal,
            2,
            sy,
            hal.width - 4,
            sh,
            self.config.selector_radius,
            1,
        )
        item = self.menu.get_item(self.index)
        if item:
            hal.text(item, 6, sy + 3, 0)

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

        # 高亮当前选中的磁贴（反色边框）
        tw, th = self.config.tile_width, self.config.tile_height
        tm = self.config.tile_margin
        group_w = total * tw + max(0, total - 1) * tm
        if group_w <= hal.width:
            start_x = max(0, (hal.width - group_w) // 2)
        else:
            start_x = (hal.width - tw) // 2
        x = start_x + self.index * (tw + tm) - cam_x
        ty = self.config.tile_top_margin
        if -tw < x < hal.width and x + tw > 0:
            DrawUtils.round_rect(hal, x, ty, tw, th, 3, 0)
            # 顶部和底部各加一条短实线，增强选中感
            hal.hline(x + 4, ty + 1, tw - 8, 0)
            hal.hline(x + 4, ty + th - 2, tw - 8, 0)


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

    def render(self, hal, cam_x, cam_y):
        if self.menu_type == "tile":
            self.render_tile(hal, cam_x, cam_y)
        else:
            self.render_list(hal, cam_x, cam_y)

    def render_list(self, hal, cam_x, cam_y):
        item_h = hal.config.item_height
        screen_h = hal.config.screen_height
        for i, name in enumerate(self._items):
            y = i * item_h - cam_y
            if -item_h < y < screen_h:
                has_child = self._children.get(name) is not None
                label = "> " + name if has_child else "  " + name
                hal.text(label, 10, y + 4, 1)
                if has_child:
                    hal.text(">", hal.width - 12, y + 4, 1)

    def render_tile(self, hal, cam_x, cam_y):
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
        for i, name in enumerate(self._items):
            x = start_x + i * (tw + tm) - cam_x
            if -tw < x < hal.width and x + tw > 0:
                DrawUtils.fill_round_rect(hal, x, ty, tw, th, 3, 1)
                short = name[:4]
                hal.text(short, x + (tw - len(short) * 8) // 2, ty + th // 2 - 4, 0)


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
        "_fps_timer",
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

    def init(self, root_menu):
        """
        初始化启动器
        :param root_menu: 根菜单（最顶层菜单）
        设置当前菜单，重置选择器和摄像头
        """
        self.current_menu = root_menu
        self.selector.inject(root_menu)
        self.camera.reset()

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

        self.current_menu = child
        self.selector.inject(child)
        self.camera.reset()
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
        self.current_menu = parent

        self.selector.inject(self.current_menu)
        if idx < self.current_menu.item_count():
            self.selector.index = idx
        self.camera.reset()
        return True

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
        self.hal.fill(0)

        if self.app_mode and self.active_app:
            # ===== App 面板模式 =====
            self.active_app.update(self)
            self.active_app.render(self.hal)
        else:
            # ===== 菜单模式 =====
            cam_x, cam_y = self.camera.get_pos()
            if self.current_menu:
                self.current_menu.render(self.hal, cam_x, cam_y)
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
