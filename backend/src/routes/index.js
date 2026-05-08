'use strict';

const { Router } = require('express');
const healthRoutes = require('./health.routes');

const router = Router();

/**
 * Mount all application routes here.
 *
 * Convention:
 *   router.use('/resource', resourceRoutes);
 *
 * Payment / transaction / user routes will be added in subsequent PRs.
 */
router.use('/health', healthRoutes);

module.exports = router;
