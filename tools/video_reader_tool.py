import json
import math
import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import ensure_dirs, error_response, success_response


VIDEO_READER_VERSION = "2026.06.13-audio-skip-v2"

SUPPORTED_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".m4v",
    ".wmv",
    ".flv",
}

DEFAULT_OUTPUT_ROOT = Path(r"C:\AI-Agent\outputs\video_reader")

DEFAULT_FFMPEG_PATHS = [
    Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
    Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
]

DEFAULT_FFPROBE_PATHS = [
    Path(r"C:\ffmpeg\bin\ffprobe.exe"),
    Path(r"C:\Program Files\ffmpeg\bin\ffprobe.exe"),
    Path(r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe"),
]


def _validate_video_path(video_path: str) -> Path:
    path = Path(video_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File video tidak ditemukan: {path}")

    if not path.is_file():
        raise ValueError(f"Path bukan file: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Format video tidak didukung: {extension}. "
            f"Gunakan: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    return path


def _find_executable(
    env_name: str,
    executable_names: List[str],
    default_paths: List[Path],
) -> Path:
    env_path = os.environ.get(env_name)

    if env_path:
        candidate = Path(env_path).expanduser()

        if candidate.exists():
            return candidate.resolve()

    for executable_name in executable_names:
        detected = shutil.which(executable_name)

        if detected:
            return Path(detected).resolve()

    for candidate in default_paths:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        f"{executable_names[0]} tidak ditemukan. "
        f"Tambahkan FFmpeg ke PATH atau set environment variable {env_name}."
    )


def _find_ffmpeg() -> Path:
    return _find_executable(
        env_name="FFMPEG_CMD",
        executable_names=["ffmpeg", "ffmpeg.exe"],
        default_paths=DEFAULT_FFMPEG_PATHS,
    )


def _find_ffprobe() -> Path:
    return _find_executable(
        env_name="FFPROBE_CMD",
        executable_names=["ffprobe", "ffprobe.exe"],
        default_paths=DEFAULT_FFPROBE_PATHS,
    )


def _run_process(
    command: List[str],
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    if process.returncode != 0:
        raise RuntimeError(
            f"Perintah gagal dengan exit code {process.returncode}. "
            f"Output: {process.stderr or process.stdout}"
        )

    return process


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_fraction(value: Optional[str]) -> Optional[float]:
    if not value:
        return None

    if "/" not in value:
        return _to_float(value)

    numerator, denominator = value.split("/", 1)

    try:
        denominator_value = float(denominator)

        if denominator_value == 0:
            return None

        return float(numerator) / denominator_value
    except (TypeError, ValueError):
        return None


def _format_duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None

    return str(timedelta(seconds=int(seconds)))


def probe_video(video_path: str) -> Dict[str, Any]:
    tool_name = "probe_video"

    try:
        ensure_dirs()
        path = _validate_video_path(video_path)
        ffprobe = _find_ffprobe()

        process = _run_process(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            timeout=120,
        )

        raw = json.loads(process.stdout)

        format_data = raw.get("format", {})
        streams = raw.get("streams", [])

        video_streams = [
            stream
            for stream in streams
            if stream.get("codec_type") == "video"
        ]

        audio_streams = [
            stream
            for stream in streams
            if stream.get("codec_type") == "audio"
        ]

        primary_video = video_streams[0] if video_streams else {}
        primary_audio = audio_streams[0] if audio_streams else {}

        duration_seconds = (
            _to_float(format_data.get("duration"))
            or _to_float(primary_video.get("duration"))
            or _to_float(primary_audio.get("duration"))
        )

        fps = (
            _parse_fraction(primary_video.get("avg_frame_rate"))
            or _parse_fraction(primary_video.get("r_frame_rate"))
        )

        metadata = {
            "file_path": str(path),
            "file_type": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "duration_seconds": duration_seconds,
            "duration_human": _format_duration(duration_seconds),
            "format_name": format_data.get("format_name"),
            "format_long_name": format_data.get("format_long_name"),
            "bit_rate": _to_int(format_data.get("bit_rate")),
            "video_stream_count": len(video_streams),
            "audio_stream_count": len(audio_streams),
            "width": _to_int(primary_video.get("width")),
            "height": _to_int(primary_video.get("height")),
            "fps": fps,
            "video_codec": primary_video.get("codec_name"),
            "video_codec_long_name": primary_video.get("codec_long_name"),
            "pixel_format": primary_video.get("pix_fmt"),
            "audio_codec": primary_audio.get("codec_name"),
            "audio_sample_rate": _to_int(primary_audio.get("sample_rate")),
            "audio_channels": _to_int(primary_audio.get("channels")),
            "tags": format_data.get("tags", {}),
            "streams": streams,
            "ffprobe_path": str(ffprobe),
        }

        return success_response(
            tool=tool_name,
            message="Metadata video berhasil dibaca",
            extra=metadata,
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def _prepare_output_dir(
    video_path: Path,
    output_dir: Optional[str],
) -> Path:
    if output_dir:
        destination = Path(output_dir).expanduser().resolve()
    else:
        destination = (
            DEFAULT_OUTPUT_ROOT
            / video_path.stem
        ).resolve()

    destination.mkdir(parents=True, exist_ok=True)
    return destination


def extract_audio(
    video_path: str,
    output_dir: Optional[str] = None,
    filename: str = "audio_16k_mono.wav",
    overwrite: bool = True,
) -> Dict[str, Any]:
    tool_name = "extract_video_audio"

    try:
        ensure_dirs()
        path = _validate_video_path(video_path)

        probe_result = probe_video(str(path))

        if not probe_result.get("success"):
            raise RuntimeError(
                probe_result.get("error", "Gagal membaca metadata video.")
            )

        audio_stream_count = int(
            probe_result.get("audio_stream_count", 0) or 0
        )

        if audio_stream_count < 1:
            return success_response(
                tool=tool_name,
                message="Video tidak memiliki audio; ekstraksi dilewati",
                extra={
                    "video_path": str(path),
                    "audio_available": False,
                    "audio_stream_count": 0,
                    "audio_path": None,
                    "skipped": True,
                    "skip_reason": "Video tidak memiliki audio stream.",
                },
            )

        ffmpeg = _find_ffmpeg()
        destination = _prepare_output_dir(path, output_dir)
        output_path = destination / filename

        if output_path.suffix.lower() != ".wav":
            output_path = output_path.with_suffix(".wav")

        overwrite_flag = "-y" if overwrite else "-n"

        _run_process(
            [
                str(ffmpeg),
                overwrite_flag,
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                str(output_path),
            ],
            timeout=1800,
        )

        return success_response(
            tool=tool_name,
            message="Audio video berhasil diekstrak",
            file_path=output_path,
            extra={
                "video_path": str(path),
                "output_dir": str(destination),
                "audio_available": True,
                "audio_stream_count": audio_stream_count,
                "audio_path": str(output_path),
                "sample_rate": 16000,
                "channels": 1,
                "ffmpeg_path": str(ffmpeg),
                "skipped": False,
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def _calculate_frame_timestamps(
    duration_seconds: float,
    frame_count: int,
) -> List[float]:
    if frame_count <= 0:
        raise ValueError("frame_count harus lebih besar dari 0.")

    if duration_seconds <= 0:
        raise ValueError("Durasi video tidak valid.")

    if frame_count == 1:
        return [duration_seconds / 2.0]

    margin = min(1.0, duration_seconds * 0.02)
    start = margin
    end = max(start, duration_seconds - margin)

    step = (end - start) / (frame_count - 1)

    return [
        max(0.0, min(duration_seconds, start + step * index))
        for index in range(frame_count)
    ]


def extract_frames(
    video_path: str,
    output_dir: Optional[str] = None,
    frame_count: int = 8,
    width: int = 1280,
    image_quality: int = 2,
    overwrite: bool = True,
) -> Dict[str, Any]:
    tool_name = "extract_video_frames"

    try:
        ensure_dirs()
        path = _validate_video_path(video_path)
        ffmpeg = _find_ffmpeg()

        probe_result = probe_video(str(path))

        if not probe_result.get("success"):
            raise RuntimeError(
                probe_result.get(
                    "error",
                    "Gagal membaca durasi video.",
                )
            )

        duration_seconds = _to_float(
            probe_result.get("duration_seconds")
        )

        if duration_seconds is None or duration_seconds <= 0:
            raise ValueError("Durasi video tidak dapat dibaca.")

        destination = _prepare_output_dir(path, output_dir)
        frames_dir = destination / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        timestamps = _calculate_frame_timestamps(
            duration_seconds=duration_seconds,
            frame_count=frame_count,
        )

        extracted_frames: List[Dict[str, Any]] = []
        overwrite_flag = "-y" if overwrite else "-n"

        for index, timestamp in enumerate(timestamps, start=1):
            frame_path = frames_dir / f"frame_{index:03d}.jpg"

            filter_expression = (
                f"scale='min({width},iw)':-2"
                if width > 0
                else "scale=iw:ih"
            )

            _run_process(
                [
                    str(ffmpeg),
                    overwrite_flag,
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-vf",
                    filter_expression,
                    "-q:v",
                    str(image_quality),
                    str(frame_path),
                ],
                timeout=300,
            )

            extracted_frames.append({
                "frame_index": index,
                "timestamp_seconds": round(timestamp, 3),
                "timestamp_human": _format_duration(timestamp),
                "file_path": str(frame_path),
            })

        manifest_path = destination / "frames_manifest.json"

        manifest_path.write_text(
            json.dumps(
                {
                    "video_path": str(path),
                    "duration_seconds": duration_seconds,
                    "frame_count": len(extracted_frames),
                    "frames": extracted_frames,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return success_response(
            tool=tool_name,
            message="Frame video berhasil diekstrak",
            file_path=frames_dir,
            extra={
                "video_path": str(path),
                "output_dir": str(destination),
                "frames_dir": str(frames_dir),
                "manifest_path": str(manifest_path),
                "frame_count": len(extracted_frames),
                "frames": extracted_frames,
                "ffmpeg_path": str(ffmpeg),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def transcribe_audio_faster_whisper(
    audio_path: str,
    output_dir: Optional[str] = None,
    model_size: str = "small",
    language: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> Dict[str, Any]:
    tool_name = "transcribe_video_audio"

    try:
        ensure_dirs()
        path = Path(audio_path).expanduser().resolve()

        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File audio tidak ditemukan: {path}")

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Dependency faster-whisper belum terpasang. Jalankan: "
                "py -m pip install faster-whisper"
            ) from exc

        destination = (
            Path(output_dir).expanduser().resolve()
            if output_dir
            else path.parent.resolve()
        )
        destination.mkdir(parents=True, exist_ok=True)

        model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )

        segments_generator, info = model.transcribe(
            str(path),
            language=language,
            vad_filter=True,
        )

        segments: List[Dict[str, Any]] = []
        text_parts: List[str] = []

        for segment in segments_generator:
            text = segment.text.strip()

            segments.append({
                "start": round(segment.start, 3),
                "end": round(segment.end, 3),
                "text": text,
            })

            if text:
                text_parts.append(text)

        full_text = " ".join(text_parts).strip()

        transcript_txt = destination / "transcript.txt"
        transcript_json = destination / "transcript.json"

        transcript_txt.write_text(
            full_text,
            encoding="utf-8",
        )

        transcript_json.write_text(
            json.dumps(
                {
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "duration": info.duration,
                    "segments": segments,
                    "text": full_text,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return success_response(
            tool=tool_name,
            message="Audio video berhasil ditranskripsikan",
            file_path=transcript_txt,
            extra={
                "audio_path": str(path),
                "output_dir": str(destination),
                "model_size": model_size,
                "device": device,
                "compute_type": compute_type,
                "detected_language": info.language,
                "language_probability": info.language_probability,
                "duration_seconds": info.duration,
                "segment_count": len(segments),
                "text": full_text,
                "segments": segments,
                "transcript_txt": str(transcript_txt),
                "transcript_json": str(transcript_json),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)


def read_video(
    video_path: str,
    output_dir: Optional[str] = None,
    frame_count: int = 8,
    extract_audio_file: bool = True,
    transcribe: bool = False,
    whisper_model: str = "small",
    language: Optional[str] = None,
    whisper_device: str = "cpu",
    whisper_compute_type: str = "int8",
) -> Dict[str, Any]:
    tool_name = "read_video"

    try:
        ensure_dirs()
        path = _validate_video_path(video_path)
        destination = _prepare_output_dir(path, output_dir)

        metadata_result = probe_video(str(path))

        if not metadata_result.get("success"):
            raise RuntimeError(
                metadata_result.get("error", "Gagal membaca metadata.")
            )

        frames_result = extract_frames(
            video_path=str(path),
            output_dir=str(destination),
            frame_count=frame_count,
        )

        if not frames_result.get("success"):
            raise RuntimeError(
                frames_result.get("error", "Gagal mengekstrak frame.")
            )

        audio_result = None
        transcript_result = None

        if extract_audio_file or transcribe:
            audio_result = extract_audio(
                video_path=str(path),
                output_dir=str(destination),
            )

            if not audio_result.get("success"):
                raise RuntimeError(
                    audio_result.get("error", "Gagal mengekstrak audio.")
                )

        if transcribe:
            audio_path = (
                audio_result.get("audio_path")
                if audio_result
                else None
            )

            if not audio_path:
                transcript_result = success_response(
                    tool="transcribe_video_audio",
                    message="Transkripsi dilewati karena video tidak memiliki audio",
                    extra={
                        "skipped": True,
                        "skip_reason": "Video tidak memiliki audio stream.",
                        "audio_path": None,
                        "text": "",
                        "segments": [],
                    },
                )
            else:
                transcript_result = transcribe_audio_faster_whisper(
                    audio_path=audio_path,
                    output_dir=str(destination),
                    model_size=whisper_model,
                    language=language,
                    device=whisper_device,
                    compute_type=whisper_compute_type,
                )

                if not transcript_result.get("success"):
                    raise RuntimeError(
                        transcript_result.get(
                            "error",
                            "Gagal mentranskripsikan audio.",
                        )
                    )

        summary_path = destination / "video_reader_result.json"

        result_payload = {
            "video_path": str(path),
            "output_dir": str(destination),
            "metadata": metadata_result,
            "frames": frames_result,
            "audio": audio_result,
            "transcript": transcript_result,
        }

        summary_path.write_text(
            json.dumps(
                result_payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return success_response(
            tool=tool_name,
            message="Video berhasil diproses",
            file_path=destination,
            extra={
                **result_payload,
                "summary_path": str(summary_path),
            },
        )

    except Exception as exc:
        return error_response(tool_name, exc)
