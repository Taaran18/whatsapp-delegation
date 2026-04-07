-- WhatsApp Delegation App - Database Schema
-- Database: emarketing_bot
-- Engine: MySQL / MariaDB

USE emarketing_bot;

-- ─────────────────────────────────────────────
-- Table: employees
-- Lookup table so OpenAI can resolve names→email
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employees (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    whatsapp_number   VARCHAR(50)  UNIQUE NOT NULL COMMENT 'E.164 format e.g. +919876543210',
    name              VARCHAR(255) NOT NULL,
    email             VARCHAR(255),
    department        VARCHAR(255),
    role              VARCHAR(255),
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────
-- Table: tasks
-- Core delegation records
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    task_id             VARCHAR(50)  UNIQUE NOT NULL COMMENT 'Human-readable e.g. TASK-001',

    -- Display columns (matches frontend table headers)
    timestamp           DATETIME     DEFAULT CURRENT_TIMESTAMP          COMMENT 'When message was received',
    task_description    TEXT                                             COMMENT 'AI-extracted task summary',
    assigned_by         VARCHAR(255)                                     COMMENT 'Sender display name',
    assignee_contact    VARCHAR(50)                                      COMMENT 'Sender WA number',
    assigned_to         VARCHAR(255)                                     COMMENT 'Person task is for (name)',
    employee_email_id   VARCHAR(255)                                     COMMENT 'Assignee email',
    target_date         DATE                                             COMMENT 'AI-extracted deadline',
    priority            ENUM('Low','Medium','High','Critical') DEFAULT 'Medium',
    approval_needed     TINYINT(1)   DEFAULT 0                           COMMENT '0=No 1=Yes',
    client_name         VARCHAR(255),
    department          VARCHAR(255),
    assigned_name       VARCHAR(255)                                     COMMENT 'Who delegated (display)',
    assigned_email_id   VARCHAR(255)                                     COMMENT 'Delegator email',
    comments            TEXT,
    source_link         VARCHAR(500)                                     COMMENT 'Google Drive URL for voice / empty for text',

    -- Internal tracking
    message_type        ENUM('text','voice') DEFAULT 'text',
    raw_message         TEXT                                             COMMENT 'Original transcription or /task text',
    status              ENUM('Pending','In Progress','Completed','Cancelled') DEFAULT 'Pending',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_status     (status),
    INDEX idx_priority   (priority),
    INDEX idx_target_date (target_date),
    INDEX idx_assignee   (employee_email_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────
-- Table: message_logs
-- Raw webhook payloads for auditing / reprocessing
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS message_logs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    wa_message_id   VARCHAR(100) UNIQUE                                  COMMENT 'WhatsApp own message ID',
    sender_number   VARCHAR(50),
    message_type    ENUM('text','voice','other') DEFAULT 'other',
    raw_payload     JSON                                                  COMMENT 'Full webhook body',
    processed       TINYINT(1)  DEFAULT 0                                COMMENT '1 = task created',
    task_id         VARCHAR(50) NULL                                      COMMENT 'FK to tasks.task_id',
    error_message   TEXT        NULL                                      COMMENT 'Set if processing failed',
    received_at     DATETIME    DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_processed (processed),
    INDEX idx_task_id   (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────
-- Sequence helper: auto-generate TASK-001 style IDs
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS task_sequence (
    id  INT AUTO_INCREMENT PRIMARY KEY
) ENGINE=InnoDB AUTO_INCREMENT=1;
