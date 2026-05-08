'use strict';

const request = require('supertest');

const app = require('../src/app');
const paymentModel = require('../src/models/payment.model');

describe('Payment flow', () => {
  beforeEach(() => {
    paymentModel.reset();
  });

  it('should create and process a payment successfully', async () => {
    const payload = {
      amount: 10.01,
      currency: 'usd',
      idempotencyKey: 'idem-success-001',
    };

    const res = await request(app).post('/api/v1/payments').send(payload);

    expect(res.statusCode).toBe(201);
    expect(res.body.success).toBe(true);
    expect(res.body.data).toMatchObject({
      amount: payload.amount,
      currency: 'USD',
      idempotencyKey: payload.idempotencyKey,
      status: 'SUCCESS',
      failureReason: null,
    });
    expect(res.body.data.gatewayReference).toEqual(expect.any(String));
    expect(res.body.data.statusHistory.map((entry) => entry.status)).toEqual([
      'PENDING',
      'PROCESSING',
      'SUCCESS',
    ]);
  });

  it('should return failed status when gateway simulator declines the payment', async () => {
    const res = await request(app).post('/api/v1/payments').send({
      amount: 10.0,
      currency: 'USD',
      idempotencyKey: 'idem-failure-001',
    });

    expect(res.statusCode).toBe(201);
    expect(res.body.data.status).toBe('FAILED');
    expect(res.body.data.failureReason).toBe('Payment was declined by gateway simulator');
    expect(res.body.data.statusHistory.map((entry) => entry.status)).toEqual([
      'PENDING',
      'PROCESSING',
      'FAILED',
    ]);
  });

  it('should handle idempotent replay without creating a duplicate payment', async () => {
    const payload = {
      amount: 10.01,
      currency: 'USD',
      idempotencyKey: 'idem-replay-001',
    };

    const firstResponse = await request(app).post('/api/v1/payments').send(payload);
    const secondResponse = await request(app).post('/api/v1/payments').send(payload);

    expect(firstResponse.statusCode).toBe(201);
    expect(secondResponse.statusCode).toBe(200);
    expect(secondResponse.body.message).toBe('Payment already exists for this idempotency key');
    expect(secondResponse.body.data.id).toBe(firstResponse.body.data.id);
    expect(secondResponse.body.data.status).toBe(firstResponse.body.data.status);
  });

  it('should return a validation error for invalid request payload', async () => {
    const res = await request(app).post('/api/v1/payments').send({
      amount: -50,
      currency: 'USDT',
      idempotencyKey: 'short',
      extra: 'not-allowed',
    });

    expect(res.statusCode).toBe(400);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('Validation failed');
    expect(res.body.errors.length).toBeGreaterThan(0);
  });

  it('should retrieve an existing payment by id', async () => {
    const createResponse = await request(app).post('/api/v1/payments').send({
      amount: 10.01,
      currency: 'USD',
      idempotencyKey: 'idem-get-001',
    });

    const paymentId = createResponse.body.data.id;
    const getResponse = await request(app).get(`/api/v1/payments/${paymentId}`);

    expect(getResponse.statusCode).toBe(200);
    expect(getResponse.body.message).toBe('Payment retrieved');
    expect(getResponse.body.data.id).toBe(paymentId);
  });

  it('should return 404 for unknown payment id', async () => {
    const res = await request(app).get('/api/v1/payments/eff8767c-d669-4176-ae0a-b6f760463955');

    expect(res.statusCode).toBe(404);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('Payment not found');
  });
});
