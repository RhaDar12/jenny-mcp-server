from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ModuleNotFoundError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from core import (
    DIRS,
    ensure_dirs,
    make_id,
    success_response,
    error_response
)

from delivered_file import create_delivery_record


def create_text_image(text, output_path, size=(1280, 720)):
    """
    Membuat gambar background sederhana berisi teks.
    """
    img = Image.new("RGB", size, color=(20, 20, 20))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except Exception:
        font = ImageFont.load_default()

    max_width = size[0] - 160
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + " " + word if current_line else word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        text_width = bbox[2] - bbox[0]

        if text_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    line_height = 70
    total_height = len(lines) * line_height
    y = (size[1] - total_height) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (size[0] - text_width) // 2
        draw.text((x, y), line, fill=(255, 255, 255), font=font)
        y += line_height

    img.save(output_path)


def create_video_from_text(
    text,
    duration=8,
    target=None,
    caption="Video dari AI-Agent"
):
    """
    Membuat video MP4 sederhana dari teks.
    """
    tool_name = "create_video_from_text"

    try:
        ensure_dirs()

        if not text or not text.strip():
            raise ValueError("Teks kosong, tidak bisa membuat video.")

        video_id = make_id("video_text")
        image_path = DIRS["temp"] / f"{video_id}.png"
        output_path = DIRS["videos"] / f"{video_id}.mp4"

        create_text_image(text, image_path)

        clip = ImageClip(str(image_path)).with_duration(float(duration))
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio=False,
            logger=None
        )

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Video dari teks berhasil dibuat",
            file_path=output_path,
            extra={
                "video_id": video_id,
                "duration": duration,
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
        return error_response(tool_name, e)


def create_video_from_image(
    image_path,
    duration=8,
    audio_path=None,
    target=None,
    caption="Video dari gambar AI-Agent"
):
    """
    Membuat video MP4 dari gambar.
    Jika audio_path diberikan, audio akan dimasukkan.
    """
    tool_name = "create_video_from_image"

    try:
        ensure_dirs()

        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Gambar tidak ditemukan: {image_path}")

        video_id = make_id("video_image")
        output_path = DIRS["videos"] / f"{video_id}.mp4"

        clip = ImageClip(str(image_path)).set_duration(float(duration))

        if audio_path:
            audio_path = Path(audio_path)

            if not audio_path.exists():
                raise FileNotFoundError(f"Audio tidak ditemukan: {audio_path}")

            audio = AudioFileClip(str(audio_path))
            clip = clip.set_duration(audio.duration)
            clip = clip.with_audio(audio)
            
        clip.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None
        )

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Video dari gambar berhasil dibuat",
            file_path=output_path,
            extra={
                "video_id": video_id,
                "image_path": str(image_path),
                "audio_path": str(audio_path) if audio_path else None,
                "duration": duration,
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
        return error_response(tool_name, e)


def create_slideshow_video(
    image_paths,
    seconds_per_image=3,
    audio_path=None,
    target=None,
    caption="Slideshow video dari AI-Agent"
):
    """
    Membuat video slideshow dari beberapa gambar.
    image_paths dipisahkan dengan tanda |
    Contoh:
    C:/img1.png|C:/img2.png|C:/img3.png
    """
    tool_name = "create_slideshow_video"

    try:
        ensure_dirs()

        if isinstance(image_paths, str):
            image_paths = [p.strip() for p in image_paths.split("|") if p.strip()]

        if not image_paths:
            raise ValueError("Tidak ada gambar untuk slideshow.")

        clips = []

        for img in image_paths:
            img_path = Path(img)

            if not img_path.exists():
                raise FileNotFoundError(f"Gambar tidak ditemukan: {img_path}")

            clip = ImageClip(str(img_path)).set_duration(float(seconds_per_image))
            clips.append(clip)

        final_clip = concatenate_videoclips(clips, method="compose")

        if audio_path:
            audio_path = Path(audio_path)

            if not audio_path.exists():
                raise FileNotFoundError(f"Audio tidak ditemukan: {audio_path}")

            audio = AudioFileClip(str(audio_path))
            final_clip = final_clip.with_audio(audio)

        video_id = make_id("video_slideshow")
        output_path = DIRS["videos"] / f"{video_id}.mp4"

        final_clip.write_videofile(
            str(output_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None
        )

        delivery = create_delivery_record(
            file_path=output_path,
            target=target,
            caption=caption
        )

        return success_response(
            tool=tool_name,
            message="Slideshow video berhasil dibuat",
            file_path=output_path,
            extra={
                "video_id": video_id,
                "image_count": len(image_paths),
                "seconds_per_image": seconds_per_image,
                "audio_path": str(audio_path) if audio_path else None,
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
        return error_response(tool_name, e)