'use strict';

const { Router } = require('express');

const validateRequest = require('../middlewares/validateRequest');
const { createPayment, getPaymentById } = require('../controllers/payment.controller');
const {
  createPaymentValidation,
  getPaymentValidation,
} = require('../validators/payment.validator');

const router = Router();

/**
 * @route  POST /payments
 * @desc   Create and process a payment
 * @access Public
 */
router.post('/', createPaymentValidation, validateRequest, createPayment);

/**
 * @route  GET /payments/:paymentId
 * @desc   Fetch one payment by id
 * @access Public
 */
router.get('/:paymentId', getPaymentValidation, validateRequest, getPaymentById);

module.exports = router;
