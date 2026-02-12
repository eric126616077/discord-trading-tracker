"""
鈴聲播放器 - Windows 版本
使用 winsound 模組（Windows 內建）
支援音效 + 視覺閃爍提醒
"""
import threading
import time
import winsound
import os
import ctypes

class SoundPlayer:
    """鈴聲播放器 - 支援持續響鈴 + 視覺閃爍直到確認"""
    
    def __init__(self):
        self.unread_count = 0
        self.alert_thread = None
        self.running = False
        self._lock = threading.Lock()
        self.flashing = False
    
    def add_unread(self):
        """新增未讀訊息，開始響鈴"""
        with self._lock:
            self.unread_count += 1
            if self.alert_thread is None or not self.alert_thread.is_alive():
                self.start_alert()
    
    def clear_unread(self):
        """清除未讀，停止響鈴"""
        with self._lock:
            self.unread_count = 0
            self.stop_alert()
    
    def start_alert(self):
        """開始持續響鈴 + 視覺閃爍"""
        if self.running:
            return
        
        self.running = True
        self.flashing = True
        self.alert_thread = threading.Thread(target=self._play_loop, daemon=True)
        self.alert_thread.start()
    
    def stop_alert(self):
        """停止響鈴"""
        self.running = False
        self.flashing = False
        self.alert_thread = None
        # 重置控制台顏色
        self._reset_console()
    
    def _reset_console(self):
        """重置控制台顏色"""
        try:
            import colorama
            colorama.init()
            colorama.deinit()
        except:
            pass
        # Windows API 重置
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleTextAttribute(kernel32.GetStdHandle(-11), 7)
        except:
            pass
    
    def _flash_console(self):
        """視覺閃爍 - 交替紅色和正常色"""
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            
            # 紅色 (4)
            kernel32.SetConsoleTextAttribute(handle, 4 | 8)  # 紅色 + 高亮
            time.sleep(0.3)
            # 正常 (7)
            kernel32.SetConsoleTextAttribute(handle, 7)
            time.sleep(0.2)
        except Exception as e:
            print(f"[Sound] 視覺閃爍錯誤: {e}")
    
    def _play_loop(self):
        """響鈴循環 - 嗶嗶嗶 + 閃爍"""
        beep_count = 0
        
        while self.running and self.unread_count > 0:
            beep_count += 1
            
            # 音效：嗶聲
            try:
                # 2000Hz 高頻嗶聲，更容易聽見
                winsound.Beep(2000, 300)  # 2000Hz, 300ms
            except Exception as e:
                print(f"[Sound] 播放嗶聲失敗: {e}")
            
            # 視覺閃爍
            if self.flashing:
                self._flash_console()
            
            # 每隔一段時間打印提示
            if beep_count % 10 == 1:
                print(f"\r{'='*60}")
                print(f"  🔔 【未讀訊息】{self.unread_count} 條待確認 - 按 Ctrl+C 停止或點擊網頁「全部己讀」")
                print(f"{'='*60}\n")
            
            # 停頓：400ms
            time.sleep(0.4)
        
        # 結束時重置
        self._reset_console()


def play_notification_sound():
    """播放單次通知音效"""
    try:
        winsound.Beep(1500, 500)  # 1500Hz, 500ms
    except Exception as e:
        print(f"[Sound] 通知音效失敗: {e}")


def flash_screen():
    """閃爍屏幕"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        
        # 快速閃爍 3 次
        for _ in range(3):
            kernel32.SetConsoleTextAttribute(handle, 4 | 8 | 2)  # 紅色 + 高亮 + 綠色 = 黃色
            time.sleep(0.1)
            kernel32.SetConsoleTextAttribute(handle, 7)  # 正常
            time.sleep(0.1)
    except Exception as e:
        print(f"[Sound] 屏幕閃爍失敗: {e}")
