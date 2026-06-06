import os
import subprocess
from typing import Optional

if os.name == 'nt':
    SUBPROCESS_KWARGS = {'creationflags': 0x08000000}
else:
    SUBPROCESS_KWARGS = {}

def rclone_copy(local_path: str, remote_path: str, rclone_config_path: Optional[str] = None) -> bool:
    """
    Execute an rclone copy command to upload files/folders to a remote location.
    
    :param local_path: Absolute path to local file or directory.
    :param remote_path: Remote target in the format 'remote:path/to/folder'.
    :param rclone_config_path: Optional path to rclone.conf file.
    """
    if not os.path.exists(local_path):
        print(f"[rclone] Local path does not exist: {local_path}")
        return False

    cmd = ["rclone", "copy", local_path, remote_path]
    
    # Append config flag if config path is provided
    if rclone_config_path and os.path.exists(rclone_config_path):
        cmd.extend(["--config", rclone_config_path])

    try:
        print(f"[rclone] Uploading: {os.path.basename(local_path)} -> {remote_path} ...")
        # Run rclone copy
        res = subprocess.run(cmd, capture_output=True, text=True, **SUBPROCESS_KWARGS)
        if res.returncode == 0:
            print(f"[rclone] Upload successfully completed.")
            return True
        else:
            print(f"[rclone] Upload failed (Exit code: {res.returncode}). Error: {res.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("[rclone] Error: rclone executable not found. Please ensure rclone is installed and added to your PATH.")
        return False
    except Exception as e:
        print(f"[rclone] Error running rclone command: {e}")
        return False
