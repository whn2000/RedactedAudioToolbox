import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Redirect stdout/stderr to logging so we can capture print statements in app.log
from core.logger import get_logger
logger = get_logger("WebUI")

class WebStdoutRedirector:
    def __init__(self, original_stream, log_level=logging.INFO):
        self.original_stream = original_stream
        self.log_level = log_level
        self.buffer = []

    def write(self, message):
        self.original_stream.write(message)
        # Process lines
        if "\n" in message:
            parts = message.split("\n")
            self.buffer.append(parts[0])
            full_line = "".join(self.buffer).strip()
            if full_line:
                if "/api/status" not in full_line and "/api/logs" not in full_line:
                    logging.getLogger("SystemOut").log(self.log_level, full_line)
            self.buffer = parts[1:]
        else:
            self.buffer.append(message)

    def flush(self):
        self.original_stream.flush()

    def isatty(self):
        return hasattr(self.original_stream, 'isatty') and self.original_stream.isatty()

# Redirect standard print output to logger
sys.stdout = WebStdoutRedirector(sys.stdout, logging.INFO)
sys.stderr = WebStdoutRedirector(sys.stderr, logging.ERROR)

import core.globals
from core.context import AppContext
from core.paths import app_paths
from core.tasks import Task, TaskState
from core.site_config import SITE_CONFIGS
from pipeline_manager import PipelineManager
from core.seeding.seeding_manager import SeedingManager
from cross_seed.engine import CrossSeedEngine

# Start up context
core.globals.app_context = AppContext()
core.globals.app_context.startup()

app = FastAPI(title="Redacted Audio Toolbox WebUI")

# Global variables to hold active long-running engine/pipeline objects
global_pipeline: Optional[PipelineManager] = None
global_cross_seed_engine: Optional[CrossSeedEngine] = None
global_pipeline_lock = threading.Lock()

# Define Custom Tasks for TaskManager
class SearchTask(Task):
    def __init__(self, task_id: str, options: SimpleNamespace):
        super().__init__(id=task_id, name=f"Search ({options.site_config['source']})", type="search")
        self.options = options
        self.pipeline = None

    def run(self, context):
        global global_pipeline
        self.update_progress(0.0)
        self.update_state(TaskState.RUNNING)
        logger.info(f"Starting search task on {self.options.site_config['source']}")

        # Start search pipeline if requested
        if self.options.enable_pipeline:
            try:
                import time as _time
                # Set up callbacks logging directly to python logger so it ends up in app.log
                self.pipeline = PipelineManager(
                    self.options.qb_host, self.options.qb_port, self.options.qb_user, self.options.qb_pass,
                    None, self.options,
                    log_main=lambda s: logger.info(f"[Pipeline] {s}"),
                    log_process=lambda s: logger.info(f"[Pipeline-Transcode] {s}"),
                    log_check=lambda s: logger.info(f"[Pipeline-Audit] {s}")
                )
                self.pipeline.start()
                with global_pipeline_lock:
                    global_pipeline = self.pipeline
                self.options.pipeline = self.pipeline
            except Exception as e:
                logger.error(f"Failed to start pipeline: {e}")

        # Execute search
        from core.searcher import perform_search
        try:
            perform_search(self.options, abort_flag=lambda: self._cancel_flag)
            self.update_progress(100.0)
            self.update_state(TaskState.COMPLETED)
        except Exception as e:
            logger.error(f"Search task encountered error: {e}", exc_info=True)
            self.update_state(TaskState.FAILED, error=str(e))
        finally:
            if self.pipeline:
                logger.info("Search finished. Pipeline will continue running in background.")

class DownsampleTask(Task):
    def __init__(self, task_id: str, base_dir: str, tracker_url: str, source_flag: str, flac_out: bool, mp3_320_out: bool, mp3_v0_out: bool):
        super().__init__(id=task_id, name=f"Transcode: {Path(base_dir).name}", type="downsample")
        self.base_dir = base_dir
        self.tracker_url = tracker_url
        self.source_flag = source_flag
        self.flac_out = flac_out
        self.mp3_320_out = mp3_320_out
        self.mp3_v0_out = mp3_v0_out

    def run(self, context):
        self.update_progress(5.0)
        from flac_downsampler import process_batch_with_options
        try:
            process_batch_with_options(
                self.base_dir, self.tracker_url, self.source_flag,
                self.flac_out, self.mp3_320_out, self.mp3_v0_out
            )
            self.update_progress(100.0)
            self.update_state(TaskState.COMPLETED)
        except Exception as e:
            logger.error(f"Downsample task failed: {e}")
            self.update_state(TaskState.FAILED, error=str(e))

class LosslessCheckTask(Task):
    def __init__(self, task_id: str, album_dir: str, fast_mode: bool):
        super().__init__(id=task_id, name=f"Audit/Check: {Path(album_dir).name}", type="lossless_check")
        self.album_dir = album_dir
        self.fast_mode = fast_mode

    def run(self, context):
        self.update_progress(10.0)
        from lossless_checker import process_album
        try:
            # Output directory for spectrograms inside data/cache
            cache_dir = app_paths.spectrograms_dir / Path(self.album_dir).name
            success = process_album(self.album_dir, output_dir=cache_dir, fast_mode=self.fast_mode)
            self.update_progress(100.0)
            if success:
                self.update_state(TaskState.COMPLETED)
            else:
                self.update_state(TaskState.FAILED, error="Lossless check failed or rip log warnings found.")
        except Exception as e:
            logger.error(f"Lossless check task failed: {e}")
            self.update_state(TaskState.FAILED, error=str(e))

class SeedingTask(Task):
    def __init__(self, task_id: str, local_path: str, torrent_path: str, remote_save_path: str, use_remote: bool):
        super().__init__(id=task_id, name=f"Remote Seed: {Path(local_path).name}", type="seeding")
        self.local_path = local_path
        self.torrent_path = torrent_path
        self.remote_save_path = remote_save_path
        self.use_remote = use_remote

    def run(self, context):
        self.update_progress(10.0)
        try:
            manager = SeedingManager(context.gateway)
            success = manager.seed_torrent(
                local_path=self.local_path,
                torrent_path=self.torrent_path,
                use_remote=self.use_remote,
                remote_save_path=self.remote_save_path,
                on_progress=lambda msg: logger.info(f"[RemoteSeeding] {msg}")
            )
            self.update_progress(100.0)
            if success:
                self.update_state(TaskState.COMPLETED)
            else:
                self.update_state(TaskState.FAILED, error="Seeding or rclone sync failed. Check logs.")
        except Exception as e:
            logger.error(f"Seeding task failed: {e}")
            self.update_state(TaskState.FAILED, error=str(e))

# Models
class SearchStartRequest(BaseModel):
    site: str = "RED"
    api_key: str = ""
    passkey: str = ""
    media: str = "CD"
    year_earliest: int = 1970
    year_latest: int = 2023
    find_number: int = 50
    max_size: int = 2048
    min_size: int = 0
    request_interval: float = 3.0
    save_path: str = "./downloads"
    bandcamp: bool = False
    ignore_lossy: bool = False
    ignore_16bit: bool = False
    ignore_mp3_exists: bool = False
    ignore_warnings: bool = False
    ignore_trumpable: bool = False
    exclude_zero_snatches: bool = False
    auto_download: bool = False
    min_seeders: int = 0
    buffer_limit: float = 10.0
    buffer_formula: str = "(U / 0.65) - D"
    use_fl_token: bool = False
    fl_token_threshold: int = 500
    release_types: Dict[str, bool] = {}
    order_by: str = "time"
    enable_pipeline: bool = False
    qb_host: str = "http://127.0.0.1"
    qb_port: str = "8080"
    qb_user: str = "admin"
    qb_pass: str = "adminadmin"
    pipeline_use_remote: bool = False

class DownsampleStartRequest(BaseModel):
    album_dir: str
    tracker_url: str
    source_flag: str
    flac_out: bool = True
    mp3_320_out: bool = False
    mp3_v0_out: bool = False

class LosslessCheckStartRequest(BaseModel):
    album_dir: str
    fast_mode: bool = False

class SeedingStartRequest(BaseModel):
    local_path: str
    torrent_path: str
    remote_save_path: str
    qb_host: str = "http://127.0.0.1"
    qb_port: str = "8080"
    qb_user: str = "admin"
    qb_pass: str = "adminadmin"
    client_type: str = "qBittorrent"
    rclone_remote: str = ""
    rclone_config: str = ""

class CrossSeedStartRequest(BaseModel):
    source_site: str = "OPS"
    target_sites: List[str] = ["RED"]
    qb_host: str = "http://127.0.0.1"
    qb_port: str = "8080"
    qb_user: str = "admin"
    qb_pass: str = "adminadmin"
    save_path: str = "./cross_seed_torrents"
    client_type: str = "qBittorrent"
    rclone_remote: str = ""
    rclone_config: str = ""

class ConfigSaveRequest(BaseModel):
    site: str
    global_cfg: Dict
    sites: Dict
    seeding: Dict

# Endpoints
@app.get("/api/status")
def get_status():
    tasks = []
    for t in core.globals.app_context.tasks.list_tasks():
        tasks.append({
            "id": t.id,
            "name": t.name,
            "type": t.type,
            "state": t.state.value,
            "progress": t.progress,
            "error_message": t.error_message,
            "updated_at": t.updated_at
        })
    tasks.sort(key=lambda x: x["updated_at"], reverse=True)
    
    return {
        "app_state": core.globals.app_context.state.get_state().value,
        "tasks": tasks,
        "pipeline_active": global_pipeline is not None and global_pipeline.is_running,
        "cross_seed_active": global_cross_seed_engine is not None and global_cross_seed_engine.is_running
    }

@app.get("/api/config")
def get_config():
    gateway = core.globals.app_context.gateway
    
    # Read nested config from database / YAML
    site = gateway.get_config("site", "RED")
    global_cfg = gateway.get_config("global", {
        "qb_host": "http://127.0.0.1",
        "qb_port": "8080",
        "qb_user": "admin",
        "qb_pass": "adminadmin",
        "enable_pipeline": False,
        "pipeline_use_remote": False
    })
    sites = gateway.get_config("sites", {"RED": {}, "OPS": {}, "JPS": {}, "DIC": {}})
    
    # Read seeding config
    seeding = {
        "host": gateway.get_config("seeding.host", global_cfg.get("qb_host", "http://127.0.0.1")),
        "port": str(gateway.get_config("seeding.port", global_cfg.get("qb_port", "8080"))),
        "user": gateway.get_config("seeding.user", global_cfg.get("qb_user", "admin")),
        "pass": gateway.get_config("seeding.pass", global_cfg.get("qb_pass", "adminadmin")),
        "client_type": gateway.get_config("seeding.client_type", "qBittorrent"),
        "rclone_remote": gateway.get_config("seeding.rclone_remote", ""),
        "rclone_config": gateway.get_config("seeding.rclone_config", ""),
        "manual_local_path": gateway.get_config("seeding.manual_local_path", ""),
        "manual_torrent_path": gateway.get_config("seeding.manual_torrent_path", ""),
        "manual_remote_save_path": gateway.get_config("seeding.manual_remote_save_path", ""),
        "save_path": gateway.get_config("seeding.save_path", "./cross_seed_torrents"),
        "source_site": gateway.get_config("seeding.source_site", "OPS"),
        "target_red": gateway.get_config("seeding.target_red", True),
        "target_ops": gateway.get_config("seeding.target_ops", False),
        "target_jps": gateway.get_config("seeding.target_jps", False),
        "target_dic": gateway.get_config("seeding.target_dic", False)
    }
    
    return {
        "site": site,
        "global": global_cfg,
        "sites": sites,
        "seeding": seeding
    }

@app.post("/api/config")
def save_config(req: ConfigSaveRequest):
    try:
        gateway = core.globals.app_context.gateway
        gateway.set_config("site", req.site)
        gateway.set_config("global", req.global_cfg)
        gateway.set_config("sites", req.sites)
        
        # Save seeding configs separately
        for k, v in req.seeding.items():
            gateway.set_config(f"seeding.{k}", v)
            
        return {"status": "success", "message": "Configuration saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search/start")
def start_search(req: SearchStartRequest):
    # Map request values to SimpleNamespace
    options = SimpleNamespace(
        api_key=req.api_key.strip(),
        passkey=req.passkey.strip(),
        site_config=SITE_CONFIGS.get(req.site, SITE_CONFIGS["RED"]),
        bandcamp=req.bandcamp,
        cache=f'EliteTMHelper2_{req.site}.cache',
        dont_cache_yays=False,
        ignore_20_pages_limit=False,
        any16bit=req.ignore_16bit,
        lossy=req.ignore_lossy,
        trumpable=req.ignore_trumpable,
        uns=False,
        max_size=req.max_size * 1048576,
        min_size=req.min_size * 1048576,
        ignore_mp3_exists=req.ignore_mp3_exists,
        ignore_warnings=req.ignore_warnings,
        media=req.media if req.media else "",
        min_seeders=req.min_seeders,
        order_by=req.order_by,
        order_way="desc",
        output=str(app_paths.output_dir / f'EliteTMHelper2_{req.site}_Found.txt'),
        output_args=False,
        html=False,
        find_number=req.find_number,
        release_type="",
        exclude_zero_snatches=req.exclude_zero_snatches,
        auto_download=req.auto_download,
        release_type_allowed={
            1: req.release_types.get("Album", True),
            3: req.release_types.get("Soundtrack", True),
            5: req.release_types.get("EP", True),
            6: req.release_types.get("Anthology", True),
            7: req.release_types.get("Compilation", True),
            9: req.release_types.get("Single", True),
            11: req.release_types.get("Live album", True),
            13: req.release_types.get("Remix", True),
            14: req.release_types.get("Bootleg", True),
            15: req.release_types.get("Interview", True),
            16: req.release_types.get("Mixtape", True),
            17: req.release_types.get("Demo", True),
            21: req.release_types.get("Unknown", True),
            22: req.release_types.get("Concert Recording", True),
            23: req.release_types.get("DJ Mix", True)
        },
        buffer_limit=req.buffer_limit,
        buffer_formula=req.buffer_formula,
        use_fl_token=req.use_fl_token,
        fl_token_threshold=req.fl_token_threshold,
        show_api_times=False,
        show_size=True,
        tags=None,
        tags_type=0,
        year_earliest=req.year_earliest,
        year_latest=req.year_latest,
        request_interval=req.request_interval,
        save_path=req.save_path,
        qb_host=req.qb_host,
        qb_port=req.qb_port,
        qb_user=req.qb_user,
        qb_pass=req.qb_pass,
        enable_pipeline=req.enable_pipeline,
        pipeline_use_remote=req.pipeline_use_remote
    )
    
    task_id = f"search_{int(time.time())}"
    task = SearchTask(task_id, options)
    core.globals.app_context.tasks.submit(task)
    return {"status": "success", "task_id": task_id}

@app.post("/api/search/stop/{task_id}")
def stop_search(task_id: str):
    core.globals.app_context.tasks.cancel_task(task_id)
    return {"status": "success"}

@app.post("/api/downsample/start")
def start_downsample(req: DownsampleStartRequest):
    task_id = f"downsample_{int(time.time())}"
    task = DownsampleTask(
        task_id, req.album_dir, req.tracker_url, req.source_flag,
        req.flac_out, req.mp3_320_out, req.mp3_v0_out
    )
    core.globals.app_context.tasks.submit(task)
    return {"status": "success", "task_id": task_id}

@app.post("/api/check/start")
def start_check(req: LosslessCheckStartRequest):
    task_id = f"check_{int(time.time())}"
    task = LosslessCheckTask(task_id, req.album_dir, req.fast_mode)
    core.globals.app_context.tasks.submit(task)
    return {"status": "success", "task_id": task_id}

@app.post("/api/seeding/start")
def start_seeding(req: SeedingStartRequest):
    # Update local config values for seeding
    gateway = core.globals.app_context.gateway
    gateway.set_config("seeding.host", req.qb_host)
    gateway.set_config("seeding.port", req.qb_port)
    gateway.set_config("seeding.user", req.qb_user)
    gateway.set_config("seeding.pass", req.qb_pass)
    gateway.set_config("seeding.client_type", req.client_type)
    gateway.set_config("seeding.rclone_remote", req.rclone_remote)
    gateway.set_config("seeding.rclone_config", req.rclone_config)
    gateway.set_config("seeding.manual_local_path", req.local_path)
    gateway.set_config("seeding.manual_torrent_path", req.torrent_path)
    gateway.set_config("seeding.manual_remote_save_path", req.remote_save_path)
    
    use_remote = bool(req.rclone_remote)
    task_id = f"seed_{int(time.time())}"
    task = SeedingTask(task_id, req.local_path, req.torrent_path, req.remote_save_path, use_remote)
    core.globals.app_context.tasks.submit(task)
    return {"status": "success", "task_id": task_id}

@app.post("/api/crossseed/start")
def start_crossseed(req: CrossSeedStartRequest):
    global global_cross_seed_engine
    if global_cross_seed_engine and global_cross_seed_engine.is_running:
        raise HTTPException(status_code=400, detail="Cross-seed engine is already running.")
        
    # Update configurations
    gateway = core.globals.app_context.gateway
    gateway.set_config("seeding.host", req.qb_host)
    gateway.set_config("seeding.port", req.qb_port)
    gateway.set_config("seeding.user", req.qb_user)
    gateway.set_config("seeding.pass", req.qb_pass)
    gateway.set_config("seeding.client_type", req.client_type)
    gateway.set_config("seeding.rclone_remote", req.rclone_remote)
    gateway.set_config("seeding.rclone_config", req.rclone_config)
    gateway.set_config("seeding.save_path", req.save_path)
    gateway.set_config("seeding.source_site", req.source_site)
    
    # Save target site configurations
    gateway.set_config("seeding.target_red", "RED" in req.target_sites)
    gateway.set_config("seeding.target_ops", "OPS" in req.target_sites)
    gateway.set_config("seeding.target_jps", "JPS" in req.target_sites)
    gateway.set_config("seeding.target_dic", "DIC" in req.target_sites)

    # Initialize and start CrossSeedEngine
    global_cross_seed_engine = CrossSeedEngine(
        core.globals.app_context,
        global_pipeline,
        req.qb_host,
        req.qb_port,
        req.qb_user,
        req.qb_pass,
        req.save_path,
        client_type=req.client_type,
        rclone_remote=req.rclone_remote if req.rclone_remote else None,
        rclone_config=req.rclone_config if req.rclone_config else None
    )
    # Redirect engine logs to python logging
    global_cross_seed_engine.log = lambda msg: logger.info(f"[CrossSeed] {msg}")
    
    # Run async engine start
    threading.Thread(
        target=global_cross_seed_engine.start,
        args=(req.source_site, req.target_sites),
        daemon=True
    ).start()
    
    return {"status": "success"}

@app.post("/api/crossseed/stop")
def stop_crossseed():
    global global_cross_seed_engine
    if global_cross_seed_engine:
        global_cross_seed_engine.stop()
        return {"status": "success", "message": "Cross-seed engine stopping."}
    return {"status": "error", "message": "Engine is not running."}

@app.post("/api/pipeline/start")
def start_pipeline_manual():
    global global_pipeline
    with global_pipeline_lock:
        if global_pipeline and global_pipeline.is_running:
            return {"status": "success", "message": "Pipeline already active."}
            
        gateway = core.globals.app_context.gateway
        global_cfg = gateway.get_config("global", {})
        active_site = gateway.get_config("site", "RED")
        sites = gateway.get_config("sites", {})
        
        # Load API option namespaces
        site_opt = sites.get(active_site, {})
        options = SimpleNamespace(
            api_key=site_opt.get("api_key", ""),
            save_path=site_opt.get("save_path", "./downloads"),
            qb_host=global_cfg.get("qb_host", "http://127.0.0.1"),
            qb_port=global_cfg.get("qb_port", "8080"),
            qb_user=global_cfg.get("qb_user", "admin"),
            qb_pass=global_cfg.get("qb_pass", "adminadmin"),
            site_config=SITE_CONFIGS.get(active_site, SITE_CONFIGS["RED"]),
            ignore_mp3_exists=site_opt.get("ignore_mp3_exists", False),
            ignore_warnings=site_opt.get("ignore_warnings", False)
        )
        
        global_pipeline = PipelineManager(
            options.qb_host, options.qb_port, options.qb_user, options.qb_pass,
            None, options,
            log_main=lambda s: logger.info(f"[Pipeline] {s}"),
            log_process=lambda s: logger.info(f"[Pipeline-Transcode] {s}"),
            log_check=lambda s: logger.info(f"[Pipeline-Audit] {s}")
        )
        global_pipeline.start()
        
    return {"status": "success", "message": "Pipeline manager started."}

@app.post("/api/pipeline/stop")
def stop_pipeline_manual():
    global global_pipeline
    with global_pipeline_lock:
        if global_pipeline:
            global_pipeline.stop()
            global_pipeline = None
            return {"status": "success", "message": "Pipeline manager stopped."}
    return {"status": "error", "message": "Pipeline is not active."}

@app.get("/api/logs")
def get_logs(lines: int = 150):
    log_file = app_paths.logs_dir / "app.log"
    if not log_file.exists():
        return {"logs": "Logging file not found yet. Trigger some actions."}
    try:
        # Read last N lines
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()
            tail = content[-lines:]
            return {"logs": "".join(tail)}
    except Exception as e:
        return {"logs": f"Error reading log file: {e}"}

@app.post("/api/logs/clear")
def clear_logs():
    log_file = app_paths.logs_dir / "app.log"
    try:
        if log_file.exists():
            with open(log_file, "w", encoding="utf-8") as f:
                f.truncate(0)
        return {"status": "success", "message": "Log file cleared."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Auto-start pipeline manager on boot if configured
def auto_boot_pipeline():
    global global_pipeline
    try:
        gateway = core.globals.app_context.gateway
        global_cfg = gateway.get_config("global", {})
        if global_cfg.get("enable_pipeline", False):
            logger.info("Auto-booting background PipelineManager as requested by config...")
            start_pipeline_manual()
    except Exception as e:
        logger.error(f"Failed to auto-boot pipeline manager: {e}")

# Run auto-boot
threading.Thread(target=auto_boot_pipeline, daemon=True).start()

# Mount Frontend static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    logger.info("Launching Redacted Audio Toolbox WebUI on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
