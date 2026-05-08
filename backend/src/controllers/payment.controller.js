'use strict';

const ApiResponse = require('../utils/ApiResponse');
const paymentService = require('../services/payment.service');

const createPayment = async (req, res, next) => {
  try {
    const { payment, idempotentReplay } = await paymentService.createPayment(req.body);

    const response = new ApiResponse(
      idempotentReplay ? 200 : 201,
      payment,
      idempotentReplay ? 'Payment already exists for this idempotency key' : 'Payment processed',
    );

    return response.send(res);
  } catch (error) {
    return next(error);
  }
};

const getPaymentById = async (req, res, next) => {
  try {
    const payment = paymentService.getPaymentById(req.params.paymentId);
    const response = new ApiResponse(200, payment, 'Payment retrieved');

    return response.send(res);
  } catch (error) {
    return next(error);
  }
};

module.exports = {
  createPayment,
  getPaymentById,
};
