# epaper4in2.py (Waveshare 4.2 inch Rev2.1 専用ドライバ)
import time
from machine import Pin

class EPD:
    def __init__(self, spi, cs, dc, rst, busy):
        self.spi = spi
        self.cs = Pin(cs, Pin.OUT)
        self.dc = Pin(dc, Pin.OUT)
        self.rst = Pin(rst, Pin.OUT)
        self.busy = Pin(busy, Pin.IN, Pin.PULL_UP)
        self.cs.value(1)
        self.dc.value(1)

    def wait_until_idle(self):
        time.sleep_ms(10)
        timeout = 0
        while self.busy.value() == 1:  # Rev2.1は Busy=1 で処理中
            time.sleep_ms(100)
            timeout += 1
            if timeout > 200: # 20秒でタイムアウト
                print("  [!] Busy timeout")
                break

    def send_command(self, command):
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([command]))
        self.cs.value(1)

    def send_data(self, data):
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(bytearray([data]))
        self.cs.value(1)

    def init(self):
        # 1. ハードウェアリセット
        self.rst.value(1)
        time.sleep_ms(20)
        self.rst.value(0)
        time.sleep_ms(2)
        self.rst.value(1)
        time.sleep_ms(20)

        # 2. ソフトウェアリセット
        self.send_command(0x12)
        self.wait_until_idle()

        # =========================================================================
        # ★ ここからが Rev2.1 専用の初期化コマンド（かすれ解決の要）
        # =========================================================================
        
        # Display update control (V2用電圧・波形設定)
        self.send_command(0x21) 
        self.send_data(0x40)    # 旧式は0x00だが、Rev2.1は 0x40 が必須
        self.send_data(0x00)

        # Border Waveform Control (フチの波形設定)
        self.send_command(0x3C)
        self.send_data(0x05)

        # Data Entry Mode (左から右、上から下への書き込み設定)
        self.send_command(0x11)
        self.send_data(0x03)

        # RAM X address start/end (400ピクセル = 50バイト = 0x00 から 0x31)
        self.send_command(0x44)
        self.send_data(0x00)
        self.send_data(0x31)

        # RAM Y address start/end (300ピクセル = 0x00 から 0x012B)
        self.send_command(0x45)
        self.send_data(0x00)
        self.send_data(0x00)
        self.send_data(0x2B)
        self.send_data(0x01)

        # RAM Counter X/Y 初期値セット
        self.send_command(0x4E)
        self.send_data(0x00)
        self.send_command(0x4F)
        self.send_data(0x00)
        self.send_data(0x00)
        
        self.wait_until_idle()

    def display(self, image):
        # ラズパイ側で完璧なデータを作成済なので、そのまま流し込む
        self.send_command(0x24) # Write RAM (B/W)
        self.dc.value(1)
        self.cs.value(0)
        self.spi.write(image)
        self.cs.value(1)

        # Rev2.1用 フルリフレッシュ実行コマンド
        self.send_command(0x22)
        self.send_data(0xF7)
        self.send_command(0x20)
        self.wait_until_idle()

    def sleep(self):
        self.send_command(0x10) # DEEP_SLEEP_MODE
        self.send_data(0x01)
