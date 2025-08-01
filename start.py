import sys
import subprocess
import venv
from pathlib import Path
import os


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"


def run_command_live(command, env=None):
    """
    Запускает команду и возвращает True в случае успеха, False - при ошибке.
    """
    try:
        # subprocess.run с check=True будет стримить вывод и выбросит исключение при ошибке
        subprocess.run(command, check=True, env=env)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(
            f"{Colors.FAIL}Ошибка выполнения команды '{' '.join(map(str, command))}': {e}{Colors.ENDC}"
        )
        return False


def setup_environment(project_root, use_local_llm):
    """Создает .env файл с настройками."""
    env_file_path = project_root / ".env"
    with open(env_file_path, "w") as f:
        f.write(f"USE_LOCAL_LLM={str(use_local_llm).lower()}\n")
    print(f"{Colors.OKGREEN}.env файл сконфигурирован.{Colors.ENDC}")


def main():
    print(f"{Colors.HEADER}--- AI Quest Generator: Desktop Setup ---{Colors.ENDC}")
    project_root = Path(__file__).parent
    venv_dir = project_root / ".venv"

    # --- Интерактивный выбор с fallback для неинтерактивных сред ---
    use_local_llm = False  # Начальное значение
    try:
        choice = (
            input(
                f"{Colors.WARNING}Хотите установить поддержку локальных LLM (llama.cpp)? (y/n): {Colors.ENDC}"
            )
            .lower()
            .strip()
        )
        use_local_llm = choice == "y"
    except EOFError:
        print(
            f"\n{Colors.WARNING}Запуск в неинтерактивном режиме. Поддержка локальных LLM будет включена по умолчанию.{Colors.ENDC}"
        )
        use_local_llm = True  # Устанавливаем в true для неинтерактивного запуска

    setup_environment(project_root, use_local_llm)

    if not venv_dir.exists():
        print(f"{Colors.OKBLUE}Создание виртуального окружения...{Colors.ENDC}")
        venv.create(venv_dir, with_pip=True)
        print(f"{Colors.OKGREEN}Виртуальное окружение создано.{Colors.ENDC}")
    else:
        print(f"{Colors.OKGREEN}Виртуальное окружение найдено.{Colors.ENDC}")

    python_executable = (
        venv_dir / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else venv_dir / "bin" / "python"
    )

    print(f"\n{Colors.OKBLUE}Установка зависимостей...{Colors.ENDC}")
    if not run_command_live(
        [str(python_executable), "-m", "pip", "install", "-r", "requirements.txt"]
    ):
        sys.exit(1)
    print(f"{Colors.OKGREEN}Основные зависимости установлены.{Colors.ENDC}")

    # --- Двухэтапная установка llama-cpp-python с fallback ---
    if use_local_llm:
        print(
            f"\n{Colors.OKBLUE}Попытка №1: Установка llama-cpp-python с поддержкой GPU (NVIDIA)...{Colors.ENDC}"
        )
        env = {**os.environ, "CMAKE_ARGS": "-DLLAMA_CUBLAS=on", "FORCE_CMAKE": "1"}
        llama_install_command = [
            str(python_executable),
            "-m",
            "pip",
            "install",
            "llama-cpp-python",
            "--force-reinstall",
            "--no-cache-dir",
            "--no-binary",
            ":all:",
        ]

        if run_command_live(llama_install_command, env=env):
            print(
                f"{Colors.OKGREEN}llama-cpp-python успешно установлен с поддержкой GPU!{Colors.ENDC}"
            )
        else:
            print(
                f"{Colors.FAIL}\nНе удалось установить версию с поддержкой GPU.{Colors.ENDC}"
            )
            print(
                f"\n{Colors.OKBLUE}Попытка №2: Установка стандартной версии llama-cpp-python (fallback)...{Colors.ENDC}"
            )
            print(
                f"{Colors.WARNING}Эта версия может использовать pre-compiled wheels и с большей вероятностью установится.{Colors.ENDC}"
            )

            cpu_install_command = [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "llama-cpp-python",
            ]
            if run_command_live(cpu_install_command):
                print(
                    f"{Colors.OKGREEN}Стандартная версия llama-cpp-python успешно установлена.{Colors.ENDC}"
                )
            else:
                print(
                    f"{Colors.FAIL}\nНе удалось установить llama-cpp-python даже в стандартной конфигурации.{Colors.ENDC}"
                )
                print(
                    f"{Colors.WARNING}Пожалуйста, убедитесь, что у вас установлены 'Visual Studio Build Tools' (с компонентом 'C++ desktop development').{Colors.ENDC}"
                )
                print(
                    f"{Colors.WARNING}Для поддержки GPU также требуется совместимый NVIDIA CUDA Toolkit.{Colors.ENDC}"
                )
                sys.exit(1)
    else:
        print(f"\n{Colors.OKBLUE}Пропускаем установку llama-cpp-python.{Colors.ENDC}")

    print(f"\n{Colors.OKGREEN}Установка завершена. Запуск приложения...{Colors.ENDC}")
    if not run_command_live([str(python_executable), "run_desktop.py"]):
        sys.exit(1)


if __name__ == "__main__":
    main()