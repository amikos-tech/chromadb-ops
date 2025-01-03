package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"database/sql"

	"github.com/amikos-tech/chromadb-ops/internal/chroma"
	chromadb "github.com/amikos-tech/chromadb-ops/internal/db"
	_ "github.com/mattn/go-sqlite3"
	"github.com/pkg/errors"
	"github.com/spf13/cobra"
)

type tokenizerType string

const (
	tokenizerUnicode61 tokenizerType = "unicode61"
	tokenizerTrigram   tokenizerType = "trigram"
	tokenizerPorter    tokenizerType = "porter"
	tokenizerAscii     tokenizerType = "ascii"
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

func validateTokenizer(s string) (string, error) {
	if strings.HasPrefix(s, string(tokenizerUnicode61)) {
		return string(s), nil
	}
	if strings.HasPrefix(s, string(tokenizerTrigram)) {
		return string(s), nil
	}
	if strings.HasPrefix(s, string(tokenizerPorter)) {
		return string(s), nil
	}
	if strings.HasPrefix(s, string(tokenizerAscii)) {
		return string(s), nil
	}
	return "", fmt.Errorf("invalid tokenizer: %s. Supported values 'unicode61', 'trigram', 'porter' and 'ascii'. See https://www.sqlite.org/fts5.html#tokenizers", s)
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
	_tokenizer, err := cmd.Flags().GetString("tokenizer")
	if err != nil {
		return errors.Wrap(err, "failed to get tokenizer flag")
	}
	tokenizer, err := validateTokenizer(_tokenizer)
	if err != nil {
		return err
	}

	fmt.Fprintf(os.Stderr, "Rebuilding FTS index for %s with tokenizer: '%s'\n", persistDir, tokenizer)

	ctx := context.Background()

	sqlFile := filepath.Join(persistDir, "chroma.sqlite3")
	db, err := sql.Open("sqlite3", "file:"+sqlFile+"?mode=rw")
	if err != nil {
		return err
	}
	_, err = db.ExecContext(ctx, "BEGIN EXCLUSIVE")
	if err != nil {
		return errors.Wrap(err, "failed to begin exclusive transaction")
	}
	var commited = false
	defer func() {
		if !commited {
			if _, err := db.ExecContext(ctx, "ROLLBACK"); err != nil {
				fmt.Fprintf(os.Stderr, "failed to rollback transaction: %v\n", err)
			}
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
	_, err = db.ExecContext(ctx, fmt.Sprintf("CREATE VIRTUAL TABLE IF NOT EXISTS embedding_fulltext_search USING fts5(string_value, tokenize='%s')", tokenizer))
	if err != nil {
		return errors.Wrap(err, "failed to create FTS")
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
		_, err = db.ExecContext(ctx, "COMMIT")
		if err != nil {
			return errors.Wrap(err, "failed to commit transaction")
		}
		commited = true
	}
	return nil
}

func init() {
	FTSCommand.AddCommand(ftsRebuildCommand)
	ftsRebuildCommand.Flags().BoolP("dry-run", "d", false, "Dry run the operation")
	ftsRebuildCommand.Flags().StringP("tokenizer", "t", "trigram", "Tokenizer to use for FTS. Supported values 'unicode61', 'trigram', 'porter' and 'ascii'. See https://www.sqlite.org/fts5.html#tokenizers")
	RootCmd.AddCommand(FTSCommand)
}
