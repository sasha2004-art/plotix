import sys
from pathlib import Path
import webview
import shutil
from huggingface_hub import hf_hub_url, HfFolder
from huggingface_hub.errors import RepositoryNotFoundError, EntryNotFoundError
import requests
from requests.exceptions import HTTPError
import json
import logging
import threading
import os
import time
import math

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- РЕШЕНИЕ ПРОБЛЕМЫ ИМПОРТОВ ---
project_root = Path(__file__).parent
app_dir = project_root / "app"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(app_dir))
# ------------------------------------

from app.main import app  # noqa: E402


class Api:
    def __init__(self):
        self._window = None
        self._is_maximized = False
        self._download_tasks: dict[
            str, dict[str, threading.Thread | threading.Event]
        ] = {}
        self._tasks_lock = threading.Lock()

    def _format_bytes(self, size_bytes):
        if size_bytes <= 0:  # Добавил проверку на <= 0 для большей надежности
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = int(math.log(size_bytes, 1024))
        p = pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def set_window(self, window):
        self._window = window

    def minimize(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize(self):
        if self._window:
            if self._is_maximized:
                self._window.restore()
            else:
                self._window.maximize()
            self._is_maximized = not self._is_maximized

    def close(self):
        logger.info("Close requested. Cancelling all active downloads.")
        with self._tasks_lock:
            for task_id, task_data in list(self._download_tasks.items()):
                cancel_flag = task_data.get("cancel_flag")
                if isinstance(cancel_flag, threading.Event):
                    cancel_flag.set()
                logger.info(f"Cancellation flag set for task: {task_id}")
        if self._window:
            self._window.destroy()

    def open_file_dialog(self):
        if not self._window:
            return
        file_types = ("GGUF models (*.gguf)",)
        return self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types
        )

    def save_quest_to_file(self, content: str):
        if not self._window:
            return {"status": "error", "message": "Window not available"}
        default_filename = "quest.json"
        try:
            quest_data = json.loads(content)
            if "questTitle" in quest_data and quest_data["questTitle"]:
                safe_title = "".join(
                    c
                    for c in quest_data["questTitle"]
                    if c.isalnum() or c in (" ", "_", "-")
                ).rstrip()
                default_filename = f"{safe_title}.json"
        except (json.JSONDecodeError, TypeError):
            pass
        file_types = ("JSON Files (*.json)", "All files (*.*)")
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=default_filename, file_types=file_types
        )
        if result:
            try:
                with open(result, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"status": "ok", "message": f"Файл сохранен в {result}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "cancelled", "message": "Сохранение отменено"}

    def manage_files(self, action: str, source_paths: list):
        if not source_paths:
            return {"status": "error", "message": "Файлы не были переданы."}
        target_dir = Path(__file__).parent / "quest-generator" / "models"
        target_dir.mkdir(parents=True, exist_ok=True)
        messages = []
        error_count = 0
        for src_str in source_paths:
            source_path = Path(src_str)
            destination_path = target_dir / source_path.name
            try:
                if action == "copy":
                    shutil.copy2(source_path, destination_path)
                    messages.append(f"✅ Скопирован: {source_path.name}")
                elif action == "move":
                    shutil.move(str(source_path), str(destination_path))
                    messages.append(f"✅ Перемещен: {source_path.name}")
            except Exception as e:
                messages.append(f"❌ Ошибка с файлом {source_path.name}: {e}")
                error_count += 1
        final_message = "\n".join(messages)
        status = "ok" if error_count == 0 else "error"
        return {"status": status, "message": final_message}

    def _cleanup_task(self, task_id: str):
        with self._tasks_lock:
            self._download_tasks.pop(task_id, None)
            logger.info(f"Task '{task_id}' cleaned up.")

    def _download_worker(
        self, repo_id: str, filename: str, cancel_flag: threading.Event
    ):
        task_id = f"{repo_id}/{filename}"
        status, message = "error", "Произошла неизвестная ошибка."

        models_dir = Path.cwd() / "quest-generator" / "models"
        models_dir.mkdir(exist_ok=True)
        local_path = models_dir / filename

        try:
            url = hf_hub_url(repo_id=repo_id, filename=filename)
            logger.info(f"Starting download for {task_id} from {url}")

            # ИЗМЕНЕНИЕ: Получаем токен и добавляем заголовок авторизации
            token = HfFolder.get_token()
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"

            with requests.get(url, stream=True, timeout=15, headers=headers) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("content-length", 0))

                with open(local_path, "wb") as f:
                    downloaded_size = 0
                    chunk_size = 8192
                    last_update_time = time.time()
                    bytes_since_last_update = 0

                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if cancel_flag.is_set():
                            raise InterruptedError("Download cancelled by user.")

                        if chunk:
                            f.write(chunk)
                            chunk_len = len(chunk)
                            downloaded_size += chunk_len
                            bytes_since_last_update += chunk_len

                            current_time = time.time()
                            if current_time - last_update_time >= 1.0:
                                speed = bytes_since_last_update / (
                                    current_time - last_update_time
                                )
                                percentage = (
                                    (downloaded_size / total_size * 100)
                                    if total_size > 0
                                    else 0
                                )

                                if self._window:
                                    js_code = (
                                        f"window.updateDownloadProgress("
                                        f"'{repo_id}', '{filename}', "
                                        f"'{self._format_bytes(downloaded_size)}', '{self._format_bytes(total_size)}', "
                                        f"'{self._format_bytes(speed)}/s', {percentage})"
                                    )
                                    self._window.evaluate_js(js_code)

                                last_update_time = current_time
                                bytes_since_last_update = 0

            status = "ok"
            message = f"Модель '{filename}' успешно скачана."

        except InterruptedError as e:
            logger.info(e)
            status = "cancelled"
            message = "Скачивание отменено пользователем."
        except (RepositoryNotFoundError, EntryNotFoundError):
            message = f"Репозиторий '{repo_id}' или файл '{filename}' не найден."
            logger.error(message)
        # ИЗМЕНЕНИЕ: Более детальная обработка HTTP ошибок
        except HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            logger.error(f"HTTP error {status_code} for {task_id}: {e}")
            if status_code == 401:
                message = (
                    f"Ошибка 401: Доступ запрещен. Для скачивания этой модели, возможно, "
                    "требуется принять условия на ее странице в Hugging Face и/или "
                    "войти в аккаунт через 'huggingface-cli login' в вашем терминале."
                )
            elif status_code == 404:
                message = f"Ошибка 404: Файл '{filename}' не найден в репозитории '{repo_id}'."
            else:
                message = f"HTTP ошибка {status_code} при скачивании."
        except requests.exceptions.RequestException as e:
            message = f"Сетевая ошибка при скачивании: {e}"
            logger.error(f"Network error for {task_id}: {e}")
        except Exception as e:
            message = f"Произошла непредвиденная ошибка: {e}"
            logger.error(f"Generic download error for {task_id}", exc_info=True)
        finally:
            if status == "cancelled" and local_path.exists():
                try:
                    local_path.unlink()
                    logger.info(f"Deleted partial file: {local_path}")
                except OSError as e_del:
                    logger.error(f"Failed to delete partial file {local_path}: {e_del}")

            if self._window:
                escaped_message = json.dumps(message)
                js_code = f"window.dispatchDownloadEvent('{repo_id}', '{filename}', '{status}', {escaped_message})"
                self._window.evaluate_js(js_code)

            self._cleanup_task(task_id)

    def download_model(self, repo_id, filename):
        task_id = f"{repo_id}/{filename}"
        with self._tasks_lock:
            if task_id in self._download_tasks:
                return {
                    "status": "error",
                    "message": "Скачивание этой модели уже идет.",
                }
            cancel_flag = threading.Event()
            thread = threading.Thread(
                target=self._download_worker, args=(repo_id, filename, cancel_flag)
            )
            self._download_tasks[task_id] = {
                "thread": thread,
                "cancel_flag": cancel_flag,
            }
        thread.start()
        return {"status": "started"}

    def cancel_download(self, repo_id: str, filename: str):
        task_id = f"{repo_id}/{filename}"
        with self._tasks_lock:
            task = self._download_tasks.get(task_id)
            if task and isinstance(task.get("cancel_flag"), threading.Event):
                task["cancel_flag"].set()
                return {"status": "ok"}
        return {"status": "error"}


if __name__ == "__main__":
    api = Api()
    window = webview.create_window(
        "AI Quest Generator",
        app,
        js_api=api,
        width=1280,
        height=800,
        resizable=True,
        frameless=True,
        easy_drag=False,
    )
    api.set_window(window)
    webview.start(debug=True)
