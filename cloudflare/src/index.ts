import { Container, getRandom } from "@cloudflare/containers";

interface Env extends Cloudflare.Env {
  OPENAI_API_KEY?: string;
}

const API_PREFIX = "/api/v1";
const GATEWAY_INSTANCE_COUNT = 5;
const AGENT_INSTANCE_COUNT = 5;

export class GatewayContainer extends Container<Env> {
  defaultPort = 8000;
  pingEndpoint = "health";
  sleepAfter = "5m";

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
      GATEWAY_DATABASE_URL: env.DATABASE_URL,
      GATEWAY_REDIS_URL: env.REDIS_URL,
      GATEWAY_S3_ENDPOINT_URL: env.R2_ENDPOINT_URL,
      GATEWAY_S3_ACCESS_KEY: env.R2_ACCESS_KEY_ID,
      GATEWAY_S3_SECRET_KEY: env.R2_SECRET_ACCESS_KEY,
      GATEWAY_S3_BUCKET_NAME: env.R2_BUCKET_NAME,
      GATEWAY_AGENT_SERVICE_URL: "",
      DB_POOL_SIZE: "3",
      DB_MAX_OVERFLOW: "2",
      GEMINI_API_KEY: env.GEMINI_API_KEY,
      OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
      GATEWAY_LOG_LEVEL: "INFO",
    };
  }
}

export class AgentContainer extends Container<Env> {
  defaultPort = 8001;
  pingEndpoint = "health";
  sleepAfter = "5m";

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
      AGENT_DATABASE_URL: env.DATABASE_URL,
      AGENT_REDIS_URL: env.REDIS_URL,
      DB_POOL_SIZE: "3",
      DB_MAX_OVERFLOW: "2",
      AGENT_GEMINI_API_KEY: env.GEMINI_API_KEY,
      AGENT_OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
      GEMINI_API_KEY: env.GEMINI_API_KEY,
      OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
      AGENT_LOG_LEVEL: "INFO",
    };
  }
}

export class CeleryContainer extends Container<Env> {
  defaultPort = 8002;
  pingEndpoint = "health";
  sleepAfter = "2m";

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
      WORKER_DATABASE_URL: env.DATABASE_URL,
      WORKER_REDIS_URL: env.REDIS_URL,
      DB_POOL_SIZE: "3",
      DB_MAX_OVERFLOW: "2",
      WORKER_S3_ENDPOINT_URL: env.R2_ENDPOINT_URL,
      WORKER_S3_ACCESS_KEY: env.R2_ACCESS_KEY_ID,
      WORKER_S3_SECRET_KEY: env.R2_SECRET_ACCESS_KEY,
      WORKER_S3_BUCKET_NAME: env.R2_BUCKET_NAME,
      WORKER_DEEPGRAM_API_KEY: env.DEEPGRAM_API_KEY,
      WORKER_GEMINI_API_KEY: env.GEMINI_API_KEY,
      WORKER_OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
      WORKER_DEFAULT_LLM_MODEL: "gemini-3.8-flash",
      GEMINI_API_KEY: env.GEMINI_API_KEY,
      OPENAI_API_KEY: env.OPENAI_API_KEY ?? "",
    };
  }
}

function isAgentRoute(pathname: string): boolean {
  return pathname === `${API_PREFIX}/agent` || pathname.startsWith(`${API_PREFIX}/agent/`);
}

function isAgentHealthRoute(pathname: string): boolean {
  return pathname === `${API_PREFIX}/system/status`;
}

function rewriteAudioStreamPath(request: Request): Request {
  const url = new URL(request.url);
  const sessionId = url.pathname.slice("/ws/audio/".length);
  url.pathname = `${API_PREFIX}/audio/stream/${sessionId}`;
  return new Request(url, request);
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith(`${API_PREFIX}/`)) {
      if (isAgentRoute(url.pathname)) {
        const container = await getRandom(env.AGENT, AGENT_INSTANCE_COUNT);
        return container.fetch(request);
      }

      const container = await getRandom(env.GATEWAY, GATEWAY_INSTANCE_COUNT);
      const response = await container.fetch(
        url.pathname.startsWith("/ws/audio/")
          ? rewriteAudioStreamPath(request)
          : request,
      );

      if (!isAgentHealthRoute(url.pathname) || !response.ok) {
        return response;
      }

      const payload = (await response.json()) as Record<string, unknown>;
      let agentStatus = "OFFLINE";
      try {
        const agent = await (
          await getRandom(env.AGENT, AGENT_INSTANCE_COUNT)
        ).fetch(new Request(new URL("/health", request.url)));
        agentStatus = agent.ok ? "ONLINE" : "OFFLINE";
      } catch {
        agentStatus = "OFFLINE";
      }
      payload.agent = { status: agentStatus, port: 8001 };
      const headers = new Headers(response.headers);
      headers.delete("content-length");
      return Response.json(payload, {
        status: response.status,
        headers,
      });
    }

    if (url.pathname.startsWith("/ws/audio/")) {
      const container = await getRandom(env.GATEWAY, GATEWAY_INSTANCE_COUNT);
      return container.fetch(rewriteAudioStreamPath(request));
    }

    return env.ASSETS.fetch(request);
  },

  async scheduled(
    _controller: ScheduledController,
    env: Env,
    _context: ExecutionContext,
  ): Promise<void> {
    const health = await env.CELERY.getByName("celery-worker").fetch(
      new Request("http://container/health"),
    );
    if (!health.ok) {
      throw new Error(`Celery container health check failed: ${health.status}`);
    }
  },
} satisfies ExportedHandler<Env>;
