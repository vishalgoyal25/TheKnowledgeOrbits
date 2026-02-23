/**
 * @file logger.ts
 * @description Professional, namespaced logging utility for TheKnowledgeOrbits frontend.
 *
 * ## Usage
 * ```ts
 * import { createLogger } from '@/lib/logger';
 * const logger = createLogger('Auth');
 *
 * logger.info('User logged in', { userId });
 * logger.warn('Token expiring soon');
 * logger.error('Login failed', error);
 * ```
 *
 * ## Behaviour
 * - **Development**: Logs are printed to the browser console with colour-coded
 *   namespace prefixes so you can filter by module (`[Auth]`, `[Bookmarks]`, etc.).
 * - **Production**: Only `warn` and `error` levels are emitted (info/debug is
 *   silenced). In a future phase these can be wired to Sentry or a remote sink.
 */

type LogLevel = "debug" | "info" | "warn" | "error";

/** Colour palette for dev console — one colour per namespace instance */
const NAMESPACE_COLOURS = [
  "#7C3AED", // violet
  "#0891B2", // cyan
  "#059669", // emerald
  "#D97706", // amber
  "#DC2626", // red
  "#2563EB", // blue
  "#DB2777", // pink
  "#65A30D", // lime
];

let _colourIndex = 0;
const _colourMap = new Map<string, string>();

function getColour(namespace: string): string {
  if (!_colourMap.has(namespace)) {
    _colourMap.set(
      namespace,
      NAMESPACE_COLOURS[_colourIndex++ % NAMESPACE_COLOURS.length],
    );
  }
  return _colourMap.get(namespace)!;
}

const IS_PRODUCTION = process.env.NODE_ENV === "production";

/** Determines whether a given log level should be emitted in the current env. */
function shouldLog(level: LogLevel): boolean {
  if (IS_PRODUCTION) {
    // Silence debug / info in production to reduce noise
    return level === "warn" || level === "error";
  }
  return true;
}

// Map log levels to native console methods to avoid direct console.* usage
const CONSOLE_METHODS: Record<LogLevel, (...args: unknown[]) => void> = {
  debug: (...args) => console.debug(...args), // eslint-disable-line no-console
  info: (...args) => console.info(...args), // eslint-disable-line no-console
  warn: (...args) => console.warn(...args), // eslint-disable-line no-console
  error: (...args) => console.error(...args), // eslint-disable-line no-console
};

const LEVEL_STYLES: Record<LogLevel, string> = {
  debug: "color: #6B7280; font-weight: normal",
  info: "font-weight: bold",
  warn: "color: #D97706; font-weight: bold",
  error: "color: #DC2626; font-weight: bold",
};

export interface Logger {
  /** Fine-grained information typically of interest when diagnosing problems. */
  debug(message: string, ...args: unknown[]): void;
  /** General operational info about what the application is doing. */
  info(message: string, ...args: unknown[]): void;
  /** Potentially harmful situations that do not stop execution. */
  warn(message: string, ...args: unknown[]): void;
  /** Error events that might still allow the application to continue running. */
  error(message: string, ...args: unknown[]): void;
}

/**
 * Creates a namespaced logger instance.
 *
 * @param namespace - A short descriptive label, e.g. `'Auth'`, `'Bookmarks'`.
 * @returns A `Logger` object with `debug`, `info`, `warn`, and `error` methods.
 *
 * @example
 * const logger = createLogger('ReadingProgress');
 * logger.info('Progress saved', { percent: 42 });
 * // → [ReadingProgress] Progress saved { percent: 42 }
 */
export function createLogger(namespace: string): Logger {
  const colour = getColour(namespace);

  function log(level: LogLevel, message: string, args: unknown[]): void {
    if (!shouldLog(level)) return;

    const prefix = `[${namespace}]`;

    if (typeof window !== "undefined") {
      // Browser: use %c styling
      CONSOLE_METHODS[level](
        `%c${prefix}%c ${message}`,
        `color: ${colour}; font-weight: bold`,
        LEVEL_STYLES[level],
        ...args,
      );
    } else {
      // Node / SSR: use Chalk for terminal colours
      // Note: Chalk is imported dynamically to avoid breaking browser builds
      try {
        // We use a hacky way to get chalk since it's ESM only and this might be CJS/SSR transpiled
        // In modern Next.js this usually works fine.
        const chalk = require("chalk");
        const levelColours: Record<LogLevel, any> = {
          debug: chalk.gray,
          info: chalk.blue.bold,
          warn: chalk.yellow.bold,
          error: chalk.red.bold,
        };

        const formattedPrefix = chalk.hex(colour).bold(prefix);
        const formattedMessage = levelColours[level](message);

        CONSOLE_METHODS[level](formattedPrefix, formattedMessage, ...args);
      } catch (e) {
        // Fallback to plain text if chalk is unavailable
        CONSOLE_METHODS[level](prefix, message, ...args);
      }
    }
  }

  return {
    debug: (message, ...args) => log("debug", message, args),
    info: (message, ...args) => log("info", message, args),
    warn: (message, ...args) => log("warn", message, args),
    error: (message, ...args) => log("error", message, args),
  };
}

/** Convenience pre-built logger for one-off use without creating a namespace. */
export const logger = createLogger("App");
