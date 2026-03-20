"""
スライドショー動画作成アプリ（GUI版）
"""

import os
import glob
import math
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

DEFAULT_PHOTOS_DIR = r"C:\Users\81906\ClaudeCodeFolder\Vol1\picture"
DEFAULT_MUSIC_FILE = r"C:\Users\81906\ClaudeCodeFolder\Vol1\music\09-手紙 ～拝啓 十五の君へ～.3gp"
DEFAULT_OUTPUT_FILE = r"C:\Users\81906\ClaudeCodeFolder\Vol1\slideshow.mp4"


def create_slideshow(photos_dir, music_file, duration_per_photo, output_file,
                     max_photos, log_func, done_func):
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

        # 画像ファイルを取得
        all_files = glob.glob(os.path.join(photos_dir, "*"))
        image_files = [
            f for f in all_files
            if os.path.splitext(f)[1].lower() in (".jpg", ".jpeg", ".png")
        ]

        if not image_files:
            log_func(f"エラー: {photos_dir} に画像ファイルが見つかりません。")
            done_func(False)
            return

        # ランダムに選択
        if max_photos is not None and max_photos < len(image_files):
            image_files = random.sample(image_files, max_photos)

        image_files.sort()

        total = len(image_files)
        total_sec = total * duration_per_photo
        log_func(f"写真: {total} 枚をランダム選択")
        log_func(f"1枚あたり: {duration_per_photo} 秒 / 合計: {total_sec:.0f} 秒 ({total_sec/60:.1f} 分)")
        log_func("画像を読み込み中...")

        clips = []
        fade_duration = 0.5
        output_size = (1920, 1080)

        for i, img_path in enumerate(image_files):
            log_func(f"  [{i+1}/{total}] {os.path.basename(img_path)}")
            clip = (
                ImageClip(img_path)
                .resized(output_size)
                .with_duration(duration_per_photo)
                .with_effects([
                    __import__("moviepy.video.fx", fromlist=["CrossFadeIn"]).CrossFadeIn(fade_duration),
                ])
            )
            clips.append(clip)

        log_func("動画を結合中...")
        video = concatenate_videoclips(clips, method="compose")

        if music_file and os.path.exists(music_file):
            log_func("音楽を追加中...")
            audio = AudioFileClip(music_file)
            video_duration = video.duration

            if audio.duration < video_duration:
                from moviepy import concatenate_audioclips
                loop_count = math.ceil(video_duration / audio.duration)
                audio = concatenate_audioclips([audio] * loop_count)

            audio = audio.subclipped(0, video_duration)
            audio = audio.with_effects([
                __import__("moviepy.audio.fx", fromlist=["AudioFadeOut"]).AudioFadeOut(2)
            ])
            video = video.with_audio(audio)
        elif music_file:
            log_func(f"警告: 音楽ファイルが見つかりません: {music_file}")

        log_func(f"動画を出力中: {output_file}")
        video.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac",
                              logger=None)

        log_func(f"\n完成! -> {output_file}")
        done_func(True)

    except Exception as e:
        log_func(f"\nエラーが発生しました: {e}")
        done_func(False)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("スライドショー動画作成")
        self.resizable(False, False)
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # --- 写真フォルダ ---
        tk.Label(self, text="写真フォルダ:").grid(row=0, column=0, sticky="e", **pad)
        self.photos_var = tk.StringVar(value=DEFAULT_PHOTOS_DIR)
        tk.Entry(self, textvariable=self.photos_var, width=50).grid(row=0, column=1, **pad)
        tk.Button(self, text="参照", command=self._browse_photos).grid(row=0, column=2, **pad)

        # --- 音楽ファイル ---
        tk.Label(self, text="音楽ファイル:").grid(row=1, column=0, sticky="e", **pad)
        self.music_var = tk.StringVar(value=DEFAULT_MUSIC_FILE)
        tk.Entry(self, textvariable=self.music_var, width=50).grid(row=1, column=1, **pad)
        tk.Button(self, text="参照", command=self._browse_music).grid(row=1, column=2, **pad)

        # --- 出力ファイル ---
        tk.Label(self, text="出力ファイル:").grid(row=2, column=0, sticky="e", **pad)
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_FILE)
        tk.Entry(self, textvariable=self.output_var, width=50).grid(row=2, column=1, **pad)
        tk.Button(self, text="参照", command=self._browse_output).grid(row=2, column=2, **pad)

        # --- 写真の枚数 ---
        tk.Label(self, text="写真の枚数:").grid(row=3, column=0, sticky="e", **pad)
        self.count_var = tk.IntVar(value=20)
        tk.Spinbox(self, from_=1, to=9999, textvariable=self.count_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        # --- 1枚あたりの秒数 ---
        tk.Label(self, text="1枚あたりの秒数:").grid(row=4, column=0, sticky="e", **pad)
        self.duration_var = tk.DoubleVar(value=3.0)
        tk.Spinbox(self, from_=1, to=30, increment=0.5, textvariable=self.duration_var, width=10).grid(row=4, column=1, sticky="w", **pad)

        # --- 実行ボタン ---
        self.run_btn = tk.Button(self, text="動画を作成", command=self._run,
                                  bg="#4CAF50", fg="white", font=("", 11, "bold"), padx=10)
        self.run_btn.grid(row=5, column=0, columnspan=3, pady=10)

        # --- ログ ---
        tk.Label(self, text="進捗ログ:").grid(row=6, column=0, sticky="nw", **pad)
        self.log_text = tk.Text(self, width=65, height=15, state="disabled", bg="#f5f5f5")
        self.log_text.grid(row=6, column=1, columnspan=2, **pad)

        scrollbar = tk.Scrollbar(self, command=self.log_text.yview)
        scrollbar.grid(row=6, column=3, sticky="ns", pady=5)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def _browse_photos(self):
        path = filedialog.askdirectory(initialdir=self.photos_var.get())
        if path:
            self.photos_var.set(path)

    def _browse_music(self):
        path = filedialog.askopenfilename(
            initialdir=os.path.dirname(self.music_var.get()),
            filetypes=[("音楽ファイル", "*.mp3 *.3gp *.m4a *.wav *.aac"), ("すべてのファイル", "*.*")]
        )
        if path:
            self.music_var.set(path)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(self.output_var.get()),
            defaultextension=".mp4",
            filetypes=[("MP4動画", "*.mp4")]
        )
        if path:
            self.output_var.set(path)

    def _log(self, message):
        def _update():
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.after(0, _update)

    def _done(self, success):
        def _update():
            self.run_btn.config(state="normal", text="動画を作成")
            if success:
                messagebox.showinfo("完成", f"動画を保存しました:\n{self.output_var.get()}")
            else:
                messagebox.showerror("エラー", "動画の作成に失敗しました。\nログを確認してください。")
        self.after(0, _update)

    def _run(self):
        self.run_btn.config(state="disabled", text="処理中...")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        thread = threading.Thread(target=create_slideshow, kwargs={
            "photos_dir": self.photos_var.get(),
            "music_file": self.music_var.get(),
            "duration_per_photo": self.duration_var.get(),
            "output_file": self.output_var.get(),
            "max_photos": self.count_var.get(),
            "log_func": self._log,
            "done_func": self._done,
        }, daemon=True)
        thread.start()


if __name__ == "__main__":
    app = App()
    app.mainloop()
