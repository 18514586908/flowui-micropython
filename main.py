from flowui import HAL, Config, Menu, Launcher, App
from machine import TouchPad, Pin
import time

# ============================================================
# 示例 App 面板 —— 你只需继承 App，实现几个方法即可
# ============================================================

class LEDApp(App):
    """LED 控制面板（示例）"""

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
        hal.text("Pin1:+   Pin2:-", 8, 54, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 0:  # 短按 → 切换开关
            self.state = not self.state
        elif pin_index == 1:  # 短按 → 亮度+
            self.brightness = min(100, self.brightness + 10)
        elif pin_index == 2:  # 短按 → 亮度-
            self.brightness = max(0, self.brightness - 10)

    def on_close(self, launcher):
        print("LEDApp closed, state=", self.state)


class SensorApp(App):
    """传感器读数面板（示例——模拟数据）"""

    def on_open(self, launcher):
        self.counter = 0

    def update(self, launcher):
        self.counter += 1

    def render(self, hal):
        hal.fill(0)
        hal.text("Sensor Read", 20, 4, 1)
        hal.hline(20, 13, 88, 1)
        temp = (self.counter * 7) % 50 + 20
        humid = (self.counter * 13) % 30 + 60
        light = (self.counter * 3) % 100
        hal.text("Temp: {} C".format(temp), 8, 22, 1)
        hal.text("Humi: {} %".format(humid), 8, 34, 1)
        hal.text("Light: {} %".format(light), 8, 46, 1)
        hal.text("Pin0:Back", 8, 54, 1)


class MotorApp(App):
    """电机控制面板（示例）"""

    def on_open(self, launcher):
        self.speed = 0

    def render(self, hal):
        hal.fill(0)
        hal.text("Motor Control", 16, 4, 1)
        hal.hline(16, 13, 96, 1)
        hal.text("Speed: " + str(self.speed), 8, 22, 1)
        bar_w = int(self.speed / 255 * 80)
        hal.fill_rect(8, 34, bar_w, 8, 1)
        hal.rect(8, 34, 80, 8, 1)
        hal.text("Pin1:+10  Pin2:-10", 8, 50, 1)
        hal.text("Pin0:Back", 8, 54, 1)

    def handle_touch_pin(self, pin_index, raw_value):
        if pin_index == 1:
            self.speed = min(255, self.speed + 10)
        elif pin_index == 2:
            self.speed = max(0, self.speed - 10)


# ============================================================
# 硬件初始化
# ============================================================

cfg = Config()
hal = HAL(cfg, scl_pin=22, sda_pin=21, i2c_addr=0x3C)
launcher = Launcher(hal, cfg)

# 触摸引脚
touch_pins = [4, 14, 27, 33]
touch_pads = [TouchPad(Pin(p)) for p in touch_pins]

# 自动校准触摸阈值
baseline = []
for i, pad in enumerate(touch_pads):
    vals = []
    for _ in range(10):
        vals.append(pad.read())
        time.sleep_ms(10)
    avg = sum(vals) // len(vals)
    baseline.append(avg)
    print("GPIO{} 基准={}".format(touch_pins[i], avg))

thresholds = [int(b * 0.75) for b in baseline]
print("阈值:", thresholds)

hal.fill(0)
for i in range(4):
    hal.text("GPIO{}: {}".format(touch_pins[i], baseline[i]), 0, i * 16, 1)
hal.show()
time.sleep(2)

# ============================================================
# 构建菜单树 —— 将 App 面板绑定到磁贴菜单项
# ============================================================

root = Menu("Main")
sub1 = Menu("Tools")
sub2 = Menu("Settings")
sub3 = Menu("About")

sub1.add_item("LED Control")
sub1.add_item("Sensor Read")
sub1.add_item("Motor Test")

sub2.add_item("WiFi Config")
sub2.add_item("Display Set")
sub2.add_item("Sound Set")

sub3.add_item("Version 1.0")
sub3.add_item("Author: lyyx")
sub3.add_item("Power by MicroPython")

# 磁贴菜单 —— 绑定 App 面板
tile_menu = Menu("Apps", menu_type="tile")
tile_menu.add_item("LED",    app=LEDApp())
tile_menu.add_item("Sensor", app=SensorApp())
tile_menu.add_item("Motor",  app=MotorApp())
tile_menu.add_item("Camera")
tile_menu.add_item("Music")
tile_menu.add_item("Radio")
tile_menu.add_item("Maps")

root.add_item("Tools", sub1)
root.add_item("Settings", sub2)
root.add_item("Apps", tile_menu)
root.add_item("About", sub3)
root.add_item("Exit")

launcher.init(root)

# ============================================================
# 触摸输入循环 —— 适配 App 模式
# ============================================================

touched = [False, False, False, False]

while True:
    for i, pad in enumerate(touch_pads):
        v1 = pad.read()
        v2 = pad.read()
        v3 = pad.read()
        val = min(v1, v2, v3)

        if val < thresholds[i] and not touched[i]:
            touched[i] = True

            if launcher.app_mode:
                # App 模式：pin 3 = 返回/退出 App
                # 其他 pin 路由到 App.handle_touch_pin
                if i == 3:
                    launcher.exit_app()
                else:
                    launcher.active_app.handle_touch_pin(i, val)
            elif launcher.popup_state != 0:
                launcher.dismiss_popup()
                if i == 3:
                    launcher.close()
            elif i == 0:
                launcher.selector.go_prev()
            elif i == 1:
                launcher.selector.go_next()
            elif i == 2:
                launcher.open()
            elif i == 3:
                launcher.close()

        elif val >= thresholds[i]:
            touched[i] = False

    launcher.update()
