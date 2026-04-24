-- ============================================================
-- SMC Pattern Detector — MySQL Database Schema
-- Database: smc_detector
-- Version:  1.0
-- Author:   AutoStackAI
-- ============================================================

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS smc_detector
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE smc_detector;

-- ============================================================
-- DROP TABLES (reverse dependency order to avoid FK errors)
-- ============================================================

DROP TABLE IF EXISTS trade_log;
DROP TABLE IF EXISTS signals;
DROP TABLE IF EXISTS patterns;
DROP TABLE IF EXISTS candles;

-- ============================================================
-- TABLE 1: candles — Raw OHLCV Price Data
-- Source: yfinance API / TradingView CSV export
-- ============================================================

CREATE TABLE candles (
    id         BIGINT PRIMARY KEY AUTO_INCREMENT,
    pair       VARCHAR(10)   NOT NULL,                -- e.g. 'EURUSD', 'XAUUSD'
    timeframe  VARCHAR(5)    NOT NULL,                -- '1M','5M','15M','1H','4H','1D'
    open       DECIMAL(10,5) NOT NULL,
    high       DECIMAL(10,5) NOT NULL,
    low        DECIMAL(10,5) NOT NULL,
    close      DECIMAL(10,5) NOT NULL,
    volume     BIGINT        NOT NULL DEFAULT 0,
    timestamp  TIMESTAMP     NOT NULL,

    -- Composite index for fast lookups by pair + timeframe + time range
    INDEX idx_pair_tf_ts (pair, timeframe, timestamp),

    -- Prevent duplicate candles for same pair/timeframe/timestamp
    UNIQUE KEY uq_candle (pair, timeframe, timestamp)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE 2: patterns — ML-Detected SMC Patterns
-- Written by: detect.py (XGBoost predict_proba output)
-- ============================================================

CREATE TABLE patterns (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,
    candle_id        BIGINT        NOT NULL,
    pattern_type     VARCHAR(20)   NOT NULL,           -- 'BOS','CHoCH','OB','FVG','liquidity'
    confidence_score DECIMAL(4,3)  NOT NULL,           -- 0.000 to 1.000 (from predict_proba)
    detected_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    timeframe        VARCHAR(5)    NOT NULL,
    confirmed        BOOLEAN       DEFAULT FALSE,

    -- FK: every pattern must reference an existing candle
    FOREIGN KEY (candle_id) REFERENCES candles(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Index for filtering by pattern type and confidence
    INDEX idx_pattern_type (pattern_type),
    INDEX idx_confidence (confidence_score),
    INDEX idx_candle_id (candle_id)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE 3: signals — Trade Signals with Auto-Computed RR Ratio
-- Written by: signals.py
-- rr_ratio is a GENERATED COLUMN (computed by MySQL, never inserted)
-- ============================================================

CREATE TABLE signals (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    pattern_id   BIGINT        NOT NULL,
    direction    ENUM('LONG','SHORT') NOT NULL,
    entry_price  DECIMAL(10,5) NOT NULL,
    stop_loss    DECIMAL(10,5) NOT NULL,
    take_profit  DECIMAL(10,5) NOT NULL,

    -- Generated column: MySQL auto-computes RR ratio
    -- Formula: |take_profit - entry| / |entry - stop_loss|
    rr_ratio     DECIMAL(4,2)  GENERATED ALWAYS AS
                     (ABS(take_profit - entry_price) / ABS(entry_price - stop_loss)) STORED,

    status       ENUM('PENDING','ACTIVE','HIT_TP','HIT_SL','CANCELLED') DEFAULT 'PENDING',
    created_at   TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

    -- FK: every signal must reference an existing pattern
    FOREIGN KEY (pattern_id) REFERENCES patterns(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Indexes for common queries
    INDEX idx_status (status),
    INDEX idx_rr_ratio (rr_ratio),
    INDEX idx_pattern_id (pattern_id)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE 4: trade_log — Execution Results & Backtesting
-- Tracks actual trade outcomes for performance analytics
-- ============================================================

CREATE TABLE trade_log (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    signal_id    BIGINT        NOT NULL,
    actual_entry DECIMAL(10,5),
    actual_exit  DECIMAL(10,5),
    pnl          DECIMAL(10,2),                        -- Profit/Loss in account currency
    pips         DECIMAL(8,2),                         -- Profit/Loss in pips
    outcome      VARCHAR(10),                          -- 'WIN','LOSS','BE'
    opened_at    TIMESTAMP     NULL,
    closed_at    TIMESTAMP     NULL,

    -- FK: every trade must reference an existing signal
    FOREIGN KEY (signal_id) REFERENCES signals(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Indexes
    INDEX idx_outcome (outcome),
    INDEX idx_signal_id (signal_id)
) ENGINE=InnoDB;

-- ============================================================
-- VERIFICATION: Show all tables created
-- ============================================================

SHOW TABLES;

-- ============================================================
-- Quick sanity check: describe each table
-- ============================================================

DESCRIBE candles;
DESCRIBE patterns;
DESCRIBE signals;
DESCRIBE trade_log;
