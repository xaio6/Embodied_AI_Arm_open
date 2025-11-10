# -*- coding: utf-8 -*-
"""
启动引导工具：
- 资源目录准备（ProgramData/HorizonArm），同步 config/mujoco_dll/data（仅冻结环境）
- 全局 UI 缩放环境变量设置（冻结环境优先；本地由动态DPI驱动）
"""
import os
import sys
import shutil
import datetime


def apply_global_ui_scale():
    """按分辨率和系统DPI设置 QT_SCALE_FACTOR，可被环境变量 UI_SCALE 覆盖。"""
    try:
        # 本地运行时跳过全局环境缩放，交给 Qt + 动态缩放处理
        if not getattr(sys, 'frozen', False) and not os.environ.get('UI_SCALE', '').strip():
            return
        ui_scale = os.environ.get('UI_SCALE', '').strip()
        if not ui_scale:
            width = None
            height = None
            dpi_scale = 1.0
            try:
                if sys.platform == 'win32':
                    import ctypes
                    user32 = ctypes.windll.user32
                    width = int(user32.GetSystemMetrics(0))
                    height = int(user32.GetSystemMetrics(1))
                    try:
                        gdi32 = ctypes.windll.gdi32
                        hdc = user32.GetDC(0)
                        dpi_x = gdi32.GetDeviceCaps(hdc, 88)
                        user32.ReleaseDC(0, hdc)
                        if dpi_x:
                            dpi_scale = max(0.5, min(3.0, float(dpi_x) / 96.0))
                    except Exception:
                        pass
                else:
                    width, height = 1920, 1080
            except Exception:
                width, height = 1920, 1080

            h = max(height or 0, 0)
            if h >= 2160:
                scale = 0.60
            elif h >= 1440:
                scale = 0.70
            else:
                base = 0.80
                if dpi_scale >= 1.50:
                    base = 0.70
                elif dpi_scale >= 1.25:
                    base = 0.75
                scale = base
            ui_scale = f"{scale:.2f}"

        os.environ.setdefault('QT_ENABLE_HIGHDPI_SCALING', '1')
        os.environ.setdefault('QT_SCALE_FACTOR_ROUNDING_POLICY', 'PassThrough')
        os.environ['QT_SCALE_FACTOR'] = str(float(ui_scale))
        # 静默
    except Exception as _e:
        # 静默
        pass


def _get_programdata_root(app_dir: str) -> str:
    if sys.platform == 'win32':
        pd = os.environ.get('PROGRAMDATA') or os.environ.get('ProgramData') or 'C\\ProgramData'
        return os.path.join(pd, 'HorizonArm')
    return os.path.join(os.path.dirname(app_dir), 'HorizonArmResources')


def _get_fallback_root(app_dir: str) -> str:
    if sys.platform == 'win32':
        local = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(local, 'HorizonArm')
    return os.path.join(os.path.expanduser('~'), '.horizon_arm_resources')


def _sync_dir(src_dir: str, dst_dir: str):
    try:
        if not os.path.isdir(src_dir):
            return
        os.makedirs(dst_dir, exist_ok=True)
        for root, dirs, files in os.walk(src_dir):
            rel = os.path.relpath(root, src_dir)
            out_dir = os.path.join(dst_dir, rel) if rel != '.' else dst_dir
            os.makedirs(out_dir, exist_ok=True)
            for f in files:
                s = os.path.join(root, f)
                d = os.path.join(out_dir, f)
                try:
                    if (not os.path.exists(d)) or (os.path.getsize(d) != os.path.getsize(s)):
                        shutil.copy2(s, d)
                except Exception:
                    pass
    except Exception:
        pass


def prepare_resource_root(base_dir: str, app_dir: str) -> str:
    """将资源同步到 ProgramData（失败则 LocalAppData）并切换工作目录，返回资源根路径。"""
    candidates = [_get_programdata_root(app_dir), _get_fallback_root(app_dir)]
    last_error = None
    for resource_root in candidates:
        try:
            os.makedirs(resource_root, exist_ok=True)
            for name in ('config', 'mujoco_dll', 'data'):
                _sync_dir(os.path.join(base_dir, name), os.path.join(resource_root, name))
            os.environ['HORIZON_DATA_DIR'] = resource_root
            os.chdir(resource_root)
            # 静默
            return resource_root
        except Exception as _e:
            last_error = _e
            continue
    # 静默
    return candidates[-1]


def setup_process_logging(resource_root: str) -> str:
    """将 stdout/stderr 重定向到资源根目录 logs 下的时间戳日志文件，并保留原有输出。返回日志路径。"""
    try:
        logs_dir = os.path.join(resource_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_path = os.path.join(logs_dir, f'app_{ts}.log')

        class _Tee:
            def __init__(self, file_obj, console_stream=None):
                self._file = file_obj
                self._console = console_stream
            def write(self, data):
                try:
                    self._file.write(data)
                    self._file.flush()
                except Exception:
                    pass
                if self._console is not None:
                    try:
                        self._console.write(data)
                        self._console.flush()
                    except Exception:
                        pass
            def flush(self):
                try:
                    self._file.flush()
                except Exception:
                    pass
                if self._console is not None:
                    try:
                        self._console.flush()
                    except Exception:
                        pass

        # 打开文件并重定向
        log_f = open(log_path, 'a', encoding='utf-8', errors='ignore')
        sys.stdout = _Tee(log_f, getattr(sys, 'stdout', None))
        sys.stderr = _Tee(log_f, getattr(sys, 'stderr', None))
        # 静默
        return log_path
    except Exception:
        return ''



def configure_mujoco_runtime(resource_root: str, app_dir: str) -> None:
    """占位：为兼容启动代码而提供的空实现。

    发行版不依赖仿真时无需配置任何 DLL 路径；
    若未来需要启用仿真，可在此补充搜索并加入 `mujoco_dll` 的路径。
    """
    try:
        # 保持空操作，避免因缺失 MuJoCo 导致启动失败
        return
    except Exception:
        # 静默
        pass