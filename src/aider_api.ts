import fastify, { FastifyInstance } from 'fastify';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs/promises';
import { FastifyRequest, FastifyReply } from 'fastify';

// Get the Node.js process
declare const process: {
  execPath: string;
  env: { [key: string]: string | undefined };
  argv: string[];
  exit: (code?: number) => never;
  cwd(): string;
};

// Configure logging
const logger = {
  debug: (msg: string) => {
    fs.appendFile('aider_api.log', `${new Date().toISOString()} - DEBUG - ${msg}\n`)
      .catch((err: Error) => console.error(err.message));
    console.debug(`${new Date().toISOString()} - DEBUG - ${msg}`);
  },
  error: (msg: string) => {
    fs.appendFile('aider_api.log', `${new Date().toISOString()} - ERROR - ${msg}\n`)
      .catch((err: Error) => console.error(err.message));
    console.error(`${new Date().toISOString()} - ERROR - ${msg}`);
  }
};

// Types
interface AiderRequest {
  message: string;
  files?: { [key: string]: string };
  auto_commits: boolean;
  dirty_commits: boolean;
  dry_run: boolean;
  root?: string;
  stream?: boolean;
}

interface AiderResponse {
  'raw-stdout': string;
  'raw-stderr': string;
  error?: string;
}

// Create Fastify instance
const app: FastifyInstance = fastify({
  logger: true
});

// Helper function to get aider executable path
function getAiderPath(): string {
  return path.join(process.cwd(), 'venv', 'bin', 'aider');
}

// Main function to collect aider output
async function collectAiderOutput(
  message: string,
  files: { [key: string]: string } | undefined,
  auto_commits: boolean,
  dirty_commits: boolean,
  dry_run: boolean,
  root: string = ".",
  stream: boolean = true
): Promise<AiderResponse | AsyncGenerator<string, void, unknown>> {
  logger.debug(`Starting collectAiderOutput with message: ${message}`);
  logger.debug(`Files to process: ${files ? Object.keys(files) : 'None'}`);

  try {
    // Get aider executable path
    const aiderPath = getAiderPath();
    logger.debug(`Using aider from: ${aiderPath}`);

    // Prepare the aider command
    const cmd = [
      aiderPath,
      "--message", message,
      auto_commits ? "--auto-commits" : "--no-auto-commits",
      dirty_commits ? "--dirty-commits" : "--no-dirty-commits",
      dry_run ? "--dry-run" : "--no-dry-run",
      "--no-show-model-warnings",
      "--yes"
    ];

    // Add files if provided
    if (files) {
      cmd.push(...Object.keys(files));
    }

    logger.debug(`Working directory: ${path.resolve(root)}`);
    logger.debug(`Executing command: ${cmd.join(' ')}`);

    // Create and start the process
    const childProcess = spawn(cmd[0], cmd.slice(1), {
      cwd: path.resolve(root),
      env: process.env
    });

    if (stream) {
      // Streaming mode using SSE
      return (async function* () {
        let stdoutLines: string[] = [];
        let stderrLines: string[] = [];

        try {
          await new Promise<void>((resolve, reject) => {
            childProcess.stdout.on('data', (data: Buffer) => {
              const line = data.toString().trim();
              if (line) {
                stdoutLines.push(line + '\n');
                return `event: progress\ndata: ${JSON.stringify({ type: 'stdout', content: line })}\n\n`;
              }
            });

            childProcess.stderr.on('data', (data: Buffer) => {
              const line = data.toString().trim();
              if (line) {
                stderrLines.push(line + '\n');
                return `event: progress\ndata: ${JSON.stringify({ type: 'stderr', content: line })}\n\n`;
              }
            });

            childProcess.on('close', () => {
              const result: AiderResponse = {
                'raw-stdout': stdoutLines.join(''),
                'raw-stderr': stderrLines.join('')
              };

              if (result['raw-stdout'].includes('https://aider.chat/docs/troubleshooting')) {
                result.error = 'something went wrong';
                if (result['raw-stdout'].includes('models-and-keys.html')) {
                  result.error += ', AI key or model not found';
                }
              }

              return `event: complete\ndata: ${JSON.stringify(result)}\n\n`;
              resolve();
            });

            childProcess.on('error', (error) => {
              return `event: error\ndata: ${JSON.stringify({ error: error.message })}\n\n`;
              reject(error);
            });
          });
        } catch (error) {
          yield `event: error\ndata: ${JSON.stringify({ error: String(error) })}\n\n`;
        }
      })();
    } else {
      // Non-streaming mode
      let stdoutData = '';
      let stderrData = '';

      // Collect output
      childProcess.stdout.on('data', (data: Buffer) => {
        stdoutData += data.toString();
      });

      childProcess.stderr.on('data', (data: Buffer) => {
        stderrData += data.toString();
      });

      // Wait for process to complete
      const exitCode = await new Promise<number>((resolve) => {
        childProcess.on('close', resolve);
      });

      const response: AiderResponse = {
        'raw-stdout': stdoutData,
        'raw-stderr': stderrData
      };

      // Check for specific error conditions in stdout
      if (stdoutData.includes('https://aider.chat/docs/troubleshooting')) {
        response.error = 'something went wrong';
        
        if (stdoutData.includes('models-and-keys.html')) {
          response.error += ', AI key or model not found';
        }
      }

      return response;
    }

  } catch (error) {
    logger.error(`Error: Failed to execute aider process: ${error instanceof Error ? error.message : String(error)}`);
    return {
      'raw-stdout': '',
      'raw-stderr': `Error: Failed to execute aider process: ${error instanceof Error ? error.message : String(error)}\n`
    };
  }
}

// Define the POST endpoint
app.post('/run-aider', async (request: FastifyRequest, reply: FastifyReply) => {
  try {
    const { message, files, auto_commits, dirty_commits, dry_run, root, stream = true } = request.body as AiderRequest;
    const result = await collectAiderOutput(
      message,
      files,
      auto_commits,
      dirty_commits,
      dry_run,
      root,
      stream
    );

    if (stream) {
      reply.raw.setHeader('Content-Type', 'text/event-stream');
      reply.raw.setHeader('Cache-Control', 'no-cache');
      reply.raw.setHeader('Connection', 'keep-alive');

      // Handle client disconnect
      request.raw.on('close', () => {
        reply.raw.end();
      });

      // Stream SSE events
      try {
        for await (const event of result as AsyncGenerator<string, void, unknown>) {
          if (event) {
            reply.raw.write(event);
          }
        }
      } catch (error) {
        logger.error(`Error streaming events: ${error}`);
        reply.raw.write(`event: error\ndata: ${JSON.stringify({ error: String(error) })}\n\n`);
      } finally {
        reply.raw.end();
      }
    } else {
      return result;
    }
  } catch (error) {
    logger.error(`Error in /run-aider endpoint: ${error instanceof Error ? error.message : String(error)}`);
    reply.status(500).send({ error: error instanceof Error ? error.message : String(error) });
  }
});

// Main function to start the server
async function main() {
  try {
    const args = process.argv.slice(2);
    let host = '127.0.0.1';
    let port = 8000;

    // Parse command line arguments
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--host' && i + 1 < args.length) {
        host = args[i + 1];
        i++;
      } else if (args[i] === '--port' && i + 1 < args.length) {
        port = parseInt(args[i + 1], 10);
        i++;
      }
    }

    await app.listen({ host, port });
    console.log(`Server running at http://${host}:${port}`);
  } catch (err) {
    console.error('Error starting server:', err);
    process.exit(1);
  }
}

// Start the server if this is the main module
if (require.main === module) {
  main();
}

export default app;
