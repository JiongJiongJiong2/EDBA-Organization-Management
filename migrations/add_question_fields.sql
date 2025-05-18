-- Backup existing questions table
CREATE TABLE questions_backup AS SELECT * FROM questions;

-- Drop existing questions table
DROP TABLE IF EXISTS questions;

-- Create new questions table with updated schema
CREATE TABLE questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL,
    sender_id INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 0,
    answer TEXT,
    submit_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    response_time TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES members(user_id)
);

-- Migrate data from backup
INSERT INTO questions (question_id, title, description, sender_id, status, answer, submit_time, response_time)
SELECT 
    question_id,
    COALESCE(title, 'No Title') as title,
    description,
    sender_id,
    status,
    answer,
    COALESCE(submit_time, CURRENT_TIMESTAMP) as submit_time,
    response_time
FROM questions_backup;

-- Drop backup table
DROP TABLE questions_backup;
