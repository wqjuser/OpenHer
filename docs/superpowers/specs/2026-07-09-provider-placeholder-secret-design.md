# Provider Placeholder Secret Design

## Goal

Do not treat copied `.env.example` placeholder API keys as configured provider secrets.

## Design

Filter placeholder-style secret values in `providers/config.py` before provider availability is computed. This catches both new `.env` files copied from `.env.example` and existing local `.env` files that still contain `your_*_key_here` values.

Also comment the sample DashScope key in `.env.example`; users should opt in by filling a real key.
