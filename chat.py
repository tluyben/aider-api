#!/usr/bin/env python3
import argparse
import json
import os
import readline
import requests
import sys
from typing import Dict

def main():
    parser = argparse.ArgumentParser(description='Interactive chat with Aider API')
    parser.add_argument('--port', type=int, default=8000, help='Port number (default: 8000)')
    parser.add_argument('files', nargs='*', help='Initial files to edit')
    args = parser.parse_args()

    # Initialize file contents
    files: Dict[str, str] = {}
    for file in args.files:
        try:
            with open(file, 'r') as f:
                files[file] = f.read()
        except Exception as e:
            print(f"Error reading {file}: {e}", file=sys.stderr)
            sys.exit(1)

    # Set up readline history
    histfile = os.path.join(os.path.expanduser("~"), ".aider_chat_history")
    try:
        readline.read_history_file(histfile)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass

    print("Chat session started. Type your messages (Ctrl+C to exit)")
    print("Files being edited:", list(files.keys()) or "none")
    print("Use Up/Down arrows for history")
    
    while True:
        try:
            # Get user input
            message = input("\n> ")
            if not message.strip():
                continue

            # Prepare the request
            url = f"http://localhost:{args.port}/run-aider"
            data = {
                "message": message,
                "files": files,
                "auto_commits": True,
                "dirty_commits": True,
                "dry_run": False
            }

            # Make the request and stream the response
            with requests.post(url, json=data, stream=True) as response:
                response.raise_for_status()
                in_file_section = False
                current_file = None
                file_content = []

                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue

                    # Check for file section markers
                    if line == "--- Modified Files ---":
                        in_file_section = True
                        continue
                    elif in_file_section and line.startswith("--- ") and line.endswith(" ---"):
                        if current_file and file_content:
                            # Update the files dict with the new content
                            files[current_file] = "\n".join(file_content)
                            file_content = []
                        current_file = line[4:-4]  # Extract filename from "--- filename ---"
                        continue
                    
                    if in_file_section and current_file:
                        file_content.append(line)
                    else:
                        try:
                            result = json.loads(line)
                            if 'raw-stdout' in result:
                                if result['raw-stdout']:
                                    print("STDOUT:")
                                    print(result['raw-stdout'])
                            if 'raw-stderr' in result:
                                if result['raw-stderr']:
                                    print("STDERR:")
                                    print(result['raw-stderr'])
                            if 'error' in result and result['error']:
                                print("ERROR:")
                                print(result['error'])
                        except json.JSONDecodeError:
                            # If it's not JSON, print the line as-is
                            print(line)

                # Handle the last file if any
                if current_file and file_content:
                    files[current_file] = "\n".join(file_content)

        except KeyboardInterrupt:
            print("\nExiting chat session")
            readline.write_history_file(histfile)
            break
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with API: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
