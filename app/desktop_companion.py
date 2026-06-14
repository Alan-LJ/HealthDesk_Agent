from __future__ import annotations

import ctypes
import json
import math
import random
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from typing import Any


TRANSPARENT = "#01FF01"
PET_SIZE = 180
CANVAS_W = 380
CANVAS_H = 520
PET_CENTER_X = CANVAS_W // 2
PET_CENTER_Y = 345
NAME_Y = 466
HEART_SOURCE_Y = 246
GREEN_THRESHOLD = 100
DRAG_DEAD_ZONE = 3
VISIBLE_MARGIN = 48
HEART_COLORS = ["#FF4D6D", "#FF6B8A", "#FF85A1", "#FF3366", "#FF80AB", "#F06292", "#E91E63"]

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PET_ASSET_DIR = PROJECT_ROOT / "pics"
POSITION_FILE = PROJECT_ROOT / ".hdagent" / "desktop_companion_position.json"


class DesktopCompanion:
    """Windows desktop companion using a transparent borderless tkinter window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("HealthDesk Agent Companion")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)

        self.canvas = tk.Canvas(
            self.root,
            width=CANVAS_W,
            height=CANVAS_H,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        self.img_normal = self._load_pet_image(PET_ASSET_DIR / "corgi_normal.png")
        self.img_excited = self._load_pet_image(PET_ASSET_DIR / "corgi_ears_up.png")
        self.current_excited = False
        self.pet_image_id = self.canvas.create_image(PET_CENTER_X, PET_CENTER_Y, image=self.img_normal, tags=("pet",))
        self.name_id = self.canvas.create_text(
            PET_CENTER_X,
            NAME_Y,
            text="小灵",
            fill="#15df2a",
            font=("Microsoft YaHei UI", 13, "bold"),
            tags=("pet",),
        )
        self.shadow_id = self.canvas.create_oval(
            PET_CENTER_X - 72,
            PET_CENTER_Y + 82,
            PET_CENTER_X + 72,
            PET_CENTER_Y + 102,
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
        self.dialog_visible = False
        self.reply_hide_after: str | None = None
        self.reset_after: str | None = None
        self.runtime: Any = None
        self.busy = False

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

    def _build_dialog(self) -> None:
        frame = tk.Frame(self.canvas, bg="#ffffff", highlightbackground="#75d6d0", highlightthickness=1)
        frame.grid_columnconfigure(0, weight=1)

        head = tk.Frame(frame, bg="#ffffff")
        head.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        head.grid_columnconfigure(0, weight=1)
        tk.Label(head, text="小灵", bg="#ffffff", fg="#18232b", font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        tk.Button(
            head,
            text="×",
            width=3,
            command=self._hide_dialog,
            bg="#ffffff",
            fg="#63737d",
            relief="flat",
            cursor="hand2",
        ).grid(row=0, column=1, sticky="e")

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
        self.dialog_window_id = self.canvas.create_window(20, 20, width=340, height=168, anchor="nw", window=frame, state="hidden")

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
            img.thumbnail((PET_SIZE, PET_SIZE), Image.LANCZOS)
            layer = Image.new("RGBA", (PET_SIZE, PET_SIZE), (0, 0, 0, 0))
            layer.paste(img, ((PET_SIZE - img.width) // 2, (PET_SIZE - img.height) // 2), img)
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
        scale = max(1, round(max(source.width(), source.height()) / PET_SIZE))
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
        x = right - CANVAS_W - 80
        y = bottom - CANVAS_H - 80
        if POSITION_FILE.exists():
            try:
                data = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
                x = int(data.get("x", x))
                y = int(data.get("y", y))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        x, y = self._clamp_position(x, y)
        self.root.geometry(f"{CANVAS_W}x{CANVAS_H}{self._geometry_offset(x, y)}")

    def _save_position(self) -> None:
        POSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {"x": self.root.winfo_x(), "y": self.root.winfo_y()}
        POSITION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _clamp_position(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = self._virtual_screen_bounds()
        return (
            max(left - CANVAS_W + VISIBLE_MARGIN, min(x, right - VISIBLE_MARGIN)),
            max(top - CANVAS_H + VISIBLE_MARGIN, min(y, bottom - VISIBLE_MARGIN)),
        )

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
        from app.agent_runtimes import AgentRunRequest, LangGraphDeepSeekRuntime
        from app.main_state import repo

        if self.runtime is None:
            self.runtime = LangGraphDeepSeekRuntime(repo=repo)
        result = self.runtime.run(AgentRunRequest(task=task, user_id="default"))
        return result.model_dump()

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
        x = PET_CENTER_X + random.uniform(-38, 38)
        y = HEART_SOURCE_Y + random.uniform(-8, 26)
        size = random.randint(12, 22)
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
        self.bounce_offsets = [-10, -5, 4, 3, 0]
        self._apply_next_bounce()

    def _apply_next_bounce(self) -> None:
        if not self.bounce_offsets:
            return
        offset = self.bounce_offsets.pop(0)
        self.canvas.coords(self.pet_image_id, PET_CENTER_X, PET_CENTER_Y + offset)
        if offset == 0:
            return
        self.root.after(70, self._apply_next_bounce)

    def _on_right_click(self, event: tk.Event) -> None:
        menu = tk.Menu(self.root, tearoff=0, font=("Microsoft YaHei UI", 10))
        menu.add_command(label="摸摸小灵", command=self._click_reaction)
        menu.add_command(label="隐藏对话", command=self._hide_dialog)
        menu.add_separator()
        menu.add_command(label="再见", command=self.root.destroy)
        menu.tk_popup(int(event.x_root), int(event.y_root))


def main() -> None:
    DesktopCompanion().run()


if __name__ == "__main__":
    main()
