"""Ultra Mode için ayrı tkinter timer penceresi - Pygame'den tamamen bağımsız"""
import tkinter as tk
from tkinter import ttk
import time
import threading

from localization import t

class TimerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ultra Mode Timer")
        self.root.geometry("300x600")
        self.root.configure(bg='#000000')
        
        # Pencereyi her zaman üstte tut
        self.root.attributes('-topmost', True)
        
        self.total_time = 120  # 2 dakika
        self.start_time = None
        self.paused = False
        self.paused_elapsed = 0
        self.running = False
        
        # UI Elementleri
        self.create_widgets()
        
        # Timer thread
        self.timer_thread = None
        
    def create_widgets(self):
        """UI elementlerini oluştur"""
        
        # Başlık
        title = tk.Label(
            self.root,
            text="ULTRA MODE",
            font=("Courier New", 16, "bold"),
            bg="#000000",
            fg="#666666"
        )
        title.pack(pady=20)
        
        # Zaman göstergesi
        self.time_label = tk.Label(
            self.root,
            text="2:00",
            font=("Courier New", 48, "bold"),
            bg="#000000",
            fg="#00ff88"
        )
        self.time_label.pack(pady=20)
        
        # Progress bar container
        self.progress_frame = tk.Frame(self.root, bg="#1a1a1a")
        self.progress_frame.pack(pady=20, padx=40, fill=tk.BOTH, expand=True)
        
        # 12 kare oluştur
        self.squares = []
        for i in range(12):
            square = tk.Frame(
                self.progress_frame,
                bg="#1a1a1a",
                highlightbackground="#444444",
                highlightthickness=2,
                width=60,
                height=40
            )
            square.pack(pady=2, fill=tk.X)
            square.pack_propagate(False)
            self.squares.append(square)
        
        # Kontrol butonları
        btn_frame = tk.Frame(self.root, bg="#000000")
        btn_frame.pack(pady=10)
        
        self.start_btn = tk.Button(
            btn_frame,
            text=t('timer_start'),
            command=self.start_timer,
            bg="#00ff88",
            fg="#000000",
            font=("Courier New", 12, "bold"),
            width=12
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = tk.Button(
            btn_frame,
            text=t('timer_pause'),
            fg="#000000",
            font=("Courier New", 12, "bold"),
            width=15,
            state=tk.DISABLED
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        # Klavye kısayolları
        self.root.bind('r', lambda e: self.start_timer())
        self.root.bind('R', lambda e: self.start_timer())
        self.root.bind('<space>', lambda e: self.toggle_pause())
        
    def start_timer(self):
        """Timer'ı başlat"""
        self.start_time = time.time()
        self.paused = False
        self.paused_elapsed = 0
        self.running = True
        
        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        
        # Timer thread'i başlat
        if self.timer_thread is None or not self.timer_thread.is_alive():
            self.timer_thread = threading.Thread(target=self.update_timer, daemon=True)
            self.timer_thread.start()
    
    def toggle_pause(self):
        """Timer'ı duraklat/devam ettir"""
        if not self.running:
            return
            
        if self.paused:
            # Devam et
            self.start_time = time.time()
            self.paused = False
            self.pause_btn.config(text=t('timer_pause'), bg="#ffa500")
        else:
            # Duraklat
            self.paused_elapsed += time.time() - self.start_time
            self.paused = True
            self.pause_btn.config(text=t('timer_resume'), bg="#00ff88")
    
    def update_timer(self):
        """Timer'ı güncelle - thread içinde çalışır"""
        while self.running:
            if not self.paused:
                elapsed = (time.time() - self.start_time) + self.paused_elapsed
                remaining = max(0, self.total_time - elapsed)
                
                # UI'ı güncelle (main thread'de)
                self.root.after(0, self.update_ui, elapsed, remaining)
                
                # Süre bittiyse dur
                if remaining <= 0:
                    self.root.after(0, self.timer_finished)
                    break
            
            time.sleep(0.016)  # ~60 FPS
    
    def update_ui(self, elapsed, remaining):
        """UI elementlerini güncelle - main thread'de çağrılmalı"""
        # Zaman göstergesini güncelle
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.time_label.config(text=f"{minutes}:{seconds:02d}")
        
        # Renk değiştir
        if remaining <= 10:
            self.time_label.config(fg="#ff4444")
        elif remaining <= 30:
            self.time_label.config(fg="#ffa500")
        else:
            self.time_label.config(fg="#00ff88")
        
        # Progress bar karelerini güncelle
        filled_squares = min(int(elapsed // 10), 12)
        
        for i in range(12):
            if i < filled_squares:
                # Dolu kare
                if remaining <= 10:
                    color = "#ff4444"
                elif remaining <= 30:
                    color = "#ffa500"
                else:
                    color = "#00ff88"
                self.squares[i].config(bg=color, highlightbackground=color)
            else:
                # Boş kare
                self.squares[i].config(bg="#1a1a1a", highlightbackground="#444444")
    
    def timer_finished(self):
        """Timer bitti"""
        self.running = False
        self.time_label.config(text="0:00", fg="#ff4444")
        self.start_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
    
    def run(self):
        """Pencereyi çalıştır"""
        self.root.mainloop()
    
    def close(self):
        """Pencereyi kapat"""
        self.running = False
        self.root.quit()
        self.root.destroy()


def start_timer_window():
    """Timer penceresini başlat - Ultra Mode başladığında çağır"""
    timer = TimerWindow()
    timer.run()


if __name__ == "__main__":
    start_timer_window()
