#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FlowUI 中文字库生成脚本（PC 端运行）

功能：
  1. 自动扫描项目源码中使用到的中文字符
  2. 使用 PC 端字体生成 16x16 点阵字模
  3. 输出轻量的 cn_font.py 和二进制 cn_font.bin
  4. ESP32 上电后只读 bin 文件，无需再解析大字库

用法：
  python gen_cn_font.py

自定义字库：
  - 在 EXTRA_CHARS 中添加额外汉字
  - 修改 SOURCE_FILES 指定需要扫描的源码文件
  - 修改 FONT_PATH 指定字体路径
"""

from PIL import Image, ImageDraw, ImageFont
import os

# 需要扫描的源码文件（自动提取其中出现的中文）
SOURCE_FILES = ["main.py", "flowui.py"]

# 额外手动添加的汉字（如未来动态生成的字符串）
EXTRA_CHARS = ""

# 字体路径（Windows 黑体）
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

# 点阵尺寸
FONT_SIZE = 16
BYTES_PER_CHAR = 32  # 16x16 = 256 bits = 32 bytes


def extract_chinese_from_source(path):
    """
    从源码文件中提取所有中文字符。
    
    遍历文件内容，收集所有 Unicode 码点 > 127 的字符（即中文字符）。
    使用 set 自动去重。

    Args:
        path: 文件路径（如 "main.py"）

    Returns:
        文件中出现的中文字符集合（set of char）
    """
    chars = set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # 遍历每个字符，保留中文字符
        for ch in text:
            if ord(ch) > 127:
                chars.add(ch)
    except FileNotFoundError:
        print(f"[警告] 找不到文件：{path}")
    return chars


def collect_chars():
    """
    收集所有需要用到的汉字。

    合并来源：
    1. EXTRA_CHARS 中手动指定的汉字
    2. SOURCE_FILES 列表中所有源码文件中出现的中文字符

    返回按 Unicode 码点排序的字符串，确保每次生成结果一致。

    Returns:
        排序后的唯一汉字字符串
    """
    all_chars = set(EXTRA_CHARS)
    for path in SOURCE_FILES:
        all_chars |= extract_chinese_from_source(path)

    # 按 Unicode 码点排序，保证多次运行结果相同
    chars = sorted(all_chars, key=lambda c: ord(c))
    return "".join(chars)


def char_to_bytes(ch, font):
    """
    将单个字符渲染为 16x16 位图，返回 32 bytes。

    步骤：
    1. 创建 16x16 的 1-bit 图像
    2. 使用 PIL 的 truetype 字体渲染字符
    3. 逐行扫描像素：
       - 每行 16 像素 = 2 bytes（左 8 像素 + 右 8 像素）
       - 每个 byte 的 bit0（LSB）对应最左像素
       - 与 MicroPython 的 MONO_HLSB 格式一致

    Args:
        ch:   要渲染的字符
        font: PIL ImageFont 对象

    Returns:
        32 bytes 的位图数据
    """
    # 创建 16x16 的 1-bit（黑白）图像，初始全黑
    img = Image.new("1", (FONT_SIZE, FONT_SIZE), 0)
    draw = ImageDraw.Draw(img)
    # 用指定字体绘制字符，颜色 = 1（白色）
    draw.text((0, 0), ch, font=font, fill=1)

    # 逐行扫描像素，转换为 MONO_HLSB 格式的 bytes
    data = bytearray()
    for y in range(FONT_SIZE):       # 16 行
        byte1 = 0                     # 左 8 像素
        byte2 = 0                     # 右 8 像素
        for x in range(FONT_SIZE):   # 16 列
            if img.getpixel((x, y)):
                if x < 8:
                    byte1 |= (0x80 >> x)         # bit0 = 最左像素
                else:
                    byte2 |= (0x80 >> (x - 8))   # bit0 = 最左像素
        data.append(byte1)
        data.append(byte2)
    return bytes(data)


def generate():
    """
    主生成函数。

    流程：
    1. 检查字体文件是否存在
    2. 收集所有需要的中文字符
    3. 逐个字符生成 16x16 位图
    4. 写入 cn_font.bin（二进制）
    5. 生成 cn_font.py（Python 索引）
    """
    if not os.path.exists(FONT_PATH):
        print(f"[错误] 字体文件不存在: {FONT_PATH}")
        print("请修改 FONT_PATH 为系统中的黑体或宋体文件路径")
        return

    chars = collect_chars()
    if not chars:
        print("[警告] 未找到任何中文字符")
        return

    print(f"[信息] 扫描到 {len(chars)} 个不同汉字")

    # 加载字体，渲染所有字符
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    font_data = bytearray()
    for ch in chars:
        font_data.extend(char_to_bytes(ch, font))

    # 写入二进制字库文件
    with open("cn_font.bin", "wb") as f:
        f.write(font_data)

    # 生成轻量 cn_font.py（不含大字模数据，只有索引和读取逻辑）
    lines = [
        "# -*- coding: utf-8 -*+",
        '"""',
        "FlowUI 中文显示模块（轻量版）",
        "",
        "使用方式：",
        "  1. 在 PC 端运行 gen_cn_font.py 生成本文件和 cn_font.bin",
        "  2. 将 cn_font.py 和 cn_font.bin 一起上传到 ESP32",
        "  3. HAL.text() 会自动检测中文字符并调用本模块渲染",
        "",
        "注意：",
        "  本模块不含字模数据，运行时按偏移读取 cn_font.bin",
        "  如需显示新的汉字，修改 gen_cn_font.py 后重新生成",
        '"""',
        "",
        "FONT_SIZE = 16",
        "ASCII_WIDTH = 8",
        "ASCII_HEIGHT = 8",
        f"SUPPORTED_CHARS = {repr(chars)}",
        "",
        "# 建立汉字到 bin 文件偏移的映射",
        "_char_to_offset = {c: i * 32 for i, c in enumerate(SUPPORTED_CHARS)}",
        "",
        "# 小型缓存：避免同一帧重复读取同一汉字",
        "_bitmap_cache = {}",
        "_CACHE_MAX = 64",
        "",
        "def _is_chinese(ch):",
        "    return ord(ch) > 127",
        "",
        "def _get_char_bitmap(ch):",
        "    \"\"\"从 cn_font.bin 读取单个汉字的 32 bytes 字模\"\"\"",
        "    offset = _char_to_offset.get(ch)",
        "    if offset is None:",
        "        return None",
        "",
        "    # 缓存命中直接返回",
        "    bmp = _bitmap_cache.get(ch)",
        "    if bmp is not None:",
        "        return bmp",
        "",
        "    try:",
        "        with open('cn_font.bin', 'rb') as f:",
        "            f.seek(offset)",
        "            bmp = f.read(32)",
        "    except OSError:",
        "        return None",
        "",
        "    # 加入缓存",
        "    if len(_bitmap_cache) >= _CACHE_MAX:",
        "        # 简单清掉一半缓存",
        "        for _ in range(_CACHE_MAX // 2):",
        "            if _bitmap_cache:",
        "                _bitmap_cache.pop(next(iter(_bitmap_cache)))",
        "    _bitmap_cache[ch] = bmp",
        "    return bmp",
        "",
        "def _draw_chinese_char(hal, ch, x, y, color):",
        "    bmp = _get_char_bitmap(ch)",
        "    if bmp is None:",
        "        return FONT_SIZE  # 缺字时留空占位",
        "    for row in range(FONT_SIZE):",
        "        b1 = bmp[row * 2]",
        "        b2 = bmp[row * 2 + 1]",
        "        for col in range(8):",
        "            if b1 & (0x80 >> col):",
        "                hal.pixel(x + col, y + row, color)",
        "        for col in range(8):",
        "            if b2 & (0x80 >> col):",
        "                hal.pixel(x + 8 + col, y + row, color)",
        "    return FONT_SIZE",
        "",
        "def text_width(text):",
        "    width = 0",
        "    for ch in text:",
        "        if _is_chinese(ch):",
        "            width += FONT_SIZE",
        "        else:",
        "            width += ASCII_WIDTH",
        "    return width",
        "",
        "def draw_text(hal, text, x, y, color=1):",
        "    \"\"\"在指定位置绘制中英混合字符串\"\"\"",
        "    cx = x",
        "    for ch in text:",
        "        if _is_chinese(ch):",
        "            cx += _draw_chinese_char(hal, ch, cx, y, color)",
        "        elif ord(ch) >= 32:",
        "            # 调用 HAL 内部方法，避免颜色二次转换",
        "            hal._text_ascii(ch, cx, y + 8, color)",
        "            cx += ASCII_WIDTH",
        "    return cx - x",
        "",
        "def contains_chinese(text):",
        "    \"\"\"判断字符串是否包含中文字符\"\"\"",
        "    for ch in text:",
        "        if _is_chinese(ch):",
        "            return True",
        "    return False",
        "",
    ]

    with open("cn_font.py", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[完成] 已生成 cn_font.bin ({len(font_data)} bytes) 和 cn_font.py")
    print(f"[完成] 共包含 {len(chars)} 个汉字")


if __name__ == "__main__":
    generate()
