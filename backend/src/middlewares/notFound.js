'use strict';

const ApiError = require('../utils/ApiError');

/**
 * 404 catch-all middleware.
 * Place this AFTER all route definitions and BEFORE errorHandler.
 */
const notFound = (req, _res, next) => {
  next(ApiError.notFound(`Route not found: ${req.method} ${req.originalUrl}`));
};

module.exports = notFound;
