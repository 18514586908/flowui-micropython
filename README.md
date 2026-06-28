
<div align="center">

# FlowUI — MicroPython

<img src="https://img.shields.io/badge/MicroPython-ESP32-green?style=flat-square&logo=micropython" />
<img src="https://img.shields.io/badge/OLED-SSD1306%20128x64-blue?style=flat-square" />
<img src="https://img.shields.io/badge/license-MIT-orange?style=flat-square" />

**FlowUI** 是一个轻量级的 OLED 用户界面框架，面向 **ESP32 + SSD1306 OLED 128×64** 的 **MicroPython** 平台。它在 [AstraThreshold/oled-ui-astra](https://github.com/AstraThreshold/oled-ui-astra)（C++/STM32）的设计灵感基础上，重新整理并扩展为适合 MicroPython 使用的独立项目。

支持**多级菜单导航**、**横向磁贴布局**、**平滑动画**、**电容触摸输入**以及可扩展的 **App 面板系统**。

</div>

---

## 特性

-   **多级菜单树** — 树形结构菜单，支持无限级嵌套，自动管理返回导航
-   **双布局模式** — 纵向列表（List）和横向磁贴（Tile），均支持平滑滚动
-   **App 面板系统** — 自定义功能面板，生命周期 `on_open → update → render → on_close`
-   **电容触摸** — 基于 ESP32 TouchPad 的 4 通道触摸输入，自动校准阈值
-   **平滑动画** — 指数缓动算法，菜单滚动、弹出框、选择器全部带平滑过渡
-   **圆角矩形** — 在 SSD1306（仅支持矩形）上逐像素绘制圆角矩形，带半径缓存
-   **弹出提示** — 非阻塞式 PopInfo，带滑入/滑出动画
-   **调试模式** — 实时显示 FPS、空闲内存、菜单路径
-   **浅色模式** — 通过 `Config.light_mode` 一键切换白底黑字
-   **硬件抽象层(HAL)** — 接收 `Config`，封装 OLED 绘图 & 按键扫描，解耦 UI 与硬件

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

### 2. 上传项目文件

将 `flowui.py` 和 `ssd1306.py` 上传到 ESP32，以及你的 `main.py`：

```bash
# 使用 ampy、rshell 或 Thonny 等工具
ampy put flowui.py
ampy put ssd1306.py
ampy put main.py
```

### 3. 编写你的 main.py

```python
from flowui import HAL, Config, Menu, Launcher, App

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
    # ... 处理触摸输入 ...
    launcher.update()
```

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

### 核心类

| 类 | 职责 |
|------|----------|
| `Config` | UI 配置中心：屏幕尺寸、动画速度、间距、颜色模式等 |
| `HAL` | 硬件抽象层：接收 `Config`，封装 OLED 绘图 API + 按键状态机扫描 |
| `Animation` | 指数缓动插值工具（float & int 版本） |
| `DrawUtils` | 高级绘图：圆角矩形（空心/实心） |
| `Menu` | 树形菜单节点：支持子菜单、App 绑定、双布局 |
| `Selector` | 选择器高亮条：索引管理 + 平滑移动动画 |
| `Camera` | 视口摄像机：菜单滚动时平滑偏移视图 |
| `Launcher` | 主控制器：统筹菜单导航、渲染循环、弹出提示、App 模式 |
| `App` | 应用面板基类：实现生命周期方法即可创建功能面板 |

---

## App 面板系统

通过继承 `App` 类创建自定义功能面板，然后通过 `Menu.add_item(name, app=your_app)` 绑定到菜单项。

### 生命周期

```
on_open(launcher)  →  update(launcher)  →  render(hal)  →  on_close(launcher)
   (进入时调用)         (每帧逻辑更新)      (每帧绘制)        (退出时调用)
```

### 示例：LED 控制面板

```python
class LEDApp(App):
    def on_open(self, launcher):
        self.state = False
        self.brightness = 50

    def render(self, hal):
        hal.fill(0)
        hal.text("LED: " + ("ON" if self.state else "OFF"), 8, 22, 1)
        hal.text("Bright: " + str(self.brightness), 8, 34, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:
            self.state = not self.state
        elif pin_index == 1:
            self.brightness = min(100, self.brightness + 10)

# 绑定到菜单
tile_menu.add_item("LED", app=LEDApp())
```

### 运行 App 时的触摸按键映射

| 触摸引脚 | 功能 |
|-----------|---------|
| GPIO4  (Pin 0) | App 自定义（例：切换开关） |
| GPIO14 (Pin 1) | App 自定义（例：增加） |
| GPIO27 (Pin 2) | App 自定义（例：减少） |
| GPIO33 (Pin 3) | **强制返回**菜单（长按/触摸） |

---

## 触摸输入

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

---

## 弹出提示 (PopInfo)

非阻塞式弹出提示，带滑入/滑出动画：

```python
launcher.pop_info("Saved!", 600)   # 显示"Saved!" 持续 600ms
launcher.dismiss_popup()           # 立即关闭
```

---

## 配置文件

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

> **注意：** `HAL` 现在需要接收 `Config` 实例，例如 `hal = HAL(cfg, scl_pin=22, sda_pin=21)`，以确保屏幕尺寸、浅色模式等配置在硬件层生效。

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

## 项目结构

```
flowui-micropython/
├── flowui.py            # 🔧 框架核心库（最新版）
├── main.py              # 🚀 用户主程序
├── ssd1306.py           # 📟 SSD1306 OLED 驱动
├── README.md            # 📖 本文档
│
├── 0.1/                 # 📁 旧版 v0.1
│   ├── astra_ui.py      #   核心框架（无 App 系统）
│   ├── main.py          #   示例主程序
│   ├── boot.py          #   ESP32 启动脚本
│   ├── ssd1306.py       #   OLED 驱动
│   └── touch_test.py    #   触摸测试工具
│
└── 1.0/                 # 📁 新版 v1.0
    ├── astra_ui.py      #   核心框架（含 App 系统 + 调试）
    ├── main.py          #   示例主程序（含 App 示例）
    ├── boot.py          #   ESP32 启动脚本
    ├── ssd1306.py       #   OLED 驱动
    └── touch_test.py    #   触摸测试工具
```

### 版本差异

| 特性 | v0.1 | v1.0 | FlowUI（当前） |
|------|------|------|----------------|
| 菜单导航 | ✓ | ✓ | ✓ |
| 双布局 (List / Tile) | ✓ | ✓ | ✓（滚动优化） |
| 弹出提示 | ✓ | ✓ | ✓ |
| App 面板系统 | ✗ | ✓ | ✓ |
| 按键输入 (GPIO) | ✗ | ✓ | ✓ |
| 调试模式 (FPS/GC) | ✗ | ✓ | ✓ |
| `gc` 模块引用 | ✗ | ✓ | ✓ |
| 浅色模式 | ✗ | ✗ | ✓ |
| 配置驱动 HAL | ✗ | ✗ | ✓ |

---

## 原项目

FlowUI 的设计受到 [AstraThreshold/oled-ui-astra](https://github.com/AstraThreshold/oled-ui-astra)（C++/STM32）的启发，但已针对 MicroPython / ESP32 平台进行了大量重构与扩展，是一个独立维护的项目。

---

## License

MIT License，详见 LICENSE 文件。
