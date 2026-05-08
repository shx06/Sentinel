'use strict';

const request = require('supertest');
const app = require('../src/app');

describe('GET /api/v1/health', () => {
  it('should return 200 with success status', async () => {
    const res = await request(app).get('/api/v1/health');

    expect(res.statusCode).toBe(200);
    expect(res.body).toMatchObject({
      success: true,
      message: 'Success',
    });
    expect(res.body.data).toMatchObject({
      status: 'ok',
      environment: expect.any(String),
    });
    expect(res.body.data.uptime).toBeGreaterThanOrEqual(0);
    expect(res.body.data.timestamp).toBeDefined();
  });
});

describe('404 handler', () => {
  it('should return 404 for unknown routes', async () => {
    const res = await request(app).get('/api/v1/unknown-route');

    expect(res.statusCode).toBe(404);
    expect(res.body.success).toBe(false);
  });
});
