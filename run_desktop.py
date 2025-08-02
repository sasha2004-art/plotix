import sys
import os
from pathlib import Path

# Блок проверки виртуального окружения (без изменений)
if sys.prefix == sys.base_prefix:
    project_root = Path(__file__).parent
    venv_dir = project_root / ".venv"
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        print("\n\033[91mОшибка: Виртуальное окружение не найдено!\033[0m")
        print(
            f"\033[93mПожалуйста, запустите 'python {project_root / 'start.py'}' для первоначальной настройки.\033[0m"
        )
        sys.exit(1)
    print(
        f"\033[94mНе в виртуальном окружении. Перезапуск с использованием: {venv_python}\033[0m"
    )
    try:
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)
    except Exception as e:
        print(f"\n\033[91mКритическая ошибка при попытке перезапуска: {e}\033[0m")
        sys.exit(1)

import webview
import shutil
from huggingface_hub import HfFolder, whoami, hf_hub_url
from huggingface_hub.utils import HfHubHTTPError
from huggingface_hub.errors import RepositoryNotFoundError, EntryNotFoundError
import requests
from requests.exceptions import HTTPError
import json
import logging
import threading
import time
import math

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent
app_dir = project_root / "app"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(app_dir))

from app.main import app
from webview.errors import JavascriptException

# Определяем пути к файлам данных
DATA_DIR = project_root / "plotix_data"
CHATS_FILE_PATH = DATA_DIR / "chats.json"
API_KEYS_FILE_PATH = DATA_DIR / "api_keys.json"


class Api:
    def __init__(self):
        self._window = None
        self._is_maximized = False
        self._download_tasks: dict[
            str, dict[str, threading.Thread | threading.Event]
        ] = {}
        self._tasks_lock = threading.Lock()

    # ... (существующие функции _format_bytes, set_window, minimize, toggle_maximize, close, finalize_shutdown и т.д. остаются без изменений)
    def _format_bytes(self, size_bytes):
        if size_bytes <= 0:
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
        logger.info("Close requested. Asking JS to prepare for shutdown.")
        if self._window:
            self._window.evaluate_js("window.prepareForShutdown()")

    def finalize_shutdown(self):
        logger.info("JS has confirmed shutdown readiness. Finalizing.")
        if self._window:
            self._window.destroy()

    def open_file_dialog(self):
        if not self._window:
            return
        file_types = ("GGUF models (*.gguf)",)
        return self._window.create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=True, file_types=file_types
        )

    def get_hf_status(self):
        token = HfFolder.get_token()
        if not token:
            return {"logged_in": False}
        try:
            user_info = whoami()
            return {"logged_in": True, "username": user_info.get("name")}
        except HfHubHTTPError:
            return {"logged_in": False, "error": "Сохраненный токен недействителен."}

    def save_hf_token(self, token: str):
        if not token or not isinstance(token, str):
            HfFolder.delete_token()
            logger.info("User logged out from Hugging Face.")
            return {"status": "ok", "message": "Вы вышли из аккаунта."}
        try:
            user_info = whoami(token=token)
            HfFolder.save_token(token)
            username = user_info.get("name")
            logger.info(f"Successfully logged into Hugging Face as {username}")
            return {
                "status": "ok",
                "message": f"Вы успешно вошли как {username}!",
                "username": username,
            }
        except HfHubHTTPError:
            logger.warning("Invalid Hugging Face token provided.")
            return {
                "status": "error",
                "message": "Неверный токен. Проверьте его и попробуйте снова.",
            }
        except Exception as e:
            logger.error(f"An unexpected error occurred during HF login: {e}")
            return {"status": "error", "message": "Произошла непредвиденная ошибка."}

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

    def _call_js_func(self, js_code: str):
        if self._window:
            try:
                self._window.evaluate_js(js_code)
            except JavascriptException as e:
                logger.warning(f"Could not execute JS: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred during JS call: {e}")

    def _download_worker(
        self, repo_id: str, filename: str, cancel_flag: threading.Event
    ):
        # ... (этот метод без изменений)
        task_id = f"{repo_id}/{filename}"
        status, message = "error", "Произошла неизвестная ошибка."
        models_dir = Path.cwd() / "quest-generator" / "models"
        models_dir.mkdir(exist_ok=True)
        local_path = models_dir / filename
        try:
            url = hf_hub_url(repo_id=repo_id, filename=filename)
            logger.info(f"Starting download for {task_id} from {url}")
            token = HfFolder.get_token()
            headers = {}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            self._call_js_func(f"window.startDownload('{repo_id}', '{filename}');")
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
                            if (
                                current_time - last_update_time >= 1.0
                                or downloaded_size == total_size
                            ):
                                speed = (
                                    bytes_since_last_update
                                    / (current_time - last_update_time)
                                    if (current_time - last_update_time) > 0
                                    else 0
                                )
                                percentage = (
                                    (downloaded_size / total_size * 100)
                                    if total_size > 0
                                    else 0
                                )
                                progress_data = {
                                    "repo_id": repo_id,
                                    "filename": filename,
                                    "downloaded_str": self._format_bytes(
                                        downloaded_size
                                    ),
                                    "total_str": self._format_bytes(total_size),
                                    "speed_str": f"{self._format_bytes(speed)}/s",
                                    "percentage": percentage,
                                }
                                js_code = f"window.updateDownloadProgress({json.dumps(progress_data)})"
                                self._call_js_func(js_code)
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
        except HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            logger.error(f"HTTP error {status_code} for {task_id}: {e}")
            if status_code == 403:
                model_url = f"https://huggingface.co/{repo_id}"
                message = f'Для доступа к этой модели необходимо принять ее условия. Пожалуйста, перейдите на <a href="{model_url}" target="_blank" rel="noopener noreferrer">страницу модели</a>, войдите в аккаунт и примите лицензионное соглашение. После этого попробуйте скачать снова.'
            elif status_code == 401:
                message = f"Ошибка 401: Неверный токен. Попробуйте снова войти в Hugging Face через настройки приложения."
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
            finish_data = {
                "repo_id": repo_id,
                "filename": filename,
                "status": status,
                "message": message,
            }
            js_code = f"window.finishDownload({json.dumps(finish_data)})"
            self._call_js_func(js_code)
            self._cleanup_task(task_id)

    def download_model(self, repo_id, filename):
        # ... (этот метод без изменений)
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
        # ... (этот метод без изменений)
        task_id = f"{repo_id}/{filename}"
        with self._tasks_lock:
            task = self._download_tasks.get(task_id)
            if task and isinstance(task.get("cancel_flag"), threading.Event):
                task["cancel_flag"].set()
                return {"status": "ok"}
        return {"status": "error"}

    def save_chats_to_disk(self, chats_data: dict) -> dict:
        """Сохраняет объект чатов в файл chats.json."""
        try:
            DATA_DIR.mkdir(exist_ok=True)
            with open(CHATS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(chats_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Чаты успешно сохранены в {CHATS_FILE_PATH}")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Ошибка сохранения chats.json: {e}")
            return {"status": "error", "message": str(e)}

    def load_chats_from_disk(self) -> dict:
        """Загружает объект чатов из файла chats.json."""
        if not CHATS_FILE_PATH.exists():
            return {}
        try:
            with open(CHATS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Чаты успешно загружены из {CHATS_FILE_PATH}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Ошибка загрузки или парсинга chats.json: {e}")
            return {}

    # ==================== ИЗМЕНЕНИЕ: Новые функции для ключей API ====================
    def save_api_keys(self, keys_data: dict) -> dict:
        """Сохраняет ключи API в файл api_keys.json."""
        try:
            DATA_DIR.mkdir(exist_ok=True)
            with open(API_KEYS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(keys_data, f, indent=2)
            logger.info(f"Ключи API успешно сохранены в {API_KEYS_FILE_PATH}")
            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Ошибка сохранения api_keys.json: {e}")
            return {"status": "error", "message": str(e)}

    def load_api_keys(self) -> dict:
        """Загружает ключи API из файла api_keys.json."""
        if not API_KEYS_FILE_PATH.exists():
            return {}
        try:
            with open(API_KEYS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"Ключи API успешно загружены из {API_KEYS_FILE_PATH}")
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Ошибка загрузки или парсинга api_keys.json: {e}")
            return {}

    # ===============================================================================


if __name__ == "__main__":
    api = Api()
    # Создание папки данных перед запуском окна
    DATA_DIR.mkdir(exist_ok=True)

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
    webview.start(debug=True, icon="./app/static/img/iconca.ico")
