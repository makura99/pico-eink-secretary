import network
import urequests
import time
import machine
import epaper4in2
import ntptime
from secrets import secrets

# --- 0. 起動 ---
print("起動しました！ 5秒以内にStopを押せば中断できます...")
led = machine.Pin('LED', machine.Pin.OUT)
for _ in range(10):
    led.toggle()
    time.sleep(0.5)

# --- 1. 設定項目 ---
SCHEDULES = [
    (7, 0), (8, 0), (9, 0), (15, 0), (17, 0)
]
JST_OFFSET = 9 * 60 * 60
MAX_SLEEP_SEC = 3600 # 1時間以上のスリープを禁止して分割する

# --- 2. ピンアサインと初期化 ---
sck  = machine.Pin(10)
mosi = machine.Pin(11)
cs   = machine.Pin(9)
dc   = machine.Pin(8)
rst  = machine.Pin(12)
busy = machine.Pin(13)

spi = machine.SPI(1, baudrate=1000000, polarity=0, phase=0, sck=sck, mosi=mosi)
eink = epaper4in2.EPD(spi, cs, dc, rst, busy)
eink.init()

# --- 3. Wi-Fi接続 ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(secrets['ssid'], secrets['password'])

for i in range(20):
    if wlan.isconnected():
        break
    time.sleep(1)

if not wlan.isconnected():
    print("Wi-Fi失敗、再試行待機")
    eink.sleep()
    machine.deepsleep(600000)

# --- 4. 時刻同期 ---
try:
    ntptime.host = "ntp.nict.jp"
    ntptime.settime()
    current_timestamp = time.time() + JST_OFFSET
    tm = time.localtime(current_timestamp)
    current_hour, current_min = tm[3], tm[4]
except Exception as e:
    print("時刻同期失敗:", e)
    eink.sleep()
    machine.deepsleep(300000)

# --- 5. 更新判定と実行 ---
current_total_min = current_hour * 60 + current_min
should_update = any(0 <= (current_total_min - (h * 60 + m)) < 5 for h, m in SCHEDULES)

if should_update:
    try:
        response = urequests.get("http://192.168.11.50:8000/eink/display.raw", stream=True)
        if response.status_code == 200:
            img_data = response.raw.read(15000)
            eink.display(img_data)
            response.close()
    except Exception as e:
        print("更新エラー:", e)

eink.sleep()

# --- 6. 次の更新までの待機計算とディープスリープ ---
current_total_sec = ((current_hour * 60 + current_min) * 60) + tm[5]
next_target_sec = None

for h, m in SCHEDULES:
    sched_sec = (h * 60 + m) * 60
    if sched_sec > current_total_sec + 60:
        next_target_sec = sched_sec
        break

if next_target_sec is None:
    first_sched_sec = (SCHEDULES[0][0] * 60 + SCHEDULES[0][1]) * 60
    sleep_seconds = (86400 - current_total_sec) + first_sched_sec
else:
    sleep_seconds = next_target_sec - current_total_sec

# 分割スリープの適用
if sleep_seconds > MAX_SLEEP_SEC:
    sleep_ms = MAX_SLEEP_SEC * 1000
    print(f"待機が長いため {MAX_SLEEP_SEC}秒 で一旦起きます")
else:
    sleep_ms = sleep_seconds * 1000
    print(f"次の更新まで {sleep_seconds}秒 眠ります")

wlan.active(False)
machine.deepsleep(sleep_ms)
