'use strict';

/**
 * Standard API error class.
 * All operational errors thrown inside controllers / services should be
 * instances of ApiError so the global error-handler can respond correctly.
 */
class ApiError extends Error {
  /**
   * @param {number}  statusCode  - HTTP status code (e.g. 400, 401, 404, 500)
   * @param {string}  message     - Human-readable error message
   * @param {Array}   [errors=[]] - Optional array of validation / field errors
   * @param {string}  [stack='']  - Optional pre-built stack string
   */
  constructor(statusCode, message, errors = [], stack = '') {
    super(message);

    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.success = false;
    this.errors = errors;

    if (stack) {
      this.stack = stack;
    } else {
      Error.captureStackTrace(this, this.constructor);
    }
  }

  // ── Convenience factory methods ──────────────────────────────────────────

  static badRequest(message = 'Bad Request', errors = []) {
    return new ApiError(400, message, errors);
  }

  static unauthorized(message = 'Unauthorized') {
    return new ApiError(401, message);
  }

  static forbidden(message = 'Forbidden') {
    return new ApiError(403, message);
  }

  static notFound(message = 'Resource not found') {
    return new ApiError(404, message);
  }

  static conflict(message = 'Conflict') {
    return new ApiError(409, message);
  }

  static unprocessable(message = 'Unprocessable Entity', errors = []) {
    return new ApiError(422, message, errors);
  }

  static tooManyRequests(message = 'Too Many Requests') {
    return new ApiError(429, message);
  }

  static internal(message = 'Internal Server Error') {
    return new ApiError(500, message);
  }
}

module.exports = ApiError;
