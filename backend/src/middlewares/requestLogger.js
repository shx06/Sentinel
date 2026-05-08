'use strict';

const morgan = require('morgan');
const logger = require('../utils/logger');

/**
 * HTTP request logger middleware powered by Morgan + Winston.
 *
 * In production the standard `combined` Apache format is used.
 * In all other environments a concise `dev` format is used.
 */
const httpLogger = morgan(process.env.NODE_ENV === 'production' ? 'combined' : 'dev', {
  stream: {
    write: (message) => logger.http(message.trim()),
  },
});

module.exports = httpLogger;
