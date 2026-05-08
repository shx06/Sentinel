'use strict';

const express = require('express');
const helmet = require('helmet');
const cors = require('cors');

const config = require('../config');
const routes = require('./routes');
const requestLogger = require('./middlewares/requestLogger');
const notFound = require('./middlewares/notFound');
const errorHandler = require('./middlewares/errorHandler');

const app = express();

// ── Security headers ──────────────────────────────────────────────────────
app.use(helmet());

// ── CORS ──────────────────────────────────────────────────────────────────
app.use(
  cors({
    origin: config.cors.origins,
    methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization'],
    credentials: true,
  }),
);

// ── Body parsers ─────────────────────────────────────────────────────────
app.use(express.json({ limit: '10kb' }));
app.use(express.urlencoded({ extended: true, limit: '10kb' }));

// ── HTTP request logging ──────────────────────────────────────────────────
app.use(requestLogger);

// ── Routes ────────────────────────────────────────────────────────────────
app.use(`${config.api.prefix}/${config.api.version}`, routes);

// ── 404 handler (must come after all routes) ──────────────────────────────
app.use(notFound);

// ── Global error handler (must be last, 4-argument form) ─────────────────
app.use(errorHandler);

module.exports = app;
