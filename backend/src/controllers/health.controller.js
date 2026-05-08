'use strict';

const ApiResponse = require('../utils/ApiResponse');

/**
 * GET /health
 * Returns a 200 OK with service status information.
 */
const getHealth = (_req, res) => {
  const response = new ApiResponse(200, {
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
  });

  return response.send(res);
};

module.exports = { getHealth };
