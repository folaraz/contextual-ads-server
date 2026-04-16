package postgres

import (
	"context"
	"database/sql"
	"fmt"

	_ "github.com/lib/pq"
)

var dbConn *sql.DB

func InitDB(cfg *Config) error {
	connStr := cfg.ConnectionURL()

	var err error
	dbConn, err = sql.Open("postgres", connStr)
	if err != nil {
		return fmt.Errorf("failed to open database: %w", err)
	}

	// Configure connection pool
	dbConn.SetMaxOpenConns(cfg.MaxOpenConns)
	dbConn.SetMaxIdleConns(cfg.MaxIdleConns)
	dbConn.SetConnMaxLifetime(cfg.ConnMaxLifetime)
	dbConn.SetConnMaxIdleTime(cfg.ConnMaxIdleTime)

	ctx := context.Background()
	if err := dbConn.PingContext(ctx); err != nil {
		return fmt.Errorf("failed to ping database: %w", err)
	}

	fmt.Println("Database connection established successfully")
	return nil
}

func GetDB() (*sql.DB, error) {
	if dbConn == nil {
		return nil, fmt.Errorf("database not initialized")
	}
	return dbConn, nil
}
