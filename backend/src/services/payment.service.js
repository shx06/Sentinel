'use strict';

const { v4: uuidv4 } = require('uuid');

const ApiError = require('../utils/ApiError');
const paymentModel = require('../models/payment.model');

const PAYMENT_STATUS = Object.freeze({
  PENDING: 'PENDING',
  PROCESSING: 'PROCESSING',
  SUCCESS: 'SUCCESS',
  FAILED: 'FAILED',
});

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Simulates gateway behaviour for the first payment flow.
 * Uses a deterministic rule so integration tests remain stable:
 * payments with amounts ending in 0 or 5 cents fail, others succeed.
 */
const simulateGatewayProcessing = async ({ amount, id }) => {
  await wait(10);

  const amountInCents = Math.round(Number(amount) * 100);
  const isFailure = amountInCents % 5 === 0;

  if (isFailure) {
    return {
      status: PAYMENT_STATUS.FAILED,
      failureReason: 'Payment was declined by gateway simulator',
    };
  }

  return {
    status: PAYMENT_STATUS.SUCCESS,
    gatewayReference: `gw_${id.replace(/-/g, '').slice(0, 18)}`,
  };
};

const processPayment = async (paymentId) => {
  const payment = paymentModel.findById(paymentId);

  if (!payment) {
    throw ApiError.notFound('Payment not found');
  }

  if (payment.status === PAYMENT_STATUS.PROCESSING) {
    throw ApiError.conflict('Payment is already being processed');
  }

  if ([PAYMENT_STATUS.SUCCESS, PAYMENT_STATUS.FAILED].includes(payment.status)) {
    return payment;
  }

  paymentModel.updateStatus({
    paymentId,
    status: PAYMENT_STATUS.PROCESSING,
    reason: 'Gateway processing started',
  });

  const gatewayResult = await simulateGatewayProcessing(payment);

  if (gatewayResult.status === PAYMENT_STATUS.FAILED) {
    return paymentModel.updateStatus({
      paymentId,
      status: PAYMENT_STATUS.FAILED,
      reason: gatewayResult.failureReason,
      failureReason: gatewayResult.failureReason,
    });
  }

  return paymentModel.updateStatus({
    paymentId,
    status: PAYMENT_STATUS.SUCCESS,
    reason: 'Gateway approved payment',
    gatewayReference: gatewayResult.gatewayReference,
  });
};

const createPayment = async ({ amount, currency, idempotencyKey }) => {
  const existingPayment = paymentModel.findByIdempotencyKey(idempotencyKey);

  if (existingPayment) {
    return {
      payment: existingPayment,
      idempotentReplay: true,
    };
  }

  const payment = paymentModel.create({
    id: uuidv4(),
    amount: Number(amount),
    currency,
    idempotencyKey,
  });

  const processedPayment = await processPayment(payment.id);

  return {
    payment: processedPayment,
    idempotentReplay: false,
  };
};

const getPaymentById = (paymentId) => {
  const payment = paymentModel.findById(paymentId);

  if (!payment) {
    throw ApiError.notFound('Payment not found');
  }

  return payment;
};

module.exports = {
  PAYMENT_STATUS,
  createPayment,
  getPaymentById,
};
