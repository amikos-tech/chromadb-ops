package cmd

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"

	"database/sql"

	"github.com/amikos-tech/chromadb-ops/internal/chroma"
	chromadb "github.com/amikos-tech/chromadb-ops/internal/db"
	_ "github.com/mattn/go-sqlite3"
	"github.com/pkg/errors"
	"github.com/spf13/cobra"
)

var CleanCommand = &cobra.Command{
	Use:   "clean",
	Short: "Clean up orphanated segments",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		err := clean(cmd, args)
		if err != nil {
			cmd.SilenceUsage = true
			return err
		}
		return nil
	},
}

func clean(cmd *cobra.Command, args []string) error {
	persistDir := args[0]
	if err := chroma.CheckPersistDir(persistDir); err != nil {
		return errors.Wrap(err, "failed to check persist directory")
	}
	dryRun, err := cmd.Flags().GetBool("dry-run")
	if err != nil {
		return errors.Wrap(err, "failed to get dry-run flag")
	}
	fmt.Fprintf(os.Stderr, "Cleaning orphanated segments in %s\n", persistDir)

	ctx := context.Background()

	sqlFile := filepath.Join(persistDir, "chroma.sqlite3")
	db, err := sql.Open("sqlite3", "file:"+sqlFile+"?mode=ro")
	if err != nil {
		return err
	}

	queries := chromadb.New(db)
	segments, err := queries.GetSegments(ctx)
	if err != nil {
		return errors.Wrap(err, "failed to get segments")
	}

	segmentDirs, err := chroma.GetSegmentDirs(persistDir)
	if err != nil {
		return errors.Wrap(err, "failed to get segment dirs")
	}

	if len(segmentDirs) == 0 {
		fmt.Fprintln(os.Stderr, "no segments found")
		return nil
	}
	var segmentIDs []string

	for _, segment := range segments {
		segmentIDs = append(segmentIDs, segment.ID)
	}
	var deletedCount int = 0
	var deletedDirs []string
	for _, segmentDir := range segmentDirs {
		if !slices.Contains(segmentIDs, segmentDir) {
			fmt.Fprintf(os.Stderr, "Deleting orphanated segment dir: %s\n", filepath.Join(persistDir, segmentDir))
			if !dryRun {
				err := os.RemoveAll(filepath.Join(persistDir, segmentDir))
				if err != nil {
					return errors.Wrap(err, "failed to delete orphanated segment dir")
				}
				deletedCount++
				deletedDirs = append(deletedDirs, filepath.Join(persistDir, segmentDir))
			}
		}
	}
	fmt.Fprintf(os.Stderr, "Deleted %d orphanated segment dirs: %v\n", deletedCount, deletedDirs)
	return nil
}

func init() {
	CleanCommand.Flags().BoolP("dry-run", "d", false, "Dry run the operation")
	RootCmd.AddCommand(CleanCommand)
}
