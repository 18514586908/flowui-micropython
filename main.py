# ==========================================================================
# FlowUI v2.0 - 主程序入口（main.py）
# ==========================================================================
# 此文件是 ESP32 上电后自动运行的 MicroPython 脚本。
# 它展示了 FlowUI 的完整使用流程：
#
#   1. 导入框架组件（HAL, Config, Menu, Launcher, App）
#   2. 定义 App 面板类（继承 App 基类）
#   3. 硬件初始化（I2C → OLED → 触摸校准）
#   4. 构建菜单树（列表菜单 + 磁贴菜单 + 子菜单）
#   5. 触摸输入循环（菜单导航 / App 事件路由）
#
# 你可以直接修改此文件来创建自己的 UI 应用。
# 所有需要修改的地方都加了详细的注释说明。
# ==========================================================================

# ── 导入 FlowUI 框架 ─────────────────────────────────────────
from flowui import HAL, Config, Menu, Launcher, App

# ── 导入 ESP32 硬件模块 ──────────────────────────────────────
from machine import TouchPad, Pin  # TouchPad = 电容触摸, Pin = GPIO
import time

# ══════════════════════════════════════════════════════════════
# 第 1 步：定义 App 面板类
# ══════════════════════════════════════════════════════════════
# 每个 App 类继承自 flowui.App 基类，实现生命周期方法：
#   on_open()   — 进入面板时调用（初始化）
#   update()    — 每帧逻辑更新（可选）
#   render()    — 每帧绘制屏幕（必须）
#   on_close()  — 退出面板时调用（清理）
#   handle_touch_pin() — 触摸引脚事件（可选）
#
# 定义后通过 Menu.add_item(name, app=MyApp()) 绑定到菜单项。
# 用户选中该项并点击"进入"时，自动切换到 App 全屏模式。
# ==========================================================================

# ── 示例 App 1：LED 控制面板 ─────────────────────────────
class LEDApp(App):
    """
    LED 控制面板示例。
    
    展示：
    - 如何在 App 中保存状态（state, brightness）
    - 如何使用触摸引脚 0/1/2 控制开关和亮度
    - 如何绘制文字和分隔线
    """
    def on_open(self, launcher):
        # 【生命周期】进入面板时初始化状态
        self.state = False          # LED 开关状态（True=开）
        self.brightness = 50        # 亮度值（0-100）

    def render(self, hal):
        # 【生命周期】每帧绘制屏幕内容
        hal.fill(0)                            # 清屏（黑色背景）
        hal.text("LED Control", 20, 4, 1)       # 标题
        hal.hline(20, 13, 88, 1)                # 分隔线
        status = "ON" if self.state else "OFF"
        hal.text("State: " + status, 8, 22, 1)   # 状态行
        hal.text("Bright: " + str(self.brightness), 8, 34, 1)  # 亮度行
        hal.text("Pin0:Toggle", 8, 50, 1)        # 操作提示
        hal.text("Pin1:+   Pin2:-", 8, 54, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        # 【触摸事件】触摸引脚触发时调用
        if pin_index == 0:            # GPIO4 → 切换开关
            self.state = not self.state
        elif pin_index == 1:          # GPIO14 → 亮度+
            self.brightness = min(100, self.brightness + 10)
        elif pin_index == 2:          # GPIO27 → 亮度-
            self.brightness = max(0, self.brightness - 10)

    def on_close(self, launcher):
        # 【生命周期】退出面板时调用
        print("[LEDApp] 关闭面板，state={}".format(self.state))


# ── 示例 App 2：传感器读数面板（模拟数据）───────────────
class SensorApp(App):
    """
    传感器读数面板示例。
    
    展示：
    - 如何在 update() 中每帧更新数据
    - 如何使用简单的伪随机算法模拟传感器值
    - 温度、湿度、光照三个参数的显示
    """
    def on_open(self, launcher):
        self.counter = 0              # 帧计数器，用于生成模拟数据

    def update(self, launcher):
        self.counter += 1             # 每帧递增，作为随机种子

    def render(self, hal):
        # 用帧计数器生成看起来像传感器读数的模拟值
        hal.fill(0)
        hal.text("Sensor Read", 20, 4, 1)
        hal.hline(20, 13, 88, 1)
        # 温度：20-70°C（counter * 7 确保数值变化）
        temp = (self.counter * 7) % 50 + 20
        # 湿度：60-90%（counter * 13 产生不同步的变化）
        humid = (self.counter * 13) % 30 + 60
        # 光照：0-100%（counter * 3 缓慢变化）
        light = (self.counter * 3) % 100
        hal.text("Temp: {} C".format(temp), 8, 22, 1)
        hal.text("Humi: {} %".format(humid), 8, 34, 1)
        hal.text("Light: {} %".format(light), 8, 46, 1)
        hal.text("Pin0:Back", 8, 54, 1)          # 触摸 3 键返回菜单


# ── 示例 App 3：电机控制面板 ─────────────────────────────
class MotorApp(App):
    """
    电机控制面板示例。
    
    展示：
    - 如何绘制进度条（fill_rect 显示百分比）
    - 如何使用边框（rect）绘制外框
    - 控制值范围 0-255
    """
    def on_open(self, launcher):
        self.speed = 0                # 电机速度（0-255）

    def render(self, hal):
        hal.fill(0)
        hal.text("Motor Control", 16, 4, 1)
        hal.hline(16, 13, 96, 1)
        hal.text("Speed: " + str(self.speed), 8, 22, 1)  # 速度数字
        # 绘制进度条：实心矩形（已填充部分）+ 空心矩形（外框）
        bar_w = int(self.speed / 255 * 80)  # 将 0-255 映射到 0-80 像素宽
        hal.fill_rect(8, 34, bar_w, 8, 1)    # 填充条
        hal.rect(8, 34, 80, 8, 1)            # 外框
        hal.text("Pin1:+10  Pin2:-10", 8, 50, 1)
        hal.text("Pin0:Back", 8, 54, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        # GPIO14=加速，GPIO27=减速
        if pin_index == 1:
            self.speed = min(255, self.speed + 10)
        elif pin_index == 2:
            self.speed = max(0, self.speed - 10)


# ══════════════════════════════════════════════════════════════
# 第 2 步：硬件初始化
# ══════════════════════════════════════════════════════════════
# Config：所有 UI 参数在这里统一配置
# HAL：    硬件抽象层，管理 OLED + 按键
# Launcher：主控制器，管理菜单导航和渲染循环
# ==========================================================================

print("[main] === FlowUI v2.0 启动 ===")

# ── 创建配置实例（可选：修改默认参数）────────────────────
cfg = Config()
# 示例：取消注释下方行来自定义
# cfg.scroll_speed = 60       # 放慢滚动速度
# cfg.light_mode = True       # 开启浅色模式
# cfg.transition_buffer = True  # 双缓冲过渡（默认开）
# cfg.selector_height = 18    # 选择器高度（v2.0 默认 18）

# ── 创建硬件抽象层 ───────────────────────────────────────
# 参数：Config, SCL引脚, SDA引脚, I2C地址
hal = HAL(cfg, scl_pin=22, sda_pin=21, i2c_addr=0x3C)

# ── 创建主控制器 ─────────────────────────────────────────
launcher = Launcher(hal, cfg)

# ── 触摸引脚初始化 ──────────────────────────────────────
# ESP32 的 TouchPad 可以直接读取电容触摸值
# 4 个触摸引脚分别对应 4 个方向的触摸焊盘
touch_pins = [4, 14, 27, 33]    # GPIO 引脚号
touch_pads = [TouchPad(Pin(p)) for p in touch_pins]

# ══════════════════════════════════════════════════════════════
# 第 3 步：触摸阈值自动校准
# ══════════════════════════════════════════════════════════════
# 原理：
#   未触摸时，读数值较大（如 60-80）
#   触摸时，读数值显著下降（如 20-40）
# 读取 10 次取平均值作为"基准值"，
# 基准值的 75% 作为"触摸阈值"。
# 校准结果会显示在屏幕上 2 秒，并输出到串口。
# ==========================================================================

print("[main] 开始自动校准触摸阈值...")
baseline = []                    # 每个引脚的基准值
for i, pad in enumerate(touch_pads):
    vals = []
    # 连续读取 10 次取平均，降低单次噪声
    for _ in range(10):
        vals.append(pad.read())
        time.sleep_ms(10)        # 每次读取间隔 10ms
    avg = sum(vals) // len(vals)
    baseline.append(avg)
    print("[main] GPIO{} 触摸基准值={}".format(touch_pins[i], avg))

# 阈值 = 基准值的 75%（经验值，可根据灵敏度调整）
thresholds = [int(b * 0.75) for b in baseline]
print("[main] 触摸阈值:", thresholds)

# 在屏幕上显示校准结果 2 秒
hal.fill(0)
for i in range(4):
    hal.text("GPIO{}: {}".format(touch_pins[i], baseline[i]), 0, i * 16, 1)
hal.show()
print("[main] 触摸校准结果显示 2 秒")
time.sleep(2)


# ══════════════════════════════════════════════════════════════
# 第 4 步：构建菜单树
# ══════════════════════════════════════════════════════════════
# FlowUI 使用树形菜单结构：
#
#   主菜单
#   ├── 工具（子菜单）
#   │   ├── LED 控制
#   │   ├── 传感器读数
#   │   └── 电机测试
#   ├── 设置（子菜单）
#   │   ├── WiFi 设置
#   │   ├── 显示设置
#   │   └── 声音设置
#   ├── 应用（磁贴菜单） ← 绑定 App 面板
#   │   ├── LED → LEDApp
#   │   ├── Sensor → SensorApp
#   │   └── Motor → MotorApp
#   ├── 关于（子菜单）
#   └── 退出
#
# 注意：磁贴菜单（menu_type="tile"）适合绑定 App 面板，
#       列表菜单（menu_type="list"，默认）适合文字导航。
# ==========================================================================

# ── 创建根菜单和下级菜单 ──────────────────────────────
root = Menu("主菜单")
sub1 = Menu("工具")           # 列表模式（默认）
sub2 = Menu("设置")
sub3 = Menu("关于")

# ── 向子菜单中添加项 ─────────────────────────────────
# add_item(name, child_menu=None, app=None)
# name：显示的文字
# child_menu：关联的子菜单（选中后进入该菜单）
# app：关联的 App 面板（选中后进入该 App）
sub1.add_item("LED 控制")          # 简单叶节点（无子菜单）
sub1.add_item("传感器读数")
sub1.add_item("电机测试")

sub2.add_item("WiFi 设置")
sub2.add_item("显示设置")
sub2.add_item("声音设置")

sub3.add_item("Version 2.0")       # about 里显示版本号
sub3.add_item("Author: lyyx")
sub3.add_item("Power by MicroPython")

# ── 磁贴菜单 —— 绑定 App 面板 ─────────────────────────
tile_menu = Menu("应用", menu_type="tile")
tile_menu.add_item("LED",    app=LEDApp())      # 绑定 App
tile_menu.add_item("Sensor", app=SensorApp())
tile_menu.add_item("Motor",  app=MotorApp())
tile_menu.add_item("Camera")                   # 无 App（只占位）
tile_menu.add_item("Music")
tile_menu.add_item("Radio")
tile_menu.add_item("Maps")

# ── 组装到根菜单 ────────────────────────────────────
root.add_item("工具", sub1)      # 第一个参数是显示名称
root.add_item("设置", sub2)      # 第二个参数是子菜单
root.add_item("应用", tile_menu) # 磁贴菜单
root.add_item("关于", sub3)
root.add_item("退出")             # 叶节点（无子菜单）

print("[main] 菜单树构建完成，共 {} 个主菜单项".format(root.item_count()))

# ── 初始化 Launcher ────────────────────────────────────
launcher.init(root)
print("[main] Launcher 初始化完成，进入主循环")


# ══════════════════════════════════════════════════════════════
# 第 5 步：主循环 - 触摸输入处理
# ══════════════════════════════════════════════════════════════
# 每帧执行：
#   1. 读取 4 个触摸引脚的值
#   2. 连续读 3 次取最小值（抗噪声）
#   3. 与阈值比较判断触摸/释放
#   4. 根据状态路由到对应处理函数
#
# 触摸引脚功能映射（菜单模式）：
#   GPIO4  (Pin 0) = 上一项
#   GPIO14 (Pin 1) = 下一项
#   GPIO27 (Pin 2) = 进入/打开
#   GPIO33 (Pin 3) = 返回
#
# 触摸引脚功能映射（App 模式）：
#   GPIO4  (Pin 0) = App 自定义（handle_touch_pin 处理）
#   GPIO14 (Pin 1) = App 自定义
#   GPIO27 (Pin 2) = App 自定义
#   GPIO33 (Pin 3) = 返回菜单（强制退出 App）
# ==========================================================================

touched = [False, False, False, False]  # 每个引脚的上次触摸状态（防重复触发）

while True:
    # ── 轮询 4 个触摸引脚 ──────────────────────────────
    for i, pad in enumerate(touch_pads):
        # 连续读取 3 次取最小值，提高抗噪能力
        v1 = pad.read()
        v2 = pad.read()
        v3 = pad.read()
        val = min(v1, v2, v3)

        # ── 检测触摸（值 < 阈值）且未重复触发 ──────────
        if val < thresholds[i] and not touched[i]:
            touched[i] = True   # 标记已触发，防止同一触摸重复响应

            if launcher.app_mode:
                # ── App 模式 ──────────────────────────
                # pin 0-2 路由到当前 App 的 handle_touch_pin
                # pin 3 强制退出 App 返回菜单
                print("[main] 触摸引脚 {} 触发".format(i))
                if i == 3:
                    launcher.exit_app()               # Pin 3 = 返回菜单
                else:
                    launcher.active_app.handle_touch_pin(i, val)

            elif launcher.popup_state != 0:
                # ── 弹出提示显示中 ────────────────────
                # 任意触摸关闭弹出提示
                print("[main] 触摸关闭弹出提示")
                launcher.dismiss_popup()
                if i == 3:
                    launcher.close()

            elif i == 0:
                # ── 菜单导航：上一项 ─────────────────
                print("[main] 触摸：向上")
                launcher.selector.go_prev()

            elif i == 1:
                # ── 菜单导航：下一项 ─────────────────
                print("[main] 触摸：向下")
                launcher.selector.go_next()

            elif i == 2:
                # ── 菜单导航：进入子菜单 / 打开 App ────
                print("[main] 触摸：进入/打开")
                launcher.open()

            elif i == 3:
                # ── 菜单导航：返回上级菜单 ─────────────
                print("[main] 触摸：返回")
                launcher.close()

        # ── 检测释放（值 >= 阈值）─
        elif val >= thresholds[i]:
            touched[i] = False    # 更新触摸状态，允许下次触发

    # ── 核心循环：每帧更新 → 渲染 → 刷新屏幕 ─────────
    launcher.update()
