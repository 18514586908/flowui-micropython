# -*- coding: utf-8 -*+
"""
FlowUI 中文显示模块（轻量版 v2.0）
====================================

本模块由 PC 端的 gen_cn_font.py 自动生成。
运行时从 cn_font.bin 按偏移读取字模数据，不包含大字模数据本身。

设计特点：
  - SUPPORTED_CHARS：字符串索引，每个汉字在 bin 中的偏移 = index × 32
  - _char_to_offset：汉字 → 偏移的快速查找字典
  - _bitmap_cache：64 字 LRU 缓存，避免同一帧重复读取
  - _font_file：全局文件句柄，避免反复 open/close
  - 英文使用 framebuf 内置 8x8 字体（y+8 底部对齐中文 16px）

使用方式：
  1. 在 PC 端运行: python gen_cn_font.py
  2. 将本文件和 cn_font.bin 一起上传到 ESP32
  3. HAL.text() 自动检测中文并调用 draw_text()

如需添加新汉字：
  1. 修改 gen_cn_font.py 中的 EXTRA_CHARS
  2. 重新运行: python gen_cn_font.py
  3. 重新上传 cn_font.py 和 cn_font.bin
"""

# ── 字体常量 ──────────────────────────────────────────────
FONT_SIZE = 16      # 16×16 点阵（共 256 bit = 32 bytes/字）
ASCII_WIDTH = 8     # 英文字符宽度
ASCII_HEIGHT = 8    # 英文字符高度
SUPPORTED_CHARS = '°×—←↑→↔≈─│└├═、。【】一三上下不与且两个中串临为主义之乎也了事二于五亚些产亮仅仍从他代以件任优会传伪似但位低住体何余作你使例供侧保信修值偏做停储像允元充先光免入全公共关其具典兼内再写冲决况准减几出击函分切列则刚创初判别到制刷刻前剩剪力功加动包化区半单占卡即历厚原参双反发取受变叠口只可史右叶号合同名后向否含启周命和响器噪四回围固图圆在地场圾址均坐块垂垃型域基塞填增声处备复外多大央失头套好如始委子字存学它安完定实容宽寸对导封射将小少尺尼尾层居屏展属嵌工左己已带帧常幅幕干平并序库应底度建开式引张弧弹强当录形影径待循心必志快态性总恢息情意感慢成或户所手才打托执扫找承抖抗抠护抽担拉拍拟择拷持挂指按换据掉接控推掩描提插摄摸操支收改放效敏数整文断新方无日时明映是显普景更最有期未末本机束条来松板构析果架染查标树校样核根框检模次止正此步残段每比毫水没法注活流浅测浮消淡深混添清渡温渲湿源滑滚灵点焊焦然照父片版物特状率环现理生用由电画畅界留白百的盖盘目直相省看真瞬矩短码础硬确磁示禁离种秒称移程空立符第等筹简算管箭类精系素索紧约级纯纳线组细织经绑结绘给统继续维缓缘缩置者职联背能脚自致舍航色节若英范荐获菜著藏行表被裁装要覆见视觉角解触计认让记许设试询该详语说读谁调象贝负责败贴资走起超越距跟路跳踪转轮软轴载较辑输边达过运近返这进连退送适选透逐递通速逻逼遇遍避部都配采释里重量针钟链销键镜长闭闲间阈防阵阶阻际降限除随隐隔集需露静非面音顶项顺须预题颜额首驱验高黑默齐（），：；～'

# ── 偏移映射字典：汉字 → bin 文件字节偏移 ──────────────
# 每个汉字占 32 bytes，偏移 = 索引 × 32
_char_to_offset = {c: i * 32 for i, c in enumerate(SUPPORTED_CHARS)}

# ── 字模缓存 ────────────────────────────────────────────
# 缓存最近 64 个汉字，避免同一帧重复文件读取
_bitmap_cache = {}       # key=字符(char), value=32 bytes
_CACHE_MAX = 64           # 最大缓存数（占 ~2KB RAM）


def _is_chinese(ch):
    """判断字符是否中文（Unicode > 127）。"""
    return ord(ch) > 127


def _get_char_bitmap(ch):
    """
    从 cn_font.bin 读取单个汉字的 32 bytes 位图。

    查找流程：偏移映射 → LRU 缓存 → 文件读取 → 加入缓存

    Args:
        ch: 中文字符

    Returns:
        32 bytes 位图，或 None（字库中不存在）
    """
    offset = _char_to_offset.get(ch)
    if offset is None:
        return None          # 字符不在字库中

    # 缓存命中直接返回
    bmp = _bitmap_cache.get(ch)
    if bmp is not None:
        return bmp

    # 从 bin 文件读取
    try:
        with open('cn_font.bin', 'rb') as f:
            f.seek(offset)          # 定位到目标汉字
            bmp = f.read(32)        # 读取 32 字节字模
    except OSError:
        return None                 # 文件读取失败

    # 加入缓存（FIFO：满则清半）
    if len(_bitmap_cache) >= _CACHE_MAX:
        for _ in range(_CACHE_MAX // 2):
            if _bitmap_cache:
                _bitmap_cache.pop(next(iter(_bitmap_cache)))
    _bitmap_cache[ch] = bmp
    return bmp


def _draw_chinese_char(hal, ch, x, y, color):
    """
    在指定位置绘制一个 16×16 汉字。

    每行 16 像素 = 2 bytes（左8 + 右8），共 16 行。
    使用 hal.pixel 逐像素绘制。

    Returns:
        FONT_SIZE (16)：字符宽度
    """
    bmp = _get_char_bitmap(ch)
    if bmp is None:
        return FONT_SIZE  # 缺字时留空占位
    for row in range(FONT_SIZE):
        b1 = bmp[row * 2]          # 左 8 像素
        b2 = bmp[row * 2 + 1]      # 右 8 像素
        for col in range(8):
            if b1 & (0x80 >> col):  # bit0 = 最左像素
                hal.pixel(x + col, y + row, color)
        for col in range(8):
            if b2 & (0x80 >> col):
                hal.pixel(x + 8 + col, y + row, color)
    return FONT_SIZE


def text_width(text):
    """
    计算中英混合字符串的宽度。

    中文 = 16px，英文 = 8px。

    Args:
        text: 输入字符串

    Returns:
        总宽度（像素）
    """
    width = 0
    for ch in text:
        if _is_chinese(ch):
            width += FONT_SIZE
        else:
            width += ASCII_WIDTH
    return width


def draw_text(hal, text, x, y, color=1):
    """
    在指定位置绘制中英混合字符串。

    中文用 16×16 点阵，英文用 8×8 字体（y+8 底部对齐）。

    Args:
        hal:    HAL 实例
        text:   字符串
        x, y:   左上角坐标
        color:  逻辑颜色 0/1

    Returns:
        实际绘制的总宽度
    """
    cx = x
    for ch in text:
        if _is_chinese(ch):
            cx += _draw_chinese_char(hal, ch, cx, y, color)
        elif ord(ch) >= 32:
            # 英文：8x8 字体，y+8 使英文底部与中文底部对齐
            # 注意：hal._text_ascii 不会对 color 二次转换
            hal._text_ascii(ch, cx, y + 8, color)
            cx += ASCII_WIDTH
    return cx - x

def contains_chinese(text):
    """判断字符串是否包含中文字符"""
    for ch in text:
        if _is_chinese(ch):
            return True
    return False
