package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"database/sql"

	"github.com/amikos-tech/chromadb-ops/internal/chroma"
	chromadb "github.com/amikos-tech/chromadb-ops/internal/db"
	_ "github.com/mattn/go-sqlite3"
	"github.com/pkg/errors"
	"github.com/spf13/cobra"
)

var FTSCommand = &cobra.Command{
	Use:   "fts",
	Short: "Full text search operations",
}

var ftsRebuildCommand = &cobra.Command{
	Use:   "rebuild",
	Short: "Rebuild the FTS index",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return ftsRebuild(cmd, args)
	},
}

func ftsRebuild(cmd *cobra.Command, args []string) error {
	persistDir := args[0]
	if err := chroma.CheckPersistDir(persistDir); err != nil {
		return errors.Wrap(err, "failed to check persist directory")
	}
	dryRun, err := cmd.Flags().GetBool("dry-run")
	if err != nil {
		return errors.Wrap(err, "failed to get dry-run flag")
	}
	if dryRun {
		fmt.Fprintf(os.Stderr, "Note: Dry run mode enabled. No changes will be made.\n")
	}

	fmt.Fprintf(os.Stderr, "Rebuilding FTS index in %s\n", persistDir)

	ctx := context.Background()

	sqlFile := filepath.Join(persistDir, "chroma.sqlite3")
	db, err := sql.Open("sqlite3", "file:"+sqlFile+"?mode=rw")
	if err != nil {
		return err
	}

	tx := chromadb.NewTx(db, ctx)
	err = tx.BeginExclusive()
	if err != nil {
		return errors.Wrap(err, "failed to begin exclusive transaction")
	}
	defer func() {
		if err := tx.Rollback(); err != nil {
			fmt.Fprintf(os.Stderr, "failed to rollback transaction: %v\n", err)
		}
	}()

	queries := chromadb.New(db)
	err = queries.DropFTS(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS")
	}
	err = queries.DropFTSConfig(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS config")
	}
	err = queries.DropFTSContent(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS content")
	}
	err = queries.DropFTSData(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS data")
	}
	err = queries.DropFTSDocsize(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS docsize")
	}
	err = queries.DropFTSIdx(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to drop FTS idx")
	}
	err = queries.CreateFTS(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to create FTS")
	}
	err = queries.InsertFTS(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to insert FTS")
	}
	if !dryRun {
		err = tx.Commit()
		if err != nil {
			return errors.Wrap(err, "failed to commit transaction")
		}
	}
	return nil
}

func init() {
	FTSCommand.AddCommand(ftsRebuildCommand)
	ftsRebuildCommand.Flags().BoolP("dry-run", "d", false, "Dry run the operation")
	RootCmd.AddCommand(FTSCommand)
}
