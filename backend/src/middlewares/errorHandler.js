'use strict';

const ApiError = require('../utils/ApiError');
const logger = require('../utils/logger');
const config = require('../../config');

/**
 * Global error-handling middleware.
 * Must be registered LAST in the Express middleware chain (4-argument form).
 *
 * Handles:
 *  - ApiError instances  → structured JSON error (operational errors)
 *  - Unexpected errors   → 500 Internal Server Error (programming / unknown errors)
 */
// eslint-disable-next-line no-unused-vars
const errorHandler = (err, req, res, _next) => {
  let error = err;

  // Wrap non-ApiError instances so we always work with a known shape
  if (!(error instanceof ApiError)) {
    const statusCode = error.statusCode || 500;
    const message =
      config.env === 'production' && statusCode === 500
        ? 'Internal Server Error'
        : error.message || 'Internal Server Error';

    error = new ApiError(statusCode, message, [], err.stack);
  }

  const statusCode = error.statusCode;
  const response = {
    success: false,
    message: error.message,
    errors: error.errors || [],
    ...(config.env !== 'production' && { stack: error.stack }),
  };

  // Log server-side (5xx) errors
  if (statusCode >= 500) {
    logger.error(`${req.method} ${req.originalUrl} — ${error.message}`, {
      stack: error.stack,
    });
  }

  return res.status(statusCode).json(response);
};

module.exports = errorHandler;
