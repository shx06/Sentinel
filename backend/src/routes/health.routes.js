'use strict';

const { Router } = require('express');
const { getHealth } = require('../controllers/health.controller');

const router = Router();

/**
 * @route  GET /health
 * @desc   Service health-check
 * @access Public
 */
router.get('/', getHealth);

module.exports = router;
