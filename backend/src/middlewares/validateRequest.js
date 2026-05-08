'use strict';

const { validationResult } = require('express-validator');

const ApiError = require('../utils/ApiError');

const validateRequest = (req, _res, next) => {
  const validationErrors = validationResult(req);

  if (validationErrors.isEmpty()) {
    return next();
  }

  const errors = validationErrors.array().map((error) => ({
    field: error.path,
    message: error.msg,
    value: error.value,
  }));

  return next(ApiError.badRequest('Validation failed', errors));
};

module.exports = validateRequest;
