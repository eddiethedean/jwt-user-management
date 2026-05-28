BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 48330986b7bb

CREATE TABLE invite_tokens (
    id SERIAL NOT NULL, 
    email VARCHAR NOT NULL, 
    token_hash VARCHAR NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITHOUT TIME ZONE, 
    grant_admin BOOLEAN NOT NULL, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_invite_tokens_email ON invite_tokens (email);

CREATE INDEX ix_invite_tokens_grant_admin ON invite_tokens (grant_admin);

CREATE UNIQUE INDEX ix_invite_tokens_token_hash ON invite_tokens (token_hash);

CREATE TABLE password_reset_tokens (
    id SERIAL NOT NULL, 
    email VARCHAR NOT NULL, 
    token_hash VARCHAR NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_password_reset_tokens_email ON password_reset_tokens (email);

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);

CREATE TABLE users (
    id SERIAL NOT NULL, 
    email VARCHAR NOT NULL, 
    full_name VARCHAR, 
    country VARCHAR, 
    command VARCHAR, 
    hashed_password VARCHAR NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    is_admin BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_is_active ON users (is_active);

CREATE INDEX ix_users_is_admin ON users (is_admin);

INSERT INTO alembic_version (version_num) VALUES ('48330986b7bb') RETURNING alembic_version.version_num;

COMMIT;

