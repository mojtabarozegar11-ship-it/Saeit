#!/usr/bin/env python3
"""Assemble *already AI-generated* PICM scene clips into one private MP4.

This is NOT an image animation or video-generation model. It refuses to create
an output until every required real scene clip is present and probeable.
Run on an isolated GPU worker (not on the factory VPS) with ffmpeg/ffprobe.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SHOT_NAME = re.compile(r"^shot_[0-9]{2}\.mp4$")
LEGAL_DURATIONS = {5, 10, 30, 60}
SIZE = {"16:9": (1280, 720), "9:16": (720, 1280)}


class AssemblyError(RuntimeError):
    pass


def load_plan(metadata_path):
    path = Path(metadata_path)
    if not path.is_file() or path.is_symlink():
        raise AssemblyError("private_story_metadata_missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    plan = data.get("storyboard", data)
    duration = plan.get("duration")
    scenes = plan.get("scenes")
    if type(duration) is not int or duration not in LEGAL_DURATIONS:
        raise AssemblyError("invalid_story_duration")
    if plan.get("ratio") not in SIZE or not isinstance(scenes, list):
        raise AssemblyError("invalid_story_plan")
    if not scenes or len(scenes) > 12:
        raise AssemblyError("invalid_scene_count")
    last_end = 0
    for idx, scene in enumerate(scenes, 1):
        sec = scene.get("duration")
        if (scene.get("shot") != idx or type(sec) is not int or sec < 1 or
                scene.get("start") != last_end or scene.get("end") != last_end + sec):
            raise AssemblyError("inconsistent_scene_timing")
        last_end += sec
    if last_end != duration:
        raise AssemblyError("incorrect_total_runtime")
    return plan


def _run(args, timeout=90):
    try:
        return subprocess.run(args, capture_output=True, text=True,
                              check=True, timeout=timeout).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as err:
        raise AssemblyError("media_tool_failed: " + str(err)[:300]) from err


def _verify_tools():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise AssemblyError("ffmpeg_and_ffprobe_required_on_gpu_worker")


def video_duration(path):
    """Trust ffprobe only: a file extension or file size is not proof of video."""
    detail = json.loads(_run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=codec_type,width,height",
        "-of", "json", str(path)]))
    streams = detail.get("streams", [])
    if not streams or streams[0].get("codec_type") != "video":
        raise AssemblyError("no_real_video_stream")
    try:
        duration = float(detail["format"]["duration"])
    except (ValueError, KeyError, TypeError) as err:
        raise AssemblyError("video_duration_missing") from err
    if not (0.1 < duration < 600):
        raise AssemblyError("unreasonable_video_duration")
    return duration


def assemble(plan, clip_dir, destination):
    """Return output path only if every AI scene exists and MP4 is validated.

    No fake image-to-video output. Never fetch a network URL or accept a remote
    output path; sensitive source files stay on the private worker filesystem.
    """
    _verify_tools()
    clips = Path(clip_dir).resolve(strict=True)
    if not clips.is_dir():
        raise AssemblyError("missing_private_clip_directory")
    final = Path(destination)
    if final.exists() or final.is_symlink() or final.suffix.lower() != ".mp4":
        raise AssemblyError("destination_must_be_new_mp4")
    parent = final.parent.resolve(strict=True)
    if not parent.is_dir():
        raise AssemblyError("missing_output_directory")
    width, height = SIZE[plan["ratio"]]
    scenes = plan["scenes"]
    sources = []
    for index, scene in enumerate(scenes, 1):
        name = "shot_%02d.mp4" % index
        if not SHOT_NAME.fullmatch(name):
            raise AssemblyError("invalid_video_filename")
        clip = clips / name
        if not clip.is_file() or clip.is_symlink():
            raise AssemblyError("missing_real_ai_clip_" + name)
        actual = video_duration(clip)
        if actual + 0.12 < scene["duration"]:
            raise AssemblyError("ai_clip_too_short_" + name)
        sources.append(clip)
    with tempfile.TemporaryDirectory(prefix=".picm-story-", dir=parent) as work:
        scratch = Path(work)
        os.chmod(scratch, 0o700)
        normalized = []
        for index, (clip, scene) in enumerate(zip(sources, scenes), 1):
            dst = scratch / ("scene_%02d.mp4" % index)
            filter_str = ("scale=%d:%d:force_original_aspect_ratio=decrease,"
                "pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black,fps=24,"
                "trim=duration=%d,setpts=PTS-STARTPTS" %
                (width, height, width, height, scene["duration"]))
            _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(clip), "-an", "-vf", filter_str,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "24", "-t",
                str(scene["duration"]), "-y", str(dst)], timeout=300)
            normalized.append(dst)
        # Concat demuxer paths are created in our 0700 private temp dir.
        playlist = scratch / "clips.txt"
        playlist.write_text("".join("file '%s'\n" % v.name for v in normalized), encoding="utf-8")
        staged = scratch / "story.mp4"
        _run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "1", "-i", str(playlist),
            "-c", "copy", "-movflags", "+faststart", "-y", str(staged)],
            timeout=180)
        if abs(video_duration(staged) - plan["duration"]) > 0.5:
            raise AssemblyError("rendered_story_runtime_mismatch")
        os.chmod(staged, 0o600)
        os.replace(staged, final)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", required=True, help="Private staged *.stage.json")
    parser.add_argument("--clips", required=True, help="Private real AI clips shot_01.mp4 ...")
    parser.add_argument("--output", required=True, help="New private final *.mp4")
    args = parser.parse_args()
    result = assemble(load_plan(args.metadata), args.clips, args.output)
    print(json.dumps({"state": "assembled_real_clips", "path": str(result)}))


if __name__ == "__main__":
    main()
