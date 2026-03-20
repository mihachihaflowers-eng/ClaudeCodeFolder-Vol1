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
import customtkinter as ctk
from proglog import ProgressBarLogger

DEFAULT_PHOTOS_DIR = r"C:\Users\81906\ClaudeCodeFolder\Vol1\picture"
DEFAULT_MUSIC_FILE = r"C:\Users\81906\ClaudeCodeFolder\Vol1\music\09-手紙 ～拝啓 十五の君へ～.3gp"
DEFAULT_OUTPUT_FILE = r"C:\Users\81906\ClaudeCodeFolder\Vol1\slideshow.mp4"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CancellableLogger(ProgressBarLogger):
    """MoviePyのエンコード進捗を取得しキャンセルを検知するロガー"""
    def __init__(self, cancel_event, progress_callback):
        super().__init__()
        self._cancel = cancel_event
        self._progress_cb = progress_callback

    def bars_callback(self, bar, attr, value, old_value=None):
        if self._cancel.is_set():
            raise InterruptedError("キャンセルされました")
        if attr == "index":
            total = self.bars[bar].get("total", 0)
            if total and total > 0:
                self._progress_cb(value / total)


def get_music_duration(music_file):
    """音楽ファイルの長さ（秒）を返す。失敗時は None"""
    try:
        from moviepy import AudioFileClip
        with AudioFileClip(music_file) as a:
            return a.duration
    except Exception:
        return None


OUTPUT_MODES = {
    "PC":     {"size": (1920, 1080), "label": "PC（横長 16:9）"},
    "iPhone": {"size": (1080, 1920), "label": "iPhone（縦長 9:16）"},
}


def create_slideshow(photos_dir, music_file, duration_per_photo, output_file,
                     output_mode, log_func, photo_progress_cb, encode_progress_cb,
                     done_func, cancel_event):
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

        all_files = glob.glob(os.path.join(photos_dir, "*"))
        image_files = [
            f for f in all_files
            if os.path.splitext(f)[1].lower() in (".jpg", ".jpeg", ".png")
        ]

        if not image_files:
            log_func("❌ エラー: 画像ファイルが見つかりません")
            done_func(False)
            return

        # 音楽長さとクロスフェードから枚数を自動計算
        FADE = 0.8
        max_photos = None
        if music_file and os.path.exists(music_file):
            music_duration = get_music_duration(music_file)
            if music_duration and duration_per_photo > FADE:
                effective = duration_per_photo - FADE
                max_photos = max(1, int((music_duration - FADE) / effective) + 1)
                m, s = divmod(int(music_duration), 60)
                log_func(f"🎵 音楽の長さ: {m}分{s:02d}秒 ÷ {duration_per_photo:.1f}秒/枚 → {max_photos} 枚")

        if max_photos is not None and max_photos < len(image_files):
            image_files = random.sample(image_files, max_photos)
        image_files.sort()

        total = len(image_files)
        total_sec = total * duration_per_photo
        log_func(f"📂 写真フォルダ: {photos_dir}")
        log_func(f"🎵 音楽ファイル: {os.path.basename(music_file)}")
        log_func(f"🖼  写真: {total} 枚をランダム選択")
        log_func(f"⏱  合計時間: {total_sec:.0f}秒 ({total_sec/60:.1f}分)")
        log_func("─" * 45)
        log_func("📥 写真を読み込み中...")

        clips = []
        fade_duration = 0.8  # クロスフェード時間（秒）
        output_size = OUTPUT_MODES.get(output_mode, OUTPUT_MODES["PC"])["size"]
        log_func(f"📐 出力モード: {OUTPUT_MODES.get(output_mode, OUTPUT_MODES['PC'])['label']} ({output_size[0]}×{output_size[1]})")
        CrossFadeIn = __import__("moviepy.video.fx", fromlist=["CrossFadeIn"]).CrossFadeIn

        for i, img_path in enumerate(image_files):
            if cancel_event.is_set():
                log_func("⛔ キャンセルされました")
                done_func(False)
                return
            log_func(f"  [{i+1:02d}/{total}] {os.path.basename(img_path)}")
            photo_progress_cb((i + 1) / total)
            clip = ImageClip(img_path).resized(output_size).with_duration(duration_per_photo)
            # 最初の1枚以外にクロスフェードを適用
            if i > 0:
                clip = clip.with_effects([CrossFadeIn(fade_duration)])
            clips.append(clip)

        if cancel_event.is_set():
            log_func("⛔ キャンセルされました")
            done_func(False)
            return

        log_func("─" * 45)
        log_func("🔗 クリップを結合中（クロスフェード）...")
        # padding を負にするとクリップが重なり、クロスフェードが発生する
        video = concatenate_videoclips(clips, method="compose", padding=-fade_duration)

        if music_file and os.path.exists(music_file):
            log_func("🎵 音楽を追加中...")
            audio = AudioFileClip(music_file)
            if audio.duration < video.duration:
                from moviepy import concatenate_audioclips
                loop_count = math.ceil(video.duration / audio.duration)
                audio = concatenate_audioclips([audio] * loop_count)
            audio = audio.subclipped(0, video.duration)
            audio = audio.with_effects([
                __import__("moviepy.audio.fx", fromlist=["AudioFadeOut"]).AudioFadeOut(2)
            ])
            video = video.with_audio(audio)
        elif music_file:
            log_func(f"⚠️  音楽ファイルが見つかりません")

        log_func("─" * 45)
        log_func("🎬 動画をエンコード中...")

        # 一時音声ファイルのパスを出力先フォルダに明示指定
        output_dir = os.path.dirname(os.path.abspath(output_file))
        temp_audio = os.path.join(output_dir, "TEMP_slideshow_audio.mp4")
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass

        logger = CancellableLogger(cancel_event, encode_progress_cb)
        video.write_videofile(
            output_file, fps=24, codec="libx264", audio_codec="aac",
            logger=logger, temp_audiofile=temp_audio
        )

        log_func("─" * 45)
        log_func(f"✅ 完成! → {output_file}")
        done_func(True)

    except InterruptedError:
        log_func("⛔ キャンセルされました")
        _cleanup_temp(output_file)
        # 中途半端な出力ファイルも削除
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                log_func(f"🗑  中途半端な出力ファイルを削除しました")
            except Exception:
                pass
        done_func(False)
    except Exception as e:
        log_func(f"❌ エラー: {e}")
        _cleanup_temp(output_file)
        done_func(False)


def _cleanup_temp(output_file):
    """中断・エラー時の一時ファイルを削除"""
    output_dir = os.path.dirname(os.path.abspath(output_file))
    tmp = os.path.join(output_dir, "TEMP_slideshow_audio.mp4")
    if os.path.exists(tmp):
        try:
            os.remove(tmp)
        except Exception:
            pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎬 スライドショー動画作成")
        self.geometry("1100x560")
        self.resizable(False, False)
        self._cancel_event = threading.Event()
        self._build_ui()

    def _build_ui(self):
        # ---- タイトル ----
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=24, pady=(16, 8))
        ctk.CTkLabel(
            title_frame, text="🎬 スライドショー動画作成",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left")

        # ---- メインエリア（左右2列） ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        # ======== 左カラム：設定 ========
        left = ctk.CTkFrame(main, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=4)

        ctk.CTkLabel(left, text="設定", font=ctk.CTkFont(size=13, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 6))

        def file_row(label, var, browse_cmd):
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)
            ctk.CTkLabel(row, text=label, width=100, anchor="e",
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 6))
            ctk.CTkEntry(row, textvariable=var).pack(side="left", expand=True, fill="x", padx=(0, 6))
            ctk.CTkButton(row, text="参照", width=60, command=browse_cmd).pack(side="left")

        self.photos_var = tk.StringVar(value=DEFAULT_PHOTOS_DIR)
        self.music_var  = tk.StringVar(value=DEFAULT_MUSIC_FILE)
        self.output_var = tk.StringVar(value=DEFAULT_OUTPUT_FILE)

        file_row("写真フォルダ", self.photos_var, self._browse_photos)
        file_row("音楽ファイル", self.music_var,  self._browse_music)
        file_row("出力ファイル", self.output_var, self._browse_output)

        # 区切り線
        ctk.CTkFrame(left, height=1, fg_color="#333355").pack(fill="x", padx=16, pady=10)

        # 出力モード選択
        mode_row = ctk.CTkFrame(left, fg_color="transparent")
        mode_row.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkLabel(mode_row, text="出力モード:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(4, 10))
        self.mode_var = tk.StringVar(value="PC")
        ctk.CTkSegmentedButton(
            mode_row,
            values=["PC", "iPhone"],
            variable=self.mode_var,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")
        self.mode_desc = ctk.CTkLabel(mode_row, text="1920×1080（横長）",
                                       font=ctk.CTkFont(size=11), text_color="gray")
        self.mode_desc.pack(side="left", padx=10)
        self.mode_var.trace_add("write", lambda *_: self.mode_desc.configure(
            text="1920×1080（横長）" if self.mode_var.get() == "PC" else "1080×1920（縦長）"
        ))

        # 数値設定（横並び）
        num_row = ctk.CTkFrame(left, fg_color="transparent")
        num_row.pack(fill="x", padx=12, pady=4)

        # 1枚あたりの秒数
        dur_box = ctk.CTkFrame(num_row, corner_radius=10)
        dur_box.pack(side="left", expand=True, fill="x", padx=(0, 8))
        ctk.CTkLabel(dur_box, text="1枚あたりの秒数", font=ctk.CTkFont(size=11)).pack(pady=(8, 2))
        self.duration_var = tk.DoubleVar(value=3.0)
        ctk.CTkEntry(dur_box, textvariable=self.duration_var, width=90, justify="center",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 8))

        # 自動計算された枚数
        count_box = ctk.CTkFrame(num_row, corner_radius=10)
        count_box.pack(side="left", expand=True, fill="x")
        ctk.CTkLabel(count_box, text="写真の枚数（自動計算）", font=ctk.CTkFont(size=11)).pack(pady=(8, 2))
        self.count_label = ctk.CTkLabel(count_box, text="— 枚",
                                         font=ctk.CTkFont(size=20, weight="bold"),
                                         text_color="#4fa3e0")
        self.count_label.pack()
        self.count_detail_label = ctk.CTkLabel(count_box, text="",
                                                font=ctk.CTkFont(size=10),
                                                text_color="gray")
        self.count_detail_label.pack(pady=(0, 8))

        self.duration_var.trace_add("write", lambda *_: self._update_count())
        self.music_var.trace_add("write", lambda *_: self._update_count())
        self._update_count()

        # ボタン（左カラム下部）
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=(12, 14))

        self.run_btn = ctk.CTkButton(
            btn_frame, text="▶  動画を作成", height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10, command=self._run
        )
        self.run_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btn_frame, text="■  中断", height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=10, fg_color="#c0392b", hover_color="#922b21",
            command=self._stop, state="disabled"
        )
        self.stop_btn.pack(side="left", expand=True, fill="x")

        # ======== 右カラム：進捗＋ログ ========
        right = ctk.CTkFrame(main, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 8), pady=4)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="進捗", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        # プログレスバー
        prog = ctk.CTkFrame(right, fg_color="transparent")
        prog.grid(row=0, column=0, sticky="ew", padx=12, pady=(28, 0))

        ctk.CTkLabel(prog, text="写真の読み込み", font=ctk.CTkFont(size=11)).pack(anchor="w")
        bar_row1 = ctk.CTkFrame(prog, fg_color="transparent")
        bar_row1.pack(fill="x", pady=(2, 6))
        self.photo_bar = ctk.CTkProgressBar(bar_row1, height=12, corner_radius=6)
        self.photo_bar.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.photo_bar.set(0)
        self.photo_label = ctk.CTkLabel(bar_row1, text="0%", width=36,
                                         font=ctk.CTkFont(size=11), text_color="gray")
        self.photo_label.pack(side="left")

        ctk.CTkLabel(prog, text="動画エンコード", font=ctk.CTkFont(size=11)).pack(anchor="w")
        bar_row2 = ctk.CTkFrame(prog, fg_color="transparent")
        bar_row2.pack(fill="x", pady=(2, 0))
        self.encode_bar = ctk.CTkProgressBar(bar_row2, height=12, corner_radius=6,
                                              progress_color="#e05c5c")
        self.encode_bar.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self.encode_bar.set(0)
        self.encode_label = ctk.CTkLabel(bar_row2, text="0%", width=36,
                                          font=ctk.CTkFont(size=11), text_color="gray")
        self.encode_label.pack(side="left")

        # ログ
        ctk.CTkLabel(right, text="進捗ログ", font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, sticky="w", padx=16, pady=(12, 2))
        self.log_box = ctk.CTkTextbox(right, font=ctk.CTkFont(family="Consolas", size=10),
                                       fg_color="#1a1a2e", corner_radius=8)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(28, 12))
        self.log_box.configure(state="disabled")

    # ---- 枚数自動計算 ----
    def _update_count(self):
        def _calc():
            music = self.music_var.get()
            try:
                dur = self.duration_var.get()
            except Exception:
                dur = 3.0
            FADE = 0.8  # クロスフェード時間（slideshow.pyと同じ値）
            if music and os.path.exists(music) and dur > FADE:
                music_dur = get_music_duration(music)
                if music_dur:
                    # クロスフェード分を考慮した正確な計算
                    # 合計時間 = (N-1)*(dur-FADE) + dur = N*dur - (N-1)*FADE
                    # → N = (music_dur - FADE) / (dur - FADE) + 1 を整数に
                    effective = dur - FADE
                    count = max(1, int((music_dur - FADE) / effective) + 1)
                    m, s = divmod(int(music_dur), 60)
                    detail = f"{m}分{s:02d}秒 ÷ {dur:.1f}秒/枚"
                    def _upd(c=count, d=detail):
                        self.count_label.configure(text=f"{c} 枚")
                        self.count_detail_label.configure(text=d)
                    self.after(0, _upd)
                    return
            def _reset():
                self.count_label.configure(text="— 枚")
                self.count_detail_label.configure(text="音楽ファイルを選択してください")
            self.after(0, _reset)
        threading.Thread(target=_calc, daemon=True).start()

    # ---- ファイル選択 ----
    def _browse_photos(self):
        p = filedialog.askdirectory(initialdir=self.photos_var.get())
        if p: self.photos_var.set(p)

    def _browse_music(self):
        p = filedialog.askopenfilename(
            initialdir=os.path.dirname(self.music_var.get()),
            filetypes=[("音楽ファイル", "*.mp3 *.3gp *.m4a *.wav *.aac"), ("すべて", "*.*")]
        )
        if p: self.music_var.set(p)

    def _browse_output(self):
        p = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(self.output_var.get()),
            defaultextension=".mp4", filetypes=[("MP4動画", "*.mp4")]
        )
        if p: self.output_var.set(p)

    # ---- ログ更新 ----
    def _log(self, msg):
        def _upd():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(0, _upd)

    # ---- プログレス更新 ----
    def _set_photo_progress(self, v):
        def _upd():
            self.photo_bar.set(v)
            self.photo_label.configure(text=f"{v*100:.0f}%")
        self.after(0, _upd)

    def _set_encode_progress(self, v):
        def _upd():
            self.encode_bar.set(v)
            self.encode_label.configure(text=f"{v*100:.0f}%")
        self.after(0, _upd)

    # ---- 完了 ----
    def _done(self, success):
        def _upd():
            self.run_btn.configure(state="normal", text="▶  動画を作成")
            self.stop_btn.configure(state="disabled")
            if success:
                messagebox.showinfo("完成 🎉", f"動画を保存しました:\n{self.output_var.get()}")
            else:
                messagebox.showerror("エラー / キャンセル", "動画の作成を完了できませんでした。\nログを確認してください。")
        self.after(0, _upd)

    # ---- 実行 ----
    def _run(self):
        self._cancel_event.clear()
        self.run_btn.configure(state="disabled", text="処理中...")
        self.stop_btn.configure(state="normal")
        self.photo_bar.set(0)
        self.encode_bar.set(0)
        self.photo_label.configure(text="0%")
        self.encode_label.configure(text="0%")
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

        threading.Thread(target=create_slideshow, kwargs={
            "photos_dir":         self.photos_var.get(),
            "music_file":         self.music_var.get(),
            "duration_per_photo": self.duration_var.get(),
            "output_file":        self.output_var.get(),
            "output_mode":        self.mode_var.get(),
            "log_func":           self._log,
            "photo_progress_cb":  self._set_photo_progress,
            "encode_progress_cb": self._set_encode_progress,
            "done_func":          self._done,
            "cancel_event":       self._cancel_event,
        }, daemon=True).start()

    # ---- 中断 ----
    def _stop(self):
        self._cancel_event.set()
        self.stop_btn.configure(state="disabled", text="中断中...")
        self._log("⛔ 中断リクエストを送信しました...")


if __name__ == "__main__":
    app = App()
    app.mainloop()
