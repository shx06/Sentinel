'use strict';

const { createLogger, format, transports } = require('winston');
const config = require('../../config');

const { combine, timestamp, printf, colorize, errors } = format;

const devFormat = combine(
  colorize(),
  timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  errors({ stack: true }),
  printf(({ level, message, timestamp: ts, stack }) => {
    return stack ? `${ts} [${level}]: ${message}\n${stack}` : `${ts} [${level}]: ${message}`;
  }),
);

const prodFormat = combine(timestamp(), errors({ stack: true }), format.json());

const logger = createLogger({
  level: config.log.level,
  format: config.env === 'production' ? prodFormat : devFormat,
  transports: [new transports.Console()],
  exitOnError: false,
});

module.exports = logger;
