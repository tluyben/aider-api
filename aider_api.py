from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
import subprocess
import asyncio
import sys
import os
from typing import Optional
import tempfile
import shutil
import logging
import shlex
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    filename='aider_api.log',  # Log to file instead of stdout
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aider API Server")

class AiderRequest(BaseModel):
    message: str
    files: Optional[dict[str, str]] = None  # filename: content, optional
    auto_commits: bool = True
    dirty_commits: bool = True
    dry_run: bool = False
    root: str = "."  # Directory to run aider in, defaults to current directory
    stream: bool = True  # Whether to stream the response using SSE

async def collect_aider_output(message: str, files: Optional[dict[str, str]], auto_commits: bool, 
                            dirty_commits: bool, dry_run: bool, root: str = ".", stream: bool = True):
    
    logger.debug(f"Starting stream_aider_output with message: {message}")
    logger.debug(f"Files to process: {list(files.keys()) if files else 'None'}")
    # Create a temporary directory to store the files if needed
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write the files to the temporary directory if provided
        if files:
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
            # "--stream" if not dry_run else "--no-stream",
            "--auto-commits" if auto_commits else "--no-auto-commits",
            "--dirty-commits" if dirty_commits else "--no-dirty-commits",
            "--dry-run" if dry_run else "--no-dry-run", 
            "--no-show-model-warnings", # Do not show model warnings
            "--yes"  # Automatically confirm any prompts
        ]
        
        # Add model if specified in environment
        # if "AIDER_MODEL" in os.environ:
        #     cmd.extend(["--model", f'"{os.environ["AIDER_MODEL"]}"'])
            
        # Add files if provided
        if files:
            cmd.extend([os.path.join(temp_dir, f) for f in files.keys()])

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
            error_msg = f"Error: Failed to start aider process: {e}\n"
            logger.error(error_msg)
            return {
                "raw-stdout": "",
                "raw-stderr": error_msg
            }

        # Collect output
        if stream:
            async def event_generator():
                stdout_lines = []
                stderr_lines = []
                
                while True:
                    try:
                        # Read from stdout and stderr concurrently
                        stdout_data, stderr_data = await asyncio.gather(
                            process.stdout.readline(),
                            process.stderr.readline()
                        )
                        
                        if stdout_data:
                            line = stdout_data.decode().rstrip()
                            stdout_lines.append(line + "\n")
                            yield {
                                "event": "progress",
                                "data": json.dumps({"type": "stdout", "content": line})
                            }
                        if stderr_data:
                            line = stderr_data.decode().rstrip()
                            stderr_lines.append(line + "\n")
                            yield {
                                "event": "progress",
                                "data": json.dumps({"type": "stderr", "content": line})
                            }
                            
                        if not stdout_data and not stderr_data:
                            # Process complete, send final result
                            result = {
                                "raw-stdout": "".join(stdout_lines),
                                "raw-stderr": "".join(stderr_lines)
                            }
                            
                            if "https://aider.chat/docs/troubleshooting" in result["raw-stdout"]:
                                result["error"] = "something went wrong"
                                if "models-and-keys.html" in result["raw-stdout"]:
                                    result["error"] += ", AI key or model not found"
                            
                            yield {
                                "event": "complete",
                                "data": json.dumps(result)
                            }
                            break
                            
                    except Exception as e:
                        logger.error(f"Error processing output: {e}")
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": f"Failed to process output: {e}"})
                        }
                        break

            return event_generator()
        else:
            # Non-streaming mode
            stdout_lines = []
            stderr_lines = []
            
            while True:
                try:
                    stdout_data, stderr_data = await asyncio.gather(
                        process.stdout.read(),
                        process.stderr.read()
                    )
                    
                    if stdout_data:
                        stdout_lines.extend(stdout_data.decode().splitlines(True))
                    if stderr_data:
                        stderr_lines.extend(stderr_data.decode().splitlines(True))
                        
                    if not stdout_data and not stderr_data:
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing output: {e}")
                    stderr_lines.append(f"Error: Failed to process output: {e}\n")
                    break

            await process.wait()

            result = {
                "raw-stdout": "".join(stdout_lines),
                "raw-stderr": "".join(stderr_lines)
            }

            if "https://aider.chat/docs/troubleshooting" in result["raw-stdout"]:
                result["error"] = "something went wrong"
                if "models-and-keys.html" in result["raw-stdout"]:
                    result["error"] += ", AI key or model not found"

            return result

@app.post("/run-aider")
async def run_aider(request: AiderRequest):
    try:
        result = await collect_aider_output(
            request.message,
            request.files,
            request.auto_commits,
            request.dirty_commits,
            request.dry_run,
            request.root,
            request.stream
        )
        
        if request.stream:
            return EventSourceResponse(result)
        else:
            return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import argparse
    import uvicorn
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Run the Aider API server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to listen on (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8000, help='Port to listen on (default: 8000)')
    
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
