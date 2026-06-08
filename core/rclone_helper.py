import os
import re
import subprocess
from typing import Optional, Callable

if os.name == 'nt':
    SUBPROCESS_KWARGS = {'creationflags': 0x08000000}
else:
    SUBPROCESS_KWARGS = {}

def rclone_copy_with_progress(
    local_path: str,
    remote_path: str,
    rclone_config_path: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> bool:
    """
    使用 subprocess.Popen 异步管道执行 rclone copy，解析 --progress 进度并回调。
    
    :param local_path: 本地文件或目录的绝对路径
    :param remote_path: 远程目标（例如 'remote:path/to/folder'）
    :param rclone_config_path: 可选的 rclone.conf 路径
    :param progress_callback: 接收进度更新字符串的回调函数
    :return: 传输是否成功（退出码是否为 0）
    """
    if not os.path.exists(local_path):
        err_msg = f"[rclone] 本地路径不存在: {local_path}"
        if progress_callback:
            progress_callback(err_msg)
        else:
            print(err_msg)
        return False

    cmd = ["rclone", "copy", local_path, remote_path, "--progress"]
    
    if rclone_config_path and os.path.exists(rclone_config_path):
        cmd.extend(["--config", rclone_config_path])

    # 匹配 rclone --progress 进度行的正则表达式
    # 例如: Transferred:      5.2 MiB / 15.6 MiB, 33%, 1.2 MiB/s, ETA 8s
    progress_re = re.compile(
        r"Transferred:\s+([\d\.]+.*?)\s+/\s+([\d\.]+.*?),\s+(\d+%),\s+([\d\.]+.*?/s),\s+ETA\s+(\S+)"
    )

    try:
        start_msg = f"[rclone] 正在开始上传: {os.path.basename(local_path)} -> {remote_path} ..."
        if progress_callback:
            progress_callback(start_msg)
        else:
            print(start_msg)

        # 启动进程并捕获标准输出和标准错误
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            **SUBPROCESS_KWARGS
        )

        last_progress_percent = -1

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                line_str = line.strip()
                match = progress_re.search(line_str)
                if match:
                    size_done, size_total, percent_str, speed, eta = match.groups()
                    percent_val = int(percent_str.replace('%', ''))
                    # 避免在日志中输出大量重复的相同进度，只在百分比改变时输出，或者隔一段时间输出
                    if percent_val != last_progress_percent:
                        progress_msg = f"⏳ 进度: {percent_str} | 已传: {size_done}/{size_total} | 速度: {speed} | 剩余: {eta}"
                        if progress_callback:
                            progress_callback(progress_msg)
                        else:
                            print(progress_msg)
                        last_progress_percent = percent_val
                elif line_str:
                    # 过滤掉 rclone 其他重复的内部进度汇总信息行
                    if any(x in line_str for x in ["Errors:", "Checks:", "Renamed:", "Deleted:", "Elapsed time:"]):
                        continue
                    # 只回调一些有用的非空状态行
                    if progress_callback:
                        progress_callback(line_str)
                    else:
                        print(line_str)

        returncode = process.wait()
        
        if returncode == 0:
            success_msg = f"[rclone] 上传完成。"
            if progress_callback:
                progress_callback(success_msg)
            else:
                print(success_msg)
            return True
        else:
            fail_msg = f"[rclone] 上传失败 (退出码: {returncode})"
            if progress_callback:
                progress_callback(fail_msg)
            else:
                print(fail_msg)
            return False

    except FileNotFoundError:
        err_msg = "[rclone] 错误: 未找到 rclone 可执行程序。请确保 rclone 已安装并添加到 PATH。"
        if progress_callback:
            progress_callback(err_msg)
        else:
            print(err_msg)
        return False
    except Exception as e:
        err_msg = f"[rclone] 运行 rclone 发生异常: {e}"
        if progress_callback:
            progress_callback(err_msg)
        else:
            print(err_msg)
        return False

def rclone_copy(local_path: str, remote_path: str, rclone_config_path: Optional[str] = None) -> bool:
    """
    保持对旧代码的向后兼容接口。
    """
    return rclone_copy_with_progress(local_path, remote_path, rclone_config_path, progress_callback=None)
