"""Prepare real artifacts and serve an isolated authenticated synthetic judge demo.

Provider credentials are inherited in process memory, never written here.
The separate access token is stored privately under ignored .judge/.
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
import uvicorn
from app import providers
from app.main import create_app


def private_directory(path):
    path.mkdir(exist_ok=True)
    if os.name == "nt":
        account = subprocess.check_output(["whoami"], text=True).strip()
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", account + ":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        path.chmod(0o700)


def clean_environment(include_provider=False):
    names = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"}
    environment = {key: value for key, value in os.environ.items() if key.upper() in names}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    if include_provider:
        environment.update({key: value for key, value in os.environ.items() if key.startswith("HISABGUARD_")})
        environment["HISABGUARD_JUDGE_MODE"] = "0"
        environment.pop("HISABGUARD_ACCESS_TOKEN", None)
        environment["HISABGUARD_SEED_DEMO"] = "1"
    return environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="nvidia/nemotron-3.5-super-vl:free")
    parser.add_argument("--port", type=int, default=8835)
    parser.add_argument("--case", action="append", dest="cases", help="Target a regression case without overwriting the earlier failed evaluation.")
    args = parser.parse_args()
    private = ROOT / ".judge"
    private_directory(private)
    status_file = private / "status.json"
    progress = {"created_at": datetime.now(timezone.utc).isoformat(), "model": args.model, "port": args.port,
                "stage": "starting", "synthetic_only": True, "worker_pid": os.getpid()}

    def status(stage, **fields):
        progress.update(stage=stage, **fields)
        temporary = status_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(progress, indent=2), encoding="utf-8")
        temporary.replace(status_file)

    os.environ.update(HISABGUARD_LLM_BASE_URL="https://openrouter.ai/api/v1", HISABGUARD_LLM_MODEL=args.model,
                      HISABGUARD_REASONING_MODE="off", HISABGUARD_VISION_MODEL="", HISABGUARD_STT_API_KEY="",
                      HISABGUARD_JUDGE_MODE="0")
    tunnel = None
    server = None
    try:
        if not providers.get_status()["model_configured"]:
            raise RuntimeError("No in-memory provider credential is configured")
        with (private / "preparation.log").open("a", encoding="utf-8") as log:
            status("evaluating")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            evaluation_path = f"artifacts/submission-evaluation-recheck-{stamp}.json" if args.cases else "artifacts/submission-evaluation.json"
            command = [sys.executable, "scripts/evaluate.py", "--live", "--provider", "configured",
                       "--max-calls", "18", "--pace-seconds", "3.2", "--output", evaluation_path]
            for case in args.cases or ["promise", "cash_with_driver", "duplicate_fuel"]:
                command.extend(["--case", case])
            evaluation = subprocess.run(command, cwd=ROOT, env=clean_environment(True), stdout=log, stderr=log, timeout=240)
            if evaluation.returncode:
                raise RuntimeError("Live evaluation failed; see private preparation log")
            result = json.loads((ROOT / evaluation_path).read_text(encoding="utf-8"))
            if result["summary"]["model_failures"] or not result["summary"]["accounting_unchanged"]:
                raise RuntimeError("One or more live investigations failed; no successful demo is substituted")
            status("recording", evaluation=evaluation_path, evaluation_summary=result["summary"])
            prior = set((ROOT / "artifacts").glob("recording-live-*/recording.json"))
            recording = subprocess.run([sys.executable, "scripts/record_demo.py", "--mode", "live", "--provider", "configured", "--seconds", "90"],
                                       cwd=ROOT, env=clean_environment(True), stdout=log, stderr=log, timeout=300)
            reports = set((ROOT / "artifacts").glob("recording-live-*/recording.json")) - prior
            if recording.returncode or len(reports) != 1:
                raise RuntimeError("Real live recording failed; no prerecorded success substituted")
            report_path = reports.pop()
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not report["successful"] or report["mode"] != "live":
                raise RuntimeError("Recording did not verify a live model workflow")
            video = ROOT / report["video"]
            published_video = video.with_name("HisabGuard-live-demo.mp4")
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                conversion = subprocess.run([ffmpeg, "-y", "-i", str(video), "-c:v", "libx264", "-preset", "veryfast",
                                              "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(published_video)],
                                             env=clean_environment(), stdout=log, stderr=log, timeout=120)
                if conversion.returncode:
                    published_video = video
            else:
                published_video = video
            status("starting_judge", video=str(published_video.relative_to(ROOT)), recording_report=str(report_path.relative_to(ROOT)),
                   recording_seconds=report["elapsed_seconds"])

        token = secrets.token_urlsafe(24)
        (private / "access.json").write_text(json.dumps({"access_token": token, "note": "Private judge access only; no provider credentials."}), encoding="utf-8")
        os.environ.update(HISABGUARD_JUDGE_MODE="1", HISABGUARD_ACCESS_TOKEN=token, HISABGUARD_JUDGE_MAX_RUNS="20",
                          HISABGUARD_DATA_DIR=str(private / "runtime"), HISABGUARD_SEED_DEMO="1")
        server = uvicorn.Server(uvicorn.Config(create_app(private / "runtime"), host="127.0.0.1", port=args.port,
                                               log_level="error", access_log=False, proxy_headers=True, forwarded_allow_ips="127.0.0.1"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(.1)
        if not server.started:
            raise RuntimeError("Judge server did not start")
        cloudflared = shutil.which("cloudflared")
        if not cloudflared:
            raise RuntimeError("Cloudflare tunnel CLI is unavailable")
        tunnel_log = private / "tunnel.log"
        with tunnel_log.open("w", encoding="utf-8") as log:
            tunnel = subprocess.Popen([cloudflared, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", f"http://127.0.0.1:{args.port}"],
                                      env=clean_environment(), stdout=log, stderr=log)
        url = None
        for _ in range(90):
            if tunnel.poll() is not None:
                raise RuntimeError("Tunnel process exited; inspect private tunnel log")
            found = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", tunnel_log.read_text(encoding="utf-8", errors="replace"))
            if found:
                url = found.group()
                break
            time.sleep(1)
        if not url:
            raise RuntimeError("No HTTPS judge URL was issued")
        os.environ["HISABGUARD_DEV_ORIGIN"] = url
        status("verifying_external", public_url=url, tunnel_pid=tunnel.pid, local_url=f"http://127.0.0.1:{args.port}/")
        for _ in range(30):
            try:
                with httpx.Client(timeout=15, follow_redirects=True) as client:
                    public = client.get(url + "/")
                    denied = client.get(url + "/api/trips")
                    authorized = client.get(url + "/api/trips", headers={"Authorization": "Bearer " + token})
                    if public.status_code == 200 and denied.status_code == 401 and authorized.status_code == 200:
                        status("ready", authenticated_external=True, initial_trips=authorized.json()["overview"]["trips"])
                        break
            except httpx.RequestError:
                pass
            time.sleep(2)
        else:
            raise RuntimeError("External authentication checks did not pass")
        while tunnel.poll() is None and not server.should_exit:
            time.sleep(2)
        raise RuntimeError("Judge service or tunnel stopped")
    except Exception as exc:
        status("blocked", error=str(exc)[:300])
        return 1
    finally:
        if server:
            server.should_exit = True
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
