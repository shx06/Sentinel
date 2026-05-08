'use strict';

const { body, param } = require('express-validator');

const allowedCreateFields = ['amount', 'currency', 'idempotencyKey'];

const createPaymentValidation = [
  body()
    .isObject()
    .withMessage('Request body must be a JSON object')
    .custom((value) => {
      const unknownFields = Object.keys(value).filter(
        (field) => !allowedCreateFields.includes(field),
      );

      if (unknownFields.length > 0) {
        throw new Error(`Unknown fields are not allowed: ${unknownFields.join(', ')}`);
      }

      return true;
    }),
  body('amount')
    .exists({ checkFalsy: true })
    .withMessage('amount is required')
    .bail()
    .isFloat({ gt: 0 })
    .withMessage('amount must be a positive number')
    .bail()
    .custom((value) => {
      if (!/^\d+(\.\d{1,2})?$/.test(String(value))) {
        throw new Error('amount must have at most 2 decimal places');
      }

      return true;
    }),
  body('currency')
    .exists({ checkFalsy: true })
    .withMessage('currency is required')
    .bail()
    .isString()
    .withMessage('currency must be a string')
    .bail()
    .trim()
    .isLength({ min: 3, max: 3 })
    .withMessage('currency must be a 3-letter ISO code')
    .bail()
    .isAlpha()
    .withMessage('currency must only contain letters')
    .customSanitizer((value) => value.toUpperCase()),
  body('idempotencyKey')
    .exists({ checkFalsy: true })
    .withMessage('idempotencyKey is required')
    .bail()
    .isString()
    .withMessage('idempotencyKey must be a string')
    .bail()
    .trim()
    .isLength({ min: 8, max: 128 })
    .withMessage('idempotencyKey must be between 8 and 128 characters'),
];

const getPaymentValidation = [
  param('paymentId').isUUID(4).withMessage('paymentId must be a valid UUID'),
];

module.exports = {
  createPaymentValidation,
  getPaymentValidation,
};
