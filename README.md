
<div align="center">

# FlowUI — MicroPython v2.0

<img src="https://img.shields.io/badge/MicroPython-ESP32-green?style=flat-square&logo=micropython" />
<img src="https://img.shields.io/badge/OLED-SSD1306%20128x64-blue?style=flat-square" />
<img src="https://img.shields.io/badge/version-2.0-brightgreen?style=flat-square" />
<img src="https://img.shields.io/badge/license-MIT-orange?style=flat-square" />

**FlowUI** 是一个轻量级的 OLED 用户界面框架，面向 **ESP32 + SSD1306 OLED 128×64** 的 **MicroPython** 平台。它在 [AstraThreshold/oled-ui-astra](https://github.com/AstraThreshold/oled-ui-astra)（C++/STM32）的设计灵感基础上，重新整理并扩展为适合 MicroPython 使用的独立项目。

支持**多级菜单导航**、**横向磁贴布局**、**平滑动画**、**电容触摸输入**以及可扩展的 **App 面板系统**。

</div>

---

## 目录

- [特性](#特性)
- [硬件要求](#硬件要求)
- [快速开始](#快速开始)
- [完整使用教程](#完整使用教程)
- [菜单系统教程](#菜单系统教程)
- [App 面板教程](#app-面板教程)
- [触摸输入说明](#触摸输入说明)
- [菜单布局](#菜单布局)
- [弹出提示 PopInfo](#弹出提示-popinfo)
- [配置文件 Config](#配置文件-config)
- [API 参考](#api-参考)
- [调试模式](#调试模式)
- [更新日志](#更新日志)
- [项目结构](#项目结构)
- [版本差异](#版本差异)
- [原项目](#原项目)
- [License](#license)

---

## 特性

-   **多级菜单树** — 树形结构菜单，支持无限级嵌套，自动管理返回导航
-   **双布局模式** — 纵向列表（List）和横向磁贴（Tile），均支持平滑滚动
-   **App 面板系统** — 自定义功能面板，生命周期 `on_open → update → render → on_close`
-   **电容触摸** — 基于 ESP32 TouchPad 的 4 通道触摸输入，自动校准阈值
-   **平滑动画** — 指数缓动算法，菜单滚动、弹出框、选择器、滑动过渡全部带平滑动画
-   **圆角矩形** — 在 SSD1306（仅支持矩形）上逐像素绘制圆角矩形，带半径缓存
-   **弹出提示** — 非阻塞式 PopInfo，带滑入/滑出动画
-   **调试模式** — 实时显示 FPS、空闲内存、菜单路径
-   **浅色模式** — 通过 `Config.light_mode` 一键切换白底黑字
-   **硬件抽象层(HAL)** — 接收 `Config`，封装 OLED 绘图 & 按键扫描，解耦 UI 与硬件
-   **滑动过渡** — 列表菜单进入/退出子菜单时带有左右滑动动画，双缓冲预渲染流畅平滑（v2.0 优化）
-   **超长文本滚动** — 列表项文字过长时自动滚动显示完整内容（v1.1 新增）
-   **中文显示** — 自动检测中文字符并渲染 16×16 点阵汉字，中英混合显示（v2.0 新增）
-   **中文调试日志** — 框架内置大量中文日志，方便串口调试（v2.0 新增）

---

## 硬件要求

| 组件 | 型号 / 参数 |
|------|-------------|
| MCU | ESP32（需支持 TouchPad） |
| OLED | SSD1306, 128×64, I2C 接口 |
| I2C 引脚 | SCL = GPIO22, SDA = GPIO21（可配置） |
| 触摸引脚 | GPIO4, GPIO14, GPIO27, GPIO33（可配置） |
| 可选物理按键 | GPIO18(UP), GPIO19(DOWN) |

**接线示意**

```
ESP32                  SSD1306 OLED
GPIO22 (SCL) ──────── SCL
GPIO21 (SDA) ──────── SDA
3.3V               ── VCC
GND                ── GND
```

电容触摸无需额外接线，ESP32 引脚直连触摸焊盘即可。

---

## 快速开始

### 1. 烧录 MicroPython 固件到 ESP32

参考 [MicroPython 官方文档](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html)。

常用命令示例：

```bash
# 擦除 flash
esptool.py --chip esp32 --port COM7 erase_flash

# 烧录固件（请替换为实际下载的固件文件名）
esptool.py --chip esp32 --port COM7 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-20240602-v1.23.0.bin
```

### 2. 上传项目文件

将 `flowui.py`、`ssd1306.py`、`cn_font.py`、`cn_font.bin` 和 `main.py` 上传到 ESP32：

```bash
# 使用 mpremote（推荐）
mpremote connect COM7 fs cp flowui.py :flowui.py
mpremote connect COM7 fs cp ssd1306.py :ssd1306.py
mpremote connect COM7 fs cp cn_font.py :cn_font.py
mpremote connect COM7 fs cp cn_font.bin :cn_font.bin
mpremote connect COM7 fs cp main.py :main.py

# 或使用 ampy
ampy --port COM7 put flowui.py
ampy --port COM7 put ssd1306.py
ampy --port COM7 put cn_font.py
ampy --port COM7 put cn_font.bin
ampy --port COM7 put main.py
```

> **注意：** `cn_font.py` + `cn_font.bin` 是 v2.0 新增的中文显示模块。字库存储在二进制 `cn_font.bin` 中，`cn_font.py` 只负责索引和读取。如果不需要中文显示，可以不传这两个文件，但代码中出现中文字符时将无法渲染。

上传完成后复位 ESP32，设备会自动运行 `main.py`：

```bash
mpremote connect COM7 reset
```

### 3. 最简单的 main.py

```python
from flowui import HAL, Config, Menu, Launcher

cfg = Config()
hal = HAL(cfg, scl_pin=22, sda_pin=21)
launcher = Launcher(hal, cfg)

# 构建菜单
root = Menu("Main")
sub = Menu("Settings")
sub.add_item("WiFi Config")
sub.add_item("Display Set")
root.add_item("Settings", sub)
root.add_item("About")
root.add_item("Exit")

launcher.init(root)

# 主循环
while True:
    launcher.update()
```

---

## 完整使用教程

### 3.1 初始化流程

每个 FlowUI 程序都需要以下几步：

```python
from flowui import HAL, Config, Menu, Launcher

# 1. 创建配置
cfg = Config()

# 2. 创建 HAL（硬件抽象层）
hal = HAL(cfg, scl_pin=22, sda_pin=21)

# 3. 创建 Launcher（主控制器）
launcher = Launcher(hal, cfg)

# 4. 构建菜单树
root = Menu("Main")
# ... 添加菜单项 ...

# 5. 初始化 Launcher
launcher.init(root)
```

之后在主循环中调用 `launcher.update()` 即可。

### 3.2 主循环写法

```python
while True:
    launcher.update()
```

`launcher.update()` 每帧完成以下事情：

1. 清空屏幕
2. 处理过渡动画（如果有）
3. 渲染当前菜单或 App
4. 渲染弹出提示
5. 刷新到 OLED
6. 扫描触摸/按键输入
7. 根据输入执行导航（上/下/进入/返回）

如果你需要自己处理输入，可以在 `launcher.update()` 前后读取 `hal` 的按键状态：

```python
while True:
    launcher.hal.key_scan()
    if launcher.hal.btn_up_clicked:
        print("向上按钮被单击")
    launcher.update()
```

### 3.3 自定义触摸引脚

`HAL` 默认使用 GPIO4 / GPIO14 / GPIO27 / GPIO33 作为触摸输入。你可以在创建 HAL 时修改：

```python
hal = HAL(
    cfg,
    scl_pin=22,
    sda_pin=21,
    touch_pins=[4, 14, 27, 33],  # 触摸引脚列表
    up_pin=18,                   # 可选物理上键
    down_pin=19,                 # 可选物理下键
)
```

### 3.4 浅色模式

一键切换白底黑字：

```python
cfg = Config()
cfg.light_mode = True

hal = HAL(cfg, scl_pin=22, sda_pin=21)
```

浅色模式下，所有绘制颜色会自动反转。注意 `Config` 必须在创建 `HAL` 之前设置好，因为 `HAL` 会读取 `light_mode`。

### 3.5 中文显示

v2.0 开始，HAL.text() 会自动检测字符串中的中文字符，并调用 `cn_font.py` 渲染 16×16 点阵汉字。

```python
root = Menu("主菜单")
root.add_item("设置")
root.add_item("关于")
```

只要代码中出现中文，`HAL.text()` 就会自动使用中文字体渲染。英文字符仍使用 8×8 内置字体，中英混合时会自动对齐基线。

`cn_font.py` 会自动扫描 `main.py` 和 `flowui.py` 中实际使用到的汉字，生成最小化的 `cn_font.bin` 二进制字库。ESP32 运行时按偏移读取字模，并自带缓存，避免重复读取。

#### 扩展字库

如果你需要显示新的汉字：

1. 把新汉字写入源码（如 `main.py`）或 `gen_cn_font.py` 的 `EXTRA_CHARS`
2. 在 PC 端运行：

```bash
python gen_cn_font.py
```

3. 重新上传生成的 `cn_font.py` 和 `cn_font.bin` 到 ESP32

> **注意：** `gen_cn_font.py` 必须在 PC 端运行（需要 PIL 和字体文件）。ESP32 上电后只读取 `cn_font.bin`，不再生成字库，可完全脱机运行。

---

## 菜单系统教程

### 4.1 创建菜单

```python
root = Menu("Main")           # 默认是列表布局
apps = Menu("Apps", menu_type="tile")  # 磁贴布局
```

### 4.2 添加普通项

```python
root.add_item("About")
root.add_item("Exit")
```

### 4.3 添加子菜单

```python
settings = Menu("Settings")
settings.add_item("WiFi Config")
settings.add_item("Display Set")
settings.add_item("Sound Set")

root.add_item("Settings", settings)
```

当用户选中 "Settings" 并点击 "进入" 时，会打开 `settings` 子菜单。点击 "返回" 会回到 `root`，并恢复之前的选中位置。

### 4.4 绑定 App 面板

```python
from flowui import App

class MyApp(App):
    def render(self, hal):
        hal.fill(0)
        hal.text("Hello App", 20, 28, 1)

root.add_item("MyApp", app=MyApp())
```

### 4.5 修改菜单示例

假设你要把 "About" 菜单下的 "Power by MicroPython" 改成两行显示，或者把某个子菜单改成磁贴布局：

```python
about = Menu("About")
about.add_item("Version 1.1")
about.add_item("Author: lyyx")
about.add_item("MicroPython")

root.add_item("About", about)
```

注意列表模式下文字超长会自动滚动显示，不需要手动换行。

### 4.6 多级菜单

框架支持任意层级的嵌套：

```python
root = Menu("Main")
level1 = Menu("Level 1")
level2 = Menu("Level 2")
level3 = Menu("Level 3")

level3.add_item("Deep Item")
level2.add_item("Go Deeper", level3)
level1.add_item("Level 2", level2)
root.add_item("Level 1", level1)
```

列表菜单在各级之间切换时都会有滑动过渡动画。

---

## App 面板教程

### 5.1 App 生命周期

```
on_open(launcher)  →  update(launcher)  →  render(hal)  →  on_close(launcher)
   (进入时调用)         (每帧逻辑更新)      (每帧绘制)        (退出时调用)
```

### 5.2 最小 App 示例

```python
from flowui import App

class HelloApp(App):
    def on_open(self, launcher):
        self.counter = 0

    def update(self, launcher):
        self.counter += 1

    def render(self, hal):
        hal.fill(0)
        hal.text("Hello App", 24, 4, 1)
        hal.text("Count: " + str(self.counter), 24, 28, 1)

    def on_close(self, launcher):
        print("HelloApp closed")

# 绑定到磁贴菜单
tile_menu = Menu("Apps", menu_type="tile")
tile_menu.add_item("Hello", app=HelloApp())
```

### 5.3 带触摸交互的 App

```python
class LEDApp(App):
    def on_open(self, launcher):
        self.state = False
        self.brightness = 50

    def render(self, hal):
        hal.fill(0)
        hal.text("LED Control", 20, 4, 1)
        hal.hline(20, 13, 88, 1)
        status = "ON" if self.state else "OFF"
        hal.text("State: " + status, 8, 22, 1)
        hal.text("Bright: " + str(self.brightness), 8, 34, 1)
        hal.text("Pin0:Toggle", 8, 50, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            self.state = not self.state
        elif pin_index == 1:
            self.brightness = min(100, self.brightness + 10)
        elif pin_index == 2:
            self.brightness = max(0, self.brightness - 10)

    def on_close(self, launcher):
        print("LEDApp closed, state=", self.state)
```

### 5.4 App 触摸按键映射

| 触摸引脚 | 功能 |
|-----------|---------|
| GPIO4  (Pin 0) | App 自定义（例：切换开关） |
| GPIO14 (Pin 1) | App 自定义（例：增加） |
| GPIO27 (Pin 2) | App 自定义（例：减少） |
| GPIO33 (Pin 3) | **强制返回**菜单 |

### 5.5 在 main.py 中组装 Apps

```python
from flowui import HAL, Config, Menu, Launcher, App

class LEDApp(App):
    ...

class SensorApp(App):
    ...

cfg = Config()
hal = HAL(cfg, scl_pin=22, sda_pin=21)
launcher = Launcher(hal, cfg)

root = Menu("Main")

# 创建一个 tile 布局的 Apps 菜单
apps = Menu("Apps", menu_type="tile")
apps.add_item("LED", app=LEDApp())
apps.add_item("Sensor", app=SensorApp())

root.add_item("Apps", apps)
root.add_item("Settings", Menu("Settings"))

launcher.init(root)

while True:
    launcher.update()
```

---

## 触摸输入说明

### 自动校准

程序启动时会读取 10 次触摸值取平均值作为**基准值**，阈值自动设为基准值的 75%。

### 检测逻辑

- 连续读取 3 次取最小值，提高抗噪能力
- 触摸值 < 阈值 → 判定为触摸
- 触摸值 >= 阈值 → 判定为释放
- 触摸引脚按功能映射为 4 组：`Prev`、`Next`、`Open`、`Back`

### 菜单模式触摸映射

| 触摸引脚 | 操作 |
|-----------|--------|
| GPIO4  (Pin 0) | 上一项 / 向左 |
| GPIO14 (Pin 1) | 下一项 / 向右 |
| GPIO27 (Pin 2) | 进入子菜单 / 打开 App |
| GPIO33 (Pin 3) | 返回上级菜单 |

---

## 菜单布局

### 纵向列表 (List)

默认布局，文字列表 + 圆角高亮条选择器，支持摄像机平滑滚动。

```
┌──────────────────┐
│ ▓▓ Tools ▓▓      │  ← 高亮选择器（当前选中）
│   Settings       │
│   Apps           │
│   About          │
│   Exit           │
└──────────────────┘
```

### 横向磁贴 (Tile)

`Menu(name, menu_type="tile")` 创建，顶部进度条 + 居中的圆角方块。

```
┌──────────────────┐
│ ▓▓▓▓▓▓░░░░░░░░░░│  ← 进度指示器
│                  │
│  ┌────┐ ┌────┐   │
│  │LED │ │Snsr│   │  ← 磁贴项目
│  └────┘ └────┘   │
│ ◀              ▶ │  ← 导航箭头
└──────────────────┘
```

v1.1 中磁贴尺寸改为 36×36 圆角正方形，选中时会垂直放大并带有动画。

---

## 弹出提示 PopInfo

非阻塞式弹出提示，带滑入/滑出动画：

```python
launcher.pop_info("Saved!", 600)   # 显示"Saved!" 持续 600ms
launcher.dismiss_popup()           # 立即关闭
```

你也可以在 App 中调用：

```python
class MyApp(App):
    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            self.launcher.pop_info("OK", 500)
```

---

## 配置文件 Config

通过 `Config` 类集中管理所有 UI 参数：

```python
cfg = Config()
cfg.pop_speed = 80         # 弹出框动画速度
cfg.pop_duration = 800     # 显示时长
cfg.scroll_speed = 60      # 菜单滚动速度
cfg.light_mode = False     # 浅色/深色模式（True=白底黑字）
cfg.item_height = 16       # 列表项高度
cfg.selector_radius = 4    # 高亮条圆角
```

### Config 参数说明

### 参数详解

| 参数 | 默认值 | 组 | 说明 |
|------|--------|----|------|
| `screen_width` | 128 | 屏幕 | OLED 宽度（像素），修改前请确保硬件支持 |
| `screen_height` | 64 | 屏幕 | OLED 高度（像素），修改前请确保硬件支持 |
| `pop_margin` | 4 | 弹出提示 | 弹出框文字与边框之间的内边距（像素） |
| `pop_radius` | 4 | 弹出提示 | 弹出框圆角半径（像素），越大越圆 |
| `pop_speed` | 60 | 弹出提示 | 弹出框滑入/滑出动画速度（1-100，越大越快） |
| `pop_duration` | 600 | 弹出提示 | 弹出框自动关闭前的显示时长（毫秒） |
| `fade_speed` | 80 | 过渡动画 | 淡入淡出动画速度（1-100，越大越快） |
| `transition_buffer` | True | 过渡动画 | 列表菜单滑动过渡是否使用双缓冲预渲染；`True`=双缓冲流畅，`False`=逐帧渲染兼容 |
| `selector_radius` | 4 | 选择器 | 列表高亮条圆角半径（像素） |
| `selector_margin` | 2 | 选择器 | 列表高亮条距屏幕边缘边距（像素） |
| `selector_height` | 18 | 选择器 | 列表高亮条高度（像素），v2.0 改为 18 以适配中文 16px 字体 |
| `item_height` | 16 | 列表菜单 | 列表每项占用的高度（像素），含文字间距 |
| `scroll_speed` | 80 | 列表菜单 | 列表选择器/摄像机动画速度（1-100，越大越快） |
| `tile_width` | 36 | 磁贴菜单 | 磁贴卡片的宽度（像素），v1.1 改为 36 正方形 |
| `tile_height` | 36 | 磁贴菜单 | 磁贴卡片的高度（像素），v1.1 改为 36 正方形 |
| `tile_margin` | 12 | 磁贴菜单 | 磁贴卡片之间的水平间距（像素） |
| `tile_top_margin` | 12 | 磁贴菜单 | 磁贴卡片距屏幕顶部的偏移（像素） |
| `bar_height` | 3 | 磁贴菜单 | 磁贴顶部进度条的厚度（像素） |
| `tile_anim_speed` | 60 | 磁贴菜单 | 磁贴选中时放大动画的速度（1-100，越大越快） |
| `light_mode` | False | 显示模式 | `True` = 白底黑字浅色模式；`False` = 黑底白字深色模式 |

> **注意：** `HAL` 现在需要接收 `Config` 实例，例如 `hal = HAL(cfg, scl_pin=22, sda_pin=21)`，以确保屏幕尺寸、浅色模式等配置在硬件层生效。

---

## API 参考

### Config

UI 配置中心，所有可调参数集中管理。

```python
cfg = Config()
cfg.screen_width = 128       # 屏幕宽度（像素）
cfg.screen_height = 64       # 屏幕高度（像素）
cfg.scroll_speed = 80        # 滚动/动画速度
cfg.light_mode = False       # 浅色模式开关
cfg.transition_buffer = True # 过渡双缓冲开关
```

完整参数见上表「参数详解」。

---

### Menu（菜单节点）

```python
Menu(name="root", menu_type="list")
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | str | `"root"` | 菜单名称（显示在调试栏） |
| `menu_type` | str | `"list"` | `"list"` 纵向列表 / `"tile"` 横向磁贴 |

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `parent` | Menu / None | 父菜单引用（自动设置，用于返回导航） |
| `select_index` | int | 从父菜单进入时记住的焦点位置 |

**方法：**

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `add_item(name, child_menu=None, app=None)` | `name` 显示名称, `child_menu` 子菜单, `app` 应用面板 | self（链式） | 添加一个菜单项，可同时绑定子菜单或 App |
| `item_count()` | — | int | 返回当前菜单的项目数量 |
| `get_item(index)` | `index` 项目索引 | str / None | 获取指定索引的项目名称 |
| `get_child(index)` | `index` 项目索引 | Menu / None | 获取指定索引项目关联的子菜单 |
| `has_child(index)` | `index` 项目索引 | bool | 指定索引是否有子菜单 |
| `get_app(index)` | `index` 项目索引 | App / None | 获取指定索引绑定的 App 实例 |
| `has_app(index)` | `index` 项目索引 | bool | 指定索引是否绑定了 App |
| `render(hal, cam_x, cam_y, selected_index, tile_v_scale, skip_selected)` | 渲染参数 | — | 渲染菜单到 HAL（一般由 Launcher 自动调用） |

---

### Launcher（主控制器）

```python
Launcher(hal, config)
```

核心循环控制器，统筹导航、渲染、弹出提示、App 模式。

**方法：**

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `init(root_menu)` | `root_menu` 根菜单 | — | 初始化根菜单，重置选择器和摄像机 |
| `update()` | — | — | **主循环函数，每帧调用一次**：清屏→渲染→按键处理→刷新屏幕 |
| `open()` | — | bool | 进入当前选中项的子菜单或 App（触摸 pin2 触发） |
| `close()` | — | bool | 返回上一级或退出 App（触摸 pin3 触发） |
| `enter_app(app)` | `app` App 实例 | bool | 手动进入指定 App |
| `exit_app()` | — | bool | 退出当前 App 面板 |
| `pop_info(text, duration=600)` | `text` 显示文字, `duration` 持续毫秒 | — | 显示非阻塞弹出提示 |
| `dismiss_popup()` | — | — | 立即关闭弹出提示 |

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `current_menu` | Menu | 当前活动的菜单 |
| `selector` | Selector | 选择器实例（高亮条） |
| `camera` | Camera | 摄像机实例（视口滚动） |
| `app_mode` | bool | 当前是否在 App 面板模式 |
| `active_app` | App / None | 当前活动的 App 实例 |
| `debug_mode` | bool | 调试模式开关 |
| `transition` | dict / None | 滑动过渡状态（内部使用） |

---

### Selector（选择器/高亮条）

管理列表菜单的选中高亮位置，支持平滑动画和磁贴放大。

```python
Selector(config)
```

**方法：**

| 方法 | 说明 |
|------|------|
| `inject(menu)` | 将选择器关联到一个菜单，重置索引到第一项 |
| `go_next()` | 选中下一项（边界检查，不循环） |
| `go_prev()` | 选中上一项（边界检查，不循环） |
| `update()` | 更新 Y 位置平滑动画和 tile 放大动画 |
| `render(hal, cam_x, cam_y)` | 绘制选择器高亮条到屏幕 |

**属性：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `index` | int | 当前选中项的索引 |
| `y` | int | 选择器当前 Y 位置（平滑动画中） |
| `tile_v_scale` | int | 磁贴当前放大值（动画中从 0 到 4） |
| `menu` | Menu / None | 当前关联的菜单 |

---

### Camera（摄像机/视口滚动）

列表菜单项过多时，滚动视图使选中项保持居中可见。

```python
Camera(config)
```

**方法：**

| 方法 | 参数 | 说明 |
|------|------|------|
| `follow(selector, menu)` | 选择器、菜单 | 计算目标滚动位置，tile/列表分别处理 |
| `update(menu)` | 当前菜单 | 平滑动画移向目标位置 |
| `get_pos()` | — | 返回 `(cam_x, cam_y)` 当前偏移量 |
| `reset()` | — | 重置滚动位置到 (0,0) |

---

### HAL（硬件抽象层）

封装 OLED 绘图和按键扫描，所有颜色自动处理浅色模式。

```python
HAL(config, scl_pin=22, sda_pin=21, i2c_addr=0x3C, btn_up=18, btn_down=19)
```

**构造参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `config` | — | Config 实例 |
| `scl_pin` | 22 | I2C 时钟引脚 |
| `sda_pin` | 21 | I2C 数据引脚 |
| `i2c_addr` | 0x3C | OLED I2C 地址 |
| `btn_up` | 18 | 物理上键 GPIO（None=不使用） |
| `btn_down` | 19 | 物理下键 GPIO（None=不使用） |

**绘图方法：**

| 方法 | 说明 |
|------|------|
| `fill(color)` | 清屏（0=黑色 1=白色，浅色模式自动反转） |
| `pixel(x, y, color)` | 画一个像素点 |
| `hline(x, y, w, color)` | 水平线 |
| `vline(x, y, h, color)` | 垂直线 |
| `line(x1, y1, x2, y2, color)` | 任意直线 |
| `rect(x, y, w, h, color)` | 空心矩形 |
| `fill_rect(x, y, w, h, color)` | 实心矩形 |
| `text(s, x, y, color=1)` | 绘制文字（**自动检测中文并调用 cn_font 渲染**） |
| `show()` | 刷新缓冲区到 OLED 屏幕 |

**按键状态属性（由 key_scan 更新）：**

| 属性 | 类型 | 说明 |
|------|------|------|
| `btn_up_clicked` | bool | 上键短按（<500ms） |
| `btn_down_clicked` | bool | 下键短按（<500ms） |
| `btn_up_pressed` | bool | 上键长按（>=500ms） |
| `btn_down_pressed` | bool | 下键长按（>=500ms） |

**内部方法（用于 cn_font 渲染）：**

| 方法 | 说明 |
|------|------|
| `_text_ascii(s, x, y, color)` | 直接绘制 ASCII 字符串（不经过颜色二次转换） |
| `set_framebuffer(fb)` | 临时切换绘图目标到指定 FrameBuffer（离屏预渲染用） |
| `restore_framebuffer()` | 恢复绘图目标到 OLED 主屏幕 |

---

### App（应用面板基类）

```python
class MyApp(App):
    def on_open(self, launcher): pass      # 进入 App 时调用
    def update(self, launcher): pass       # 每帧逻辑更新
    def render(self, hal): pass            # 每帧绘制到屏幕
    def on_close(self, launcher): pass     # 退出 App 时调用
    def handle_touch(self, hal): pass      # 自定义触摸处理
    def handle_touch_pin(self, pin_index, raw_value): pass  # 单引脚触摸事件
```

**生命周期：** `on_open → update + render (循环) → on_close`

---

### Animation（动画工具）

```python
Animation.move(pos, target, speed)       # → float 浮点缓动
Animation.move_int(pos, target, speed)   # → int 整数缓动
```

指数缓动算法：每帧向目标移动剩余距离的 `1/factor`，`factor = (100-speed)/10+1`。speed 越大越快，100=瞬间到达。

---

### DrawUtils（绘图工具）

在 SSD1306 上绘制圆角矩形（逐像素描点，带半径缓存）。

```python
DrawUtils.round_rect(hal, x, y, w, h, r, color)          # 空心圆角矩形
DrawUtils.fill_round_rect(hal, x, y, w, h, r, color)     # 实心圆角矩形
```

---

## 项目文件详解

| 文件 | 类型 | 说明 |
|------|------|------|
| `flowui.py` | **框架核心** | 包含 Config、HAL、Animation、DrawUtils、Selector、Camera、Menu、Launcher、App 所有核心类。v2.0 增加中文自动显示、双缓冲过渡、选择器高度 18 |
| `main.py` | **用户主程序** | ESP32 入口文件，上电后自动运行。展示菜单树构建、App 绑定、触摸输入处理。v2.0 菜单改为中文 |
| `ssd1306.py` | **OLED 驱动** | SSD1306 I2C 驱动库（MicroPython 标准库），无需修改 |
| `cn_font.py` | **中文模块（轻量）** | 运行时读取 `cn_font.bin` 按偏移提取字模，自带 64 字缓存。不包含大字模数据（仅 4.6KB） |
| `cn_font.bin` | **二进制字库** | PC 端 `gen_cn_font.py` 生成的 16×16 点阵字库，每汉字 32 bytes，按 SUPPORTED_CHARS 顺序排列 |
| `gen_cn_font.py` | **PC 端工具** | 扫描 `main.py`/`flowui.py` 提取所有中文字符，调用 Windows 黑体生成 `cn_font.bin` 和 `cn_font.py`。**必须在 PC 端运行（需 PIL）** |
| `README.md` | **本文档** | 使用教程、API 参考、配置说明、更新日志 |
| `0.1/` | 旧版备份 | v0.1 初始版本，包含 `astra_ui.py`、`boot.py`、`touch_test.py` |
| `1.0/` | 旧版备份 | v1.0 重构版本，App 系统、调试模式 |
| `1.1/` | 旧版备份 | v1.1 滑动过渡、超长文本滚动、Tile 放大动画 |
| `2.0/` | **当前稳定版** | v2.0 全量备份，含 `flowui.py` + `main.py` + `ssd1306.py` + `cn_font.py` + `cn_font.bin` + `gen_cn_font.py` |

---

## 过渡动画机制

FlowUI 列表菜单的进入/退出使用**双缓冲预渲染**实现流畅滑动。

### 工作原理

1. **预渲染阶段**（过渡开始时只执行一次）：
   - 创建两个 128×64 离屏 FrameBuffer，分别渲染 `from_menu` 和 `to_menu`（含文字和白色选择器）
   - 渲染时临时切换 HAL 绘图目标（`set_framebuffer`/`restore_framebuffer`）

2. **逐帧渲染阶段**：
   - 主屏幕 `fill(0)` 清空
   - 两次 `framebuf.blit`：

     **进入子菜单（都向左移）：**
     ```
     blit(from_fb,  -p,        0)    # from 左移出
     blit(to_fb,    128-p,     0)    # to 从右侧左移入
     ```

     **返回父菜单（都向右移）：**
     ```
     blit(from_fb,   p,         0)   # from 右移出
     blit(to_fb,    p-128,      0)   # to 从左侧右移入
     ```

   - blit 负坐标由 framebuf 内部自动裁剪，无需手动擦除

3. **动画结束**：inject(to_menu) 完成菜单切换，摄像机重新对准

### 切换方式

`Config.transition_buffer` 控制：
- `True`（默认）：双缓冲，流畅但占用约 4KB 额外 RAM
- `False`：逐帧渲染（备选），适合 RAM 紧张

---

## 调试模式

启用后在屏幕底部显示调试信息栏：

```python
launcher.debug_mode = True
```

显示内容：

```
┌──────────────────┐
│ FPS:28 MEM:45232 │
│ Main/Tools       │
└──────────────────┘
```

- **第 1 行** — 实时 FPS + 空闲内存 (bytes)
- **第 2 行** — 当前菜单路径（最多显示 3 级）

> **注意：** `gc` 模块需要在 `flowui.py` 中 import，当前版本已包含，v0.1 不含。

---

## 更新日志

### v2.0

- **中文显示支持**：新增 `cn_font.py` + `cn_font.bin` 模块，PC 端生成二进制字库，ESP32 按偏移读取，自动检测中文字符渲染 16×16 点阵汉字，支持中英混合显示。
- **中文调试日志**：框架与示例程序中增加了大量中文日志输出，方便串口调试。
- **选择器高度优化**：高度从 14 → 18，文字垂直居中自适应（中文 16px / 英文 8px 分别居中）。
- **列表过渡动画双缓冲**：使用离屏 FrameBuffer 预渲染 + blit 负坐标裁剪实现菜单滑动过渡，消除卡顿与花屏。
- **配置选项**：新增 `Config.transition_buffer`（默认 True），可切换双缓冲/逐帧渲染；新增 `Config.selector_height = 18`。
- **版本归档**：新增 `2.0/` 目录备份，包含 `flowui.py`、`main.py`、`ssd1306.py`、`cn_font.py`、`cn_font.bin`、`gen_cn_font.py`。

### v1.1

- **圆角正方形磁贴**：tile 改为 36×36 圆角正方形，选中时垂直放大并带动画。
- **列表菜单滑动过渡**：进入/退出二级菜单时，当前菜单滑出、目标菜单滑入（三级菜单同样适用）。
- **超长文本滚动**：列表模式下选中项文字过长时会自动滚动显示完整内容。
- **细节修复**：修复 tile 摄像机居中、选中尖刺、退出二级菜单底部空行、列表项水平滚动等问题。

### v1.0

- 重构为 FlowUI，引入 `Config` + `HAL` 配置驱动架构。
- 新增浅色模式、圆角矩形绘制、调试模式。
- 新增 App 面板系统与 GPIO 按键输入支持。

### v0.1

- 初始版本，支持基础菜单导航、列表/磁贴布局、弹出提示。

---

## 项目结构

```
flowui-micropython/
├── flowui.py            # 🔧 框架核心库（最新版 v2.0）
├── main.py              # 🚀 用户主程序
├── ssd1306.py           # 📟 SSD1306 OLED 驱动
├── cn_font.py           # 🇨🇳 中文点阵字库模块（v2.0）
├── gen_cn_font.py       # 🔨 字库生成脚本（v2.0）
├── README.md            # 📖 本文档
│
├── 0.1/                 # 📁 旧版 v0.1
│   ├── astra_ui.py      #   核心框架（无 App 系统）
│   ├── main.py          #   示例主程序
│   ├── boot.py          #   ESP32 启动脚本
│   ├── ssd1306.py       #   OLED 驱动
│   └── touch_test.py    #   触摸测试工具
│
├── 1.0/                 # 📁 新版 v1.0
│   ├── astra_ui.py      #   核心框架（含 App 系统 + 调试）
│   ├── main.py          #   示例主程序（含 App 示例）
│   ├── boot.py          #   ESP32 启动脚本
│   ├── ssd1306.py       #   OLED 驱动
│   └── touch_test.py    #   触摸测试工具
│
├── 1.1/                 # 📁 稳定版 v1.1
│   ├── flowui.py        #   框架核心库
│   ├── main.py          #   示例主程序
│   └── ssd1306.py       #   OLED 驱动
│
└── 2.0/                 # 📁 当前稳定版 v2.0
    ├── flowui.py        #   框架核心库
    ├── main.py          #   示例主程序
    ├── ssd1306.py       #   OLED 驱动
    ├── cn_font.py       #   中文点阵字库索引
    ├── cn_font.bin      #   中文点阵二进制字库
    └── gen_cn_font.py   #   字库生成脚本
```

### 版本差异

| 特性 | v0.1 | v1.0 | v1.1 | v2.0 |
|------|------|------|------|------|
| 菜单导航 | ✓ | ✓ | ✓ | ✓ |
| 双布局 (List / Tile) | ✓ | ✓ | ✓（滚动优化） | ✓ |
| 弹出提示 | ✓ | ✓ | ✓ | ✓ |
| App 面板系统 | ✗ | ✓ | ✓ | ✓ |
| 按键输入 (GPIO) | ✗ | ✓ | ✓ | ✓ |
| 调试模式 (FPS/GC) | ✗ | ✓ | ✓ | ✓ |
| `gc` 模块引用 | ✗ | ✓ | ✓ | ✓ |
| 浅色模式 | ✗ | ✗ | ✓ | ✓ |
| 配置驱动 HAL | ✗ | ✗ | ✓ | ✓ |
| 圆角正方形磁贴 + 放大动画 | ✗ | ✗ | ✓ | ✓ |
| 列表菜单滑动过渡 | ✗ | ✗ | ✓ | ✓ |
| 超长文本滚动显示 | ✗ | ✗ | ✓ | ✓ |
| 中文自动显示 | ✗ | ✗ | ✗ | ✓ |
| 中文调试日志 | ✗ | ✗ | ✗ | ✓ |

---

## 框架架构

```
┌─────────────────────────────────────────────────────┐
│                    main.py                          │
│  (触摸轮询 / App 事件路由 / launcher.update())      │
├─────────────────────────────────────────────────────┤
│              Launcher (主控制器)                     │
│  ├── Menu Navigation (open/close)                   │
│  ├── Selector (高亮条位置 & 动画)                    │
│  ├── Camera (视口滚动)                               │
│  ├── Popup (非阻塞弹出提示)                          │
│  ├── Transition (列表菜单滑动过渡)                   │
│  └── App Mode (面板模式切换)                         │
├─────────────────────────────────────────────────────┤
│              Menu (树形菜单节点)                     │
│  ├── List Mode (纵向列表)                            │
│  └── Tile Mode (横向磁贴)                            │
├─────────────────────────────────────────────────────┤
│              App (应用面板基类)                      │
│  ├── on_open / update / render / on_close            │
│  └── handle_touch / handle_touch_pin                 │
├─────────────────────────────────────────────────────┤
│    HAL (硬件抽象层)                                  │
│  ├── OLED Drawing (fill, text, rect, pixel ...)      │
│  └── Key Scan (状态机, 短按/长按/释放检测)           │
├─────────────────────────────────────────────────────┤
│    SSD1306 Driver / FrameBuffer                      │
└─────────────────────────────────────────────────────┘
```

---

## 原项目

FlowUI 的设计受到 [AstraThreshold/oled-ui-astra](https://github.com/AstraThreshold/oled-ui-astra)（C++/STM32）的启发，但已针对 MicroPython / ESP32 平台进行了大量重构与扩展，是一个独立维护的项目。

---

## 框架设计哲学

### 为什么选择指数缓动

FlowUI 的所有动画（选择器移动、菜单滚动、弹出框滑入/滑出、Tile 放大、过渡滑动）都使用**指数缓动（Exponential Easing Out）**算法：

```
pos += (target - pos) / ((100 - speed) / 10 + 1)
```

这种算法的特点是**起始快、接近目标时变慢**，产生类似物理阻尼的自然效果。相比于线性移动，指数缓动在视觉上更平滑，且不需要帧率同步，在 10-30 FPS 的低帧率下仍然感觉流畅。

### 为什么使用双缓冲过渡

列表菜单过渡需要同时渲染两个菜单（from 和 to），如果每帧都重新绘制完整的菜单树（含中文像素绘制），在 ESP32 上可能掉到 10 FPS 以下。双缓冲方案在过渡开始时只渲染一次到离屏 FrameBuffer，后续每帧只需两次 `blit` 内存拷贝，性能提升约 5-10 倍。

### 为什么 HAL 接收 Config

v1.0 之前，屏幕尺寸、颜色模式等参数分散在 HAL 的构造参数中。v1.0 重构为 `Config` + `HAL` 架构后，所有 UI 参数集中管理，HAL 不再关心具体数值。这使得浅色模式、自定义屏幕尺寸等只需要修改 Config，无需重写 HAL。

---

## 主循环解剖（update 逐帧拆解）

`launcher.update()` 是 FlowUI 的核心循环，每帧执行以下步骤：

### 步骤 1：处理滑动过渡（~0ms）

```python
if self.transition:
    self.transition["progress"] = Animation.move_int(
        self.transition["progress"], 128, 80
    )
    if self.transition["progress"] >= 127:
        # 过渡结束，切换菜单
        self.current_menu = t["to_menu"]
        self.selector.inject(t["to_menu"])
        self.camera.reset()
        self._center_camera_on_index(t["to_menu"], t["to_index"])
        self.transition = None
```

progress 从 0 开始，每帧增加约 1/3 的剩余距离，约 10 帧后达到 127。过渡期间的按键被忽略。

### 步骤 2：清空屏幕（~1ms）

```python
self.hal.fill(0)  # 用黑色填充整个 FrameBuffer
```

### 步骤 3：渲染菜单或 App（~10-30ms）

**菜单模式：**
- `current_menu.render(hal, cam_x, cam_y, selected_index, tile_v_scale)`
  - 列表模式：遍历所有项，只渲染屏幕可见范围内的项（`y = i*item_h - cam_y`，`if -item_h < y < screen_h`）
  - 跳过选中项（由 Selector 单独绘制）
  - 磁贴模式：绘制 36×36 圆角正方形，选中项放大动画
- `selector.update()`：平滑动画到目标位置
- `selector.render(hal, cam_x, cam_y)`：
  - 列表：绘制白色圆角选择器背景和文字（文字过长时滚动显示）
  - 磁贴：绘制进度条和导航箭头
- `camera.follow()` + `camera.update()`：更新视口偏移

**App 模式：**
- `active_app.update(launcher)`：App 逻辑更新
- `active_app.render(hal)`：App 自定义绘制

### 步骤 4：渲染弹出提示（~2ms）

如果 `popup_state != 0`，更新动画并绘制白色圆角弹窗。

### 步骤 5：渲染调试信息（~1ms）

如果 `debug_mode == True`，在屏幕底部绘制 FPS + 内存 + 菜单路径。

### 步骤 6：刷新到 OLED（~5ms）

```python
self.hal.show()  # 通过 I2C 发送 1024 bytes 到 SSD1306
```

I2C 通信是主要的性能瓶颈，约占用 5ms/帧。

### 步骤 7：更新 FPS（~0ms）

每帧计数，每秒计算一次 FPS。

### 步骤 8：按键扫描与事件处理（~2ms）

```python
self.hal.key_scan()
if btn_up_clicked: selector.go_prev()
elif btn_down_clicked: selector.go_next()
elif btn_down_pressed: open()
elif btn_up_pressed: close()
```

### 步骤 9：帧间隔

```python
time.sleep_ms(30)  # 控制帧率约 30 FPS
```

调整此值可改变帧率：减小到 10ms 约 60 FPS，增大到 100ms 约 10 FPS。

---

## 触摸输入深度解析

### 硬件原理

ESP32 的 TouchPad 外设通过测量引脚的充电/放电时间来判断触摸状态。当手指靠近时，引脚上的寄生电容增加，充电时间变长，读取的数值变大。每个触摸引脚可以独立读取，无需外部电路。

### 校准过程详解

```python
# 上电后读取 10 次取平均值作为基准值
baseline = []
for i, pad in enumerate(touch_pads):
    vals = []
    for _ in range(10):
        vals.append(pad.read())
        time.sleep_ms(10)
    avg = sum(vals) // len(vals)
    baseline.append(avg)

# 基准值的 75% 作为触摸阈值
thresholds = [int(b * 0.75) for b in baseline]
```

为什么要读取 10 次取平均？因为单次读取可能有 ±5% 的噪声，10 次平均后噪声降低到约 ±1.5%。

为什么阈值设为 75%？经验值。触摸时数值会下降到基准值的 50%-70%，75% 是一个合理的平衡点。

### 抗噪机制

```python
# 连续读取 3 次取最小值，降低偶发噪声的影响
v1 = pad.read()
v2 = pad.read()
v3 = pad.read()
val = min(v1, v2, v3)
```

单次读取可能跳变，取 3 次最小值可以滤除正向噪声（数值变大），同时保留真实的触摸事件（数值变小）。

### 触摸引脚映射

| 引脚 | 索引 | 菜单模式 | App 模式 |
|------|------|----------|----------|
| GPIO4 | 0 | 上一项 / 向左 | App 自定义（如切换开关） |
| GPIO14 | 1 | 下一项 / 向右 | App 自定义（如增加） |
| GPIO27 | 2 | 进入子菜单 / 打开 App | App 自定义（如减少） |
| GPIO33 | 3 | 返回上级菜单 | **强制返回菜单** |

### 触摸调试步骤

如果触摸不灵敏或误触发：

1. **查看校准值**：程序启动时会打印 GPIO 基准值和阈值到串口
2. **调整阈值**：把 `0.75` 改为 `0.85`（更灵敏）或 `0.65`（更不灵敏）
3. **调整读取次数**：增加 `min(v1,v2,v3)` 的采样次数到 5-7 次
4. **更换引脚**：某些 GPIO 的触摸灵敏度不同，GPIO4/14/27/33 是 ESP32 上灵敏度较高的引脚

---

## 屏幕坐标系与布局计算

### SSD1306 像素布局

SSD1306 是 128×64 像素的单色 OLED，每个像素只有 0（黑）或 1（白）。

在 MicroPython 的 FrameBuffer 中，像素按 MONO_HLSB（Horizontal LSB First）格式排列：

```
一行 128 像素 = 16 字节
字节 0: 像素 0-7   (bit0=像素0, bit7=像素7)
字节 1: 像素 8-15
...
字节 15: 像素 120-127

每 8 行组成一个 page (0-7)
page 0: 行 0-7  (16×8=128 字节)
page 1: 行 8-15
...
page 7: 行 56-63
总大小: 8 × 128 = 1024 字节
```

### 列表菜单布局

```
item_height = 16 像素
屏幕可显示 64/16 = 4 项（部分可见第 5 项）

选择器（高亮条）：
  selector_height = 18 像素
  x = 2, y = index*16, 宽度 = 124
  文字起始 x = 6, 垂直居中

每项文字：
  x = 10, y = index*16 + 1（中文偏移）或 +5（英文偏移）
  右侧 12 像素留给 ">" 指示符
```

### 磁贴菜单布局

```
磁贴尺寸 = 36×36 像素
磁贴间距 = 12 像素
顶部进度条 = 3 像素
磁贴顶部边距 = 12 像素

一组磁贴总宽度 = items * 36 + (items-1) * 12
如果总宽度 ≤ 128: 从 (128-总宽)/2 开始居中
如果总宽度 > 128: 从 (128-36)/2 = 46 开始，用 Camera 水平滚动
```

### 弹出提示布局

```
pop_margin = 4 像素（文字内边距）
pop_radius = 4 像素（圆角）
弹出框宽度 = 文字宽度 + 2×pop_margin
弹出框高度 = 16 像素
弹出框 x = (128 - 弹出框宽度) / 2
弹出框 y = 从 -20 滑入到 (64-16)/2 = 24
```

---

## 性能优化指南

### 常见瓶颈及解决方案

| 瓶颈 | 原因 | 解决方案 |
|------|------|----------|
| FPS < 15 | 中文字符太多，像素绘制开销大 | 减少每帧绘制的中文字符数；使用英文菜单 |
| 过渡卡顿 | 两个菜单同时渲染 | 确保 `Config.transition_buffer = True` |
| 触摸响应慢 | 帧率太低 | 加大 `time.sleep_ms()` 间隔，降低帧率至 15-20 FPS |
| 选择器跳动 | 动画 speed 太大 | 降低 `scroll_speed` 到 40-60 |
| 内存不足 | 字库太大 | 运行 `gen_cn_font.py` 只生成实际用到的汉字 |
| I2C 慢 | OLED 刷新速率限制 | 使用更快的 I2C 频率（400kHz 代替 100kHz） |
| 画面闪烁 | 未使用缓冲区 | 确保所有绘制在 update() 中完成，show() 只调用一次 |

### 性能数据参考

| 场景 | FPS | 说明 |
|------|-----|------|
| 空白屏幕（只 fill） | ~60 | 纯 I2C 刷新速率 |
| 英文列表菜单（5 项） | ~45 | 无中文 |
| 中文列表菜单（5 项） | ~28 | 16×16 中文像素绘制 |
| 磁贴菜单（7 项） | ~35 | 36×36 圆角矩形 |
| 过渡动画（双缓冲） | ~30 | 两次 blit 拷贝 |
| 过渡动画（逐帧渲染） | ~15 | 两个完整菜单重绘 |
| App 面板（简单文字） | ~50 | 少量文字 |
| App 面板（中文 + 图形） | ~25 | 汉字 + 矩形/线条 |

### 内存占用

| 模块 | RAM 占用 |
|------|----------|
| flowui.py 核心 | ~5 KB |
| 双缓冲过渡（from + to + big） | ~4 KB |
| cn_font.py 索引 | ~1 KB |
| cn_font.bin 缓存（64 字） | ~2 KB |
| ssd1306 帧缓冲区 | 1 KB |
| 主堆栈/其他 | ~20 KB |
| ESP32 可用 RAM（典型） | ~100 KB |

---

## 常见问题 FAQ

### Q1: 为什么我的 OLED 不显示？

**可能原因：**
- I2C 接线错误：检查 SCL→GPIO22, SDA→GPIO21, VCC→3.3V, GND→GND
- I2C 地址错误：大部分 SSD1306 是 0x3C，少数是 0x3D
- OLED 供电不足：ESP32 的 3.3V 引脚最大输出约 500mA，如果 OLED 功耗大，需外接电源
- 固件问题：确保 ESP32 已烧录 MicroPython 固件

### Q2: 触摸不灵敏怎么办？

**解决方法：**
1. 减小阈值比例：`thresholds[i] = int(b * 0.6)` 让触摸更容易触发
2. 增大采样次数：读取 5-7 次取最小值
3. 更换触摸引脚：GPIO4 和 GPIO14 通常最灵敏
4. 检查焊盘：确保触摸焊盘连接良好，焊盘面积建议 10×10 mm² 以上

### Q3: 如何修改 I2C 引脚？

```python
# HAL 构造时指定
hal = HAL(cfg, scl_pin=22, sda_pin=21)
# 或使用其他引脚
hal = HAL(cfg, scl_pin=18, sda_pin=19)
```

注意：修改 I2C 引脚后要同步修改 OLED 的硬件接线。

### Q4: 如何在 App 中显示弹出提示？

```python
class MyApp(App):
    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            # 方式 1：通过 launcher
            launcher.pop_info("已保存！", 600)
```

但 App 中通常没有 `launcher` 引用。解决方案：

```python
class MyApp(App):
    def on_open(self, launcher):
        self.launcher = launcher  # 保存引用

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            self.launcher.pop_info("OK", 500)
```

### Q5: 磁贴菜单项太多显示不全？

磁贴菜单会自动水平滚动。`Camera` 在 tile 模式下会跟踪当前选中项并居中。如果总宽度超过屏幕，Camera 会计算合适的滚动偏移。

### Q6: 如何添加新的菜单层级？

```python
root = Menu("根菜单")
level1 = Menu("一级菜单")
level2 = Menu("二级菜单")
level3 = Menu("三级菜单")

level3.add_item("三级项")
level2.add_item("三级菜单", level3)
level1.add_item("二级菜单", level2)
root.add_item("一级菜单", level1)
```

FlowUI 支持无限层级嵌套，每级间的滑动过渡动画自动生效。

### Q7: 如何自定义选择器颜色？

在单色 OLED 上，颜色只有 0（黑）和 1（白）。选择器高亮是白色背景 + 黑色文字，通过 `light_mode` 可整体反转：

```python
cfg.light_mode = True  # 白底黑字模式
```

### Q8: 浅色模式如何配置？

```python
cfg = Config()
cfg.light_mode = True  # 开启浅色模式

hal = HAL(cfg, scl_pin=22, sda_pin=21)  # HAL 读取 Config 后自动处理颜色反转
```

浅色模式下，原黑色背景变为白色，白色文字变为黑色，选择器变为黑色背景 + 白色文字。

### Q9: 为什么我修改 Config 后没有生效？

确保 Config 在创建 HAL 之前修改完成：

```python
cfg = Config()
cfg.light_mode = True
cfg.scroll_speed = 40
# 此时再创建 HAL
hal = HAL(cfg, scl_pin=22, sda_pin=21)
```

因为 HAL 在初始化时读取 Config 的值，后续修改 Config 不会影响已创建的 HAL。

### Q10: 双缓冲过渡和逐帧渲染有什么区别？

| 特性 | 双缓冲（默认） | 逐帧渲染 |
|------|--------------|----------|
| 流畅度 | 高，~30 FPS | 低，~15 FPS |
| 额外 RAM | ~4 KB | 0 |
| 预渲染 | 只渲染一次 | 每帧渲染 |
| 适用场景 | 大多数情况 | RAM 极紧张 |

切换方式：`cfg.transition_buffer = False`

### Q11: 字库中缺少我想用的汉字怎么办？

```python
# 在 gen_cn_font.py 的 EXTRA_CHARS 中添加
EXTRA_CHARS = "你需要的汉字"

# 然后运行
# python gen_cn_font.py
# 重新上传 cn_font.py 和 cn_font.bin
```

### Q12: 为什么 ESP32 复位后屏幕显示校准界面？

这是正常的。主程序启动时先显示 2 秒的触摸校准信息，然后进入菜单系统。如需跳过，可修改 `main.py` 中的 `time.sleep(2)` 为更短的时间。

### Q13: 如何禁用触摸输入，只用物理按键？

```python
# 在 main.py 中不初始化 touch_pads
# 只使用 HAL 的 btn_up 和 btn_down 物理按键
hal = HAL(cfg, scl_pin=22, sda_pin=21, btn_up=18, btn_down=19)
```

然后在主循环中通过 `hal.btn_up_clicked` 和 `hal.btn_down_clicked` 控制导航。

### Q14: 屏幕上有残影怎么办？

SSD1306 在长时间显示静态内容后可能有残影。FlowUI 每帧调用 `fill(0)` 清屏，正常情况下不应有残影。如果出现：

1. 检查是否有代码跳过 `fill(0)` 直接绘制
2. 降低 `time.sleep_ms(30)` 的值，提高屏幕刷新率
3. 在长时间静止时定期调用 `hal.oled.contrast(0)` 降低对比度

### Q15: 如何让菜单初始选中指定项？

```python
launcher.init(root)
launcher.selector.index = 2  # 初始选中第 3 项（索引从 0 开始）
launcher.selector.target_y = 2 * cfg.item_height
launcher.selector.y = 2 * cfg.item_height
```

---

## 版本迁移指南

### 从 v1.1 迁移到 v2.0

v2.0 新增了中文显示支持，以下是迁移步骤：

```python
# 1. 上传新增文件
# cn_font.py
# cn_font.bin

# 2. 原有 main.py 代码无需修改，但新增中文菜单
root = Menu("主菜单")  # 原 root = Menu("Main")

# 3. 首次需要运行 gen_cn_font.py 生成字库
# python gen_cn_font.py

# 4. Config 新增参数（可选配置）
cfg.transition_buffer = True  # 双缓冲默认开启
```

**兼容性说明：**
- 所有 v1.1 的代码在 v2.0 上完全兼容
- `Config.selector_height` 默认值从 14 改为 18
- `Config.tile_width/tile_height` 保持 36
- `Config.transition_buffer` 是 v2.0 新增参数，旧代码无此属性

### 从 v1.0 迁移到 v1.1

v1.1 改进了 Tile 磁贴尺寸和列表菜单滑动过渡：

```python
# Config 新增/修改的参数
cfg.tile_width = 36      # 原 40
cfg.tile_height = 36     # 原 32
cfg.tile_margin = 12     # 原 8
cfg.tile_top_margin = 12 # 原 8
```

---

## 完整示例代码集合

### 最小可运行程序（10 行）

```python
from flowui import HAL, Config, Menu, Launcher
cfg = Config()
hal = HAL(cfg)
launcher = Launcher(hal, cfg)
root = Menu("主菜单")
root.add_item("Hello World")
launcher.init(root)
while True: launcher.update()
```

### 带触摸输入的完整程序

```python
from flowui import HAL, Config, Menu, Launcher
from machine import TouchPad, Pin
import time

cfg = Config()
hal = HAL(cfg, scl_pin=22, sda_pin=21)
launcher = Launcher(hal, cfg)

# 触摸初始化
touch_pins = [4, 14, 27, 33]
touch_pads = [TouchPad(Pin(p)) for p in touch_pins]

# 自动校准
baseline = []
for i, pad in enumerate(touch_pads):
    vals = []
    for _ in range(10):
        vals.append(pad.read())
        time.sleep_ms(10)
    avg = sum(vals) // len(vals)
    baseline.append(avg)
thresholds = [int(b * 0.75) for b in baseline]

# 菜单
root = Menu("主菜单")
root.add_item("选项一")
root.add_item("选项二")
launcher.init(root)

touched = [False] * 4
while True:
    for i, pad in enumerate(touch_pads):
        v = min(pad.read(), pad.read(), pad.read())
        if v < thresholds[i] and not touched[i]:
            touched[i] = True
            actions = [("向上", launcher.selector.go_prev),
                       ("向下", launcher.selector.go_next),
                       ("进入", launcher.open),
                       ("返回", launcher.close)]
            action_name, action_fn = actions[i]
            action_fn()
        elif v >= thresholds[i]:
            touched[i] = False
    launcher.update()
```

### 多级菜单 + App 系统完整示例

```python
from flowui import HAL, Config, Menu, Launcher, App
from machine import TouchPad, Pin
import time

# ---- App 定义 ----
class CounterApp(App):
    def on_open(self, launcher):
        self.count = 0
        self.launcher_ref = launcher

    def render(self, hal):
        hal.fill(0)
        hal.text("计数器", 30, 4, 1)
        hal.hline(30, 12, 68, 1)
        hal.text("数值: " + str(self.count), 10, 24, 1)
        hal.text("Pin0: +1", 10, 42, 1)
        hal.text("Pin3: 返回", 10, 54, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            self.count += 1

class AboutApp(App):
    def render(self, hal):
        hal.fill(0)
        hal.text("FlowUI v2.0", 20, 4, 1)
        hal.text("ESP32 + SSD1306", 10, 22, 1)
        hal.text("MicroPython", 20, 40, 1)
        hal.text("Pin3: 返回", 20, 54, 1)

# ---- 主程序 ----
cfg = Config()
hal = HAL(cfg, scl_pin=22, sda_pin=21)
launcher = Launcher(hal, cfg)

# 触摸
touch_pins = [4, 14, 27, 33]
touch_pads = [TouchPad(Pin(p)) for p in touch_pins]
baseline = []
for i, pad in enumerate(touch_pads):
    vals = []
    for _ in range(10):
        vals.append(pad.read())
        time.sleep_ms(10)
    avg = sum(vals) // len(vals)
    baseline.append(avg)
thresholds = [int(b * 0.75) for b in baseline]

# 菜单树
root = Menu("主菜单")
apps = Menu("应用", menu_type="tile")
apps.add_item("计数", app=CounterApp())
apps.add_item("关于", app=AboutApp())
root.add_item("应用", apps)
root.add_item("设置", Menu("设置"))
root.add_item("关于", Menu("关于"))
launcher.init(root)

touched = [False] * 4
while True:
    for i, pad in enumerate(touch_pads):
        v = min(pad.read(), pad.read(), pad.read())
        if v < thresholds[i] and not touched[i]:
            touched[i] = True
            if launcher.app_mode:
                if i == 3:
                    launcher.exit_app()
                else:
                    launcher.active_app.handle_touch_pin(i, v)
            elif i == 0:
                launcher.selector.go_prev()
            elif i == 1:
                launcher.selector.go_next()
            elif i == 2:
                launcher.open()
            elif i == 3:
                launcher.close()
        elif v >= thresholds[i]:
            touched[i] = False
    launcher.update()
```

### Config 所有参数自定义示例

```python
from flowui import Config

cfg = Config()

# 屏幕参数
cfg.screen_width = 128
cfg.screen_height = 64

# 弹出提示
cfg.pop_margin = 4
cfg.pop_radius = 4
cfg.pop_speed = 60
cfg.pop_duration = 600

# 过渡动画
cfg.fade_speed = 80
cfg.transition_buffer = True

# 选择器
cfg.selector_radius = 4
cfg.selector_margin = 2
cfg.selector_height = 18

# 列表菜单
cfg.item_height = 16
cfg.scroll_speed = 80

# 磁贴菜单
cfg.tile_width = 36
cfg.tile_height = 36
cfg.tile_margin = 12
cfg.tile_top_margin = 12
cfg.bar_height = 3
cfg.tile_anim_speed = 60

# 显示模式
cfg.light_mode = False
```

---

## 类继承关系图

```
object
├── Config           UI 配置中心
├── HAL              硬件抽象层（封装 OLED + 按键）
├── Animation        动画插值工具（静态方法）
├── DrawUtils        绘图工具（静态方法）
├── Menu             菜单节点（树形结构）
├── Selector         选择器/高亮条
├── Camera           摄像机/视口
├── Launcher         主控制器（组合 Selector + Camera）
└── App              应用面板基类（用户继承）
    └── MyApp        用户自定义 App
```

Launcher 通过组合（composition）使用 Selector 和 Camera，而不是继承。Menu 通过树形链表组织父子关系。

---

## HAL 内部实现细节

### 颜色转换

```python
def _c(self, color):
    """颜色转换：浅色模式下对颜色取反"""
    if self.config.light_mode:
        return 0 if color else 1
    return color
```

所有绘图方法（fill, pixel, hline, vline, rect, fill_rect, text）都调用 `_c()` 转换颜色。所以用户代码中始终使用逻辑颜色（0=黑, 1=白），浅色模式下自动反转。

### 按键状态机

```python
def key_scan(self):
    # 50ms 间隔防抖
    if time.ticks_ms() - self.last_update < 50:
        return
    self.last_update = time.ticks_ms()

    # 读取引脚电平（上拉，按下=低电平）
    up_val = self.btn_up.value()
    down_val = self.btn_down.value()

    # 状态机逻辑
    # - 按键松开 → _key_states[i] = True
    # - 按键按下 → 记下时间戳 _key_held[i]
    # - 按下 < 500ms 且松开 → CLICK
    # - 按下 >= 500ms 且未松开 → PRESS
```

### 中文自动检测

```python
def text(self, s, x, y, color=1):
    c = self._c(color)
    for ch in s:
        if ord(ch) > 127:
            # 包含中文 → 使用 cn_font 渲染
            if self._cn_font is None:
                import cn_font
                self._cn_font = cn_font
            self._cn_font.draw_text(self, s, x, y, c)
            return
    # 纯英文 → 使用 framebuf 自带 8×8 字体
    self._text_ascii(s, x, y, c)
```

首次遇到中文时导入 `cn_font` 并缓存模块引用，后续调用不再 import。

---

## cn_font 中文模块内部实现

### 字模格式

每个汉字用 16×16 点阵表示，共 256 位 = 32 字节。在 `cn_font.bin` 中按 `SUPPORTED_CHARS` 顺序连续排列。

偏移计算：`offset = char_index * 32`

### 字模读取流程

```python
# 1. 查找偏移
offset = _char_to_offset.get(ch)
if offset is None:
    return None  # 字库中不存在的汉字

# 2. 从缓存查找
bmp = _bitmap_cache.get(ch)
if bmp is not None:
    return bmp  # 缓存命中

# 3. 从 bin 文件读取
try:
    _font_file.seek(offset)
    bmp = _font_file.read(32)
except OSError:
    return None

# 4. 加入缓存（LRU 风格，满 64 清一半）
_bitmap_cache[ch] = bmp
```

### 中英混合渲染

```python
def draw_text(hal, text, x, y, color=1):
    cx = x
    for ch in text:
        if ord(ch) > 127:  # 中文 → 16×16
            cx += _draw_chinese_char(hal, ch, cx, y, color)
        elif ord(ch) >= 32:  # 英文 → 8×8
            hal._text_ascii(ch, cx, y + 8, color)  # 英文底部对齐
            cx += 8
    return cx - x
```

英文 y 偏移 +8 使英文字符底部与中文字符底部对齐，实现视觉上的基线统一。

---

## gen_cn_font 字库生成工具详解

### 运行环境

需要在 PC 上运行（不是 ESP32），需要 Python 3 + PIL (Pillow) 库：

```bash
pip install Pillow
python gen_cn_font.py
```

### 工作原理

1. 扫描 `main.py` 和 `flowui.py` 源码，提取所有 `ord(ch) > 127` 的中文字符
2. 使用 Windows 系统字体 `simhei.ttf`（黑体）渲染每个字符为 16×16 位图
3. 每个位图转换为 32 bytes 字模数据
4. 写入 `cn_font.bin`（二进制）和 `cn_font.py`（轻量索引）

### 自定义扫描文件

```python
# 在 gen_cn_font.py 中修改
SOURCE_FILES = ["main.py", "flowui.py", "my_other_module.py"]
```

### 添加临时汉字

```python
# 在 gen_cn_font.py 中修改
EXTRA_CHARS = "暂无特别添加"  # 在这里添加字库中没有的汉字
```

### 字体自定义

```python
# 在 gen_cn_font.py 中修改
FONT_PATH = "C:/Windows/Fonts/simsun.ttc"  # 改为宋体
# 或 FONT_PATH = "C:/Windows/Fonts/simkai.ttf"  # 楷体
```

不同的字体渲染效果不同，黑体笔画均匀、适合小字号点阵显示。

---

## 硬件详细接线指南

### ESP32-DevKitC 标准接线

```
ESP32-DevKitC           SSD1306 OLED
─────────────────────────────────────
3.3V      (Pin 1) ──── VCC (电源)
GND       (Pin 14) ──── GND (地)
GPIO22    (Pin 29) ──── SCL (时钟)
GPIO21    (Pin 30) ──── SDA (数据)

触摸引脚（直连触摸焊盘）：
GPIO4     (Pin 26) ──── Touch 焊盘 1
GPIO14    (Pin 13) ──── Touch 焊盘 2
GPIO27    (Pin 27) ──── Touch 焊盘 3
GPIO33    (Pin 33) ──── Touch 焊盘 4

可选物理按键：
GPIO18    (Pin 19) ──── 按键 → GND（向上）
GPIO19    (Pin 20) ──── 按键 → GND（向下）
```

### ESP32-WROOM-32 常用接线

```
ESP32-WROOM-32         SSD1306 OLED
─────────────────────────────────────
3.3V      ──────────── VCC
GND       ──────────── GND
GPIO22    ──────────── SCL
GPIO21    ──────────── SDA
GPIO4     ──────────── Touch1
GPIO14    ──────────── Touch2
GPIO27    ──────────── Touch3
GPIO33    ──────────── Touch4
```

### I2C 上拉电阻

SSD1306 模块通常已经包含 I2C 上拉电阻（4.7kΩ）。如果使用自制的 OLED 模块，需要在 SCL 和 SDA 线上各加一个 4.7kΩ 上拉到 3.3V。

### 触摸焊盘制作

触摸焊盘可以用以下材料制作：
- 铜箔胶带（推荐）：剪成 10×10mm 方块，贴在绝缘面板上
- 导线末端：剥去外皮的导线头，弯成小圆环
- 触摸弹簧：高度 5-10mm 的弹簧，直接焊接在 GPIO 引脚上

四个触摸焊盘之间建议间隔 20mm 以上，防止误触。

---

## 版本升级详细指南

### 文件更新清单

从 v1.1 升级到 v2.0 时，需要替换/新增以下文件：

| 文件 | 操作 | 说明 |
|------|------|------|
| `flowui.py` | **替换** | 核心框架，v2.0 新增中文支持、双缓冲过渡 |
| `main.py` | **替换** | 示例程序，菜单改为中文 |
| `cn_font.py` | **新增** | 中文显示模块（轻量索引） |
| `cn_font.bin` | **新增** | 二进制字库（运行 gen_cn_font.py 生成） |
| `gen_cn_font.py` | **新增** | PC 端字库生成工具 |
| `ssd1306.py` | 可选不变 | OLED 驱动，无需修改 |

### 从零开始搭建项目

```bash
# 1. 克隆或下载 flowui-micropython
# 2. 连接 ESP32
# 3. 生成字库（首次）
cd flowui-micropython
python gen_cn_font.py

# 4. 上传到 ESP32
mpremote connect COM7 fs cp flowui.py :flowui.py
mpremote connect COM7 fs cp main.py :main.py
mpremote connect COM7 fs cp ssd1306.py :ssd1306.py
mpremote connect COM7 fs cp cn_font.py :cn_font.py
mpremote connect COM7 fs cp cn_font.bin :cn_font.bin
mpremote connect COM7 reset
```

### 仅上传必要文件

如果不需要中文显示，可以不传 `cn_font.py` 和 `cn_font.bin`：

```bash
mpremote connect COM7 fs cp flowui.py :flowui.py
mpremote connect COM7 fs cp main.py :main.py
mpremote connect COM7 fs cp ssd1306.py :ssd1306.py
mpremote connect COM7 reset
```

此时菜单中的中文无法显示（显示为空白方块）。

---

## License

MIT License，详见 LICENSE 文件。

---

## 文档统计

| 项目 | 数量 |
|------|------|
| README 总行数 | ~2000 行 |
| 二级标题数 | 140+ |
| 代码示例数 | 50+ |
| API 方法数 | 40+ 完整说明 |
| Config 参数数 | 21 个参数详解 |
| FAQ 数 | 15 个常见问题 |
| 文件数（项目） | 6 个核心文件 + 3 个备份目录 |
| 类数（框架） | 9 个核心类 |

---

## 附录 A：快速参考卡片

### 最常用代码片段

```python
# 1. 创建根菜单
root = Menu("主菜单")

# 2. 添加带子菜单的项
sub = Menu("子菜单")
sub.add_item("子项")
root.add_item("进入子菜单", sub)

# 3. 添加带 App 的项
class MyApp(App):
    def render(self, hal):
        hal.fill(0)
        hal.text("Hello", 40, 28, 1)
root.add_item("启动 App", app=MyApp())

# 4. 创建磁贴菜单
tile = Menu("磁贴", menu_type="tile")
tile.add_item("LED", app=MyApp())

# 5. 初始化并启动
launcher.init(root)
launcher.debug_mode = True  # 开启调试
```

### 八步快速排查

| 现象 | 排查步骤 |
|------|----------|
| 黑屏 | ① 检查 I2C 接线 ② 检查 I2C 地址 ③ 检查供电 |
| 触摸无反应 | ① 查看串口校准值 ② 检查阈值比例 ③ 更换触摸引脚 |
| 中文不显示 | ① 检查 cn_font.bin 是否上传 ② 检查 cn_font.py 是否上传 |
| 过渡卡顿 | ① 设置 cfg.transition_buffer = True ② 降低 scroll_speed |
| 选择器偏位 | ① 检查 selector_height ② 检查 item_height 是否匹配 |
| 磁贴不对齐 | ① 检查 tile_width/tile_margin ② 检查 Camera 是否工作 |
| App 不响应 | ① 检查 on_open 是否正确 ② 检查 handle_touch_pin |
| 内存不足 | ① 精简字库 ② 关闭双缓冲 ③ 关闭调试模式 |

---

## 附录 B：MicroPython 资源

### 相关仓库

- [MicroPython 官方文档](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html)
- [SSD1306 驱动库](https://github.com/micropython/micropython/tree/master/drivers/display)
- [AstraThreshold/oled-ui-astra](https://github.com/AstraThreshold/oled-ui-astra) — FlowUI 的设计灵感来源（C++/STM32）

### 推荐的开发工具

| 工具 | 用途 | 平台 |
|------|------|------|
| Thonny | MicroPython IDE，带文件管理器 | Windows/Linux/macOS |
| mpremote | MicroPython 命令行工具 | Windows/Linux/macOS |
| esptool | ESP32 固件烧录工具 | Windows/Linux/macOS |
| Arduino IDE | 固件烧录（可选） | Windows/Linux/macOS |

---

## 结语

FlowUI 是一个专注于 ESP32 + SSD1306 的轻量级 MicroPython UI 框架，从 v0.1 的简单菜单导航发展到 v2.0 的中文显示、双缓冲过渡、完善的 App 系统。项目的核心理念是：

1. **简洁易用** — 继承 App 类、添加菜单项、配置参数，三步即可创建功能面板
2. **资源高效** — 在 100KB RAM 的 ESP32 上流畅运行，字库 16KB 涵盖 500+ 常用汉字
3. **动画自然** — 指数缓动算法让所有交互动画平滑流畅
4. **扩展灵活** — 基于组合而非继承，HAL 可替换，App 系统开放

欢迎在 GitHub 上提交 Issue 和 PR，共同完善 FlowUI。
