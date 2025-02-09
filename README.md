# Aider API Server

A FastAPI-based API server that provides a streaming interface to run Aider commands via HTTP requests. This server allows you to send files and instructions to Aider and receive real-time streaming responses.

## Features

- Stream Aider output in real-time
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

```
python3 aider_api.py
```

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
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode())
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
}).then((response) => {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  function read() {
    reader.read().then(({ done, value }) => {
      if (done) return;
      console.log(decoder.decode(value));
      read();
    });
  }

  read();
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

Environment variables:

- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)
- `LOG_LEVEL`: Logging level (default: info)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License
