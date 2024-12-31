package db

import (
	"context"
	"database/sql"
	"sync"
	"sync/atomic"
)

type MyTx struct {
	db      *sql.DB
	ctx     context.Context
	closemu sync.RWMutex
	done    atomic.Bool
}

func NewTx(db *sql.DB, ctx context.Context) *MyTx {
	return &MyTx{
		db:  db,
		ctx: ctx,
	}
}

func (tx *MyTx) Begin() error {
	_, err := tx.db.ExecContext(tx.ctx, "BEGIN")
	return err
}

func (tx *MyTx) BeginExclusive() error {
	_, err := tx.db.ExecContext(tx.ctx, "BEGIN EXCLUSIVE")
	return err
}

func (tx *MyTx) Exec(query string, args ...any) (sql.Result, error) {
	tx.closemu.RLock()
	defer tx.closemu.RUnlock()
	if tx.done.Load() {
		return nil, sql.ErrTxDone
	}
	return tx.db.ExecContext(tx.ctx, query, args...)
}

func (tx *MyTx) Commit() error {
	tx.closemu.Lock()
	defer tx.closemu.Unlock()
	_, err := tx.db.ExecContext(tx.ctx, "COMMIT")
	tx.done.Store(true)
	return err
}

func (tx *MyTx) Rollback() error {
	tx.closemu.Lock()
	defer tx.closemu.Unlock()
	_, err := tx.db.ExecContext(tx.ctx, "ROLLBACK")
	tx.done.Store(true)
	return err
}
