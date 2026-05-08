'use strict';

const paymentsById = new Map();
const paymentIdByIdempotencyKey = new Map();

const clonePayment = (payment) => {
  if (!payment) {
    return null;
  }

  return {
    ...payment,
    statusHistory: payment.statusHistory.map((entry) => ({ ...entry })),
  };
};

const create = ({ id, amount, currency, idempotencyKey }) => {
  const timestamp = new Date().toISOString();

  const payment = {
    id,
    amount,
    currency,
    idempotencyKey,
    status: 'PENDING',
    gatewayReference: null,
    failureReason: null,
    createdAt: timestamp,
    updatedAt: timestamp,
    statusHistory: [{ status: 'PENDING', timestamp, reason: 'Payment initiated' }],
  };

  paymentsById.set(id, payment);
  paymentIdByIdempotencyKey.set(idempotencyKey, id);

  return clonePayment(payment);
};

const updateStatus = ({ paymentId, status, reason, gatewayReference, failureReason }) => {
  const payment = paymentsById.get(paymentId);

  if (!payment) {
    return null;
  }

  const timestamp = new Date().toISOString();

  payment.status = status;
  payment.updatedAt = timestamp;
  if (gatewayReference !== undefined) {
    payment.gatewayReference = gatewayReference;
  }

  if (failureReason !== undefined) {
    payment.failureReason = failureReason;
  }

  payment.statusHistory.push({
    status,
    timestamp,
    reason,
  });

  return clonePayment(payment);
};

const findById = (paymentId) => clonePayment(paymentsById.get(paymentId));

const findByIdempotencyKey = (idempotencyKey) => {
  const paymentId = paymentIdByIdempotencyKey.get(idempotencyKey);

  if (!paymentId) {
    return null;
  }

  return findById(paymentId);
};

const reset = () => {
  paymentsById.clear();
  paymentIdByIdempotencyKey.clear();
};

module.exports = {
  create,
  updateStatus,
  findById,
  findByIdempotencyKey,
  reset,
};
