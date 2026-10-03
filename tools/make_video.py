#!/usr/bin/env python3
"""Builds the demo video for Deadline Radar.

    python3 tools/make_video.py                 # full build (~2 minutes of video)
    python3 tools/make_video.py --fast           # no narration, 2s per scene, for testing
    python3 tools/make_video.py --scenes 4       # only the first N scenes

What it does
    1. starts the real app on port 8781 in --offline mode (no network, no API key);
    2. walks the guided-tour URLs (/?demo=N, /ics/<id>) with headless Chrome and
       screenshots each one - these are real frames of the running product, not slides;
    3. writes English narration with edge-tts (en-US-AvaNeural, rate +20%);
    4. assembles docs/media/deadline_radar_demo.mp4 plus docs/media/thumbnail.jpg
       with ffmpeg, and prints an ffprobe report of the result.

Screenshots are taken with a tall window so that the whole page is inside the
initial viewport (headless Chrome does not rasterise off-screen content after a
scroll), then the region around the focused card is cropped to 1280x800 with
ffmpeg. The crop offset comes from the page itself: the app writes
`data-metrics` on <body> and this script reads it back out of --dump-dom.
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from radar import demo                                              # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
PORT = 8781
BASE = "http://127.0.0.1:%d" % PORT
WIDTH, HEIGHT, FPS = 1280, 800, 30
TALL = 6200                     # window height for the screenshot pass
MEDIA = os.path.join(ROOT, "docs", "media")
WORK = os.path.join(MEDIA, "_work")

VOICE = "en-US-AvaNeural"
RATE = "+20%"

# One line of narration per tour step, timed to what is on screen.
NARRATION = {
    0: "This is Deadline Radar. You paste any announcement, competition rules or call for "
       "entries as plain text, and it turns that mess into a brief you can act on.",
    1: "The app assumes nothing about the page. This one is a real hackathon page: dates, "
       "prizes, deliverables and judging, all written as prose, with no structure to rely on.",
    2: "One press of Analyse produces the brief. Every value below was found on the page, and "
       "every field carries a verdict: accepted, corrected, rejected, or page does not state.",
    3: "Dates are the risky part, so they are never taken from the model. Plain Python "
       "re-parses each one, renders it in ISO 8601 with its time zone, and shows the sentence "
       "and character offsets it came from.",
    4: "Prize amounts are read from the quoted sentence, never from the model's arithmetic, and "
       "each required deliverable is listed with the evidence that put it there.",
    5: "This is the audit trail. On the left, exactly what the reader proposed. On the right, "
       "what survived validation, and every field that did not.",
    6: "Now the validator is fed a proposal with an invented fifty thousand dollar prize and a "
       "deadline that is wrong. The prize is rejected, because that sentence is not on the page, "
       "and the deadline is corrected to the date the page actually states.",
    7: "Awkward pages are handled deliberately. This deadline is written with a Chinese month and "
       "day, a US time zone, and no year at all. The year comes from the page, and the field is "
       "labelled year inferred.",
    8: "A thin page is fine too. No prize amount, no eligibility, no deliverables: the brief says "
       "page does not state rather than inventing anything to fill the gap.",
    9: "The validated dates become a calendar file. Only accepted dates are written, and the "
       "deadline event carries three reminders: one week, one day, and two hours before.",
    10: "Every analysis is stored in a local sqlite3 database, so a brief can be reopened weeks "
        "later with its evidence still attached.",
    11: "The source text is kept with each evidence span highlighted in place, so any claim in "
        "the brief can be checked against the page in one look.",
    12: "Deadline Radar: no dependencies, no accounts, no paid API. Python's standard library, "
        "started with python3 app.py.",
}


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kwargs).stdout


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("%s is not a PNG" % path)
    width, height = struct.unpack(">II", head[16:24])
    return width, height


def start_app(work_dir):
    db = os.path.join(work_dir, "demo.db")
    if os.path.exists(db):
        os.remove(db)
    log = open(os.path.join(work_dir, "app.log"), "w")
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "app.py"), "--offline",
                             "--quiet", "--db", db, "--port", str(PORT)],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            with urllib.request.urlopen(BASE + "/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise RuntimeError("the app did not start on %s" % BASE)


def chrome_dump(url):
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                          "--hide-scrollbars", "--virtual-time-budget=4000",
                          "--window-size=%d,%d" % (WIDTH, TALL), "--dump-dom", url],
                         capture_output=True, text=True).stdout
    match = re.search(r'data-metrics="([^"]*)"', out)
    if not match:
        return {}
    return json.loads(match.group(1).replace("&quot;", '"'))


def chrome_shot(url, path):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                    "--hide-scrollbars", "--virtual-time-budget=4000",
                    "--window-size=%d,%d" % (WIDTH, TALL),
                    "--screenshot=" + path, url], capture_output=True, text=True)
    if not os.path.exists(path):
        raise RuntimeError("Chrome did not write %s" % path)
    return path


def capture(url, out_png):
    """Screenshot the tour step and crop the focused card to 1280x800."""
    metrics = chrome_dump(url)
    raw = out_png.replace(".png", "_full.png")
    chrome_shot(url, raw)
    _, full_h = png_size(raw)
    top = int(metrics.get("pageTop", 0)) if metrics else 0
    top = max(0, min(top - 24, max(0, full_h - HEIGHT)))
    run([FFMPEG, "-y", "-loglevel", "error", "-i", raw, "-vf",
         "crop=%d:%d:0:%d" % (WIDTH, HEIGHT, top), "-frames:v", "1", out_png])
    os.remove(raw)
    return metrics


def narration_files(scenes, work):
    """Write one mp3 per scene with edge-tts. Returns {n: path} or {} if unavailable."""
    try:
        import asyncio
        import edge_tts
    except ImportError:
        print("  edge-tts is not installed: building the video without narration")
        return {}
    out = {}
    for scene in scenes:
        path = os.path.join(work, "n%02d.mp3" % scene["step"])
        text = NARRATION.get(scene["step"])
        if not text:
            continue
        asyncio.get_event_loop().run_until_complete(
            edge_tts.Communicate(text, VOICE, rate=RATE).save(path))
        out[scene["step"]] = path
        print("  narration %02d: %5.1fs" % (scene["step"], media_duration(path)))
    return out


def media_duration(path):
    out = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path])
    return float(out.strip())


def build_audio(scenes, work, total):
    """Place each narration clip at its scene start with adelay, then mix."""
    starts = {}
    cursor = 0.0
    for scene in scenes:
        starts[scene["step"]] = cursor
        cursor += scene["seconds"]
    clips = [s for s in scenes if s.get("narr")]
    if not clips:
        return None
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for scene in clips:
        cmd += ["-i", scene["narr"]]
    parts = []
    for i, scene in enumerate(clips):
        ms = int(starts[scene["step"]] * 1000)
        parts.append("[%d:a]adelay=%d|%d[a%d]" % (i, ms, ms, i))
    parts.append("".join("[a%d]" % i for i in range(len(clips))) +
                 "amix=inputs=%d:normalize=0:dropout_transition=0[out]" % len(clips))
    voice = os.path.join(work, "voice.m4a")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]",
            "-c:a", "aac", "-b:a", "160k", "-t", "%.2f" % total, voice]
    run(cmd)
    return voice


def build_video(frames, scenes, work, out_mp4, thumbnail_png):
    segments = []
    for frame, scene in zip(frames, scenes):
        seg = os.path.join(work, "seg%02d.mp4" % scene["step"])
        run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(FPS),
             "-t", "%.3f" % scene["seconds"], "-i", frame,
             "-vf", "scale=%d:%d,format=yuv420p" % (WIDTH, HEIGHT),
             "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", seg])
        segments.append(seg)
    listing = os.path.join(work, "frames.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for seg in segments:
            fh.write("file '%s'\n" % seg)
    silent = os.path.join(work, "silent.mp4")
    run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
         "-c", "copy", silent])
    voice = os.path.join(work, "voice.m4a")
    if os.path.exists(voice):
        run([FFMPEG, "-y", "-loglevel", "error", "-i", silent, "-i", voice,
             "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-shortest", "-movflags", "+faststart", out_mp4])
    else:
        run([FFMPEG, "-y", "-loglevel", "error", "-i", silent, "-c:v", "copy",
             "-movflags", "+faststart", out_mp4])
    run([FFMPEG, "-y", "-loglevel", "error", "-i", thumbnail_png, "-vf", "scale=1280:-1",
         "-q:v", "3", os.path.join(MEDIA, "thumbnail.jpg")])


def report(out_mp4):
    if not os.path.exists(FFPROBE):
        return {}
    out = run([FFPROBE, "-v", "error", "-show_entries",
               "format=duration,size:stream=codec_name,width,height,r_frame_rate",
               "-of", "json", out_mp4])
    return json.loads(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenes", type=int, default=0, help="only the first N scenes")
    parser.add_argument("--fast", action="store_true",
                        help="2 seconds per scene and no narration (quick smoke test)")
    parser.add_argument("--keep", action="store_true", help="keep the intermediate files")
    args = parser.parse_args(argv)

    for path, name in ((CHROME, "Google Chrome"), (FFMPEG, "ffmpeg"), (FFPROBE, "ffprobe")):
        if not os.path.exists(path):
            sys.stderr.write("%s was not found at %s\n" % (name, path))
            return 2

    os.makedirs(MEDIA, exist_ok=True)
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    plan = {item["n"]: item for item in demo.plan()}
    steps = sorted(plan)
    if args.scenes:
        steps = steps[:args.scenes]

    app = start_app(WORK)
    print("app started on %s with the offline reader" % BASE)
    try:
        frames, scenes, thumbnail = [], [], None
        for n in steps:
            url = BASE + plan[n]["url"]
            frame = os.path.join(WORK, "frame%02d.png" % n)
            metrics = capture(url, frame)
            print("  frame %02d %-42s visible=%s page=%s" % (
                n, plan[n]["title"][:42], metrics.get("visible"), metrics.get("page")))
            frames.append(frame)
            scenes.append({"step": n, "seconds": 6.0, "narr": None})
            if thumbnail is None and n == 2:
                thumbnail = frame
        if thumbnail is None:
            thumbnail = frames[0]

        if args.fast:
            for scene in scenes:
                scene["seconds"] = 2.0
        else:
            print("writing narration with edge-tts (%s, %s)" % (VOICE, RATE))
            vocals = narration_files(scenes, WORK)
            for scene in scenes:
                clip = vocals.get(scene["step"])
                if clip:
                    scene["narr"] = clip
                    scene["seconds"] = round(media_duration(clip) + 0.9, 2)
                else:
                    scene["seconds"] = 5.0
        total = sum(scene["seconds"] for scene in scenes)
        print("timeline: %d scenes, %.1fs" % (len(scenes), total))

        out_mp4 = os.path.join(MEDIA, "deadline_radar_demo.mp4")
        if not args.fast:
            build_audio(scenes, WORK, total)
        build_video(frames, scenes, WORK, out_mp4, thumbnail)
    finally:
        app.terminate()
        try:
            app.wait(timeout=5)
        except Exception:
            app.kill()

    info = report(out_mp4)
    size_mb = os.path.getsize(out_mp4) / (1024.0 * 1024.0)
    print("\nwrote %s" % out_mp4)
    print("  duration : %s s" % info.get("format", {}).get("duration"))
    print("  size     : %.2f MB" % size_mb)
    for stream in info.get("streams", []):
        print("  stream   : %s %sx%s %s" % (stream.get("codec_name"), stream.get("width"),
                                            stream.get("height"), stream.get("r_frame_rate")))
    print("wrote %s" % os.path.join(MEDIA, "thumbnail.jpg"))
    if size_mb >= 25:
        print("WARNING: the file is 25MB or larger")
    if not args.keep:
        shutil.rmtree(WORK, ignore_errors=True)
    else:
        print("intermediate files kept in %s" % WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main())
