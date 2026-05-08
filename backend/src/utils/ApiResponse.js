'use strict';

/**
 * Standard API success-response wrapper.
 * Controllers should use this to send uniform JSON responses.
 */
class ApiResponse {
  /**
   * @param {number} statusCode - HTTP status code (2xx)
   * @param {*}      data       - Response payload
   * @param {string} [message='Success'] - Human-readable message
   */
  constructor(statusCode, data, message = 'Success') {
    this.statusCode = statusCode;
    this.success = statusCode < 400;
    this.message = message;
    this.data = data;
  }

  /**
   * Send this response using an Express `res` object.
   * @param {import('express').Response} res
   */
  send(res) {
    return res.status(this.statusCode).json({
      success: this.success,
      message: this.message,
      data: this.data,
    });
  }
}

module.exports = ApiResponse;
