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

app = FastAPI(title="Aider API Server")

class AiderRequest(BaseModel):
    message: str
    files: dict[str, str]  # filename: content
    auto_commits: bool = True
    dirty_commits: bool = True
    dry_run: bool = False

async def stream_aider_output(message: str, files: dict[str, str], auto_commits: bool, 
                            dirty_commits: bool, dry_run: bool):
    # Create a temporary directory to store the files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write the files to the temporary directory
        for filename, content in files.items():
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(content)

        # Prepare the aider command
        cmd = [
            "aider",
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

        # Create and start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=temp_dir
        )

        # Stream the output
        while True:
            # Read one line at a time
            line = await process.stdout.readline()
            if not line:
                break
            yield line.decode()

        # Wait for the process to complete
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
                request.dry_run
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
