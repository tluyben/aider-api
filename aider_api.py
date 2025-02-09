from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
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

async def collect_aider_output(message: str, files: Optional[dict[str, str]], auto_commits: bool, 
                            dirty_commits: bool, dry_run: bool, root: str = "."):
    
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
            "--message", shlex.quote(message),
            "--stream" if not dry_run else "--no-stream",
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
        stdout_lines = []
        stderr_lines = []
        
        while True:
            try:
                # Read from stdout and stderr concurrently
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

        # Wait for the process to complete if no errors
        await process.wait()

        # If not a dry run and files were provided, read the modified files and yield their contents
        # if not dry_run and files:
        #     yield "\n--- Modified Files ---\n"
        #     for filename in files.keys():
        #         file_path = os.path.join(temp_dir, filename)
        #         if os.path.exists(file_path):
        #             with open(file_path, 'r') as f:
        #                 content = f.read()
        #             yield f"\n--- {filename} ---\n{content}\n"

        # Return collected output

        return_content = {
            "raw-stdout": "".join(stdout_lines),
            "raw-stderr": "".join(stderr_lines)
        }

        # if the raw-stdout contains https://aider.chat/docs/troubleshooting then we add a error: 'something went wrong' to the return_content  
        if "https://aider.chat/docs/troubleshooting" in return_content["raw-stdout"]:
            return_content["error"] = "something went wrong"
            
            # now we figure WHAT went wrong, if the stdout contains 'models-and-keys.html' then we add a error: 'model not found' to the return_content
            if "models-and-keys.html" in return_content["raw-stdout"]:
                return_content["error"] += ", AI key or model not found"            

        return return_content

@app.post("/run-aider")
async def run_aider(request: AiderRequest):
    try:
        result = await collect_aider_output(
            request.message,
            request.files,
            request.auto_commits,
            request.dirty_commits,
            request.dry_run,
            request.root
        )
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
