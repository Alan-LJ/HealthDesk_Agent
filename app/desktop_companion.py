from __future__ import annotations

import ctypes
import json
import math
import os
import random
import sys
import threading
import traceback
import tkinter as tk
import tkinter.messagebox as messagebox
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


TRANSPARENT = "#01FF01"
BASE_PET_SIZE = 180
BASE_CANVAS_W = 380
BASE_CANVAS_H = 520
BASE_PET_CENTER_X = BASE_CANVAS_W // 2
BASE_PET_CENTER_Y = 345
BASE_NAME_Y = 466
BASE_HEART_SOURCE_Y = 246
BASE_DIALOG_X = 20
BASE_DIALOG_Y = 20
BASE_DIALOG_W = 340
BASE_DIALOG_H = 168
GREEN_THRESHOLD = 100
DRAG_DEAD_ZONE = 3
VISIBLE_MARGIN = 48
HEART_COLORS = ["#FF4D6D", "#FF6B8A", "#FF85A1", "#FF3366", "#FF80AB", "#F06292", "#E91E63"]
SIZE_PRESETS = {
    "small": 0.85,
    "medium": 1.0,
    "large": 1.25,
    "xlarge": 2.0,
}
PET_HEAD_GAP_PRESETS = {
    "small": 42,
    "medium": 64,
    "large": 84,
    "xlarge": 112,
}
DEFAULT_SIZE_PRESET = "medium"

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PET_ASSET_DIR = PROJECT_ROOT / "pics"
POSITION_FILE = PROJECT_ROOT / ".hdagent" / "desktop_companion_position.json"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
API_TIMEOUT_SECONDS = 8
DESKTOP_DATA_DIR = Path(os.getenv("LOCALAPPDATA", str(PROJECT_ROOT / ".hdagent"))) / "HealthDeskAgent"
ENVIRONMENT_SETTING_FIELDS = [
    ("temperature_comfort_min_c", "适宜温度下限", "°C"),
    ("temperature_comfort_max_c", "适宜温度上限", "°C"),
    ("temperature_warning_low_c", "重点低温(≤下限)", "°C"),
    ("temperature_warning_high_c", "重点高温(≥上限)", "°C"),
    ("humidity_comfort_min_percent", "适宜湿度下限", "%"),
    ("humidity_comfort_max_percent", "适宜湿度上限", "%"),
    ("humidity_warning_low_percent", "重点低湿(≤下限)", "%"),
    ("humidity_warning_high_percent", "重点高湿(≥上限)", "%"),
]


class DesktopCompanion:
    """Windows desktop companion using a transparent borderless tkinter window."""

    def __init__(self) -> None:
        self._configure_desktop_runtime_paths()
        self.api_base_url = self._load_api_base_url()
        self.size_preset = self._load_saved_size_preset()
        self.scale = SIZE_PRESETS[self.size_preset]
        self._sync_layout_metrics()

        self.root = tk.Tk()
        self.root.title("HealthDesk Agent Companion")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)

        self.canvas = tk.Canvas(
            self.root,
            width=self.canvas_w,
            height=self.canvas_h,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.img_normal = self._load_pet_image(PET_ASSET_DIR / "corgi_normal.png")
        self.img_excited = self._load_pet_image(PET_ASSET_DIR / "corgi_ears_up.png")
        self.current_excited = False
        self.pet_image_id = self.canvas.create_image(self.pet_center_x, self.pet_center_y, image=self.img_normal, tags=("pet",))
        self.name_id = self.canvas.create_text(
            self.pet_center_x,
            self.name_y,
            text="小灵",
            fill="#15df2a",
            font=("Microsoft YaHei UI", self.name_font_size, "bold"),
            tags=("pet",),
        )
        self.shadow_id = self.canvas.create_oval(
            self.pet_center_x - self.shadow_w,
            self.pet_center_y + self.shadow_top,
            self.pet_center_x + self.shadow_w,
            self.pet_center_y + self.shadow_bottom,
            fill="#18232b",
            outline="",
            stipple="gray25",
        )
        self.canvas.tag_lower(self.shadow_id, self.pet_image_id)

        self.dialog_window_id: int | None = None
        self.dialog_frame: tk.Frame | None = None
        self.input_text: tk.Text | None = None
        self.status_var = tk.StringVar(value="Ready")
        self.send_button: tk.Button | None = None
        self.size_buttons: dict[str, tk.Button] = {}
        self.dialog_visible = False
        self.reply_hide_after: str | None = None
        self.reset_after: str | None = None
        self.runtime: Any = None
        self.busy = False
        self.environment_settings_window: tk.Toplevel | None = None
        self.environment_setting_entries: dict[str, tk.Entry] = {}
        self.environment_settings_status: tk.StringVar | None = None

        self.drag_x = 0
        self.drag_y = 0
        self.was_dragged = False
        self.hearts: list[dict[str, Any]] = []
        self.animating_hearts = False
        self.bounce_offsets: list[int] = []

        self._build_dialog()
        self._bind_events()
        self._restore_position()

    def run(self) -> None:
        self.root.mainloop()

    def _sync_layout_metrics(self) -> None:
        self.canvas_w = self._scaled(BASE_CANVAS_W)
        self.canvas_h = self._scaled(BASE_CANVAS_H)
        self.pet_size = self._scaled(BASE_PET_SIZE)
        self.pet_center_x = self._scaled(BASE_PET_CENTER_X)
        self.dialog_x = self._scaled(BASE_DIALOG_X)
        self.dialog_y = self._scaled(BASE_DIALOG_Y)
        self.dialog_w = self._scaled(BASE_DIALOG_W)
        self.dialog_h = BASE_DIALOG_H
        self.pet_head_gap = PET_HEAD_GAP_PRESETS.get(
            getattr(self, "size_preset", DEFAULT_SIZE_PRESET),
            PET_HEAD_GAP_PRESETS[DEFAULT_SIZE_PRESET],
        )
        self.pet_center_y = self.dialog_y + self.dialog_h + self.pet_head_gap + self.pet_size // 2
        self.name_y = self.pet_center_y + self._scaled_delta(BASE_NAME_Y - BASE_PET_CENTER_Y)
        self.heart_source_y = self.pet_center_y + self._scaled_delta(BASE_HEART_SOURCE_Y - BASE_PET_CENTER_Y)
        self.name_font_size = max(10, self._scaled(13))
        self.heart_min_size = max(10, self._scaled(12))
        self.heart_max_size = max(self.heart_min_size + 2, self._scaled(22))
        self.heart_x_spread = self._scaled(38)
        self.shadow_w = self._scaled(72)
        self.shadow_top = self._scaled(82)
        self.shadow_bottom = self._scaled(102)

    def _scaled(self, value: int | float) -> int:
        return max(1, int(round(float(value) * self.scale)))

    def _scaled_delta(self, value: int | float) -> int:
        return int(round(float(value) * self.scale))

    @staticmethod
    def _configure_desktop_runtime_paths() -> None:
        DESKTOP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not os.getenv("DATABASE_PATH") and not os.getenv("HEALTHDESK_DB_PATH"):
            db_path = DESKTOP_DATA_DIR / "healthdesk.db"
            os.environ["DATABASE_PATH"] = str(db_path)
            os.environ["HEALTHDESK_DB_PATH"] = str(db_path)
        if not os.getenv("RAG_CHROMA_PATH"):
            os.environ["RAG_CHROMA_PATH"] = str(DESKTOP_DATA_DIR / "chroma")

    @staticmethod
    def _load_api_base_url() -> str:
        value = os.getenv("HEALTHDESK_API_BASE_URL") or os.getenv("HEALTHDESK_DESKTOP_API_BASE_URL") or DEFAULT_API_BASE_URL
        return value.strip().rstrip("/") or DEFAULT_API_BASE_URL

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.api_base_url}{path}"
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(self._format_api_error(detail, exc.code)) from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"无法连接 HealthDesk API：{self.api_base_url}") from exc
        if not text:
            return {}
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"API 返回了无法解析的 JSON：{text[:120]}") from exc
        return data if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _format_api_error(text: str, status_code: int) -> str:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text or f"HTTP {status_code}"
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            return "；".join(str(item.get("msg", item)) if isinstance(item, dict) else str(item) for item in detail)
        if detail:
            return str(detail)
        return f"HTTP {status_code}"

    @staticmethod
    def _load_saved_size_preset() -> str:
        if not POSITION_FILE.exists():
            return DEFAULT_SIZE_PRESET
        try:
            data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return DEFAULT_SIZE_PRESET
        size = data.get("size")
        if isinstance(size, str) and size in SIZE_PRESETS:
            return size
        scale = data.get("scale")
        if isinstance(scale, (int, float)):
            return min(SIZE_PRESETS, key=lambda preset: abs(SIZE_PRESETS[preset] - float(scale)))
        return DEFAULT_SIZE_PRESET

    def _build_dialog(self) -> None:
        frame = tk.Frame(self.canvas, bg="#ffffff", highlightbackground="#75d6d0", highlightthickness=1)
        frame.grid_columnconfigure(0, weight=1)

        head = tk.Frame(frame, bg="#ffffff")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        head.grid_columnconfigure(0, weight=1)
        tk.Label(head, text="小灵", bg="#ffffff", fg="#18232b", font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        size_controls = tk.Frame(head, bg="#f7fbfb", highlightbackground="#d7e2e5", highlightthickness=1)
        size_controls.grid(row=0, column=1, sticky="e", padx=(8, 8))
        self.size_buttons = {}
        for index, (preset, label) in enumerate([("small", "小"), ("medium", "中"), ("large", "大"), ("xlarge", "超大")]):
            button = tk.Button(
                size_controls,
                text=label,
                width=3 if preset != "xlarge" else 4,
                command=lambda value=preset: self._set_size_preset(value),
                relief="flat",
                bd=0,
                padx=3,
                pady=1,
                cursor="hand2",
                font=("Microsoft YaHei UI", 8),
            )
            button.grid(row=0, column=index, padx=1, pady=1)
            self.size_buttons[preset] = button
        self._sync_size_buttons()
        tk.Button(
            head,
            text="×",
            width=3,
            command=self._hide_dialog,
            bg="#ffffff",
            fg="#63737d",
            relief="flat",
            cursor="hand2",
        ).grid(row=0, column=2, sticky="e")

        self.input_text = tk.Text(
            frame,
            height=4,
            wrap="word",
            bg="#ffffff",
            fg="#18232b",
            relief="solid",
            bd=1,
            padx=8,
            pady=7,
            font=("Microsoft YaHei UI", 10),
            insertbackground="#18232b",
        )
        self.input_text.grid(row=1, column=0, sticky="ew", padx=10)
        self.input_text.bind("<Return>", self._on_return)
        self.input_text.bind("<Shift-Return>", lambda _event: None)

        foot = tk.Frame(frame, bg="#ffffff")
        foot.grid(row=2, column=0, sticky="ew", padx=10, pady=(7, 10))
        foot.grid_columnconfigure(0, weight=1)
        tk.Label(foot, textvariable=self.status_var, bg="#ffffff", fg="#63737d", font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="w")
        self.send_button = tk.Button(
            foot,
            text="发送",
            command=self._send_message,
            bg="#1d9a96",
            fg="#ffffff",
            activebackground="#16857f",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=5,
            cursor="hand2",
        )
        self.send_button.grid(row=0, column=1, sticky="e")

        self.dialog_frame = frame
        self.dialog_window_id = self.canvas.create_window(
            self.dialog_x,
            self.dialog_y,
            width=self.dialog_w,
            height=self.dialog_h,
            anchor="nw",
            window=frame,
            state="hidden",
        )

    def _bind_events(self) -> None:
        for sequence in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>"):
            self.canvas.tag_bind("pet", sequence, getattr(self, {
                "<ButtonPress-1>": "_on_press",
                "<B1-Motion>": "_on_drag",
                "<ButtonRelease-1>": "_on_release",
            }[sequence]))
        self.canvas.tag_bind("pet", "<Button-3>", self._on_right_click)
        self.root.bind("<Escape>", lambda _event: self._hide_dialog())

    def _load_pet_image(self, path: Path) -> Any:
        try:
            from PIL import Image, ImageTk
        except ModuleNotFoundError as exc:
            if self._is_jpeg_file(path):
                raise RuntimeError(
                    f"{path.name} uses JPEG/JFIF data although its extension is .png. "
                    "Install Pillow in the current virtual environment: python -m pip install Pillow>=12.0.0"
                ) from exc
            return self._load_pet_image_tk(path)

        try:
            img = Image.open(path).convert("RGBA")
            pixels = img.load()
            for y in range(img.height):
                for x in range(img.width):
                    r, g, b, a = pixels[x, y]
                    if g > 120 and g - r > GREEN_THRESHOLD and g - b > GREEN_THRESHOLD:
                        pixels[x, y] = (0, 0, 0, 0)
                    elif g > 100 and g - r > 50 and g - b > 50:
                        green_ratio = min(1.0, max(0.0, (g - max(r, b)) / 100.0))
                        pixels[x, y] = (r, min(g, int((r + b) / 2 + 12)), b, int(a * (1 - green_ratio)))
            img.thumbnail((self.pet_size, self.pet_size), Image.LANCZOS)
            layer = Image.new("RGBA", (self.pet_size, self.pet_size), (0, 0, 0, 0))
            layer.paste(img, ((self.pet_size - img.width) // 2, (self.pet_size - img.height) // 2), img)
            return ImageTk.PhotoImage(layer)
        except Exception as exc:
            raise RuntimeError(f"Failed to load pet image: {path}") from exc

    @staticmethod
    def _is_jpeg_file(path: Path) -> bool:
        try:
            return path.read_bytes()[:3] == b"\xff\xd8\xff"
        except OSError:
            return False

    def _load_pet_image_tk(self, path: Path) -> tk.PhotoImage:
        source = tk.PhotoImage(file=str(path))
        scale = max(1, round(max(source.width(), source.height()) / self.pet_size))
        small = source.subsample(scale, scale)
        output = tk.PhotoImage(width=small.width(), height=small.height())
        for y in range(small.height()):
            row = []
            transparent_x: list[int] = []
            for x in range(small.width()):
                r, g, b = self._normalize_color(small.get(x, y))
                if g > 120 and g - r > GREEN_THRESHOLD and g - b > GREEN_THRESHOLD:
                    row.append(TRANSPARENT)
                    transparent_x.append(x)
                else:
                    row.append(f"#{r:02x}{g:02x}{b:02x}")
            output.put("{" + " ".join(row) + "}", to=(0, y))
            for x in transparent_x:
                output.transparency_set(x, y, True)
        return output

    @staticmethod
    def _normalize_color(value: Any) -> tuple[int, int, int]:
        if isinstance(value, tuple):
            return int(value[0]), int(value[1]), int(value[2])
        text = str(value).lstrip("#")
        return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)

    def _restore_position(self) -> None:
        _left, _top, right, bottom = self._virtual_screen_bounds()
        x = right - self.canvas_w - 80
        y = bottom - self.canvas_h - 80
        if POSITION_FILE.exists():
            try:
                data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
                x = int(data.get("x", x))
                y = int(data.get("y", y))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        x, y = self._clamp_position(x, y)
        self._apply_window_geometry(x, y)

    def _save_position(self) -> None:
        POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "x": self.root.winfo_x(),
            "y": self.root.winfo_y(),
            "size": self.size_preset,
            "scale": self.scale,
        }
        POSITION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = self._virtual_screen_bounds()
        return (
            max(left - self.canvas_w + VISIBLE_MARGIN, min(x, right - VISIBLE_MARGIN)),
            max(top - self.canvas_h + VISIBLE_MARGIN, min(y, bottom - VISIBLE_MARGIN)),
        )

    def _apply_window_geometry(self, x: int, y: int) -> None:
        self.root.geometry(f"{self.canvas_w}x{self.canvas_h}{self._geometry_offset(x, y)}")

    def _virtual_screen_bounds(self) -> tuple[int, int, int, int]:
        if sys.platform.startswith("win"):
            try:
                user32 = ctypes.windll.user32
                left = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
                top = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
                width = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
                height = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
                if width > 0 and height > 0:
                    return left, top, left + width, top + height
            except Exception:
                pass
        try:
            left = int(self.root.winfo_vrootx())
            top = int(self.root.winfo_vrooty())
            width = int(self.root.winfo_vrootwidth())
            height = int(self.root.winfo_vrootheight())
            if width > 0 and height > 0:
                return left, top, left + width, top + height
        except tk.TclError:
            pass
        return 0, 0, int(self.root.winfo_screenwidth()), int(self.root.winfo_screenheight())

    @staticmethod
    def _geometry_offset(x: int, y: int) -> str:
        return f"{int(x):+d}{int(y):+d}"

    def _on_press(self, event: tk.Event) -> None:
        self.drag_x = int(event.x)
        self.drag_y = int(event.y)
        self.was_dragged = False

    def _on_drag(self, event: tk.Event) -> None:
        dx = int(event.x) - self.drag_x
        dy = int(event.y) - self.drag_y
        if abs(dx) > DRAG_DEAD_ZONE or abs(dy) > DRAG_DEAD_ZONE:
            self.was_dragged = True
        x, y = self._clamp_position(self.root.winfo_x() + dx, self.root.winfo_y() + dy)
        self.root.geometry(self._geometry_offset(x, y))

    def _on_release(self, _event: tk.Event) -> None:
        self._save_position()
        if not self.was_dragged:
            self._click_reaction()

    def _click_reaction(self) -> None:
        self._set_image(excited=True)
        self._spawn_hearts()
        self._bounce_pet()
        self._show_dialog()
        if self.reset_after:
            self.root.after_cancel(self.reset_after)
        self.reset_after = self.root.after(2000, lambda: self._set_image(excited=False))

    def _set_image(self, *, excited: bool) -> None:
        self.current_excited = excited
        self.canvas.itemconfig(self.pet_image_id, image=self.img_excited if excited else self.img_normal)

    def _sync_size_buttons(self) -> None:
        for preset, button in self.size_buttons.items():
            active = preset == self.size_preset
            button.config(
                bg="#1d9a96" if active else "#f7fbfb",
                fg="#ffffff" if active else "#63737d",
                activebackground="#16857f" if active else "#eaf5f5",
                activeforeground="#ffffff" if active else "#18232b",
            )

    def _set_size_preset(self, preset: str) -> None:
        if preset not in SIZE_PRESETS or preset == self.size_preset:
            return

        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        self.size_preset = preset
        self.scale = SIZE_PRESETS[preset]
        self._sync_size_buttons()
        self._sync_layout_metrics()

        self.img_normal = self._load_pet_image(PET_ASSET_DIR / "corgi_normal.png")
        self.img_excited = self._load_pet_image(PET_ASSET_DIR / "corgi_ears_up.png")
        self.canvas.config(width=self.canvas_w, height=self.canvas_h)
        self.canvas.coords(self.pet_image_id, self.pet_center_x, self.pet_center_y)
        self.canvas.itemconfig(self.pet_image_id, image=self.img_excited if self.current_excited else self.img_normal)
        self.canvas.coords(self.name_id, self.pet_center_x, self.name_y)
        self.canvas.itemconfig(self.name_id, font=("Microsoft YaHei UI", self.name_font_size, "bold"))
        self.canvas.coords(
            self.shadow_id,
            self.pet_center_x - self.shadow_w,
            self.pet_center_y + self.shadow_top,
            self.pet_center_x + self.shadow_w,
            self.pet_center_y + self.shadow_bottom,
        )
        if self.dialog_window_id is not None:
            self.canvas.coords(self.dialog_window_id, self.dialog_x, self.dialog_y)
            self.canvas.itemconfig(self.dialog_window_id, width=self.dialog_w, height=self.dialog_h)

        for heart in self.hearts:
            self.canvas.delete(heart["id"])
        self.hearts = []
        self.animating_hearts = False
        self.bounce_offsets = []

        x, y = self._clamp_position(current_x, current_y)
        self._apply_window_geometry(x, y)
        self._save_position()

    def _show_dialog(self) -> None:
        self._cancel_reply_timer()
        if self.dialog_window_id is not None:
            self.canvas.itemconfig(self.dialog_window_id, state="normal")
        self.dialog_visible = True
        if self.input_text is not None and not self.busy:
            self.input_text.config(state="normal")
            self.input_text.delete("1.0", "end")
            self.input_text.focus_set()
            self.status_var.set("Ready")

    def _hide_dialog(self) -> None:
        self._cancel_reply_timer()
        if self.dialog_window_id is not None:
            self.canvas.itemconfig(self.dialog_window_id, state="hidden")
        self.dialog_visible = False

    def _cancel_reply_timer(self) -> None:
        if self.reply_hide_after:
            self.root.after_cancel(self.reply_hide_after)
            self.reply_hide_after = None

    def _on_return(self, event: tk.Event) -> str | None:
        if int(getattr(event, "state", 0)) & 0x0001:
            return None
        self._send_message()
        return "break"

    def _send_message(self) -> None:
        if self.busy or self.input_text is None:
            return
        task = self.input_text.get("1.0", "end").strip()
        if not task:
            self.input_text.focus_set()
            return
        self.busy = True
        self.status_var.set("Agent 运行中...")
        if self.send_button is not None:
            self.send_button.config(state="disabled")
        self.input_text.config(state="disabled")
        threading.Thread(target=self._run_agent_worker, args=(task,), daemon=True).start()

    def _run_agent_worker(self, task: str) -> None:
        try:
            result = self._run_agent(task)
            text = self._format_agent_reply(result)
            self.root.after(0, lambda: self._show_reply(text))
        except Exception as exc:  # pragma: no cover - user-facing GUI fallback
            traceback.print_exc()
            self.root.after(0, lambda: self._show_reply(f"小灵没有完成这次对话：{exc}"))

    def _run_agent(self, task: str) -> dict[str, Any]:
        try:
            result = self._request_json("POST", "/agent/run", {"task": task, "user_id": "default"})
            if self._agent_result_needs_state_seed(result):
                self._ensure_api_state()
                result = self._request_json("POST", "/agent/run", {"task": task, "user_id": "default"})
            return result
        except ConnectionError:
            pass

        from app.agent_runtimes import AgentRunRequest, LangGraphDeepSeekRuntime
        from app.main_state import repo

        self._ensure_local_state()
        if self.runtime is None:
            self.runtime = LangGraphDeepSeekRuntime(repo=repo)
        result = self.runtime.run(AgentRunRequest(task=task, user_id="default"))
        return result.model_dump()

    @staticmethod
    def _agent_result_needs_state_seed(result: dict[str, Any]) -> bool:
        final_output = result.get("final_output") if isinstance(result.get("final_output"), dict) else {}
        summary = str(final_output.get("health_summary") or result.get("message") or "")
        return "当前没有状态数据" in summary or "simulation tick" in summary

    def _ensure_api_state(self) -> None:
        try:
            self._request_json("GET", "/state/current")
            return
        except RuntimeError as exc:
            if "请先调用 /simulation/tick" not in str(exc) and "当前没有状态数据" not in str(exc):
                raise
        self._request_json("POST", "/simulation/tick")

    @staticmethod
    def _ensure_local_state() -> None:
        from app.main_state import repo, simulator

        if repo.get_current_state() is not None:
            return
        tick = simulator.tick(repo.get_environment_settings("default"))
        repo.save_tick(tick.raw, tick.feature, tick.state, tick.events, tick.sensor_health)

    def _show_reply(self, text: str) -> None:
        self.busy = False
        self._set_image(excited=True)
        self._spawn_hearts()
        if self.send_button is not None:
            self.send_button.config(state="normal")
        if self.input_text is not None:
            self.input_text.config(state="normal")
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", text)
            self.input_text.config(state="disabled")
        self.status_var.set("10 秒后自动隐藏")
        if self.dialog_window_id is not None:
            self.canvas.itemconfig(self.dialog_window_id, state="normal")
        self._cancel_reply_timer()
        self.reply_hide_after = self.root.after(10000, self._hide_dialog)
        if self.reset_after:
            self.root.after_cancel(self.reset_after)
        self.reset_after = self.root.after(2000, lambda: self._set_image(excited=False))

    @staticmethod
    def _format_agent_reply(result: dict[str, Any]) -> str:
        output = result.get("final_output") if isinstance(result.get("final_output"), dict) else {}
        pet_action = output.get("pet_action") if isinstance(output.get("pet_action"), dict) else {}
        lines: list[str] = []
        summary = output.get("health_summary") or output.get("answer") or output.get("message") or result.get("message") or pet_action.get("message")
        if summary:
            lines.append(str(summary))
        recommendations = output.get("recommendations")
        if isinstance(recommendations, list):
            detail_lines = []
            for item in recommendations[:3]:
                if not isinstance(item, dict):
                    continue
                category = item.get("category") or "建议"
                action = item.get("suggested_action") or item.get("reason") or ""
                if action:
                    detail_lines.append(f"{category}: {action}")
            if detail_lines:
                lines.append("\n".join(detail_lines))
        if not lines and pet_action.get("message"):
            lines.append(str(pet_action["message"]))
        return "\n\n".join(lines) or "小灵已经收到。"

    def _spawn_hearts(self) -> None:
        for index in range(8):
            self.root.after(index * 80, self._create_heart)
        if not self.animating_hearts:
            self.animating_hearts = True
            self.root.after(40, self._animate_hearts)

    def _create_heart(self) -> None:
        x = self.pet_center_x + random.uniform(-self.heart_x_spread, self.heart_x_spread)
        y = self.heart_source_y + random.uniform(-self._scaled(8), self._scaled(26))
        size = random.randint(self.heart_min_size, self.heart_max_size)
        item = self.canvas.create_text(
            x,
            y,
            text="♥",
            fill=random.choice(HEART_COLORS),
            font=("Segoe UI Emoji", size, "bold"),
        )
        self.hearts.append(
            {
                "id": item,
                "x": x,
                "y": y,
                "vx": random.uniform(-1.8, 1.8),
                "vy": random.uniform(-3.0, -1.2),
                "size": size,
                "step": 0,
                "max_step": random.randint(28, 35),
            }
        )

    def _animate_hearts(self) -> None:
        alive = []
        for heart in self.hearts:
            heart["step"] += 1
            if heart["step"] >= heart["max_step"]:
                self.canvas.delete(heart["id"])
                continue
            heart["x"] += heart["vx"]
            heart["y"] += heart["vy"]
            heart["vy"] -= 0.02
            progress = heart["step"] / heart["max_step"]
            font_size = max(6, int(heart["size"] * (1 - progress * 0.68)))
            self.canvas.coords(heart["id"], heart["x"], heart["y"])
            self.canvas.itemconfig(heart["id"], font=("Segoe UI Emoji", font_size, "bold"))
            alive.append(heart)
        self.hearts = alive
        if self.hearts:
            self.root.after(40, self._animate_hearts)
        else:
            self.animating_hearts = False

    def _bounce_pet(self) -> None:
        if self.bounce_offsets:
            return
        self.bounce_offsets = [-self._scaled(10), -self._scaled(5), self._scaled(4), self._scaled(3), 0]
        self._apply_next_bounce()

    def _apply_next_bounce(self) -> None:
        if not self.bounce_offsets:
            return
        offset = self.bounce_offsets.pop(0)
        self.canvas.coords(self.pet_image_id, self.pet_center_x, self.pet_center_y + offset)
        if offset == 0:
            return
        self.root.after(70, self._apply_next_bounce)

    def _load_environment_settings(self) -> dict[str, Any]:
        try:
            return self._request_json("GET", "/settings/environment?user_id=default")
        except ConnectionError:
            from app.main_state import repo

            return repo.get_environment_settings("default").model_dump()

    def _save_environment_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        from app.schemas.environment import EnvironmentThresholdSettings

        settings = EnvironmentThresholdSettings(**payload)
        data = settings.model_dump()
        try:
            return self._request_json("PUT", "/settings/environment?user_id=default", data)
        except ConnectionError:
            from app.main_state import repo

            return repo.save_environment_settings(settings, "default").model_dump()

    def _open_environment_settings_dialog(self) -> None:
        if self.environment_settings_window is not None and self.environment_settings_window.winfo_exists():
            self.environment_settings_window.lift()
            self.environment_settings_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        window.title("环境阈值设置")
        window.configure(bg="#ffffff")
        window.resizable(False, False)
        window.attributes("-topmost", True)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self._close_environment_settings_dialog)

        self.environment_settings_window = window
        self.environment_setting_entries = {}
        self.environment_settings_status = tk.StringVar(value="读取中...")

        container = tk.Frame(window, bg="#ffffff", padx=14, pady=12)
        container.grid(row=0, column=0, sticky="nsew")
        tk.Label(
            container,
            text="环境阈值",
            bg="#ffffff",
            fg="#18232b",
            font=("Microsoft YaHei UI", 12, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        tk.Label(
            container,
            text="重点低温/低湿需不高于适宜下限；重点高温/高湿需不低于适宜上限。",
            bg="#ffffff",
            fg="#63737d",
            font=("Microsoft YaHei UI", 8),
            wraplength=300,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))

        for row, (name, label, unit) in enumerate(ENVIRONMENT_SETTING_FIELDS, start=2):
            tk.Label(container, text=label, bg="#ffffff", fg="#263c46", font=("Microsoft YaHei UI", 10)).grid(row=row, column=0, sticky="w", pady=4)
            entry = tk.Entry(container, width=12, relief="solid", bd=1, font=("Microsoft YaHei UI", 10))
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 6), pady=4)
            tk.Label(container, text=unit, bg="#ffffff", fg="#63737d", font=("Microsoft YaHei UI", 10)).grid(row=row, column=2, sticky="w", pady=4)
            self.environment_setting_entries[name] = entry

        tk.Label(
            container,
            textvariable=self.environment_settings_status,
            bg="#ffffff",
            fg="#63737d",
            font=("Microsoft YaHei UI", 9),
            wraplength=320,
            justify="left",
        ).grid(row=len(ENVIRONMENT_SETTING_FIELDS) + 2, column=0, columnspan=3, sticky="ew", pady=(8, 6))

        actions = tk.Frame(container, bg="#ffffff")
        actions.grid(row=len(ENVIRONMENT_SETTING_FIELDS) + 3, column=0, columnspan=3, sticky="e")
        tk.Button(
            actions,
            text="取消",
            command=self._close_environment_settings_dialog,
            bg="#ffffff",
            fg="#63737d",
            relief="flat",
            padx=12,
            pady=5,
            cursor="hand2",
        ).grid(row=0, column=0, padx=(0, 8))
        tk.Button(
            actions,
            text="确认保存",
            command=self._submit_environment_settings_dialog,
            bg="#1d9a96",
            fg="#ffffff",
            activebackground="#16857f",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=5,
            cursor="hand2",
        ).grid(row=0, column=1)

        self._center_environment_settings_dialog(window)
        threading.Thread(target=self._load_environment_settings_worker, daemon=True).start()

    def _center_environment_settings_dialog(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        width = window.winfo_reqwidth()
        height = window.winfo_reqheight()
        x = self.root.winfo_x() + max(0, (self.canvas_w - width) // 2)
        y = self.root.winfo_y() + max(0, (self.canvas_h - height) // 2)
        window.geometry(f"{width}x{height}{self._geometry_offset(x, y)}")

    def _close_environment_settings_dialog(self) -> None:
        if self.environment_settings_window is not None and self.environment_settings_window.winfo_exists():
            self.environment_settings_window.destroy()
        self.environment_settings_window = None
        self.environment_setting_entries = {}
        self.environment_settings_status = None

    def _load_environment_settings_worker(self) -> None:
        try:
            settings = self._load_environment_settings()
        except Exception as exc:
            message = str(exc)
            self.root.after(0, lambda: self._set_environment_settings_status(f"读取失败：{message}"))
            return
        self.root.after(0, lambda: self._fill_environment_settings_dialog(settings))

    def _fill_environment_settings_dialog(self, settings: dict[str, Any]) -> None:
        if self.environment_settings_window is None or not self.environment_settings_window.winfo_exists():
            return
        for name, _label, _unit in ENVIRONMENT_SETTING_FIELDS:
            entry = self.environment_setting_entries.get(name)
            if entry is None:
                continue
            value = settings.get(name, "")
            entry.delete(0, "end")
            entry.insert(0, str(value))
        self._set_environment_settings_status("当前配置已同步。")

    def _submit_environment_settings_dialog(self) -> None:
        try:
            payload = {
                name: float(self.environment_setting_entries[name].get().strip())
                for name, _label, _unit in ENVIRONMENT_SETTING_FIELDS
            }
        except (KeyError, ValueError):
            self._set_environment_settings_status("请填写完整的数字阈值。")
            return
        message = self._validate_environment_settings_payload(payload)
        if message:
            self._set_environment_settings_status(message)
            return
        self._set_environment_settings_status("保存中...")
        threading.Thread(target=self._save_environment_settings_worker, args=(payload,), daemon=True).start()

    @staticmethod
    def _validate_environment_settings_payload(payload: dict[str, float]) -> str:
        if payload["temperature_comfort_min_c"] > payload["temperature_comfort_max_c"]:
            return "适宜温度下限不能高于适宜温度上限。"
        if payload["humidity_comfort_min_percent"] > payload["humidity_comfort_max_percent"]:
            return "适宜湿度下限不能高于适宜湿度上限。"
        if payload["temperature_warning_low_c"] > payload["temperature_warning_high_c"]:
            return "重点监测低温不能高于重点监测高温。"
        if payload["humidity_warning_low_percent"] > payload["humidity_warning_high_percent"]:
            return "重点监测低湿不能高于重点监测高湿。"
        if payload["temperature_warning_low_c"] > payload["temperature_comfort_min_c"]:
            return "重点监测低温需小于或等于适宜温度下限。比如适宜下限 18°C 时，重点低温应填 18°C 或更低。"
        if payload["temperature_warning_high_c"] < payload["temperature_comfort_max_c"]:
            return "重点监测高温需大于或等于适宜温度上限。"
        if payload["humidity_warning_low_percent"] > payload["humidity_comfort_min_percent"]:
            return "重点监测低湿需小于或等于适宜湿度下限。"
        if payload["humidity_warning_high_percent"] < payload["humidity_comfort_max_percent"]:
            return "重点监测高湿需大于或等于适宜湿度上限。"
        return ""

    def _save_environment_settings_worker(self, payload: dict[str, Any]) -> None:
        try:
            saved = self._save_environment_settings(payload)
        except Exception as exc:
            message = self._format_environment_settings_error(exc)
            self.root.after(0, lambda: self._set_environment_settings_status(f"保存失败：{message}"))
            return
        self.root.after(0, lambda: self._on_environment_settings_saved(saved))

    @staticmethod
    def _format_environment_settings_error(exc: Exception) -> str:
        text = str(exc)
        known_messages = [
            "适宜温度下限不能高于适宜温度上限",
            "适宜湿度下限不能高于适宜湿度上限",
            "重点监测低温不能高于重点监测高温",
            "重点监测高温需大于或等于适宜温度上限",
            "重点监测低温需小于或等于适宜温度下限",
            "重点监测低湿不能高于重点监测高湿",
            "重点监测低湿需小于或等于适宜湿度下限",
            "重点监测高湿需大于或等于适宜湿度上限",
        ]
        for message in known_messages:
            if message in text:
                return message + "。"
        legacy_messages = {
            "temperature warning low must be <= comfort min": "重点监测低温需小于或等于适宜温度下限。",
            "temperature warning high must be >= comfort max": "重点监测高温需大于或等于适宜温度上限。",
            "humidity warning low must be <= comfort min": "重点监测低湿需小于或等于适宜湿度下限。",
            "humidity warning high must be >= comfort max": "重点监测高湿需大于或等于适宜湿度上限。",
        }
        for legacy, message in legacy_messages.items():
            if legacy in text:
                return message
        return text.splitlines()[0] if text else "未知错误"

    def _on_environment_settings_saved(self, saved: dict[str, Any]) -> None:
        self._fill_environment_settings_dialog(saved)
        messagebox.showinfo("环境阈值", "环境阈值已保存，桌宠会按新的温湿度区间提醒你。", parent=self.environment_settings_window)
        self._close_environment_settings_dialog()

    def _set_environment_settings_status(self, text: str) -> None:
        if self.environment_settings_status is not None:
            self.environment_settings_status.set(text)

    def _on_right_click(self, event: tk.Event) -> None:
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="摸摸小灵", command=self._click_reaction)
        menu.add_command(label="隐藏对话", command=self._hide_dialog)
        menu.add_command(label="设置环境适宜区间", command=self._open_environment_settings_dialog)
        menu.add_separator()
        menu.add_command(label="再见", command=self.root.destroy)
        menu.tk_popup(int(event.x_root), int(event.y_root))


def main() -> None:
    DesktopCompanion().run()


if __name__ == "__main__":
    main()
