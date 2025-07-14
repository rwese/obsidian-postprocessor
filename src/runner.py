"""
Script runner for executing post-processing scripts.

Handles execution of external scripts with proper error handling and logging.
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ScriptRunner:
    """Executes post-processing scripts on voice memos."""

    def __init__(self, script_path: Path, timeout: int = 300):
        self.script_path = script_path
        self.timeout = timeout
        self._validate_script()

    def _validate_script(self) -> None:
        """Validate that the script exists and is executable."""
        if not self.script_path.exists():
            raise FileNotFoundError(f"Script not found: {self.script_path}")

        if not self.script_path.is_file():
            raise ValueError(f"Script path is not a file: {self.script_path}")

        # Check if it's a Python script
        if self.script_path.suffix not in [".py", ".pyw"]:
            logger.warning(f"Script may not be a Python file: {self.script_path}")

    def run_script(
        self,
        note_path: Path,
        voice_file_path: Path,
        env_vars: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> bool:
        """
        Execute the post-processing script.

        Args:
            note_path: Path to the note file
            voice_file_path: Path to the voice file
            env_vars: Additional environment variables
            dry_run: If True, only show what would be executed

        Returns:
            True if script executed successfully, False otherwise
        """
        try:
            # Prepare command
            cmd = [
                "python",
                str(self.script_path),
                str(note_path),
                str(voice_file_path),
            ]

            # Prepare environment
            env = self._prepare_environment(env_vars)

            if dry_run:
                logger.info("DRY RUN - Would execute script:")
                logger.info(f"  Command: {' '.join(cmd)}")
                logger.info(f"  Working directory: {self.script_path.parent}")
                logger.info(f"  Timeout: {self.timeout} seconds")

                # Show what the script would do based on analysis
                self._show_script_preview(note_path, voice_file_path, env)
                return True

            logger.info(f"Executing script: {' '.join(cmd)}")

            # Execute script
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=self.script_path.parent,
            )

            # Log output
            if result.stdout:
                logger.info(f"Script output: {result.stdout}")

            if result.stderr:
                if result.returncode == 0:
                    logger.warning(f"Script stderr: {result.stderr}")
                else:
                    logger.error(f"Script stderr: {result.stderr}")

            # Check return code
            if result.returncode == 0:
                logger.info(f"Script executed successfully for {voice_file_path}")
                return True
            else:
                logger.error(f"Script failed with return code {result.returncode}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Script execution timed out after {self.timeout} seconds")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Script execution failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error executing script: {e}")
            return False

    def _prepare_environment(self, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Prepare environment variables for script execution.

        Args:
            env_vars: Additional environment variables

        Returns:
            Environment dictionary
        """
        import os

        # Start with current environment
        env = os.environ.copy()

        # Add custom environment variables if provided
        if env_vars:
            env.update(env_vars)

        return env

    def _show_script_preview(self, note_path: Path, voice_file_path: Path, env: Dict[str, str]) -> None:
        """Show what the script would do in dry run mode."""
        logger.info("  Script actions preview:")

        # Check if this is the transcription script
        if "add_transcript_to_voicememo.py" in self.script_path.name:
            # Get configuration from environment
            whisper_api_url = env.get("WHISPER_API_URL", "http://host.docker.internal:8020")
            whisper_model = env.get("WHISPER_MODEL", "small")
            whisper_language = env.get("WHISPER_LANGUAGE", "auto-detect")

            logger.info(f"    1. Check API health at: {whisper_api_url}/health")
            logger.info(f"    2. Get available models from: {whisper_api_url}/models")
            logger.info(f"    3. Auto-detect language from filename: {voice_file_path.name}")
            logger.info(f"    4. Transcribe audio via POST: {whisper_api_url}/transcribe")
            logger.info(f"       - Model: {whisper_model}")
            logger.info(f"       - Language: {whisper_language}")
            logger.info(f"       - Audio file: {voice_file_path.name}")
            logger.info(f"    5. Read note content from: {note_path}")
            logger.info(f"    6. Find voice embed: ![[{voice_file_path.name}]]")
            logger.info("    7. Add transcript as blockquote after embed")
            logger.info(f"    8. Write updated content back to: {note_path}")
        else:
            logger.info(f"    Custom script would process: {voice_file_path.name}")
            logger.info(f"    Note file: {note_path}")

    def validate_script_interface(self) -> bool:
        """
        Validate that the script has the expected interface.

        Returns:
            True if script interface is valid
        """
        try:
            # Try to run script with --help to check interface
            cmd = ["python", str(self.script_path), "--help"]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.script_path.parent,
            )

            # If --help works, assume script has proper interface
            if result.returncode == 0:
                logger.debug("Script interface validation passed")
                return True

            # If --help doesn't work, try with dummy args to check error message
            cmd = [
                "python",
                str(self.script_path),
                "dummy_note.md",
                "dummy_voice.webm",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.script_path.parent,
            )

            # Check if script accepts the arguments (even if it fails due to dummy files)
            stderr_lower = result.stderr.lower()
            if (
                "usage:" in stderr_lower
                or "error:" in stderr_lower
                or "note_path" in stderr_lower
                or "voice" in stderr_lower
                or "file" in stderr_lower
            ):
                logger.debug("Script appears to accept expected arguments")
                return True

            # If script exists and runs without crashing, consider it valid
            if result.returncode is not None:
                logger.debug("Script executed without fatal errors, considering valid")
                return True

            logger.warning("Could not validate script interface")
            return False

        except Exception as e:
            logger.error(f"Error validating script interface: {e}")
            return False


class MockScriptRunner(ScriptRunner):
    """Mock script runner for testing purposes."""

    def __init__(self, script_path: Path, should_succeed: bool = True):
        self.script_path = script_path
        self.should_succeed = should_succeed
        self.timeout = 300
        self.executed_calls = []

    def _validate_script(self) -> None:
        """Skip validation for mock runner."""
        pass

    def run_script(
        self,
        note_path: Path,
        voice_file_path: Path,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Mock script execution."""
        call_info = {
            "note_path": note_path,
            "voice_file_path": voice_file_path,
            "env_vars": env_vars,
        }
        self.executed_calls.append(call_info)

        logger.info(f"Mock script execution: {note_path} -> {voice_file_path}")
        return self.should_succeed

    def validate_script_interface(self) -> bool:
        """Mock validation always passes."""
        return True
