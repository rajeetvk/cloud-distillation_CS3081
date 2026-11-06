@echo off
setlocal enabledelayedexpansion

set PYTHON=python
set SUBSET=

:parse_args
if "%~1"=="" goto run_target
if /i "%~1"=="train" (
    set TARGET=train
    shift
    goto check_subset
)
if /i "%~1"=="up" (
    set TARGET=up
    shift
    goto parse_args
)
if /i "%~1"=="down" (
    set TARGET=down
    shift
    goto parse_args
)
if /i "%~1"=="test" (
    set TARGET=test
    shift
    goto parse_args
)
if /i "%~1"=="lint" (
    set TARGET=lint
    shift
    goto parse_args
)

:check_subset
if not "%~1"=="" (
    set ARG=%~1
    if "!ARG:~0,7!"=="SUBSET=" (
        set SUBSET=!ARG:~7!
        shift
        goto parse_args
    )
    if "!ARG:~0,7!"=="subset=" (
        set SUBSET=!ARG:~7!
        shift
        goto parse_args
    )
)

:run_target
if "%TARGET%"=="train" (
    if defined SUBSET (
        %PYTHON% training\train.py --subset %SUBSET%
    ) else (
        %PYTHON% training\train.py
    )
    exit /b %ERRORLEVEL%
)

if "%TARGET%"=="up" (
    k3d cluster create cloud-cluster --config cluster\k3d.yaml
    kubectl apply -f cluster\seaweedfs.yaml
    kubectl wait --namespace data --for=condition=ready pod -l app=seaweedfs --timeout=90s
    kubectl apply -f cluster\app.yaml
    exit /b %ERRORLEVEL%
)

if "%TARGET%"=="down" (
    k3d cluster delete cloud-cluster
    exit /b %ERRORLEVEL%
)

if "%TARGET%"=="test" (
    %PYTHON% -m unittest discover -s tests -p "test_*.py"
    exit /b %ERRORLEVEL%
)

if "%TARGET%"=="lint" (
    flake8 service training worker tools
    exit /b %ERRORLEVEL%
)

echo Unknown target: %TARGET%
exit /b 1
