# Payment System – Backend

A production-ready REST API scaffold built with **Node.js** and **Express.js**, designed as the foundation for a full-featured payment gateway.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Available Scripts](#available-scripts)
- [API Reference](#api-reference)
- [Code Style](#code-style)
- [Roadmap](#roadmap)

---

## Tech Stack

| Layer            | Technology                |
| ---------------- | ------------------------- |
| Runtime          | Node.js ≥ 18              |
| Framework        | Express.js 4              |
| Logging          | Winston + Morgan          |
| Security         | Helmet, CORS              |
| Validation       | express-validator         |
| Config           | dotenv                    |
| Linting          | ESLint + eslint-config-prettier |
| Formatting       | Prettier                  |
| Testing          | Jest + Supertest          |
| Dev server       | Nodemon                   |

---

## Project Structure

```
backend/
├── config/
│   └── index.js            # Centralised config (reads from .env)
├── src/
│   ├── app.js              # Express app – middleware + routes
│   ├── server.js           # HTTP server + graceful shutdown
│   ├── controllers/        # Route handlers (thin – delegate to services)
│   │   └── health.controller.js
│   ├── routes/             # Route definitions
│   │   ├── index.js        # Root router
│   │   ├── health.routes.js
│   │   └── payment.routes.js
│   ├── services/           # Business logic layer
│   │   └── payment.service.js
│   ├── models/             # Data model layer
│   │   └── payment.model.js
│   ├── middlewares/
│   │   ├── errorHandler.js  # Global error handler
│   │   ├── notFound.js      # 404 catch-all
│   │   ├── requestLogger.js # Morgan HTTP logger
│   │   └── validateRequest.js
│   ├── validators/
│   │   └── payment.validator.js
│   └── utils/
│       ├── ApiError.js     # Structured operational-error class
│       ├── ApiResponse.js  # Uniform success-response wrapper
│       └── logger.js       # Winston logger instance
├── tests/
│   ├── health.test.js
│   └── payment.test.js
├── .env.example
├── .eslintrc.js
├── .gitignore
├── .prettierrc
├── nodemon.json
└── package.json
```

---

## Getting Started

### Prerequisites

- Node.js ≥ 18
- npm ≥ 9

### Installation

```bash
# from the repo root
cd backend
npm install
cp .env.example .env   # fill in values as needed
```

### Start in development mode

```bash
npm run dev
```

The server starts at `http://localhost:3000` by default.

---

## Environment Variables

| Variable       | Default                           | Description                              |
| -------------- | --------------------------------- | ---------------------------------------- |
| `NODE_ENV`     | `development`                     | Runtime environment                      |
| `PORT`         | `3000`                            | HTTP port                                |
| `LOG_LEVEL`    | `debug`                           | Winston log level                        |
| `API_VERSION`  | `v1`                              | API version prefix                       |
| `API_PREFIX`   | `/api`                            | API base path                            |
| `CORS_ORIGINS` | `http://localhost:3000,...`        | Comma-separated allowed origins          |

Copy `.env.example` → `.env` and adjust values before running locally. **Never commit `.env`.**

---

## Available Scripts

| Script              | Description                             |
| ------------------- | --------------------------------------- |
| `npm start`         | Start production server                 |
| `npm run dev`       | Start development server (Nodemon)      |
| `npm run lint`      | Run ESLint                              |
| `npm run lint:fix`  | Run ESLint with auto-fix                |
| `npm run format`    | Format code with Prettier               |
| `npm run format:check` | Check formatting without writing    |
| `npm test`          | Run Jest test suite                     |
| `npm run test:coverage` | Run tests with coverage report      |

---

## API Reference

### Health Check

```
GET /api/v1/health
```

**Response – 200 OK**

```json
{
  "success": true,
  "message": "Success",
  "data": {
    "status": "ok",
    "uptime": 12.345,
    "timestamp": "2024-01-01T00:00:00.000Z",
    "environment": "development"
  }
}
```

### Payments (Flow 1)

```
POST /api/v1/payments
```

**Payload**

```json
{
  "amount": 10.01,
  "currency": "USD",
  "idempotencyKey": "unique-key-12345"
}
```

**Responses**

- `201` when a payment is created and processed.
- `200` for idempotent replays (same `idempotencyKey`).
- `400` for validation failures.

```
GET /api/v1/payments/:paymentId
```

**Responses**

- `200` when payment exists.
- `404` when payment is not found.

---

## Code Style

- **ESLint** enforces `eslint:recommended` plus Prettier rules.
- **Prettier** formats all JS files (single quotes, 100-char lines, trailing commas).
- Run `npm run lint:fix && npm run format` before opening a PR.

---

## Roadmap

Each feature will be delivered in a dedicated pull request:

- [x] PR 1 – Project scaffold & health check *(this PR)*
- [x] PR 2 – Payment initiation & gateway lifecycle tracking
- [ ] PR 3 – Retry strategy, timeout handling, and stronger failure recovery
- [ ] PR 4 – Transaction management & history
- [ ] PR 5 – Refunds & dispute handling
- [ ] PR 6 – Webhooks (gateway callbacks)
- [ ] PR 7 – Admin panel routes & reporting
