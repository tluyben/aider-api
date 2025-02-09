from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import subprocess
import asyncio
import sys
import os
from typing import Optional
import tempfile
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aider API Server")

class AiderRequest(BaseModel):
    message: str
    files: dict[str, str]  # filename: content
    auto_commits: bool = True
    dirty_commits: bool = True
    dry_run: bool = False
    root: str = "."  # Directory to run aider in, defaults to current directory

async def stream_aider_output(message: str, files: dict[str, str], auto_commits: bool, 
                            dirty_commits: bool, dry_run: bool, root: str = "."):
    logger.debug(f"Starting stream_aider_output with message: {message}")
    logger.debug(f"Files to process: {list(files.keys())}")
    # Create a temporary directory to store the files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write the files to the temporary directory
        for filename, content in files.items():
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(content)

        # Get the aider executable from the venv's bin directory
        venv_dir = os.path.dirname(os.path.dirname(sys.executable))
        aider_path = os.path.join(venv_dir, 'bin', 'aider')
        
        # Prepare the aider command
        cmd = [
            aider_path,
            "--message", message,
            "--stream" if not dry_run else "--no-stream",
            "--auto-commits" if auto_commits else "--no-auto-commits",
            "--dirty-commits" if dirty_commits else "--no-dirty-commits",
            "--dry-run" if dry_run else "--no-dry-run"
        ]
        
        # Add model if specified in environment
        if "AIDER_MODEL" in os.environ:
            cmd.extend(["--model", os.environ["AIDER_MODEL"]])
            
        # Add files
        cmd.extend([os.path.join(temp_dir, f) for f in files.keys()])

        logger.debug(f"Executing command: {' '.join(cmd)}")
        logger.debug(f"Working directory: {os.path.abspath(root)}")
        
        logger.debug(f"Using aider from: {aider_path}")
        logger.debug(f"Executing command: {' '.join(cmd)}")
        
        # Create and start the process
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.abspath(root),
                env=os.environ  # Pass through environment variables
            )
        except Exception as e:
            logger.error(f"Failed to start process: {e}")
            yield f"Error: Failed to start aider process: {e}\n"
            return

        # Buffer for detecting error patterns
        error_buffer = []
        has_error = False

        # Stream the output
        while True:
            # Read from both stdout and stderr
            line = await process.stdout.readline()
            err_line = await process.stderr.readline()
            
            if not line and not err_line:
                break
            
            if line:
                decoded_line = line.decode()
                logger.debug(f"stdout: {decoded_line.strip()}")
                # Only yield the line once
                yield decoded_line
            
            if err_line:
                decoded_err = err_line.decode()
                logger.error(f"stderr: {decoded_err.strip()}")
                # Only yield errors from stderr
                yield f"Error: {decoded_err}"
                
            # Update error buffer only if we have a line from stdout
            if line:
                error_buffer.append(decoded_line)
                if len(error_buffer) > 3:  # Keep last 3 lines for context
                    error_buffer.pop(0)
                
                # Check for known error patterns
                error_text = "".join(error_buffer)
                if "No OpenAI API key provided" in error_text:
                    has_error = True
                    yield "Error: OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.\n"
                    break

        # If we encountered an error, drain stderr and exit
        if has_error:
            while True:
                line = await process.stderr.readline()
                if not line:
                    break
            return

        # Wait for the process to complete if no errors
        await process.wait()

        # If not a dry run, read the modified files and yield their contents
        if not dry_run:
            yield "\n--- Modified Files ---\n"
            for filename in files.keys():
                file_path = os.path.join(temp_dir, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                    yield f"\n--- {filename} ---\n{content}\n"

@app.post("/run-aider")
async def run_aider(request: AiderRequest):
    try:
        return StreamingResponse(
            stream_aider_output(
                request.message,
                request.files,
                request.auto_commits,
                request.dirty_commits,
                request.dry_run,
                request.root
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
