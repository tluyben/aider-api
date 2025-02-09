# Aider API Server

A FastAPI-based API server that provides an interface to run Aider commands via HTTP requests. This server allows you to send files and instructions to Aider and receive structured responses.

## Features

- Structured JSON responses with stdout/stderr separation
- Send multiple files in a single request
- Configure Aider options (auto-commits, dirty-commits, dry-run)
- Temporary file handling for safety
- Docker support
- API documentation with Swagger UI

## Installation

### Local Setup with venv

1. Clone the repository:

```bash
git clone https://github.com/yourusername/aider-api
cd aider-api
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Make sure we have the latest aider

```
venv/bin/python -m pip install --upgrade aider-chat
```

4. Run the server

```bash
python3 aider_api.py [--host HOST] [--port PORT]
```

The server can be configured with the following command line arguments:
- `--host`: Host to listen on (default: 127.0.0.1)
- `--port`: Port to listen on (default: 8000)

### Docker Setup

1. Build and run using Docker:

```bash
docker build -t aider-api .
docker run -p 8000:8000 aider-api
```

2. Or use Docker Compose:

```bash
docker-compose up
```

## Usage

### Interactive Chat Demo

The repository includes a chat.py script that provides an interactive command-line interface to the API:

```bash
python3 chat.py [--port PORT] [files ...]
```

Options:
- `--port`: Port number where the API server is running (default: 8000)
- `files`: Optional list of files to edit in the chat session

The chat script allows you to:
- Interactively send messages to the API
- Edit multiple files in a session
- See stdout/stderr output clearly separated
- Get error messages in a user-friendly format

### API Usage

The server runs on `http://localhost:8000` by default.

### API Endpoints

#### POST /run-aider

Send a POST request with JSON payload containing:

- `message`: The instruction for Aider
- `files`: Dictionary of filename to file content
- `auto_commits`: (optional) Enable/disable auto commits (default: true)
- `dirty_commits`: (optional) Enable/disable dirty commits (default: true)
- `dry_run`: (optional) Enable/disable dry run mode (default: false)

### Example Usage

1. Using curl:

```bash
curl -X POST http://localhost:8000/run-aider \
  -H "Content-Type: application/json" \
  -d '{
    "message": "add a docstring to this function",
    "files": {
      "example.py": "def hello():\n    print(\"Hello, World!\")"
    }
  }'
```

```bash
curl -X POST http://localhost:8000/run-aider \
  -H "Content-Type: application/json" \
  -d '{
    "message": "/help"
  }'
```

2. Using Python requests:

```python
import requests

response = requests.post(
    "http://localhost:8000/run-aider",
    json={
        "message": "add a docstring to this function",
        "files": {
            "example.py": "def hello():\n    print(\"Hello, World!\")"
        }
    },
)

# The response is now a JSON object with the following structure:
response_json = response.json()
print("STDOUT:", response_json["raw-stdout"])
print("STDERR:", response_json["raw-stderr"])
if "error" in response_json:
    print("ERROR:", response_json["error"])
```

3. Using JavaScript fetch:

```javascript
fetch("http://localhost:8000/run-aider", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    message: "add a docstring to this function",
    files: {
      "example.py": 'def hello():\n    print("Hello, World!")',
    },
  }),
})
  .then(response => response.json())
  .then(data => {
    console.log("STDOUT:", data["raw-stdout"]);
    console.log("STDERR:", data["raw-stderr"]);
    if (data.error) {
      console.log("ERROR:", data.error);
    }
  });
});
```

## Development

### Running Tests

```bash
pytest tests/
```

### API Documentation

The API documentation is available at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Configuration

The server is configured through command line arguments when starting:

```bash
python3 aider_api.py [--host HOST] [--port PORT]
```

Arguments:
- `--host`: Host to listen on (default: 127.0.0.1)
- `--port`: Port to listen on (default: 8000)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
