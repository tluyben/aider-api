#!/usr/bin/env python3
import argparse
import json
import os
import readline
import requests
import sseclient
import sys
from typing import Dict

def main():
    parser = argparse.ArgumentParser(description='Interactive chat with Aider API')
    parser.add_argument('--port', type=int, default=8000, help='Port number (default: 8000)')
    parser.add_argument('--no-stream', action='store_true', help='Disable streaming mode')
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
                "dry_run": False,
                "stream": not args.no_stream
            }

            if args.no_stream:
                # Non-streaming mode: Get JSON response
                response = requests.post(url, json=data)
                response.raise_for_status()
                result = response.json()
                
                if result.get('raw-stdout'):
                    print("STDOUT:")
                    print(result['raw-stdout'])
                if result.get('raw-stderr'):
                    print("STDERR:")
                    print(result['raw-stderr'])
                if result.get('error'):
                    print("ERROR:")
                    print(result['error'])
            else:
                # Streaming mode: Handle SSE events
                headers = {'Accept': 'text/event-stream'}
                response = requests.post(url, json=data, stream=True, headers=headers)
                response.raise_for_status()
                
                client = sseclient.SSEClient(response)
                for event in client.events():
                    if event.event == 'progress':
                        data = json.loads(event.data)
                        if data['type'] == 'stdout':
                            print(data['content'])
                        elif data['type'] == 'stderr':
                            print("STDERR:", data['content'], file=sys.stderr)
                    elif event.event == 'complete':
                        result = json.loads(event.data)
                        if result.get('error'):
                            print("ERROR:", result['error'], file=sys.stderr)
                    elif event.event == 'error':
                        data = json.loads(event.data)
                        print("ERROR:", data.get('error', 'Unknown error'), file=sys.stderr)

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
