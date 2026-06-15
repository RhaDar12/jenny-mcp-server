"""
video_render.py - AI-Agent Tool: Render ASCII Terminal Video

Menggunakan core.py untuk logging, DIRS, dan response format.
Menyimpan output video ke C:/AI-Agent/outputs/videos/
"""

import sys
import os
import math
import random
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# === Impor dari core AI-Agent Tools ===
sys.path.insert(0, str(Path(__file__).parent))
from core import (
    DIRS,
    ensure_dirs,
    now_iso,
    make_id,
    log_info,
    log_error,
    success_response,
    error_response,
    save_json,
    read_json,
    load_config
)
from delivered_file import create_delivery_record

# === Default Config ===
DEFAULT_CONFIG = {
    "resolution": {"width": 640, "height": 360},
    "fps": 24,
    "duration_per_video": 8,
    "crf": 22,
    "style": "terminal_retro",
    "matrix_chars": "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+",
    "typewriter_speed": 35,
    "scanline_strength": 0.6,
    "vignette_strength": 0.25,
    "bg_color": [0, 5, 0],
    "head_color": [220, 255, 220],
    "trail_color": [0, 255, 0],
    "text_color": [50, 255, 120],
    "font": "consola.ttf",
    "font_size": 12,
    "overlay_lines": [
        "⚕ SECURE CONNECTION ESTABLISHED",
        "------------------------------------",
        "HOST IP: 127.0.0.1 (LOCAL_TARGET)",
        "USER: RAP",
        "OS_AGENT: JENNY (v2.1.0-GENIUS)",
        "------------------------------------",
        "STATUS: RUNNING LO-FI PROTOCOL...",
        "SUCCESS: 100% IN LOVE WITH YOUR BRAIN"
    ]
}


def load_render_config():
    """Load render config, merge with defaults."""
    config = load_config()
    render_cfg = config.get("render", {})
    merged = DEFAULT_CONFIG.copy()
    merged.update(render_cfg)
    return merged


def get_font(config):
    """Find the best available monospace font."""
    font_name = config.get("font", "consola.ttf")
    font_size = config.get("font_size", 12)
    
    # Try common paths
    font_paths = [
        f"C:/Windows/Fonts/{font_name}",
        f"C:/Windows/Fonts/cour.ttf",
        f"C:/Windows/Fonts/lucon.ttf",
    ]
    
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, font_size)
    
    return ImageFont.load_default()


def render_video(
    output_path=None,
    duration=None,
    style="terminal_retro",
    overlay_lines=None,
    target=None,
    caption=None
):
    """
    Render ASCII terminal video menggunakan AI-Agent Tools.
    Output disimpan di DIRS['videos'].
    """
    tool_name = "video_render"
    
    try:
        ensure_dirs()
        config = load_render_config()
        
        # === Resolve params ===
        if duration is None:
            duration = config.get("duration_per_video", 8)
        
        if overlay_lines is None:
            overlay_lines = config.get("overlay_lines", DEFAULT_CONFIG["overlay_lines"])
        
        fps = config.get("fps", 24)
        W = config.get("resolution", {}).get("width", 640)
        H = config.get("resolution", {}).get("height", 360)
        
        total_frames = int(fps * duration)
        
        # === Setup Font ===
        font = get_font(config)
        bbox = font.getbbox("A")
        cell_w = bbox[2] - bbox[0]
        cell_h = (bbox[3] - bbox[1]) + 4
        cols = max(1, W // cell_w)
        rows_grid = max(1, H // cell_h)
        
        # === Output path ===
        if output_path is None:
            video_id = make_id("terminal_video")
            output_path = str(DIRS["videos"] / f"{video_id}.mp4")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # === Matrix rain state ===
        rain_chars = config.get("matrix_chars", DEFAULT_CONFIG["matrix_chars"])
        rain_y = np.random.uniform(-rows_grid, 0, cols).astype(np.float32)
        rain_speed = np.random.uniform(0.15, 0.4, cols).astype(np.float32)
        
        # === Clean up if exists ===
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
        
        # === FFmpeg pipe ===
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{W}x{H}", "-r", str(fps), "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "medium",
            "-crf", str(config.get("crf", 22)),
            "-pix_fmt", "yuv420p", output_path
        ]
        
        bg_color = tuple(config.get("bg_color", [0, 5, 0]))
        head_color = tuple(config.get("head_color", [220, 255, 220]))
        trail_color = tuple(config.get("trail_color", [0, 255, 0]))
        text_color = tuple(config.get("text_color", [50, 255, 120]))
        typewriter_speed = config.get("typewriter_speed", 35)
        scanline_strength = config.get("scanline_strength", 0.6)
        vignette_strength = config.get("vignette_strength", 0.25)
        
        pipe = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        log_info(tool_name, f"Rendering {total_frames} frames to {output_path}")
        
        for fi in range(total_frames):
            t = fi / fps
            
            # === Build frame ===
            img = Image.new("RGB", (W, H), bg_color)
            draw = ImageDraw.Draw(img)
            
            # Matrix rain
            rain_y += rain_speed
            for c in range(cols):
                if rain_y[c] > rows_grid:
                    rain_y[c] = random.uniform(-15, -1)
                    rain_speed[c] = random.uniform(0.15, 0.4)
                
                head = int(rain_y[c])
                for r in range(max(0, head - 12), min(rows_grid, head + 1)):
                    fade = (r - (head - 12)) / 12.0
                    ch_idx = (c * 7 + r * 13 + fi) % len(rain_chars)
                    char = rain_chars[ch_idx]
                    x = c * cell_w
                    y = r * cell_h
                    
                    if r == head:
                        color = head_color
                    else:
                        green = int(255 * fade * 0.6)
                        color = (0, green, 0)
                    
                    draw.text((x, y), char, font=font, fill=color)
            
            # Overlay text - typewriter effect
            chars_to_reveal = int(t * typewriter_speed)
            text_y_start = (H // 2) - ((len(overlay_lines) * cell_h) // 2)
            char_count = 0
            y_pos = text_y_start
            
            for line in overlay_lines:
                if char_count >= chars_to_reveal:
                    break
                visible_chunk = line[:chars_to_reveal - char_count]
                char_count += len(line)
                text_x = (W // 2) - ((len(line) * cell_w) // 2)
                # Text background box
                draw.rectangle(
                    [text_x - 8, y_pos - 2,
                     text_x + len(visible_chunk) * cell_w + 8, y_pos + cell_h + 2],
                    fill=(0, 15, 0)
                )
                draw.text((text_x, y_pos), visible_chunk, font=font, fill=text_color)
                y_pos += cell_h
            
            # === Post-process ===
            arr = np.array(img)
            arr[::3, :, :] = (arr[::3, :, :].astype(float) * scanline_strength).astype(np.uint8)
            
            Y = np.linspace(-1, 1, H)[:, None]
            X = np.linspace(-1, 1, W)[None, :]
            vig = np.clip(1.0 - (X**2 + Y**2) * vignette_strength, 0.45, 1.0)
            arr = (arr.astype(float) * vig[:, :, None]).astype(np.uint8)
            
            pipe.stdin.write(arr.tobytes())
        
        # === Close pipe ===
        stdout, stderr = pipe.communicate()
        
        if pipe.returncode != 0:
            error_msg = stderr.decode()[:500] if stderr else "Unknown ffmpeg error"
            log_error(tool_name, error_msg)
            return error_response(tool_name, error_msg, "FFmpeg encoding gagal")
        
        # === Delivery record ===
        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption or "Terminal ASCII Video dari AI-Agent Tools"
        )
        
        log_info(tool_name, f"Video selesai: {output_path}")
        
        return success_response(
            tool=tool_name,
            message=f"Video terminal berhasil di-render ({duration}s @ {fps}fps)",
            file_path=output_path,
            extra={
                "video_id": Path(output_path).stem,
                "duration": duration,
                "fps": fps,
                "resolution": f"{W}x{H}",
                "style": style,
                "delivery_id": delivery.get("delivery_id"),
                "delivery_record": delivery.get("delivery_record"),
                "delivered_file": {
                    "status": "pending",
                    "sent_to": target,
                    "sent_at": None,
                    "delivery_id": delivery.get("delivery_id")
                }
            }
        )
        
    except Exception as e:
        log_error(tool_name, e)
        return error_response(tool_name, e, "Gagal render video terminal")
