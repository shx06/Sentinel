'use strict';

const config = require('../config');
const logger = require('./utils/logger');
const app = require('./app');

const server = app.listen(config.port, () => {
  logger.info(`Server running in ${config.env} mode on port ${config.port}`);
  logger.info(
    `Health check: http://localhost:${config.port}${config.api.prefix}/${config.api.version}/health`,
  );
});

// ── Graceful shutdown ─────────────────────────────────────────────────────

const shutdown = (signal) => {
  logger.info(`${signal} received. Shutting down gracefully…`);
  server.close(() => {
    logger.info('HTTP server closed.');
    process.exit(0);
  });

  // Force-close after 10 seconds if connections are still open
  setTimeout(() => {
    logger.error('Could not close connections in time. Forcing shutdown.');
    process.exit(1);
  }, 10_000);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// ── Unhandled promise rejections ──────────────────────────────────────────
process.on('unhandledRejection', (reason) => {
  logger.error('Unhandled Rejection:', reason);
  shutdown('unhandledRejection');
});

// ── Uncaught exceptions ───────────────────────────────────────────────────
process.on('uncaughtException', (err) => {
  logger.error('Uncaught Exception:', err);
  process.exit(1);
});

module.exports = server;
