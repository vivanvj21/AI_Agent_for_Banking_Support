@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM Autonomous Bank Assistant — Windows deployment helper
REM
REM Usage:
REM   deploy.bat setup      Install deps into a venv
REM   deploy.bat dev        Run Streamlit (local)
REM   deploy.bat api        Run FastAPI (local)
REM   deploy.bat docker     Build and start Docker Compose
REM   deploy.bat stop       Stop Docker Compose
REM   deploy.bat logs       Tail Docker Compose logs
REM   deploy.bat health     Check API health endpoint
REM   deploy.bat init-db    Initialize the database
REM ─────────────────────────────────────────────────────────────────────────────

SET COMMAND=%1
IF "%COMMAND%"=="" SET COMMAND=help

IF "%COMMAND%"=="setup" GOTO :setup
IF "%COMMAND%"=="dev" GOTO :dev
IF "%COMMAND%"=="api" GOTO :api
IF "%COMMAND%"=="docker" GOTO :docker
IF "%COMMAND%"=="stop" GOTO :stop
IF "%COMMAND%"=="logs" GOTO :logs
IF "%COMMAND%"=="health" GOTO :health
IF "%COMMAND%"=="init-db" GOTO :init_db
IF "%COMMAND%"=="help" GOTO :help
GOTO :unknown

:setup
ECHO [INFO] Creating virtual environment...
python -m venv .venv
CALL .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
ECHO [OK] Virtual environment ready.
ECHO.
ECHO Next steps:
ECHO   1. copy .env.example .env
ECHO   2. Edit .env and set ANTHROPIC_API_KEY
ECHO   3. python start.py check
ECHO   4. python start.py
GOTO :end

:dev
IF NOT EXIST ".env" (
    ECHO [WARN] .env not found. Copying .env.example...
    copy .env.example .env
    ECHO [WARN] Edit .env and set ANTHROPIC_API_KEY, then re-run.
    EXIT /B 1
)
IF EXIST ".venv\Scripts\activate.bat" CALL .venv\Scripts\activate.bat
ECHO [INFO] Starting Streamlit UI...
python start.py streamlit
GOTO :end

:api
IF NOT EXIST ".env" (
    ECHO [WARN] .env not found. Copy .env.example to .env first.
    EXIT /B 1
)
IF EXIST ".venv\Scripts\activate.bat" CALL .venv\Scripts\activate.bat
ECHO [INFO] Starting FastAPI (dev, auto-reload)...
python start.py api --reload
GOTO :end

:docker
IF NOT EXIST ".env" (
    ECHO [WARN] .env not found. Copying .env.example...
    copy .env.example .env
    ECHO [WARN] Edit .env and set ANTHROPIC_API_KEY, then re-run.
    EXIT /B 1
)
ECHO [INFO] Building and starting Docker Compose stack...
docker compose up --build -d
ECHO [OK] Stack started.
ECHO.
ECHO   Streamlit UI : http://localhost:8501
ECHO   FastAPI      : http://localhost:8000
ECHO   API Docs     : http://localhost:8000/docs
GOTO :end

:stop
ECHO [INFO] Stopping Docker Compose...
docker compose down
ECHO [OK] Stopped.
GOTO :end

:logs
docker compose logs -f --tail=100
GOTO :end

:health
ECHO [INFO] Checking health at http://localhost:8000/health...
curl -s http://localhost:8000/health
ECHO.
GOTO :end

:init_db
IF EXIST ".venv\Scripts\activate.bat" CALL .venv\Scripts\activate.bat
ECHO [INFO] Initializing database...
python start.py init-db
ECHO [OK] Done.
GOTO :end

:help
ECHO.
ECHO   Autonomous Bank Assistant — deployment helper (Windows)
ECHO.
ECHO   Usage: deploy.bat ^<command^>
ECHO.
ECHO   Commands:
ECHO     setup      Create venv and install Python dependencies
ECHO     dev        Run Streamlit UI locally
ECHO     api        Run FastAPI locally (with auto-reload)
ECHO     docker     Build and start Docker Compose
ECHO     stop       Stop Docker Compose services
ECHO     logs       Tail Docker Compose logs
ECHO     health     Check FastAPI /health endpoint
ECHO     init-db    Initialize/seed SQLite database
ECHO.
GOTO :end

:unknown
ECHO [ERROR] Unknown command: %COMMAND%
ECHO Run 'deploy.bat help' for usage.
EXIT /B 1

:end
