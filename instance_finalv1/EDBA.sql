create table applications
(
    application_id    INTEGER      not null
        primary key,
    email             VARCHAR(100) not null,
    proof_material    VARCHAR(255) not null,
    status            INTEGER      not null,
    organization_name VARCHAR(100) not null
);

create table application_documents
(
    id                INTEGER      not null
        primary key,
    application_id    INTEGER      not null
        references applications,
    file_path         VARCHAR(255) not null,
    original_filename VARCHAR(255) not null,
    upload_timestamp  DATETIME     not null
);

create table email_verifications
(
    id               INTEGER      not null
        primary key,
    email            VARCHAR(100) not null,
    code             VARCHAR(10)  not null,
    expiry_timestamp DATETIME     not null,
    used             BOOLEAN      not null
);

create index ix_email_verifications_email
    on email_verifications (email);

create table organizations
(
    organization_id INTEGER      not null
        primary key,
    name            VARCHAR(100) not null
);

create table bank_accounts
(
    account_id      INTEGER      not null
        primary key,
    organization_id INTEGER      not null
        references organizations,
    bank            VARCHAR(255) not null,
    name            VARCHAR(255) not null,
    number            VARCHAR(255) not null,
    password        VARCHAR(255) not null,
);

create table course_info
(
    course_id       INTEGER      not null
        primary key,
    organization_id INTEGER      not null
        references organizations,
    description     VARCHAR(225),
    name            VARCHAR(255) not null
);

create table members
(
    user_id         INTEGER      not null
        primary key,
    email           VARCHAR(100) not null
        unique,
    user_type       VARCHAR(2)   not null,
    fund            INTEGER      not null,
    organization_id INTEGER      not null
        references organizations
);

create table questions
(
    question_id INTEGER      not null
        primary key,
    description VARCHAR(255) not null,
    sender_id   INTEGER      not null
        references members,
    status      INTEGER      not null,
    answer      VARCHAR(255)
);

create table services
(
    service_id      INTEGER    not null
        primary key,
    organization_id INTEGER    not null
        references organizations,
    service_type    VARCHAR(1) not null,
    status          INTEGER    not null,
    cost            INTEGER    not null,
    url             VARCHAR(255),
    path            VARCHAR(255),
    method          VARCHAR(10),
    input_data      VARCHAR(255),
    output_data     VARCHAR(255)
);

create table sqlite_master
(
    type     TEXT,
    name     TEXT,
    tbl_name TEXT,
    rootpage INT,
    sql      TEXT
);