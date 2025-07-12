#!/bin/bash
set -e

# Default command if no arguments provided
if [ $# -eq 0 ]; then
    exec python main.py
fi

# Handle common commands without needing "python main.py" prefix
case "$1" in
    --help|-h)
        exec python main.py --help
        ;;
    --config)
        exec python main.py --config
        ;;
    --status)
        exec python main.py --status
        ;;
    --dry-run)
        exec python main.py --dry-run
        ;;
    --validate)
        exec python main.py --validate
        ;;
    --note)
        # Handle --note with argument
        if [ $# -lt 2 ]; then
            echo "Error: --note requires a note name argument"
            exit 1
        fi
        shift # Remove --note
        note_name="$1"
        shift # Remove note name
        exec python main.py --note "$note_name" "$@"
        ;;
    python|main.py)
        # If user explicitly calls python or main.py, pass through
        exec "$@"
        ;;
    *)
        # If it looks like a python main.py command, pass through
        if [[ "$1" == "python" && "$2" == "main.py" ]]; then
            exec "$@"
        else
            # Otherwise, assume it's arguments for main.py
            exec python main.py "$@"
        fi
        ;;
esac